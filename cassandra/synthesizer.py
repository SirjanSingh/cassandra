"""Synthesizer sub-agent (FR-S1..S3).

Turns one confirmed failure into a diverse adversarial eval dataset and uploads
it to Phoenix as a reusable dataset (regression suite forever).
"""

from __future__ import annotations

from pydantic import BaseModel

from . import llm
from .config import get_settings
from .events import bus
from .models import DatasetExample, Incident, PipelineEvent, Stage
from .phoenix_mcp import PhoenixMCP

_SYSTEM = """You are Cassandra's Synthesizer. Given one real agent failure, produce a
set of adversarial probes that stress the SAME underlying weakness through varied
phrasing, regions, and edge values - not trivial string permutations. For each probe
give the input, the expected correct answer, and a crisp pass/fail acceptance
criterion a judge can apply."""


class _Batch(BaseModel):
    examples: list[DatasetExample]


class Synthesizer:
    def __init__(self, mcp: PhoenixMCP | None = None) -> None:
        self.s = get_settings()
        self.mcp = mcp or PhoenixMCP(self.s)

    async def synthesize(self, inc: Incident) -> Incident:
        assert inc.verdict is not None
        n = self.s.synth_dataset_size
        prompt = (
            f"FAILURE CLASS: {inc.verdict.failure_class.value}\n"
            f"WHY IT FAILED: {inc.verdict.rationale}\n"
            f"ORIGINAL INPUT: {inc.span.input_text}\n"
            f"BAD OUTPUT: {inc.span.output_text}\n\n"
            f"Generate exactly {n} diverse adversarial probes as JSON."
        )
        batch: _Batch = await llm.structured(prompt, _Batch, system=_SYSTEM)
        inc.dataset_examples = batch.examples[:n]

        name = f"cassandra-{inc.verdict.failure_class.value}-{inc.span.span_id[:8]}"
        async with self.mcp.session() as phx:
            ds_id = await phx.create_dataset(
                name=name,
                description=f"Auto-synthesized from incident {inc.incident_id}: "
                f"{inc.verdict.rationale[:200]}",
            )
            count = await phx.add_examples(ds_id, inc.dataset_examples)

        inc.dataset_id = ds_id
        inc.stage = Stage.SYNTHESIZED
        await bus.publish(
            PipelineEvent(
                incident_id=inc.incident_id,
                stage=Stage.SYNTHESIZED,
                title=f"Synthesized {count}-case dataset",
                detail=name,
                phoenix_url=f"{self.s.phoenix_base_url}/datasets/{ds_id}",
                payload={"examples": [e.model_dump() for e in inc.dataset_examples]},
            )
        )
        return inc
