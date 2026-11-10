"""The checking engine: one bot turn in, a verdict with findings out.

Three layers, cheapest first. Each runs only when it has what it needs:

1. **rule** (needs a `GroundingSpec`; free, offline): the answer states a fact type the
   spec says must come from a tool ("a price", "a delivery date"), and no successful call
   to that tool happened in the turn.
2. **value** (needs a source; free, offline): every clock time and number in the answer
   must occur somewhere in the source.
3. **claim** (needs a source and an LLM): the answer is split into single facts and each
   is checked against the source. This is the layer measured on RAGTruth (43% of bad
   answers caught vs 9% for a whole-answer judge; see docs/EVIDENCE.md).

The source is what the bot was given: its tool results and/or retrieved context.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from .faithfulness import claim_check, value_check
from .grounding import GroundingSpec, _extract_claims, check_grounding
from .models import FailureClass, Finding, FindingKind, Layer, Turn, TurnResult


def check_offline(turn: Turn, spec: GroundingSpec | None = None) -> TurnResult:
    """Rule + value layers only. Pure: no LLM, no network."""
    findings: list[Finding] = []
    layers: list[Layer] = []
    declined = False

    if spec is not None:
        layers.append("rule")
        v = check_grounding(turn.answer, turn.tool_calls, spec)
        if not v.abstain and v.failure_class is not FailureClass.OK:
            kind: FindingKind = ("tool_returned_empty" if v.failure_class is FailureClass.TOOL_FAILURE
                    else "no_tool_call")
            findings.append(Finding(layer="rule", kind=kind, claim=v.claim, detail=v.rationale))
        elif v.failure_class is FailureClass.OK and not _extract_claims(turn.answer, spec):
            declined = True

    if turn.has_source():
        layers.append("value")
        for issue in value_check(turn.answer, turn.source(), turn.question):
            findings.append(Finding(
                layer="value", kind="value_not_in_data", claim=issue.value,
                detail=f"The {issue.kind} {issue.value!r} appears nowhere in the data the "
                       "bot was given."))

    return _verdict(turn, findings, layers, declined)


async def check_turn(turn: Turn, spec: GroundingSpec | None = None, *,
                     use_llm: bool = True) -> TurnResult:
    """All layers that apply. The claim layer calls the configured LLM."""
    result = check_offline(turn, spec)
    if not (use_llm and turn.has_source()) or result.verdict == "declined":
        return result
    report = await claim_check(turn.question, turn.answer, turn.source())
    findings = list(result.findings)
    for c in report.unsupported:
        findings.append(Finding(layer="claim", kind=c.status, claim=c.claim,  # type: ignore[arg-type]
                                detail=c.evidence))
    return _verdict(turn, findings, [*result.layers, "claim"], declined=False)


def _verdict(turn: Turn, findings: list[Finding], layers: list[Layer],
             declined: bool) -> TurnResult:
    if findings:
        return TurnResult(turn=turn, verdict="flagged", findings=findings, layers=layers)
    if declined:
        return TurnResult(turn=turn, verdict="declined", layers=layers,
                          note="No specific fact stated; the bot declined.")
    if turn.has_source():
        return TurnResult(turn=turn, verdict="ok", layers=layers)
    return TurnResult(turn=turn, verdict="unchecked", layers=layers,
                      note="No tool results or context were logged for this turn, so there "
                           "is nothing to check the answer against.")


async def check_many(turns: list[Turn], spec: GroundingSpec | None = None, *,
                     use_llm: bool = True, concurrency: int = 8,
                     on_done: Callable[[int, int], None] | None = None) -> list[TurnResult]:
    """Check every turn, at most `concurrency` LLM calls at a time, preserving order."""
    sem = asyncio.Semaphore(max(1, concurrency))
    done = 0

    async def one(t: Turn) -> TurnResult:
        nonlocal done
        async with sem:
            r = await check_turn(t, spec, use_llm=use_llm)
        done += 1
        if on_done:
            on_done(done, len(turns))
        return r

    tasks: list[Awaitable[TurnResult]] = [one(t) for t in turns]
    return list(await asyncio.gather(*tasks))
