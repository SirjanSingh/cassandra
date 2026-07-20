"""Multi-judge jury — aggregate several LLM inferences into one calibrated verdict.

The single LLM-as-judge is the weakest point in an eval stack: one sampled opinion,
no measure of its own reliability ("how do you know the judge is right?"). The jury
upgrades that fallback (EVAL_PLAN.md L2) from one voice to a PANEL. When the
deterministic grounding oracle abstains and we must ask an LLM, we ask K of them —
independent inferences spread across temperature so they don't all collapse to the
same sample — and aggregate by majority vote.

Two things fall out for free and both are enterprise-grade signals:
  * **agreement** — the fraction of jurors backing the winner — becomes a calibrated
    confidence multiplier: a 3-0 panel is trusted more than a 2-1 split.
  * **dissent** — the minority rationales — is surfaced instead of silently discarded.

This module is deliberately backend-agnostic: it fans out over *any* async call that
takes a temperature and returns a value, then aggregates. It imports only `models`
(never `oracle`) so it can be reused by the Diagnostician and the oracle without a
circular import.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from typing import Awaitable, Callable, TypeVar

from .models import FailureClass, JuryReport, Verdict

T = TypeVar("T")


def temperatures_for(size: int, *, max_temperature: float = 0.8) -> list[float]:
    """Deterministic temperature spread for `size` jurors.

    Juror 0 is always the temperature-0 anchor (the reproducible verdict), and the
    rest fan out evenly up to `max_temperature` to inject genuine diversity — a panel
    of identical temp-0 samples would just be one opinion counted K times.
    """
    if size <= 1:
        return [0.0]
    step = max_temperature / (size - 1)
    return [round(i * step, 3) for i in range(size)]


async def deliberate(
    make_call: Callable[[float], Awaitable[T]], temperatures: list[float]
) -> list[T]:
    """Run one judge inference per temperature, concurrently; return the votes.

    A juror that raises is dropped (its exception is swallowed) rather than aborting
    the whole panel — a jury still returns a verdict if a minority of jurors error.
    """
    raw = await asyncio.gather(
        *(make_call(t) for t in temperatures), return_exceptions=True
    )
    return [r for r in raw if not isinstance(r, BaseException)]


def _tally(labels: list[str]) -> tuple[str, float]:
    """(winning label, agreement fraction). Ties break toward the first-listed juror
    (juror 0 = the temp-0 anchor), so the tie-break is the reproducible verdict."""
    counts = Counter(labels)
    top = max(counts.values())
    winner = next(label for label in labels if counts[label] == top)
    return winner, round(top / len(labels), 4)


def aggregate_verdicts(verdicts: list[Verdict]) -> tuple[Verdict, JuryReport]:
    """Majority-vote a panel of Diagnostician verdicts into one verdict + report.

    Confidence is the winning class's mean juror-confidence SCALED by agreement, so a
    divided panel yields a lower, honest confidence (the calibration signal).
    """
    labels = [v.failure_class.value for v in verdicts]
    winner_label, agreement = _tally(labels)
    winner_class = FailureClass(winner_label)
    majority = [v for v in verdicts if v.failure_class is winner_class]
    mean_conf = sum(v.confidence for v in majority) / len(majority)
    verdict = Verdict(
        failure_class=winner_class,
        confidence=round(agreement * mean_conf, 4),
        rationale=majority[0].rationale,
        expected_behavior=majority[0].expected_behavior,
    )
    report = JuryReport(
        size=len(verdicts),
        agreement=agreement,
        votes=labels,
        dissent=[
            f"{v.failure_class.value}: {v.rationale}"
            for v in verdicts
            if v.failure_class is not winner_class
        ],
    )
    return verdict, report


def aggregate_bools(votes: list[bool]) -> tuple[bool, float]:
    """Majority-vote a panel of pass/fail booleans.

    A strict majority is required to PASS; an even split fails closed — for a
    regression gate, "the jury couldn't agree it's fine" should not ship.
    """
    passes = sum(1 for v in votes if v)
    fails = len(votes) - passes
    passed = passes > fails
    agreement = round(max(passes, fails) / len(votes), 4)
    return passed, agreement
