"""Faithfulness checks: does an answer stay true to the data it was given?

Two layers, cheapest first, for answers written from a tool result or retrieved document:

* `value_check` — deterministic, no LLM. Pulls clock times, ratings, money and other
  numbers out of the answer and reports any that do not occur anywhere in the source.
  Catches "open until 10 PM" when the data says 21:00, or "4.5 stars" when it says 4.0.
* `claim_check` — LLM, claim by claim. The answer is split into atomic statements and each
  is checked against the source on its own, so one wrong detail can't hide inside a
  long, mostly-correct answer (the failure mode of whole-answer judging, measured in
  poc/ragtruth/README.md).

Neither touches Phoenix; both are pure functions of (answer, source).
"""

from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field

from cassandra import llm

# ----------------------------------------------------------------------------- values

_NUM = r"\d+(?:[.,]\d+)*"
_TIME_12 = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m\b", re.I)
_TIME_24 = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d?)\b")
_NUMBER = re.compile(rf"(?<![\w.\-]){_NUM}(?![\w])")  # skips "COVID-19"-style tokens
# Spelled numbers that should never be checked: counts of days, list ordinals, etc.
_SMALL_OK = {str(i) for i in range(0, 8)}


def _times_12(text: str) -> list[tuple[str, tuple[int, int]]]:
    out = []
    for m in _TIME_12.finditer(text):
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        if not 1 <= h <= 12:
            continue
        pm = m.group(3).lower() == "p"
        h24 = (h % 12) + (12 if pm else 0)
        out.append((m.group(0), (h24, mi)))
    return out


def _times_24(text: str) -> set[tuple[int, int]]:
    out = set()
    for m in _TIME_24.finditer(text):
        h, mi = int(m.group(1)), int(m.group(2))
        out.add((h, mi))
        if h == 24:
            out.add((0, mi))
    return out


def _flatten(source: object) -> str:
    return source if isinstance(source, str) else json.dumps(source, ensure_ascii=False)


def _norm_num(s: str) -> str:
    s = s.replace(",", "")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


class ValueIssue(BaseModel):
    value: str
    kind: Literal["time", "number"]


def value_check(answer: str, source: object) -> list[ValueIssue]:
    """Numbers and clock times in `answer` that appear nowhere in `source`.

    Deliberately conservative: small integers (0–7, e.g. "7 days a week") are never
    checked, and a number counts as supported if it occurs anywhere in the source.
    """
    src = _flatten(source)
    issues: list[ValueIssue] = []

    src_times = _times_24(src) | {t for _, t in _times_12(src)}
    spans12 = [m.span() for m in _TIME_12.finditer(answer)]
    # a 24h match inside "9:00 PM" is the same time already read as 12h: skip it
    m24 = [m for m in _TIME_24.finditer(answer)
           if not any(a <= m.start() < b for a, b in spans12)]
    spans = spans12 + [m.span() for m in m24]
    if src_times:  # only check times when the source talks about times at all
        for raw, t in _times_12(answer):
            if t not in src_times:
                issues.append(ValueIssue(value=raw.strip(), kind="time"))
        for m in m24:
            if (int(m.group(1)), int(m.group(2))) not in src_times:
                issues.append(ValueIssue(value=m.group(0), kind="time"))

    src_nums = {_norm_num(m.group(0)) for m in _NUMBER.finditer(src)}
    for m in _NUMBER.finditer(answer):
        if any(a <= m.start() < b for a, b in spans):
            continue  # already handled as part of a clock time
        n = _norm_num(m.group(0))
        if n in _SMALL_OK or n in src_nums:
            continue
        issues.append(ValueIssue(value=m.group(0), kind="number"))
    return issues


# ----------------------------------------------------------------------------- claims

Status = Literal["supported", "contradicted", "not_in_source", "opinion"]


class Claim(BaseModel):
    claim: str
    status: Status
    evidence: str = Field(default="", description="the source text it rests on, or why not")


class ClaimReport(BaseModel):
    claims: list[Claim]

    @property
    def unsupported(self) -> list[Claim]:
        return [c for c in self.claims if c.status in ("contradicted", "not_in_source")]


_CLAIM_SYSTEM = """You check whether an AI assistant's answer is faithful to the SOURCE it was
given (a tool result or retrieved document). You are strict and literal.

1. Split the ANSWER into atomic factual claims — one fact each. A sentence like "It offers
   free WiFi and outdoor seating but no reservations" is THREE claims.
2. Judge each claim ONLY against the SOURCE, never your own knowledge:
   - supported: the source states it, or it follows directly.
   - contradicted: the source says something different (wrong time, number, name,
     yes/no flipped, wrong person or relationship).
   - not_in_source: the source does not say it. This includes adding details, causes,
     or descriptions the source never gives.
   - opinion: framing or summary with no checkable fact ("a great option", "worth a visit"),
     and advice or hedged general statements ("it can help to...", "consider booking
     ahead", "it might be useful to..."). These are never failures.
   A faithful paraphrase, or a conclusion any careful reader would draw from the source,
   is supported. Only mark a claim unsupported if it would leave a reader believing a
   specific fact (who, what, when, how many, yes/no) that the source does not give.
3. Missing or null data is UNKNOWN, not "no". If a field is null/None/absent, a claim that
   the thing is absent ("no music", "doesn't offer WiFi") is not_in_source.
4. Check every time, day, number, rating and name exactly. "Open daily 9–5" is contradicted
   if any day differs.
5. Summaries of reviews must match what the reviews say; "mixed reviews" when they are all
   positive is contradicted.

Return every claim."""


async def claim_check(question: str, answer: str, source: object) -> ClaimReport:
    """LLM claim-by-claim faithfulness check of `answer` against `source`."""
    prompt = (f"QUESTION / INSTRUCTION:\n{question}\n\n"
              f"SOURCE:\n{_flatten(source)}\n\n"
              f"ANSWER:\n{answer}\n\n"
              "Return the claims JSON.")
    return await llm.structured(prompt, ClaimReport, system=_CLAIM_SYSTEM, temperature=0.0)
