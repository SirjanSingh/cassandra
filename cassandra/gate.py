"""CI prompt regression gate: prompts are code, so test them like code.

`cassandra-gate` scores a system prompt against an eval dataset by running every
case through the live agent and judging each answer with the same LLM-as-judge the
Evaluator uses, then exits non-zero if the pass rate is below the threshold. Drop it
into GitHub Actions (see examples/github-actions-prompt-gate.yml) and every prompt
edit gets regression-tested before it ships, exactly like a unit test suite.

The dataset format is the same as the Synthesizer's output, so datasets that
Cassandra auto-synthesizes from production failures become the regression suite
that guards future prompt changes. That is the loop: incident -> dataset -> gate.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx
from pydantic import BaseModel, Field, computed_field

from . import llm
from .config import get_settings
from .evaluator import _JUDGE, _Score
from .models import DatasetExample
from .patient_client import ask_patient


class CaseResult(BaseModel):
    """One gated eval case."""

    input_text: str
    passed: bool
    why: str = ""
    reply: str = ""


class GateResult(BaseModel):
    """The gate verdict for one prompt x dataset run."""

    total: int
    passed_cases: int
    pass_rate: float
    threshold: float
    cases: list[CaseResult] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def passed(self) -> bool:
        return self.pass_rate >= self.threshold


async def _ask_agent(c: httpx.AsyncClient, endpoint: str, message: str, prompt: str) -> str:
    """Run one case through the live agent under the prompt being gated."""
    out = await ask_patient(c, message, system_override=prompt, endpoint=endpoint)
    return out.get("reply", "")


async def _judge_case(case: DatasetExample, reply: str) -> _Score:
    """Judge one answer with the Evaluator's LLM-as-judge (single source of truth)."""
    expected = case.expected_answer or case.acceptance_criterion
    return await llm.structured(
        f"CASE INPUT:\n{case.input_text}\n\nEXPECTED / ACCEPTANCE:\n{expected}\n\n"
        f"ACTUAL ANSWER:\n{reply}\n\nReturn the JSON.",
        _Score,
        system=_JUDGE,
    )


async def run_gate(
    prompt: str,
    cases: list[DatasetExample],
    *,
    threshold: float = 0.8,
    endpoint: str | None = None,
) -> GateResult:
    """Score `prompt` over `cases` against the live agent; sequential to be CI-friendly."""
    endpoint = endpoint or get_settings().patient_endpoint
    results: list[CaseResult] = []
    async with httpx.AsyncClient(timeout=60) as c:
        for case in cases:
            reply = await _ask_agent(c, endpoint, case.input_text, prompt)
            score = await _judge_case(case, reply)
            results.append(
                CaseResult(
                    input_text=case.input_text, passed=score.passed, why=score.why, reply=reply
                )
            )
    n = len(results)
    passed_cases = sum(1 for r in results if r.passed)
    return GateResult(
        total=n,
        passed_cases=passed_cases,
        pass_rate=round(passed_cases / n, 4) if n else 0.0,
        threshold=threshold,
        cases=results,
    )


def main(argv: list[str] | None = None) -> None:
    """Console entry point: exit 0 if the prompt clears the gate, 1 otherwise."""
    ap = argparse.ArgumentParser(
        prog="cassandra-gate",
        description="Regression-gate a system prompt against an eval dataset in CI.",
    )
    ap.add_argument("--prompt-file", required=True, help="file containing the system prompt")
    ap.add_argument(
        "--cases",
        required=True,
        help="JSON file: [{input_text, expected_answer, acceptance_criterion}, ...]",
    )
    ap.add_argument("--threshold", type=float, default=0.8, help="min pass rate (default 0.8)")
    ap.add_argument("--endpoint", default=None, help="agent /chat URL (default: PATIENT_ENDPOINT)")
    ap.add_argument("--max-cases", type=int, default=0, help="cap cases (0 = all)")
    ap.add_argument("--json", action="store_true", help="emit the full result as JSON")
    args = ap.parse_args(argv)

    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    raw = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    cases = [DatasetExample.model_validate(x) for x in raw]
    if args.max_cases:
        cases = cases[: args.max_cases]

    res = asyncio.run(run_gate(prompt, cases, threshold=args.threshold, endpoint=args.endpoint))

    if args.json:
        print(res.model_dump_json(indent=2))
    else:
        for c in res.cases:
            mark = "PASS" if c.passed else "FAIL"
            print(f"[{mark}] {c.input_text[:80]}")
            if not c.passed:
                print(f"       why: {c.why}")
        verdict = "PASSED" if res.passed else "FAILED"
        print(
            f"\ngate {verdict}: {res.passed_cases}/{res.total} cases "
            f"({res.pass_rate:.0%}), threshold {res.threshold:.0%}"
        )
    sys.exit(0 if res.passed else 1)


if __name__ == "__main__":
    main()
