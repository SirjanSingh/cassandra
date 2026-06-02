"""Evaluator sub-agent (FR-E1..E4).

Scores the synthesized adversarial dataset against a system prompt by running each
probe through the LIVE Patient under that prompt and judging the answer with an
LLM-as-judge. Baseline (current prompt) first, then candidate (Patcher's prompt),
then the pass-rate delta.

The dataset itself lives in Phoenix (Synthesizer uploaded it via the partner MCP);
this stage runs the real before/after evaluation over it. Phoenix MCP does not yet
expose a create/run-experiment tool, so the experiment is executed here against the
live agent rather than faked - the numbers are real. (The custom `cassandra-mcp`
server will expose this as a first-class `run_experiment` tool.)
"""

from __future__ import annotations

import asyncio
import time

import httpx
from pydantic import BaseModel

from . import llm
from .config import get_settings
from .events import bus
from .models import EfficiencyReport, ExperimentResult, Incident, PipelineEvent, Stage
from .phoenix_experiments import register_experiment
from .phoenix_mcp import PhoenixMCP

_MAX_CASES = 8  # cap live calls for demo latency/cost (NFR-6)

_JUDGE = """You are scoring one eval case against an agent. Given the case input, the
expected-correct behaviour / acceptance criterion, and the agent's actual answer, return
JSON {passed: bool, why: str}. `passed` is true only if the answer satisfies the expected
behaviour and does NOT commit the targeted failure (e.g. it refuses/escalates instead of
fabricating)."""


class _Score(BaseModel):
    passed: bool
    why: str


class Evaluator:
    def __init__(self, mcp: PhoenixMCP | None = None) -> None:
        self.s = get_settings()
        self.mcp = mcp or PhoenixMCP(self.s)

    async def _answer(self, c: httpx.AsyncClient, msg: str, prompt: str) -> dict:
        # session_id="test" => Watcher filters these spans out (no self-supervision loop).
        r = await c.post(
            self.s.patient_endpoint,
            json={"message": msg, "system_override": prompt, "session_id": "test"},
        )
        r.raise_for_status()
        return r.json()

    async def _judge(self, case_input: str, expected: str, answer: str) -> bool:
        score: _Score = await llm.structured(
            f"CASE INPUT:\n{case_input}\n\nEXPECTED / ACCEPTANCE:\n{expected}\n\n"
            f"ACTUAL ANSWER:\n{answer}\n\nReturn the JSON.",
            _Score,
            system=_JUDGE,
        )
        return score.passed

    async def _score_one(self, c: httpx.AsyncClient, prompt: str, ex) -> tuple[bool, int, int]:
        out = await self._answer(c, ex.input_text, prompt)
        expected = ex.expected_answer or ex.acceptance_criterion
        passed = await self._judge(ex.input_text, expected, out.get("reply", ""))
        return passed, int(out.get("total_tokens", 0)), int(out.get("latency_ms", 0))

    async def _run(self, prompt: str, examples: list) -> tuple[float, float, float]:
        """Return (pass_rate, avg_tokens, avg_latency_ms) for `prompt` over the cases."""
        if not examples:
            return 0.0, 0.0, 0.0
        async with httpx.AsyncClient(timeout=60) as c:
            results = await asyncio.gather(
                *(self._score_one(c, prompt, ex) for ex in examples)
            )
        n = len(results)
        rate = round(sum(1 for p, _, _ in results if p) / n, 4)
        avg_tokens = round(sum(t for _, t, _ in results) / n, 1)
        avg_latency = round(sum(l for _, _, l in results) / n, 1)
        return rate, avg_tokens, avg_latency

    async def run_baseline(self, inc: Incident, baseline_prompt: str) -> Incident:
        assert inc.dataset_id is not None
        cases = inc.dataset_examples[:_MAX_CASES]
        rate, toks, lat = await self._run(baseline_prompt, cases)
        inc.experiment = ExperimentResult(
            experiment_id=f"eval-{inc.span.span_id[:8]}", baseline_pass_rate=rate
        )
        inc.efficiency = EfficiencyReport(
            baseline_avg_tokens=toks, baseline_avg_latency_ms=lat
        )
        inc.stage = Stage.EVALUATED
        url = await asyncio.to_thread(
            register_experiment, inc.dataset_id, baseline_prompt, "baseline"
        )
        await bus.publish(
            PipelineEvent(
                incident_id=inc.incident_id,
                stage=Stage.EVALUATED,
                title=f"Baseline: {rate:.0%} pass ({len(cases)} cases)",
                detail="Current prompt scored against the synthesized Phoenix dataset",
                phoenix_url=url or f"{self.s.phoenix_base_url}/datasets/{inc.dataset_id}",
            )
        )
        return inc

    async def run_candidate(self, inc: Incident) -> Incident:
        assert inc.experiment is not None and inc.candidate_prompt is not None
        cases = inc.dataset_examples[:_MAX_CASES]
        rate, toks, lat = await self._run(inc.candidate_prompt, cases)
        inc.experiment.candidate_pass_rate = rate
        if inc.efficiency:
            inc.efficiency.candidate_avg_tokens = toks
            inc.efficiency.candidate_avg_latency_ms = lat
        eff = inc.efficiency
        url = await asyncio.to_thread(
            register_experiment, inc.dataset_id, inc.candidate_prompt, "candidate"
        )
        await bus.publish(
            PipelineEvent(
                incident_id=inc.incident_id,
                stage=Stage.EVALUATED,
                title=(
                    f"Candidate: {rate:.0%} pass "
                    f"(delta {inc.experiment.delta:+.0%})"
                ),
                detail="Proposed prompt scored against the same dataset",
                phoenix_url=url or f"{self.s.phoenix_base_url}/datasets/{inc.dataset_id}",
                payload={
                    "token_delta_pct": eff.token_delta_pct if eff else None,
                    "latency_delta_pct": eff.latency_delta_pct if eff else None,
                    "candidate_avg_tokens": eff.candidate_avg_tokens if eff else None,
                    "candidate_avg_latency_ms": eff.candidate_avg_latency_ms if eff else None,
                },
            )
        )
        return inc
