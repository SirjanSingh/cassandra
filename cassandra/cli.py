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
  dashboard    run the dashboard + SSE cockpit (default port 8085)
  run          drive one full end-to-end supervision cycle
  gate         CI prompt-regression gate (fails when a prompt edit drops the pass rate)
  pr           open the proven prompt fix for an incident as a GitHub pull request
  mcp          run Cassandra's MCP server over stdio (for Claude Desktop / Cursor)

Run `cassandra <command> --help` for command-specific options.
"""

_SUBCOMMANDS = {"dashboard", "run", "gate", "pr", "mcp"}


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


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv

    if not argv or argv[0] != "mcp":  # mcp owns stdout for JSON-RPC — leave it alone
        _make_stdout_safe()

    parser = argparse.ArgumentParser(
        prog="cassandra",
        description="Cassandra - the meta-agent that watches other agents.",
        add_help=True,
    )
    sub = parser.add_subparsers(dest="command")

    p_dash = sub.add_parser("dashboard", help="run the dashboard + SSE cockpit")
    p_dash.add_argument("--port", type=int, default=None, help="port (default: settings)")
    p_dash.add_argument("--host", default="127.0.0.1", help="bind host (default: 127.0.0.1)")

    sub.add_parser("run", help="drive one full end-to-end supervision cycle")
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
        from cassandra.banner import print_banner
        print_banner()
        parser.print_help()
        print("\n" + _COMMANDS)
        return

    command = argv[0]
    rest = argv[1:]

    if command == "mcp":
        # stdio JSON-RPC: emit NOTHING on stdout before the handshake — no banner.
        from cassandra.mcp_server import main as mcp_main
        mcp_main()
        return

    if command == "gate":
        # Pass every remaining arg straight through to gate.main; don't redefine its flags.
        from cassandra.banner import print_banner
        print_banner()
        from cassandra.gate import main as gate_main
        gate_main(rest)
        return

    if command == "dashboard":
        args = p_dash.parse_args(rest)
        from cassandra.banner import print_banner
        print_banner()
        from cassandra.config import get_settings
        port = args.port if args.port is not None else get_settings().dashboard_port
        import uvicorn
        uvicorn.run("dashboard.main:app", host=args.host, port=port)
        return

    if command == "run":
        from cassandra.banner import print_banner
        print_banner()
        from cassandra.run_once import main as run_main
        run_main()
        return

    if command == "pr":
        args = p_pr.parse_args(rest)
        from cassandra.banner import print_banner
        print_banner()
        from cassandra import pr as pr_mod
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
