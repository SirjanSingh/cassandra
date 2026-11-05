"""Multi-judge jury: pure aggregation + Diagnostician/oracle panel integration.

All offline — the LLM is mocked to return per-temperature votes so we can drive a
deterministic split and assert the majority-vote + agreement calibration.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cassandra import jury, oracle
from cassandra.config import get_settings
from cassandra.diagnostician import Diagnostician
from cassandra.models import FailureClass, SpanRecord, Verdict
from cassandra.oracle import Score


# --- pure helpers -------------------------------------------------------------


def test_temperatures_single_is_anchor():
    assert jury.temperatures_for(1) == [0.0]
    assert jury.temperatures_for(0) == [0.0]


def test_temperatures_spread():
    temps = jury.temperatures_for(3, max_temperature=0.8)
    assert temps[0] == 0.0  # juror 0 is always the temp-0 anchor
    assert temps[-1] == 0.8
    assert temps == sorted(temps) and len(set(temps)) == 3


def _v(fc: FailureClass, conf: float, why: str = "r") -> Verdict:
    return Verdict(failure_class=fc, confidence=conf, rationale=why)


def test_aggregate_verdicts_unanimous():
    verdicts = [_v(FailureClass.HALLUCINATION, 0.9)] * 3
    verdict, report = jury.aggregate_verdicts(verdicts)
    assert verdict.failure_class is FailureClass.HALLUCINATION
    assert report.agreement == 1.0 and report.unanimous
    assert verdict.confidence == 0.9  # agreement 1.0 * mean 0.9
    assert report.dissent == []


def test_aggregate_verdicts_split_keeps_confidence_orthogonal():
    verdicts = [
        _v(FailureClass.HALLUCINATION, 0.9),
        _v(FailureClass.HALLUCINATION, 0.9),
        _v(FailureClass.TOOL_FAILURE, 0.8, "it was a lookup"),
    ]
    verdict, report = jury.aggregate_verdicts(verdicts)
    assert verdict.failure_class is FailureClass.HALLUCINATION
    assert report.agreement == round(2 / 3, 4)
    # confidence is the winners' OWN mean (0.9), NOT scaled by agreement — otherwise a
    # 2-1 split could never clear the 0.7 annotate gate (the bug this guards against).
    assert verdict.confidence == 0.9
    assert any("tool_failure" in d for d in report.dissent)


def test_aggregate_verdicts_tracks_degraded_panel():
    # 1 surviving juror but 3 were requested → degraded, not a clean unanimous vote.
    verdict, report = jury.aggregate_verdicts(
        [_v(FailureClass.HALLUCINATION, 0.9)], requested_size=3
    )
    assert report.size == 1 and report.requested_size == 3
    assert report.degraded is True
    assert report.agreement == 1.0  # among survivors — but degraded flags the caveat


def test_aggregate_verdicts_tie_breaks_to_anchor():
    # 1-1 split: juror 0 (the temp-0 anchor) wins the tie.
    verdicts = [_v(FailureClass.OK, 0.6), _v(FailureClass.HALLUCINATION, 0.9)]
    verdict, report = jury.aggregate_verdicts(verdicts)
    assert verdict.failure_class is FailureClass.OK
    assert report.agreement == 0.5


def test_aggregate_bools():
    assert jury.aggregate_bools([True, True, False]) == (True, round(2 / 3, 4))
    assert jury.aggregate_bools([True, False]) == (False, 0.5)  # even split fails closed
    assert jury.aggregate_bools([True, True, True]) == (True, 1.0)


async def test_deliberate_drops_erroring_jurors():
    async def maybe(t: float) -> float:
        if t == 0.4:
            raise RuntimeError("juror crashed")
        return t

    got = await jury.deliberate(maybe, [0.0, 0.4, 0.8])
    assert got == [0.0, 0.8]


# --- Diagnostician panel ------------------------------------------------------


def _split_judge(monkeypatch):
    """Mock llm.structured so temp 0.8 dissents (tool_failure), the rest hallucinate."""

    async def fake(prompt, schema, *, system="", temperature=0.0):
        if schema is Verdict:
            fc = FailureClass.TOOL_FAILURE if temperature >= 0.8 else FailureClass.HALLUCINATION
            return Verdict(failure_class=fc, confidence=0.9, rationale=f"t={temperature}")
        if schema is Score:
            return Score(passed=temperature >= 0.8, why=f"t={temperature}")
        raise AssertionError("unexpected schema")

    monkeypatch.setattr("cassandra.llm.structured", fake)


async def test_judge_panel_size_one_no_report(monkeypatch):
    _split_judge(monkeypatch)
    verdict, report = await Diagnostician().judge_panel("in", "out", None, size=1)
    assert report is None
    assert verdict.failure_class is FailureClass.HALLUCINATION


async def test_judge_panel_majority_vote(monkeypatch):
    _split_judge(monkeypatch)
    verdict, report = await Diagnostician().judge_panel("in", "out", None, size=3)
    assert report is not None
    assert verdict.failure_class is FailureClass.HALLUCINATION  # 2 of 3
    assert report.size == 3
    assert report.agreement == round(2 / 3, 4)
    assert report.votes.count("hallucination") == 2


async def test_diagnose_sets_jury_report(monkeypatch):
    _split_judge(monkeypatch)
    # Confidence is now the winners' mean (0.9), so raise the annotate threshold above
    # it to keep this test offline (no Phoenix session for annotate_span).
    s = get_settings()
    monkeypatch.setattr(s, "jury_size", 3)
    monkeypatch.setattr(s, "diagnosis_confidence_threshold", 0.99)
    span = SpanRecord(
        span_id="s1", trace_id="t1", project="patient-prod",
        started_at=datetime.now(timezone.utc), input_text="in", output_text="out",
    )
    from cassandra.models import Incident

    inc = await Diagnostician().diagnose(Incident.from_span(span))
    assert inc.jury is not None and inc.jury.size == 3
    assert inc.verdict.failure_class is FailureClass.HALLUCINATION


# --- oracle jury fallback -----------------------------------------------------


async def test_oracle_fallback_uses_jury(monkeypatch):
    _split_judge(monkeypatch)
    s = get_settings()
    monkeypatch.setattr(s, "jury_size", 3)
    # tool_calls=None => no grounding => LLM/jury fallback. 2 of 3 jurors vote FAIL
    # (temp 0.0 and 0.4 => passed False), so the jury fails the case.
    score = await oracle.score_case("in", "expected", "answer", None)
    assert score.passed is False
    assert "jury" in score.why.lower()
