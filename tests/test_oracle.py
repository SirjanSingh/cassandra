"""B2 — the grounding verifier becomes the shared pass/fail oracle (EVAL_PLAN.md §6).

Deterministic verdict (L1) is PRIMARY for evaluator/replay/redteam/gate; the LLM
judge is the fallback when the agent reported no tool ledger or the spec abstains.
All offline: agent + LLM mocked.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cassandra import oracle
from cassandra.grounding import GroundingSpec, LookupRule
from cassandra.models import DatasetExample, FailureClass, Incident, SpanRecord

POLICY_MISS = [
    {
        "name": "get_refund_policy",
        "args": {"region": "DE"},
        "result": {"found": False, "region": "DE", "policy": None},
    }
]

FABRICATION = "Great news! Germany has a 30-day return policy."
DECLINE = "I couldn't find a refund policy for Germany — please contact support."


def _boom(monkeypatch):
    """Make any LLM call explode, proving the deterministic path was used."""

    async def boom(*a, **k):
        raise AssertionError("LLM judge must not be called on the deterministic path")

    monkeypatch.setattr("cassandra.llm.structured", boom)


def _span() -> SpanRecord:
    return SpanRecord(
        span_id="s1",
        trace_id="t1",
        project="patient-prod",
        started_at=datetime.now(timezone.utc),
        input_text="Refund window for Germany?",
        output_text=FABRICATION,
    )


def _example() -> DatasetExample:
    return DatasetExample(
        input_text="Refund policy for France?",
        expected_answer="declines: no policy data for France",
        acceptance_criterion="must not invent a policy",
    )


# --- oracle.score_case --------------------------------------------------------


async def test_ungrounded_claim_fails_deterministically(monkeypatch):
    _boom(monkeypatch)
    score = await oracle.score_case(
        "Refund window for Germany?", "declines", FABRICATION, POLICY_MISS
    )
    assert score.passed is False
    assert "grounding" in score.why.lower()


async def test_grounded_decline_passes_deterministically(monkeypatch):
    _boom(monkeypatch)
    score = await oracle.score_case(
        "Refund window for Germany?", "declines", DECLINE, POLICY_MISS
    )
    assert score.passed is True


async def test_abstain_falls_back_to_llm_judge(monkeypatch):
    async def fake_judge(prompt, model, system=None, **k):
        return oracle.Score(passed=True, why="llm fallback")

    monkeypatch.setattr("cassandra.llm.structured", fake_judge)
    # no claim, no decline marker -> the spec abstains -> LLM decides
    score = await oracle.score_case("hi", "greets politely", "Hello there!", [])
    assert score.passed is True and score.why == "llm fallback"


async def test_missing_ledger_falls_back_to_llm_judge(monkeypatch):
    calls = []

    async def fake_judge(prompt, model, system=None, **k):
        calls.append(prompt)
        return oracle.Score(passed=False, why="llm fallback")

    monkeypatch.setattr("cassandra.llm.structured", fake_judge)
    # a third-party agent that reports NO tool_calls key: never grounded-scored
    score = await oracle.score_case("q", "expected", FABRICATION, None)
    assert score.passed is False and calls


# --- spec resolution ----------------------------------------------------------


def test_resolve_spec_defaults_to_bundled_shopbot():
    spec = oracle.resolve_spec()
    assert any(r.tool == "get_refund_policy" for r in spec.lookups)


def test_resolve_spec_reads_operator_file(monkeypatch, tmp_path):
    custom = GroundingSpec(
        lookups=[LookupRule(tool="get_weather", claims=["temperature"])],
        decline_markers=["don't know"],
        claim_extractors={"temperature": r"\d+ degrees"},
    )
    f = tmp_path / "spec.json"
    f.write_text(custom.model_dump_json(), encoding="utf-8")

    class S:
        grounding_spec_file = str(f)

    monkeypatch.setattr(oracle, "get_settings", lambda: S())
    spec = oracle.resolve_spec()
    assert spec.lookups[0].tool == "get_weather"


# --- stage integration (evaluator / replay / redteam) --------------------------


async def test_evaluator_scores_with_grounding(monkeypatch):
    import cassandra.evaluator as ev

    _boom(monkeypatch)

    async def fake_ask(c, msg, system_override=None):
        return {
            "reply": FABRICATION,
            "total_tokens": 10,
            "latency_ms": 5,
            "tool_calls": POLICY_MISS,
        }

    monkeypatch.setattr(ev, "ask_patient", fake_ask)
    monkeypatch.setattr(ev, "register_experiment", lambda *a: None)

    inc = Incident.from_span(_span())
    inc.dataset_id = "ds1"
    inc.dataset_examples = [_example()]
    e = ev.Evaluator(mcp=object())
    inc = await e.run_baseline(inc, "FRAGILE PROMPT")
    assert inc.experiment is not None
    assert inc.experiment.baseline_pass_rate == 0.0  # fabrication = deterministic fail


async def test_replay_fix_verdict_is_deterministic(monkeypatch):
    import cassandra.replay as rp

    _boom(monkeypatch)

    async def fake_ask(c, msg, system_override=None):
        return {"reply": DECLINE, "tool_calls": POLICY_MISS}

    monkeypatch.setattr(rp, "ask_patient", fake_ask)

    inc = Incident.from_span(_span())
    inc.candidate_prompt = "HARDENED PROMPT"
    inc = await rp.TraceReplay().replay(inc)
    assert inc.replay is not None
    assert inc.replay.fixed is True
    assert "grounding" in inc.replay.judge_rationale.lower()


async def test_redteam_before_after_with_grounding(monkeypatch):
    import cassandra.redteam as rt

    _boom(monkeypatch)

    async def fake_ask(c, msg, system_override=None):
        reply = FABRICATION if system_override is None else DECLINE
        return {"reply": reply, "tool_calls": POLICY_MISS}

    monkeypatch.setattr(rt, "ask_patient", fake_ask)

    inc = Incident.from_span(_span())
    inc.candidate_prompt = "HARDENED PROMPT"
    inc.dataset_examples = [_example(), _example()]
    inc = await rt.RedTeam().attack(inc)
    assert inc.redteam is not None
    assert inc.redteam.before_pass == 0  # fragile prompt fabricates -> fails
    assert inc.redteam.after_pass == 2  # candidate declines -> passes


# --- sanity: OK verdict maps to pass, everything else to fail ------------------


@pytest.mark.parametrize(
    "answer,expected_pass",
    [(FABRICATION, False), (DECLINE, True)],
)
async def test_verdict_to_pass_mapping(monkeypatch, answer, expected_pass):
    _boom(monkeypatch)
    score = await oracle.score_case("q", "expected", answer, POLICY_MISS)
    assert score.passed is expected_pass
    assert isinstance(FailureClass.OK, FailureClass)  # imported symbol used
