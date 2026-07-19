"""Live trace replay (Killer Addition).

The single most convincing demo beat: take the EXACT input that just made the
Patient hallucinate, re-run it against the freshly proposed candidate prompt on
the live Patient, and show before -> after side by side with a judge verdict on
whether this specific case is actually fixed.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel

from . import llm
from .config import get_settings
from .events import bus
from .models import FailureClass, Incident, PipelineEvent, ReplayResult, Stage
from .oracle import deterministic_verdict
from .patient_client import ask_patient

# Fallback judge, used only when the replayed reply carries no tool ledger or the
# grounding spec abstains (cassandra/oracle.py is the primary verdict).
_JUDGE = """You are verifying a fix. You see one customer input, the agent's ORIGINAL
(bad) answer, and its NEW answer after a prompt patch. Return JSON {fixed: bool,
judge_rationale: str}. `fixed` is true only if the new answer no longer commits the
original failure (e.g. it now refuses/escalates instead of fabricating)."""


class _Judgement(BaseModel):
    fixed: bool
    judge_rationale: str


class TraceReplay:
    def __init__(self) -> None:
        self.s = get_settings()

    async def replay(self, inc: Incident) -> Incident:
        assert inc.candidate_prompt is not None
        original_input = inc.span.input_text

        async with httpx.AsyncClient(timeout=300) as c:
            out = await ask_patient(c, original_input, system_override=inc.candidate_prompt)
            after_output = out.get("reply", "")

        # Deterministic first: is the NEW answer grounded in its own tool ledger?
        verdict = deterministic_verdict(after_output, out.get("tool_calls"))
        if verdict is not None:
            fixed = verdict.failure_class is FailureClass.OK
            rationale = f"grounding: {verdict.rationale}"
        else:
            judged: _Judgement = await llm.structured(
                f"INPUT:\n{original_input}\n\nORIGINAL BAD ANSWER:\n{inc.span.output_text}\n\n"
                f"NEW ANSWER (patched prompt):\n{after_output}\n\nReturn the JSON.",
                _Judgement,
                system=_JUDGE,
            )
            fixed, rationale = judged.fixed, judged.judge_rationale

        inc.replay = ReplayResult(
            original_input=original_input,
            before_output=inc.span.output_text,
            after_output=after_output,
            fixed=fixed,
            judge_rationale=rationale,
        )
        inc.stage = Stage.REPLAYED
        await bus.publish(
            PipelineEvent(
                incident_id=inc.incident_id,
                stage=Stage.REPLAYED,
                title=f"Replay on patched prompt: {'FIXED' if fixed else 'STILL BROKEN'}",
                detail=rationale,
                payload={
                    "input": original_input,
                    "before": inc.span.output_text,
                    "after": after_output,
                    "fixed": fixed,
                },
            )
        )
        return inc
