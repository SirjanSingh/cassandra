"""Patcher sub-agent (FR-PA1..PA4).

Proposes a hardened system prompt that closes the failure mode, registers it as a
new Phoenix prompt version, and queues an A/B - but never auto-promotes (NG1).
"""

from __future__ import annotations

import difflib

from pydantic import BaseModel

from . import llm
from .config import get_settings
from .events import bus
from .models import Incident, PipelineEvent, Stage
from .phoenix_mcp import PhoenixMCP
from patient.agent import FRAGILE_SYSTEM_PROMPT

_SYSTEM = """You are Cassandra's Patcher. Rewrite the target agent's system prompt so it
can no longer commit the observed failure, while preserving its helpful behaviour for
valid cases. Make the minimal, surgical change (e.g. add an explicit rule to refuse and
escalate when required tool data is missing). Return the FULL revised prompt."""


class _Patch(BaseModel):
    revised_prompt: str
    change_summary: str


class Patcher:
    def __init__(self, mcp: PhoenixMCP | None = None) -> None:
        self.s = get_settings()
        self.mcp = mcp or PhoenixMCP(self.s)

    async def propose(self, inc: Incident) -> Incident:
        assert inc.verdict is not None
        prompt = (
            f"CURRENT SYSTEM PROMPT:\n{FRAGILE_SYSTEM_PROMPT}\n\n"
            f"OBSERVED FAILURE ({inc.verdict.failure_class.value}): "
            f"{inc.verdict.rationale}\n"
            f"TRIGGERING INPUT: {inc.span.input_text}\n"
            f"BAD OUTPUT: {inc.span.output_text}\n\n"
            "Return the revised prompt JSON."
        )
        patch: _Patch = await llm.structured(prompt, _Patch, system=_SYSTEM)
        inc.candidate_prompt = patch.revised_prompt
        inc.prompt_diff = "\n".join(
            difflib.unified_diff(
                FRAGILE_SYSTEM_PROMPT.splitlines(),
                patch.revised_prompt.splitlines(),
                fromfile="current",
                tofile="candidate",
                lineterm="",
            )
        )

        async with self.mcp.session() as phx:
            inc.candidate_prompt_version = await phx.create_prompt_version(
                name="patient-shopbot-system",
                prompt_text=patch.revised_prompt,
                metadata={
                    "incident": inc.incident_id,
                    "dataset": inc.dataset_id or "",
                    "failure_class": inc.verdict.failure_class.value,
                    "status": "candidate",  # NG1: NOT promoted to live traffic
                },
            )

        inc.stage = Stage.PATCHED
        await bus.publish(
            PipelineEvent(
                incident_id=inc.incident_id,
                stage=Stage.PATCHED,
                title="Candidate prompt proposed (A/B queued, not live)",
                detail=patch.change_summary,
                phoenix_url=f"{self.s.phoenix_base_url}/prompts/patient-shopbot-system",
                payload={"diff": inc.prompt_diff},
            )
        )
        return inc
