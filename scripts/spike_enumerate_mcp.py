"""Day-1 Phoenix MCP enumeration spike (IMPLEMENTATION_PLAN.md Phase 0, risk R1).

Run this FIRST, before any Phase-2 feature work. It connects to the live
@arizeai/phoenix-mcp server and dumps every tool name + input schema so the
intended surface in cassandra/phoenix_mcp.py (_TOOLS) can be reconciled with
reality. This single check de-risks the whole build.

Usage:
    PHOENIX_API_KEY=... python -m scripts.spike_enumerate_mcp
Output:
    spike_output/phoenix_mcp_tools.json   (git-ignored)
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from cassandra.phoenix_mcp import PhoenixMCP

OUT = Path("spike_output")


async def main() -> None:
    OUT.mkdir(exist_ok=True)
    mcp = PhoenixMCP()
    async with mcp.session() as phx:
        tools = await phx.list_tools()
        try:
            projects = await phx.list_projects()
        except Exception as e:  # noqa: BLE001 - spike: surface the error, don't crash
            projects = [{"error": str(e)}]

    (OUT / "phoenix_mcp_tools.json").write_text(json.dumps(tools, indent=2))
    print(f"Discovered {len(tools)} Phoenix MCP tools:\n")
    for t in tools:
        print(f"  - {t['name']}: {t['description']}")
    print(f"\nProjects reachable: {json.dumps(projects)[:300]}")
    print(f"\nFull schema written to {OUT / 'phoenix_mcp_tools.json'}")
    print("\nNEXT: reconcile cassandra/phoenix_mcp.py:_TOOLS and normalize_span() "
          "with the names/schemas above, then remove SPIKE-RECONCILE markers.")


if __name__ == "__main__":
    asyncio.run(main())
