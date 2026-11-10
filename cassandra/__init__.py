"""Cassandra checks a bot's answers against the data the bot was given.

    import asyncio, cassandra

    result = asyncio.run(cassandra.check(
        answer="Your order ships Friday via FedEx.",
        question="When does my order arrive?",
        tool_calls=[{"name": "lookup_order", "args": {"id": "A1"},
                     "result": {"found": True, "carrier": "UPS", "eta": "2026-11-20"}}],
    ))
    result.verdict    # "flagged"
    result.findings   # [Finding(claim="...FedEx...", kind="contradicted", ...)]

Without an LLM configured (or with use_llm=False) only the free offline layers run.
"""

from __future__ import annotations

from typing import Any

__version__ = "0.4.0"

from .engine import check_many, check_offline, check_turn  # noqa: E402
from .grounding import GroundingSpec, load_spec  # noqa: E402
from .models import Finding, Report, Turn, TurnResult  # noqa: E402


async def check(answer: str, *, question: str = "", tool_calls: list[dict] | None = None,
                context: Any = None, spec: GroundingSpec | None = None,
                use_llm: bool = True) -> TurnResult:
    """Check one answer against its tool results and/or retrieved context."""
    from .config import get_settings

    turn = Turn(question=question, answer=answer, tool_calls=tool_calls or [], context=context)
    return await check_turn(turn, spec, use_llm=use_llm and get_settings().llm_configured)


__all__ = ["check", "check_turn", "check_many", "check_offline", "load_spec", "GroundingSpec",
           "Turn", "TurnResult", "Finding", "Report", "__version__"]
