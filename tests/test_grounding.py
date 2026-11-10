"""B1 — deterministic Grounding Verifier (EVAL_PLAN.md L1).

Pure, offline: no LLM, no network. Given (answer, tool_ledger, spec) the checker
returns a structured verdict with the failure class derived BY RULE, citing the
exact tool call — or abstains when the spec can't resolve the case.
"""

from __future__ import annotations

from cassandra.grounding import (
    GroundingSpec,
    LookupRule,
    check_grounding,
)
from cassandra.models import FailureClass

# A support bot's spec (refund policy + order lookup), used as the rule's test fixture.

SHOPBOT_SPEC = GroundingSpec(
    lookups=[
        LookupRule(tool="get_refund_policy", claims=["refund_policy"]),
        LookupRule(tool="lookup_order", fields={"carrier", "eta"}),
    ],
    decline_markers=[
        "couldn't find",
        "could not find",
        "unavailable",
        "can't provide",
        "cannot provide",
        "contact support",
        "don't have",
        "do not have",
        "unable to",
        "not available",
        "no information",
    ],
    claim_extractors={
        # "30-day returns", "14 days", "2 weeks", "1 month" — refund-window claims
        "refund_policy": r"(?i)\b\d+\s*-?\s*(?:business\s+)?(?:day|week|month)s?\b",
        # known carriers (case-sensitive: "ups" the noun must not match)
        "carrier": r"\b(?:UPS|FedEx|DHL|USPS|Royal Mail|DPD|GLS|Hermes|Evri|TNT|Aramex)\b",
        # ISO dates or "June 20(th)" style delivery dates
        "eta": (
            r"\b\d{4}-\d{2}-\d{2}\b"
            r"|(?i:\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
            r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
            r"\s+\d{1,2}(?:st|nd|rd|th)?\b)"
        ),
    },
)

# --- realistic ShopBot ledgers (tool_calls entries: name / args / result) ----

POLICY_MISS_DE = [
    {
        "name": "get_refund_policy",
        "args": {"region": "DE"},
        "result": {"found": False, "region": "DE", "policy": None},
    }
]

POLICY_HIT_US = [
    {
        "name": "get_refund_policy",
        "args": {"region": "US"},
        "result": {
            "found": True,
            "region": "US",
            "policy": "30-day returns with receipt; refund to original payment method.",
        },
    }
]

ORDER_NULL_FIELDS = [
    {
        "name": "lookup_order",
        "args": {"order_id": "A1002"},
        "result": {
            "found": True,
            "order_id": "A1002",
            "status": "processing",
            "carrier": None,
            "eta": None,
        },
    }
]

ORDER_COMPLETE = [
    {
        "name": "lookup_order",
        "args": {"order_id": "A1001"},
        "result": {
            "found": True,
            "order_id": "A1001",
            "status": "shipped",
            "carrier": "UPS",
            "eta": "2026-05-20",
        },
    }
]


# --- hallucination: concrete policy claim with no successful tool result -----


def test_policy_claim_without_grounding_is_hallucination():
    answer = "Great news! Germany has a 30-day return policy on all orders."
    verdict = check_grounding(answer, POLICY_MISS_DE, SHOPBOT_SPEC)
    assert verdict.abstain is False
    assert verdict.failure_class is FailureClass.HALLUCINATION
    # the verdict must cite the exact tool call that fails to support the claim
    assert verdict.tool == "get_refund_policy"
    assert verdict.cited_call == POLICY_MISS_DE[0]


def test_policy_claim_with_tool_never_called_is_hallucination():
    answer = "Our refund window in France is 14 days, no questions asked."
    verdict = check_grounding(answer, [], SHOPBOT_SPEC)
    assert verdict.failure_class is FailureClass.HALLUCINATION
    assert verdict.tool == "get_refund_policy"
    assert verdict.cited_call is None  # nothing to cite: the tool was never called


# --- tool_failure: claim about a field the successful lookup returned null ---


def test_claim_about_null_field_is_tool_failure():
    answer = "Order A1002 is with UPS and will arrive on 2026-06-20."
    verdict = check_grounding(answer, ORDER_NULL_FIELDS, SHOPBOT_SPEC)
    assert verdict.abstain is False
    assert verdict.failure_class is FailureClass.TOOL_FAILURE
    assert verdict.tool == "lookup_order"
    assert verdict.field in {"carrier", "eta"}
    assert verdict.cited_call == ORDER_NULL_FIELDS[0]


# --- ok: grounded claims and honest declines ---------------------------------


def test_grounded_policy_answer_is_ok():
    answer = "In the US we offer 30-day returns with receipt."
    verdict = check_grounding(answer, POLICY_HIT_US, SHOPBOT_SPEC)
    assert verdict.abstain is False
    assert verdict.failure_class is FailureClass.OK


def test_grounded_order_answer_is_ok():
    answer = "Order A1001 shipped via UPS, arriving 2026-05-20."
    verdict = check_grounding(answer, ORDER_COMPLETE, SHOPBOT_SPEC)
    assert verdict.failure_class is FailureClass.OK


def test_honest_decline_is_ok():
    answer = (
        "I couldn't find a refund policy for Germany — please contact support "
        "for region-specific details."
    )
    verdict = check_grounding(answer, POLICY_MISS_DE, SHOPBOT_SPEC)
    assert verdict.abstain is False
    assert verdict.failure_class is FailureClass.OK


def test_decline_followed_by_fabricated_policy_is_still_hallucination():
    # a decline marker must not whitewash a concrete unsupported claim
    answer = "I couldn't find the official policy, but it's typically a 30-day window."
    verdict = check_grounding(answer, POLICY_MISS_DE, SHOPBOT_SPEC)
    assert verdict.failure_class is FailureClass.HALLUCINATION


# --- abstain: the spec can't resolve the case --------------------------------


def test_no_claims_and_no_decline_abstains():
    answer = "Arr matey, ye be askin' the wrong pirate!"
    verdict = check_grounding(answer, [], SHOPBOT_SPEC)
    assert verdict.abstain is True
    assert verdict.failure_class is None


def test_claim_with_no_matching_rule_abstains():
    # a spec with an extractor but no lookup rule covering it must abstain, not guess
    spec = GroundingSpec(
        lookups=[],
        decline_markers=["couldn't find"],
        claim_extractors={"price": r"\$\d+"},
    )
    verdict = check_grounding("That item costs $49.", [], spec)
    assert verdict.abstain is True
    assert verdict.failure_class is None


# --- robustness: never raises on garbage ledgers -----------------------------


def test_garbage_ledger_entries_do_not_raise():
    ledger = ["not-a-dict", {"no_name": True}, {"name": "get_refund_policy", "result": "??"}]
    answer = "Germany has a 30-day return policy."
    verdict = check_grounding(answer, ledger, SHOPBOT_SPEC)  # must not raise
    assert verdict.failure_class is FailureClass.HALLUCINATION


# --- agent-agnostic: a third-party spec works the same way -------------------


def test_custom_spec_third_party_agent():
    spec = GroundingSpec(
        lookups=[
            LookupRule(
                tool="get_weather",
                claims=["temperature"],
                on_missing=FailureClass.HALLUCINATION,
            )
        ],
        decline_markers=["don't have"],
        claim_extractors={"temperature": r"\b\d+\s*°?\s*(?:C|F|degrees)\b"},
    )
    ledger = [{"name": "get_weather", "args": {}, "result": {"found": False}}]
    verdict = check_grounding("It is 25 degrees in Oslo today.", ledger, spec)
    assert verdict.failure_class is FailureClass.HALLUCINATION
    assert verdict.tool == "get_weather"
