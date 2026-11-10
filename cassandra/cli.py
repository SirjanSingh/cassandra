"""The `cassandra` command.

    cassandra demo                       see a report on a bundled sample in seconds
    cassandra scan logs.jsonl [--llm]    check your bot's exported chat logs
    cassandra serve                      the checks as an HTTP API, for live use

Heavy imports happen inside each command so `cassandra --help` stays instant.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_COMMANDS = """\
commands:
  demo     scan a bundled sample travel bot's logs and write an HTML report (no setup)
  scan     check your bot's exported chat logs against the data it was given
  serve    run the checks as an HTTP API so your bot can check answers live

Run `cassandra <command> --help` for options.
"""


def _make_stdout_safe() -> None:
    """Windows consoles default to cp1252; never crash on a non-ASCII bot answer."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cassandra",
                                description="Check a bot's answers against its own data.")
    sub = p.add_subparsers(dest="command")

    d = sub.add_parser("demo", help="scan a bundled sample and write an HTML report")
    d.add_argument("--out", default="cassandra_demo_report.html")
    d.add_argument("--llm", action="store_true",
                   help="also run the claim-by-claim check (calls your configured LLM)")

    s = sub.add_parser("scan", help="check exported chat logs (JSONL, one turn per line)")
    s.add_argument("logs", help="JSONL export; see README for the line format")
    s.add_argument("--spec", default=None,
                   help="optional tool-call spec JSON: which facts must come from which tool")
    s.add_argument("--llm", action="store_true",
                   help="run the claim-by-claim check: sends each answer and its data to "
                        "your configured LLM endpoint (catches ~5x more)")
    s.add_argument("--out", default="cassandra_report.html",
                   help="report path; .html (default) or .md")
    s.add_argument("--json", default=None, help="also write full per-answer results as JSON")
    s.add_argument("--top", type=int, default=50, help="flagged answers shown in the report")
    s.add_argument("--fail-over", type=float, default=None, metavar="PCT",
                   help="exit 1 if more than PCT%% of answers are flagged (for CI)")

    v = sub.add_parser("serve", help="HTTP API: POST /v1/check")
    v.add_argument("--host", default="127.0.0.1")
    v.add_argument("--port", type=int, default=8090)
    v.add_argument("--spec", default=None, help="tool-call spec applied to every request")
    return p


def _write_report(report, out: str, top: int, json_out: str | None) -> None:
    from . import report as rep

    text = (rep.render_markdown(report, top=top) if out.lower().endswith(".md")
            else rep.render_html(report, top=top))
    Path(out).write_text(text, encoding="utf-8")
    if json_out:
        Path(json_out).write_text(rep.render_json(report), encoding="utf-8")


def _run_scan(turns, spec, *, use_llm: bool, source: str, out: str, top: int,
              json_out: str | None):
    import asyncio

    from . import llm
    from .engine import check_many
    from .config import get_settings
    from .models import Layer, Report
    from .report import summary_line

    s = get_settings()
    if use_llm:
        llm._client()  # fail fast with the setup hint, before any work
        print(f"Claim check on: sending {len(turns)} answers and their data to "
              f"{llm.describe()}", file=sys.stderr)

    def progress(done: int, total: int) -> None:
        if use_llm and (done % 10 == 0 or done == total):
            print(f"  checked {done}/{total}", file=sys.stderr)

    results = asyncio.run(check_many(turns, spec, use_llm=use_llm,
                                     concurrency=s.concurrency, on_done=progress))
    layers: list[Layer] = []
    if spec is not None:
        layers.append("rule")
    if any(t.has_source() for t in turns):
        layers.append("value")
        if use_llm:
            layers.append("claim")
    report = Report(source=source, layers=layers, results=results,
                    model=llm.describe() if use_llm else None)
    _write_report(report, out, top, json_out)
    print(f"{summary_line(report)}\nReport: {out}")
    return report


def main(argv: list[str] | None = None) -> None:
    from .llm import LLMUnavailable

    try:
        sys.exit(_main(sys.argv[1:] if argv is None else argv))
    except LLMUnavailable as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
    except ModuleNotFoundError as e:
        root = (e.name or "").split(".")[0]
        if root in {"fastapi", "uvicorn"}:
            print('`cassandra serve` needs: pip install "cassandra-ai[serve]"', file=sys.stderr)
            sys.exit(2)
        raise


def _main(argv: list[str]) -> int:
    _make_stdout_safe()
    parser = _parser()
    if not argv or argv[0] not in {"demo", "scan", "serve"}:
        from .banner import print_banner

        print_banner()
        parser.print_help()
        print("\n" + _COMMANDS)
        return 0
    args = parser.parse_args(argv)

    if args.command == "demo":
        from importlib.resources import files

        from .grounding import load_spec
        from .scan import load_turns

        sample = files("cassandra") / "samples"
        turns = load_turns(str(sample / "travel_bot_logs.jsonl"))
        sample_spec = load_spec(str(sample / "travel_bot_spec.json"))
        print(f"Demo: {len(turns)} real answers from a sample travel bot (gpt-4o-mini with "
              "live currency and weather tools).", file=sys.stderr)
        _run_scan(turns, sample_spec, use_llm=args.llm, source="sample travel bot",
                  out=args.out, top=50, json_out=None)
        return 0

    if args.command == "scan":
        from .grounding import load_spec
        from .scan import load_turns

        try:
            spec = load_spec(args.spec) if args.spec else None
            turns = load_turns(args.logs)
        except (OSError, ValueError) as e:
            print(f"scan: {e}", file=sys.stderr)
            return 2
        if not turns:
            print("scan: the log file has no turns", file=sys.stderr)
            return 2
        report = _run_scan(turns, spec, use_llm=args.llm, source=Path(args.logs).name,
                           out=args.out, top=args.top, json_out=args.json)
        if args.fail_over is not None:
            share = 100 * report.count("flagged") / len(report.results)
            if share > args.fail_over:
                print(f"FAIL: {share:.1f}% flagged is over the {args.fail_over}% limit",
                      file=sys.stderr)
                return 1
        return 0

    # serve
    import uvicorn

    from .grounding import load_spec
    from .server import create_app

    spec = load_spec(args.spec) if args.spec else None
    uvicorn.run(create_app(spec), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    main()
