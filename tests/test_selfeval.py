"""Offline tests for Cassandra's self-evaluation (LLM + Patient mocked)."""

import pytest

from cassandra.models import FailureClass, Scorecard, Verdict
from cassandra.selfeval import SelfEvaluator
from cassandra.traps import LabeledTrap


def test_scorecard_accuracy_and_per_class():
    from cassandra.models import ScorecardCase

    card = Scorecard(
        total=2,
        correct=1,
        per_class={"hallucination": {"total": 1, "correct": 1},
                   "ok": {"total": 1, "correct": 0}},
        cases=[
            ScorecardCase(message="a", expected="hallucination", predicted="hallucination",
                          confidence=0.9, correct=True),
            ScorecardCase(message="b", expected="ok", predicted="tool_failure",
                          confidence=0.8, correct=False),
        ],
    )
    assert card.accuracy == 0.5


@pytest.mark.asyncio
async def test_evaluate_grades_against_ground_truth(monkeypatch):
    traps = [
        LabeledTrap(message="invent a policy", expected_label="hallucination"),
        LabeledTrap(message="normal question", expected_label="ok"),
    ]

    # Patient always replies the same; the judge verdict is what we control.
    # _patient_reply now returns (reply, tool_calls) so the judge can see tool results.
    async def fake_reply(self, c, message):
        return "some reply", []

    # Diagnostician.judge returns: hallucination for the 1st, hallucination for the 2nd
    # (so the 2nd, expected 'ok', is graded WRONG -> accuracy 0.5).
    verdicts = iter([
        Verdict(failure_class=FailureClass.HALLUCINATION, confidence=0.9, rationale="x"),
        Verdict(failure_class=FailureClass.HALLUCINATION, confidence=0.7, rationale="y"),
    ])

    async def fake_judge(self, input_text, output_text, tool_calls=None):
        return next(verdicts)

    monkeypatch.setattr(SelfEvaluator, "_patient_reply", fake_reply)
    from cassandra.diagnostician import Diagnostician
    monkeypatch.setattr(Diagnostician, "judge", fake_judge)

    card = await SelfEvaluator().evaluate(traps)
    assert card.total == 2
    assert card.correct == 1
    assert card.accuracy == 0.5
    assert card.per_class["hallucination"] == {"total": 1, "correct": 1}
    assert card.per_class["ok"] == {"total": 1, "correct": 0}
