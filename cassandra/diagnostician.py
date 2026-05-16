"""Diagnostician sub-agent (FR-D1..D4).

Gemini 3 as LLM-as-judge over a span tree -> classify -> write a Phoenix span
annotation for confident failures -> emit enriched Incident.
"""

from __future__ import annotations

from . import llm
from .config import get_settings
from .events import bus
from .models import Incident, PipelineEvent, Stage, Verdict
from .phoenix_mcp import PhoenixMCP

_SYSTEM = """You are Cassandra's Diagnostician: a strict LLM-as-judge that audits the
behaviour of OTHER production agents from their traces. You do not chat. You return a
single JSON verdict.

Classify the span into exactly one failure_class:
- "hallucination": the agent stated facts/policy not supported by tool outputs or context
  (e.g. invented a refund policy when the policy tool returned nothing).
- "prompt_drift": the agent ignored its instructions / format / role.
- "tool_failure": a tool errored or returned no/garbled data and the agent did not
  surface or recover from it correctly.
- "ok": the response is faithful and grounded.

Be skeptical of confident, fluent answers that are not backed by a successful tool call."""


class Diagnostician:
    def __init__(self, mcp: PhoenixMCP | None = None) -> None:
        self.s = get_settings()
        self.mcp = mcp or PhoenixMCP(self.s)

    async def diagnose(self, inc: Incident) -> Incident:
        span = inc.span
        prompt = (
            f"CUSTOMER INPUT:\n{span.input_text}\n\n"
            f"AGENT OUTPUT:\n{span.output_text}\n\n"
            f"TOOL CALLS (name/args/result):\n{span.tool_calls or span.raw.get('tool.calls')}\n\n"
            "Return the verdict JSON."
        )
        verdict: Verdict = await llm.structured(prompt, Verdict, system=_SYSTEM)
        inc.verdict = verdict
        inc.stage = Stage.DIAGNOSED

        if verdict.is_failure and verdict.confidence >= self.s.diagnosis_confidence_threshold:
            async with self.mcp.session() as phx:
                inc.annotation_id = await phx.annotate_span(
                    span_id=span.span_id,
                    label=verdict.failure_class.value,
                    score=verdict.confidence,
                    explanation=verdict.rationale,
                )

        await bus.publish(
            PipelineEvent(
                incident_id=inc.incident_id,
                stage=Stage.DIAGNOSED,
                title=f"Verdict: {verdict.failure_class.value} ({verdict.confidence:.2f})",
                detail=verdict.rationale,
                phoenix_url=self.mcp.span_url(span),
                payload={"annotated": inc.annotation_id is not None},
            )
        )
        return inc
