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
  mcp          run Cassandra's MCP server over stdio (for Claude Desktop / Cursor)

Run `cassandra <command> --help` for command-specific options.
"""


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv

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
    sub.add_parser("mcp", help="run Cassandra's MCP server over stdio")

    # No subcommand (or -h/--help / unknown token) → banner + command list.
    # Never touches the heavy stack.
    if not argv or argv[0] not in {"dashboard", "run", "gate", "mcp"}:
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


if __name__ == "__main__":
    main()
