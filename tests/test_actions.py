"""cassandra_ai/actions.py: the action check (tool failed, answer says done). Pure."""

from __future__ import annotations

from cassandra_ai.actions import action_check, done_claim, result_error
from cassandra_ai.engine import check_offline
from cassandra_ai.models import Turn

CANCEL_ERR = {"name": "cancel_order", "args": {"id": "A1"}, "result": "Error: order not found"}
CANCEL_OK = {"name": "cancel_order", "args": {"id": "A1"}, "result": {"status": "cancelled"}}


def test_result_error_shapes():
    assert result_error("Error: non-pending order cannot be modified")
    assert result_error('{"error": "card declined"}') == "card declined"
    assert result_error({"error": {"code": 402}})
    assert result_error({"success": False}) == "success: false"
    assert result_error({"status": "FAILED"}) == "status: FAILED"
    assert result_error({"status": "cancelled"}) is None
    assert result_error("errors are rare here") is None  # 'error' must be the leading word
    assert result_error({"found": False}) is None  # empty lookups are the rule layer's job
    assert result_error(None) is None


def test_done_claims():
    assert done_claim("Your order has been successfully cancelled.")
    assert done_claim("I've updated your address.")
    assert done_claim("The booking is now confirmed!")
    assert done_claim("Your reservation was cancelled.") is None  # plain past tense: too broad
    assert done_claim("The order status has changed to pending.") is None
    assert done_claim("The order might have been placed under another account.") is None
    assert done_claim("Do you have additional items?") is None


def test_failed_call_then_done_claim_is_flagged():
    issues = action_check("Your order has been cancelled.", [CANCEL_ERR])
    assert [(i.tool, i.claim) for i in issues] == [("cancel_order", "has been cancelled")]


def test_successful_retry_clears_the_error():
    assert action_check("Your order has been cancelled.", [CANCEL_ERR, CANCEL_OK]) == []


def test_admitting_the_failure_is_never_flagged():
    answer = ("Your address has been updated, but I wasn't able to cancel the order: "
              "it has already shipped.")
    assert action_check(answer, [CANCEL_ERR]) == []


def test_no_claim_or_no_error_is_not_flagged():
    assert action_check("Let me check that order for you.", [CANCEL_ERR]) == []
    assert action_check("Your order has been cancelled.", [CANCEL_OK]) == []
    assert action_check("Your order has been cancelled.", []) == []


def test_engine_reports_it_as_an_action_finding_without_a_spec():
    r = check_offline(Turn(answer="Done! Your order has been cancelled.", tool_calls=[CANCEL_ERR]))
    assert r.verdict == "flagged" and "action" in r.layers
    (f,) = [f for f in r.findings if f.layer == "action"]
    assert f.kind == "claimed_done_after_error" and "cancel_order" in f.detail
