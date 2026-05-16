"""Evaluator sub-agent (FR-E1..E4).

Runs the synthesized dataset through a Phoenix experiment with an LLM-as-judge
eval: baseline (current prompt) first, then candidate (Patcher's prompt), then
computes the pass-rate delta.
"""

from __future__ import annotations

from .config import get_settings
from .events import bus
from .models import ExperimentResult, Incident, PipelineEvent, Stage
from .phoenix_mcp import PhoenixMCP


def _pass_rate(result: dict) -> float:
    """Extract pass rate from a Phoenix experiment result.

    SPIKE-RECONCILE: align with the real experiment-results schema.
    """
    if "pass_rate" in result:
        return float(result["pass_rate"])
    runs = result.get("runs") or result.get("evaluations") or []
    if not runs:
        return 0.0
    passed = sum(1 for r in runs if (r.get("label") or r.get("score")) in (True, "pass", 1))
    return round(passed / len(runs), 4)


class Evaluator:
    def __init__(self, mcp: PhoenixMCP | None = None) -> None:
        self.s = get_settings()
        self.mcp = mcp or PhoenixMCP(self.s)

    async def run_baseline(self, inc: Incident, baseline_prompt: str) -> Incident:
        assert inc.dataset_id is not None
        async with self.mcp.session() as phx:
            exp_id = await phx.create_experiment(
                dataset_id=inc.dataset_id,
                name=f"cassandra-{inc.span.span_id[:8]}-baseline",
                prompt=baseline_prompt,
            )
            raw = await phx.run_experiment(exp_id)
        inc.experiment = ExperimentResult(
            experiment_id=exp_id, baseline_pass_rate=_pass_rate(raw)
        )
        inc.stage = Stage.EVALUATED
        await bus.publish(
            PipelineEvent(
                incident_id=inc.incident_id,
                stage=Stage.EVALUATED,
                title=f"Baseline: {inc.experiment.baseline_pass_rate:.0%} pass",
                detail="Current prompt scored against the synthesized dataset",
                phoenix_url=f"{self.s.phoenix_base_url}/experiments/{exp_id}",
            )
        )
        return inc

    async def run_candidate(self, inc: Incident) -> Incident:
        assert inc.experiment is not None and inc.candidate_prompt is not None
        async with self.mcp.session() as phx:
            exp_id = await phx.create_experiment(
                dataset_id=inc.dataset_id,  # type: ignore[arg-type]
                name=f"cassandra-{inc.span.span_id[:8]}-candidate",
                prompt=inc.candidate_prompt,
            )
            raw = await phx.run_experiment(exp_id)
        inc.experiment.candidate_pass_rate = _pass_rate(raw)
        await bus.publish(
            PipelineEvent(
                incident_id=inc.incident_id,
                stage=Stage.EVALUATED,
                title=(
                    f"Candidate: {inc.experiment.candidate_pass_rate:.0%} pass "
                    f"(delta {inc.experiment.delta:+.0%})"
                ),
                detail="Proposed prompt scored against the same dataset",
                phoenix_url=f"{self.s.phoenix_base_url}/experiments/{exp_id}",
            )
        )
        return inc
