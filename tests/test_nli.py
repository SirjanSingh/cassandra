"""NLI layer (cassandra/nli.py) + its oracle integration (Layer 2 of the cascade).

Offline: the heuristic stub is exercised directly; the oracle integration uses a
mocked verifier so the routing logic (rule → NLI → LLM) is what's under test, not a
real model.
"""

from __future__ import annotations

from cassandra import nli, oracle


# --- the offline heuristic stub ------------------------------------------------


def test_heuristic_entailment():
    r = nli.HeuristicNLI().entails(
        "The domestic wire fee is 15 dollars.",
        "The domestic wire transfer fee is 15 dollars.",
    )
    assert r.label == nli.ENTAILMENT and r.supported


def test_heuristic_contradiction_on_absolute_over_claim():
    # Classic RAG over-claim: the answer asserts something absolute the evidence negates.
    r = nli.HeuristicNLI().entails(
        "Refunds are fully available.",
        "Refunds are not available.",
    )
    assert r.label == nli.CONTRADICTION and r.refuted


def test_heuristic_neutral_when_unrelated():
    r = nli.HeuristicNLI().entails(
        "The weather is sunny today.",
        "Our refund policy is thirty days.",
    )
    assert r.label == nli.NEUTRAL


def test_heuristic_handles_empty():
    r = nli.HeuristicNLI().entails("", "something")
    assert r.label == nli.NEUTRAL  # never raises


def test_get_verifier_defaults_to_heuristic(monkeypatch):
    nli.reset_verifier()
    monkeypatch.setattr(oracle.get_settings(), "nli_model", None)
    v = nli.get_verifier()
    assert isinstance(v, nli.HeuristicNLI)
    nli.reset_verifier()


# --- oracle Layer 2 routing ----------------------------------------------------


def _mock(label: str):
    return lambda claim, evidence: nli.NLIResult(label=label, score=0.9, backend="mock")


async def test_oracle_nli_contradiction_fails_without_llm(monkeypatch):
    # grounding can't apply (no ledger) but evidence contradicts -> NLI fails it, no LLM.
    async def boom(*a, **k):
        raise AssertionError("LLM must not be called when NLI decides")

    monkeypatch.setattr("cassandra.llm.structured", boom)
    monkeypatch.setattr("cassandra.nli.check_claim", _mock(nli.CONTRADICTION))
    score = await oracle.score_case("q", "expected", "answer", None, evidence="a passage")
    assert score.passed is False and "nli" in score.why.lower()


async def test_oracle_nli_entailment_passes_without_llm(monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("LLM must not be called when NLI decides")

    monkeypatch.setattr("cassandra.llm.structured", boom)
    monkeypatch.setattr("cassandra.nli.check_claim", _mock(nli.ENTAILMENT))
    score = await oracle.score_case("q", "expected", "answer", None, evidence="a passage")
    assert score.passed is True and "nli" in score.why.lower()


async def test_oracle_no_evidence_skips_nli(monkeypatch):
    # No evidence -> NLI is skipped and the LLM judge is used (default single judge).
    monkeypatch.setattr("cassandra.nli.check_claim",
                        lambda *a: (_ for _ in ()).throw(AssertionError("NLI must not run without evidence")))
    monkeypatch.setattr("cassandra.llm.structured",
                        lambda *a, **k: _passed())
    score = await oracle.score_case("q", "expected", "answer", None)
    assert score.passed is True


async def _passed():
    return oracle.Score(passed=True, why="llm ok")


async def test_oracle_neutral_nli_falls_through_to_llm(monkeypatch):
    monkeypatch.setattr("cassandra.nli.check_claim", _mock(nli.NEUTRAL))
    monkeypatch.setattr("cassandra.llm.structured", lambda *a, **k: _passed())
    score = await oracle.score_case("q", "expected", "answer", None, evidence="a passage")
    assert score.passed is True and "llm" in score.why.lower()
