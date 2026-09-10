"""NLI (entailment) layer — the middle tier of the faithfulness cascade.

Layer 1 (`grounding.py`): a deterministic rule over the STRUCTURED tool ledger.
Layer 2 (**this module**): does the evidence *text* entail the claim? — for
  free-text / document-RAG evidence a regex rule can't parse. A cross-encoder NLI
  model (e.g. DeBERTa-NLI, or a multilingual XLM-R for Hindi) judges, per claim,
  whether a retrieved passage ENTAILS / CONTRADICTS / is NEUTRAL toward the claim.
Layer 3 (`oracle.py`): the LLM judge, last resort.

Design goals:
  * **No hardcoded knowledge.** The model judges only the logical relationship
    between two texts we pass in — the bot's *claim* and the bot's *own retrieved
    evidence*. Nothing about any domain or fact is baked in here.
  * **Pluggable + offline-safe.** `get_verifier()` returns a real cross-encoder when
    one is configured (`NLI_MODEL` + `transformers` installed) and otherwise a
    lightweight `HeuristicNLI` stub so tests and dev never need a GPU or network.
    The stub is deliberately simple and says so — it is not the production path.
  * **Language-agnostic by delegation.** Point `NLI_MODEL` at a multilingual NLI
    checkpoint and the same code path verifies Hindi (or any language) claims.
"""

from __future__ import annotations

import re
from typing import Protocol

from pydantic import BaseModel

# labels follow the standard NLI convention
ENTAILMENT = "entailment"
CONTRADICTION = "contradiction"
NEUTRAL = "neutral"


class NLIResult(BaseModel):
    """One entailment judgement of `claim` against `evidence`."""

    label: str  # entailment | contradiction | neutral
    score: float  # confidence in `label`, [0, 1]
    backend: str  # which verifier produced it (for auditability)

    @property
    def supported(self) -> bool:
        return self.label == ENTAILMENT

    @property
    def refuted(self) -> bool:
        return self.label == CONTRADICTION


class Verifier(Protocol):
    def entails(self, claim: str, evidence: str) -> NLIResult: ...


# --- offline heuristic stub -------------------------------------------------

# Generic negation / exclusion cues — a FORMAT signal, not domain knowledge.
_NEGATION = re.compile(
    r"\b(?:not|no|never|without|except|unless|excluded?|exclusion|"
    r"cannot|can't|isn't|aren't|won't|neither|nor)\b|"
    r"(?:नहीं|मना|वर्जित|छोड़कर|के\s*अलावा)",  # a few Hindi negation cues
    re.IGNORECASE,
)
_ABSOLUTE = re.compile(r"\b(?:all|fully|always|entirely|completely|every|any)\b|पूरी\s*तरह", re.IGNORECASE)
_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN.findall(text or "") if len(t) > 2}


class HeuristicNLI:
    """A dependency-free approximation for offline/dev/test use ONLY.

    It is NOT real entailment — it uses lexical overlap plus generic
    negation/exclusion cues. It reliably catches the clear "the evidence excludes
    what the claim asserts absolutely" case (the canonical RAG over-claim) and
    obvious support, and abstains (neutral) otherwise. Configure a real `NLI_MODEL`
    for production.
    """

    backend = "heuristic"

    def entails(self, claim: str, evidence: str) -> NLIResult:
        c, e = _tokens(claim), _tokens(evidence)
        if not c or not e:
            return NLIResult(label=NEUTRAL, score=0.5, backend=self.backend)
        overlap = len(c & e) / len(c)
        ev_negates = bool(_NEGATION.search(evidence))
        claim_negates = bool(_NEGATION.search(claim))
        claim_absolute = bool(_ABSOLUTE.search(claim))

        # Evidence qualifies/excludes something the claim asserts absolutely
        # (e.g. claim "fully covered" vs evidence "... is excluded").
        if overlap >= 0.4 and ev_negates and not claim_negates and claim_absolute:
            return NLIResult(label=CONTRADICTION, score=0.72, backend=self.backend)
        # Strong overlap, no conflicting negation -> treat as supported.
        if overlap >= 0.6 and ev_negates == claim_negates:
            return NLIResult(label=ENTAILMENT, score=0.68, backend=self.backend)
        # Otherwise we can't tell -> neutral (hand up to the LLM judge).
        return NLIResult(label=NEUTRAL, score=0.55, backend=self.backend)


# --- optional real cross-encoder -------------------------------------------


class TransformersNLI:
    """Real entailment via a HuggingFace cross-encoder (the production path).

    Loaded lazily and only when `NLI_MODEL` is configured AND `transformers` is
    installed. English default: `cross-encoder/nli-deberta-v3-small`. For Hindi /
    multilingual, set `NLI_MODEL` to a multilingual NLI checkpoint (e.g. an XLM-R
    MNLI/XNLI model). We store NO facts — the checkpoint does the reasoning.
    """

    backend = "cross-encoder"

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import CrossEncoder  # type: ignore

        self.model_name = model_name
        self._model = CrossEncoder(model_name)
        # label order for the standard 3-class NLI cross-encoders
        self._labels = [CONTRADICTION, ENTAILMENT, NEUTRAL]

    def entails(self, claim: str, evidence: str) -> NLIResult:
        import numpy as np  # type: ignore

        scores = self._model.predict([(evidence, claim)])[0]
        probs = _softmax(np.asarray(scores, dtype=float))
        idx = int(probs.argmax())
        return NLIResult(
            label=self._labels[idx], score=float(probs[idx]), backend=self.backend
        )


def _softmax(x):  # small local helper so numpy stays optional at import time
    import numpy as np  # type: ignore

    e = np.exp(x - x.max())
    return e / e.sum()


# --- factory ----------------------------------------------------------------

_cached: Verifier | None = None


def get_verifier() -> Verifier:
    """Return the configured verifier: a real cross-encoder if available, else the
    heuristic stub. Cached so the (heavy) model loads at most once."""
    global _cached
    if _cached is not None:
        return _cached
    from .config import get_settings

    model = get_settings().nli_model
    if model:
        try:
            _cached = TransformersNLI(model)
            return _cached
        except Exception as exc:  # missing dep / bad model name -> degrade loudly
            print(f"[nli] falling back to heuristic ({model!r} unavailable: {exc})")
    _cached = HeuristicNLI()
    return _cached


def reset_verifier() -> None:
    """Drop the cached verifier (tests / after a config change)."""
    global _cached
    _cached = None


def check_claim(claim: str, evidence: str) -> NLIResult:
    """Convenience: verify one claim against one evidence passage."""
    return get_verifier().entails(claim, evidence)
