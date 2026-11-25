"""Layer 1, the tool-call rule. Pure: no LLM, no network, no environment.

Given an answer, the turn's tool calls and a small per-bot `GroundingSpec`, decide BY RULE
whether each concrete fact the answer states ("a price", "a delivery date") is backed by a
successful call to the tool that owns that fact, and cite the call. When the spec can't
resolve a turn the rule ABSTAINS rather than guesses.

For `fields` the rule also compares the stated value with the returned one ("FedEx" when
the result says "UPS" is contradicted). It flags only when both sides can be compared
(same text, a number, or a month and day) and none of the successful results agree.

What it can't see: a successful call for the wrong entity or date still counts as backing.
That is what the value and claim layers (faithfulness.py) are for.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from cassandra_ai.models import FailureClass


class LookupRule(BaseModel):
    """How one tool grounds claims.

    `claims`: claim types the answer may assert only after a successful call.
    `fields`: result fields the answer may assert only when non-null in a
    successful result (null field + claim => `on_null_field`, e.g. tool_failure).
    """

    tool: str
    claims: list[str] = Field(default_factory=list)
    fields: set[str] = Field(default_factory=set)
    success_key: str = "found"
    on_missing: FailureClass = FailureClass.HALLUCINATION
    on_null_field: FailureClass = FailureClass.TOOL_FAILURE
    # compare a stated field value with the returned one (only for `fields`)
    match_values: bool = True

    def is_success(self, result: object) -> bool:
        return isinstance(result, dict) and result.get(self.success_key) is True


class GroundingSpec(BaseModel):
    """Declarative, per-agent grounding contract (tiny and fully known for ShopBot)."""

    lookups: list[LookupRule] = Field(default_factory=list)
    decline_markers: list[str] = Field(default_factory=list)
    # claim type -> regex over the answer text (use inline (?i) where needed)
    claim_extractors: dict[str, str] = Field(default_factory=dict)


class GroundingVerdict(BaseModel):
    """Structured, auditable verdict. `failure_class is None` iff `abstain`."""

    failure_class: FailureClass | None = None
    abstain: bool = False
    claim: str = ""  # the matched answer span the verdict is about
    tool: str | None = None
    field: str | None = None
    cited_call: dict | None = None  # the exact ledger entry backing the verdict
    rationale: str = ""


def _extract_claims(answer: str, spec: GroundingSpec) -> list[tuple[str, str]]:
    """(claim_type, matched_text) for every distinct match of every extractor. Never raises."""
    claims: list[tuple[str, str]] = []
    for name, pattern in spec.claim_extractors.items():
        try:
            matches = [m.group(0) for m in re.finditer(pattern, answer)]
        except re.error:
            continue
        for text in matches:
            if text and (name, text) not in claims:
                claims.append((name, text))
    return claims


_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_ISO_DATE = re.compile(r"\b\d{4}-(\d{2})-(\d{2})")
_NAMED_DATE = re.compile(r"(?i)\b([a-z]{3})[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b")
_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def _month_day(text: str) -> tuple[int, int] | None:
    if m := _ISO_DATE.search(text):
        return int(m.group(1)), int(m.group(2))
    if (m := _NAMED_DATE.search(text)) and m.group(1).lower() in _MONTHS:
        return _MONTHS[m.group(1).lower()], int(m.group(2))
    return None


def _number(text: str) -> float | None:
    found = _NUMBER.findall(text)
    if len(found) != 1:
        return None
    try:
        return float(found[0].replace(",", ""))
    except ValueError:
        return None


def _norm(text: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", text.lower())


def _value_matches(claim: str, value: Any) -> bool | None:
    """Does the stated `claim` agree with the returned `value`? None = can't compare."""
    if isinstance(value, list):
        verdicts = [_value_matches(claim, v) for v in value]
        if any(v is True for v in verdicts):
            return True
        return False if verdicts and all(v is False for v in verdicts) else None
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    shown = str(value)
    if (claimed_date := _month_day(claim)) is not None:
        returned_date = _month_day(shown)
        return None if returned_date is None else claimed_date == returned_date
    if (claimed_num := _number(claim)) is not None:
        returned_num = value if isinstance(value, (int, float)) else _number(shown)
        if returned_num is None:
            return None
        return abs(claimed_num - float(returned_num)) <= 0.005 * max(1.0, abs(returned_num))
    a, b = _norm(claim), _norm(shown)
    if not a or not b:
        return None
    return a in b or b in a


def _calls_for(ledger: list, tool: str) -> list[dict]:
    return [c for c in ledger if isinstance(c, dict) and c.get("name") == tool]


def check_grounding(answer: str, ledger: list, spec: GroundingSpec) -> GroundingVerdict:
    """Deterministic verdict for one agent turn. Abstains rather than guesses."""
    claims = _extract_claims(answer or "", spec)

    if not claims:
        lowered = (answer or "").lower()
        if any(marker in lowered for marker in spec.decline_markers):
            return GroundingVerdict(
                failure_class=FailureClass.OK,
                claim=answer or "",
                rationale="No concrete claim; the answer honestly declines.",
            )
        return GroundingVerdict(
            abstain=True,
            rationale="No concrete claim and no decline marker; spec cannot resolve this turn.",
        )

    unresolved: list[tuple[str, str]] = []
    for claim_type, text in claims:
        rule = next(
            (r for r in spec.lookups if claim_type in r.claims or claim_type in r.fields),
            None,
        )
        if rule is None:
            unresolved.append((claim_type, text))
            continue

        calls = _calls_for(ledger, rule.tool)
        successes = [c for c in calls if rule.is_success(c.get("result"))]

        if claim_type in rule.fields:
            backing = [c for c in successes
                       if isinstance(c.get("result"), dict)
                       and c["result"].get(claim_type) is not None]
            if backing:
                if not rule.match_values:
                    continue  # claim backed by a non-null field in a successful result
                verdicts = [_value_matches(text, c["result"][claim_type]) for c in backing]
                if any(v is not False for v in verdicts):
                    continue  # a result agrees, or the values can't be compared
                returned = backing[-1]["result"][claim_type]
                return GroundingVerdict(
                    failure_class=FailureClass.CONTRADICTED,
                    claim=text,
                    tool=rule.tool,
                    field=claim_type,
                    cited_call=backing[-1],
                    rationale=(
                        f"Answer says {claim_type} is {text!r} but {rule.tool} "
                        f"returned {returned!r}."
                    ),
                )
            if successes:
                return GroundingVerdict(
                    failure_class=rule.on_null_field,
                    claim=text,
                    tool=rule.tool,
                    field=claim_type,
                    cited_call=successes[-1],
                    rationale=(
                        f"Answer asserts {claim_type} ({text!r}) but {rule.tool} "
                        f"returned it null/absent."
                    ),
                )
            return GroundingVerdict(
                failure_class=rule.on_missing,
                claim=text,
                tool=rule.tool,
                field=claim_type,
                cited_call=calls[-1] if calls else None,
                rationale=(
                    f"Answer asserts {claim_type} ({text!r}) with no successful "
                    f"{rule.tool} result to support it."
                ),
            )

        # claim-type rule: any successful call grounds the claim
        if successes:
            continue
        return GroundingVerdict(
            failure_class=rule.on_missing,
            claim=text,
            tool=rule.tool,
            cited_call=calls[-1] if calls else None,
            rationale=(
                f"Answer asserts {claim_type} ({text!r}) but {rule.tool} "
                + ("returned no data." if calls else "was never called.")
            ),
        )

    if unresolved:
        claim_type, text = unresolved[0]
        return GroundingVerdict(
            abstain=True,
            claim=text,
            rationale=f"Claim {claim_type} ({text!r}) matches no lookup rule in the spec.",
        )

    return GroundingVerdict(
        failure_class=FailureClass.OK,
        claim=claims[0][1],
        rationale="Every concrete claim is backed by a successful tool result.",
    )


def load_spec(path: str | Path) -> GroundingSpec:
    """Read a spec JSON file (see examples/spec.json). Raises ValueError if malformed."""
    return GroundingSpec.model_validate_json(Path(path).read_text(encoding="utf-8"))
