"""The `cassandra` console script — banner + subcommand dispatch.

argparse (stdlib, matching gate.py's style). Imports are done lazily *inside* each
subcommand so that `cassandra` / `cassandra --help` stay instant and don't drag in uvicorn,
the pipeline, or the MCP stack unless the chosen subcommand needs them.
"""

from __future__ import annotations

import argparse
import sys

_COMMANDS = """\
commands:
  dashboard    run the dashboard + SSE cockpit from a source checkout (default port 8085)
  run          drive one full end-to-end supervision cycle
  scan         check exported chat logs for answers no tool backed (no Phoenix needed)
  gate         CI prompt-regression gate (fails when a prompt edit drops the pass rate)
  pr           open the proven prompt fix for an incident as a GitHub pull request
  mcp          run Cassandra's MCP server over stdio (for Claude Desktop / Cursor)

Run `cassandra <command> --help` for command-specific options.
"""

_SUBCOMMANDS = {"dashboard", "run", "scan", "gate", "pr", "mcp"}

_DASHBOARD_FROM_SOURCE = """\
The dashboard and the ShopBot demo agent run from a source checkout; the PyPI package
installs only the `cassandra_ai` library and this CLI. To run them:
  git clone https://github.com/SirjanSingh/cassandra && cd cassandra
  pip install -e ".[full]"
  cassandra dashboard"""


def _dashboard_available() -> bool:
    """True when the source-checkout `dashboard` app is importable.

    The wheel ships only `cassandra_ai` (top-level `dashboard`/`patient` packages squatted
    generic import names), so a pip install has no dashboard. Checked up front: otherwise
    uvicorn fails later with an opaque "Could not import module" error.
    """
    import importlib.util

    try:
        return importlib.util.find_spec("dashboard.main") is not None
    except ModuleNotFoundError:  # no top-level `dashboard` package at all
        return False


def _make_stdout_safe() -> None:
    """Stop non-ASCII output from crashing the console on Windows.

    Windows terminals default to cp1252, so printing UTF-8 content we generate
    (emoji in a PR body, unicode in an agent's reply) raises UnicodeEncodeError and
    kills the command. Re-encode as UTF-8 and degrade unencodable characters instead
    of raising. Never called for `mcp` — that path speaks JSON-RPC on stdout.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):  # not a reconfigurable TextIOWrapper
            pass


def _scan(args: argparse.Namespace) -> int:
    """`cassandra scan`: returns the process exit code (2 = bad input, 0 otherwise)."""
    import asyncio
    import json
    from pathlib import Path

    from cassandra_ai.config import get_settings
    from cassandra_ai.grounding import GroundingSpec
    from cassandra_ai import scan as scan_mod

    spec_path = args.spec or get_settings().grounding_spec_file
    if not spec_path:
        # Never fall back to the bundled ShopBot spec: it would misgrade every other agent.
        print("scan needs this agent's grounding spec: pass --spec spec.json "
              "(or set GROUNDING_SPEC_FILE). See docs/SCAN.md.", file=sys.stderr)
        return 2
    try:
        spec = GroundingSpec.model_validate_json(Path(spec_path).read_text(encoding="utf-8"))
        turns = scan_mod.load_turns(args.logs)
    except (OSError, ValueError) as e:
        print(f"scan: {e}", file=sys.stderr)
        return 2

    results = asyncio.run(scan_mod.scan(turns, spec, judge=args.judge))
    mode = "rule + LLM judge on undecided turns" if args.judge else "rule only, no LLM"
    report = scan_mod.ScanReport(source=Path(args.logs).name, mode=mode, results=results)
    Path(args.out).write_text(scan_mod.render_markdown(report, top=args.top), encoding="utf-8")
    if args.json:
        Path(args.json).write_text(
            json.dumps([r.model_dump(mode="json") for r in results], indent=1, ensure_ascii=False),
            encoding="utf-8",
        )
    bad, total = report.count("unsupported"), len(results)
    print(f"{bad} of {total} answers stated a fact no tool backed "
          f"({report.count('undecided')} not checkable). Report: {args.out}")
    return 0


def main(argv: list[str] | None = None) -> None:
    """Entry point. A light install (`pip install cassandra-ai`) only carries what the CLI
    and the offline `scan` need; any command that reaches for the pipeline's stack gets a
    one-line fix instead of a traceback."""
    try:
        _main(argv)
    except ModuleNotFoundError as e:
        root = (e.name or "").split(".")[0]
        if not root or root in {"cassandra_ai", "patient", "dashboard"}:
            raise  # our own code is broken: show the real traceback
        print(f"This command needs the full install (missing package: {root}):\n"
              '  pip install "cassandra-ai[full]"', file=sys.stderr)
        sys.exit(1)


def _main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv

    if not argv or argv[0] != "mcp":  # mcp owns stdout for JSON-RPC — leave it alone
        _make_stdout_safe()

    parser = argparse.ArgumentParser(
        prog="cassandra",
        description="Cassandra - the meta-agent that watches other agents.",
        add_help=True,
    )
    sub = parser.add_subparsers(dest="command")

    p_dash = sub.add_parser("dashboard", help="run the dashboard + SSE cockpit (source checkout)")
    p_dash.add_argument("--port", type=int, default=None, help="port (default: settings)")
    p_dash.add_argument("--host", default="127.0.0.1", help="bind host (default: 127.0.0.1)")

    sub.add_parser("run", help="drive one full end-to-end supervision cycle")
    p_scan = sub.add_parser("scan", help="check exported chat logs for unsupported answers")
    p_scan.add_argument("logs", help="JSONL export, one turn per line (see docs/SCAN.md)")
    p_scan.add_argument("--spec", default=None,
                        help="grounding spec JSON for this agent (default: GROUNDING_SPEC_FILE)")
    p_scan.add_argument("--out", default="scan_report.md", help="markdown report path")
    p_scan.add_argument("--json", default=None, help="also write per-turn results as JSON")
    p_scan.add_argument("--top", type=int, default=10, help="examples shown in the report")
    p_scan.add_argument("--judge", action="store_true",
                        help="send turns the rule can't decide to the LLM judge (calls the LLM)")
    sub.add_parser("gate", help="CI prompt-regression gate (passes args through)", add_help=False)
    p_pr = sub.add_parser("pr", help="open the proven prompt fix as a GitHub PR")
    p_pr.add_argument("incident_id", help="incident id (reads reports/<id>.json)")
    p_pr.add_argument("--prompt-file", default=None,
                      help="agent's system-prompt file to patch (default: BASELINE_PROMPT_FILE)")
    p_pr.add_argument("--base", default="main", help="base branch for the PR (default: main)")
    p_pr.add_argument("--branch", default=None, help="override the PR branch name")
    p_pr.add_argument("--dry-run", action="store_true",
                      help="print the PR that would be opened; change nothing")
    p_pr.add_argument("--push", action="store_true",
                      help="push the branch and run `gh pr create` (outward-facing)")
    sub.add_parser("mcp", help="run Cassandra's MCP server over stdio")

    # No subcommand (or -h/--help / unknown token) → banner + command list.
    # Never touches the heavy stack.
    if not argv or argv[0] not in _SUBCOMMANDS:
        from cassandra_ai.banner import print_banner
        print_banner()
        parser.print_help()
        print("\n" + _COMMANDS)
        return

    command = argv[0]
    rest = argv[1:]

    if command == "mcp":
        # stdio JSON-RPC: emit NOTHING on stdout before the handshake — no banner.
        from cassandra_ai.mcp_server import main as mcp_main
        mcp_main()
        return

    if command == "gate":
        # Pass every remaining arg straight through to gate.main; don't redefine its flags.
        from cassandra_ai.banner import print_banner
        print_banner()
        from cassandra_ai.gate import main as gate_main
        gate_main(rest)
        return

    if command == "dashboard":
        args = p_dash.parse_args(rest)
        if not _dashboard_available():
            print(_DASHBOARD_FROM_SOURCE, file=sys.stderr)
            sys.exit(1)
        from cassandra_ai.banner import print_banner
        print_banner()
        from cassandra_ai.config import get_settings
        port = args.port if args.port is not None else get_settings().dashboard_port
        import uvicorn
        uvicorn.run("dashboard.main:app", host=args.host, port=port)
        return

    if command == "run":
        from cassandra_ai.banner import print_banner
        print_banner()
        from cassandra_ai.run_once import main as run_main
        run_main()
        return

    if command == "scan":
        args = p_scan.parse_args(rest)
        sys.exit(_scan(args))

    if command == "pr":
        args = p_pr.parse_args(rest)
        from cassandra_ai.banner import print_banner
        print_banner()
        from cassandra_ai import pr as pr_mod
        inc = pr_mod.load_incident(args.incident_id)
        res = pr_mod.open_pr(
            inc,
            prompt_file=args.prompt_file,
            base=args.base,
            branch=args.branch,
            dry_run=args.dry_run,
            push=args.push,
        )
        print(f"\n{res.title}\n  branch: {res.branch}")
        print(res.detail)
        return


if __name__ == "__main__":
    main()
