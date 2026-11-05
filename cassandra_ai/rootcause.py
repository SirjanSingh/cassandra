"""Root-cause analyzer (Killer Addition).

Runs after the Diagnostician confirms a failure. The Diagnostician says *what*
broke; this says *why* - the causal chain from trigger to bad output - and hands
the Patcher a concrete fix strategy instead of a vague "be better" prompt.
"""

from __future__ import annotations

from . import llm
from .config import get_settings
from .events import bus
from .models import Incident, PipelineEvent, RootCause, Stage
from .phoenix_mcp import PhoenixMCP

_SYSTEM = """You are Cassandra's Root-Cause Analyst. Given a confirmed agent failure and
its trace, produce a precise causal explanation - not a restatement of the symptom.

Identify the single culprit (which tool result, missing data, or prompt gap triggered
it), the ordered causal chain from that trigger to the bad output, any contributing
factors, and a concrete fix_strategy the prompt patcher can act on. Be specific and
technical; a Phoenix engineer will read this."""


class RootCauseAnalyst:
    def __init__(self, mcp: PhoenixMCP | None = None) -> None:
        self.s = get_settings()
        self.mcp = mcp or PhoenixMCP(self.s)

    async def analyze(self, inc: Incident) -> Incident:
        assert inc.verdict is not None and inc.verdict.is_failure
        span = inc.span
        prompt = (
            f"FAILURE CLASS: {inc.verdict.failure_class.value}\n"
            f"DIAGNOSIS: {inc.verdict.rationale}\n\n"
            f"CUSTOMER INPUT:\n{span.input_text}\n\n"
            f"AGENT OUTPUT:\n{span.output_text}\n\n"
            f"TOOL CALLS:\n{span.tool_calls or span.raw.get('tool.calls')}\n\n"
            "Return the structured root-cause JSON."
        )
        rc: RootCause = await llm.structured(prompt, RootCause, system=_SYSTEM)
        inc.root_cause = rc
        inc.stage = Stage.ROOT_CAUSED

        # Append the causal analysis onto the same Phoenix span annotation thread
        # so the "why" lives next to the "what" in the customer's own tool.
        if inc.annotation_id:
            async with self.mcp.session() as phx:
                await phx.annotate_span(
                    span_id=span.span_id,
                    label=f"root-cause:{rc.culprit[:40]}",
                    score=inc.verdict.confidence,
                    explanation=f"{rc.summary}\nChain: {' -> '.join(rc.causal_chain)}",
                )

        await bus.publish(
            PipelineEvent(
                incident_id=inc.incident_id,
                stage=Stage.ROOT_CAUSED,
                title=f"Root cause: {rc.culprit}",
                detail=rc.summary,
                phoenix_url=self.mcp.span_url(span),
                payload={
                    "causal_chain": rc.causal_chain,
                    "contributing_factors": rc.contributing_factors,
                    "fix_strategy": rc.fix_strategy,
                },
            )
        )
        return inc
