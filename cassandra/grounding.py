"""Layer 1, the tool-call rule. Pure: no LLM, no network, no environment.

Given an answer, the turn's tool calls and a small per-bot `GroundingSpec`, decide BY RULE
whether each concrete fact the answer states ("a price", "a delivery date") is backed by a
successful call to the tool that owns that fact, and cite the call. When the spec can't
resolve a turn the rule ABSTAINS rather than guesses.

What it can't see: a successful call for the wrong entity or date still counts as backing.
That is what the value and claim layers (faithfulness.py) are for.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from cassandra.models import FailureClass


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
    """(claim_type, matched_text) for each extractor that fires. Never raises."""
    claims: list[tuple[str, str]] = []
    for name, pattern in spec.claim_extractors.items():
        try:
            m = re.search(pattern, answer)
        except re.error:
            continue
        if m:
            claims.append((name, m.group(0)))
    return claims


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
            if any(isinstance(c.get("result"), dict) and c["result"].get(claim_type) is not None
                   for c in successes):
                continue  # claim backed by a non-null field in a successful result
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
