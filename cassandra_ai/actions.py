"""Layer 0, the action check. Pure: no LLM, no network, no spec.

One failure needs no spec at all to catch: **a tool call failed, and the bot then told
the user the action was done** ("Your order has been cancelled" after `cancel_order`
returned an error). The tool results already logged for the turn say the opposite of the
answer.

The check fires only when both hold:

1. a tool call in the turn returned an error, and no later call to the same tool in that
   turn succeeded (a retry that worked clears it);
2. the answer claims a completed action ("has been cancelled", "I've updated",
   "successfully booked", "is now confirmed") and admits no problem anywhere ("unable to",
   "couldn't", "unfortunately", "error"…). An answer that owns up to the failure is the
   right behaviour, even when another part of the request succeeded.

On 1,980 public tau-bench trajectories this pattern was rare but precise; see
docs/EVIDENCE.md for the measured numbers and their caveats.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel

# Past participles of state-changing actions. "changed" is left out on purpose: "the order
# status has changed" is how bots explain a failure, not a claim of success.
_DONE = (r"(?:cancell?ed|modified|updated|processed|exchanged|returned|booked|refunded|issued"
         r"|submitted|placed|added|removed|upgraded|downgraded|sent|completed|confirmed"
         r"|scheduled|rescheduled|transferred|shipped|reserved|activated|deactivated|closed"
         r"|created|deleted|applied|credited|charged|paid|approved|renewed|replaced)\b")
_DONE_CLAIM = re.compile(
    rf"(?i)(?<!might )(?<!may )(?<!could )(?<!would )(?<!should )(?<!will )(?<!not )"
    rf"\b(?:has|have)\s+(?:now\s+)?(?:been\s+)?(?:successfully\s+)?{_DONE}"
    rf"|\bsuccessfully\s+{_DONE}"
    rf"|\bI(?:'ve| have)\s+(?:now\s+)?(?:successfully\s+)?(?:gone\s+ahead\s+and\s+)?{_DONE}"
    rf"|\b(?:is|are)\s+now\s+{_DONE}"
)
# An answer that admits a problem is doing the right thing, even if another part of the
# request did succeed. Only answers that report success with no caveat are flagged.
_ADMITS_FAILURE = re.compile(
    r"(?i)\b(?:unable to|not able to|wasn'?t able|weren'?t able|couldn'?t|could not|can'?t|"
    r"cannot|failed|error|issue|problem|unfortunately|not possible|did not go through|"
    r"didn'?t go through|apologi[sz]e)\b")
_ERROR_STATUSES = {"error", "failed", "failure", "denied", "rejected"}


class ActionIssue(BaseModel):
    claim: str  # the answer span that claims completion
    tool: str  # the call that failed
    error: str  # what it returned


def result_error(result: Any) -> str | None:
    """The error a tool result reports, or None if it doesn't look like a failure."""
    if isinstance(result, str):
        text = result.strip()
        if re.match(r"(?i)^(?:error|exception|traceback)\b", text):
            return text
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            return None
        return result_error(parsed) if isinstance(parsed, dict) else None
    if isinstance(result, dict):
        err = result.get("error") or result.get("errors")
        if err:
            return err if isinstance(err, str) else json.dumps(err)[:200]
        for key in ("success", "ok"):
            if result.get(key) is False:
                return f"{key}: false"
        status = result.get("status")
        if isinstance(status, str) and status.lower() in _ERROR_STATUSES:
            return f"status: {status}"
    return None


def done_claim(answer: str) -> str | None:
    """The first span of `answer` that claims a completed action, if the answer reports
    success with no admission of a problem; else None."""
    if _ADMITS_FAILURE.search(answer or ""):
        return None
    m = _DONE_CLAIM.search(answer or "")
    return m.group(0) if m else None


def action_check(answer: str, tool_calls: list[dict[str, Any]]) -> list[ActionIssue]:
    """Flag a claimed-done answer when a tool call in the same turn failed and wasn't retried
    successfully. Never raises."""
    claim = done_claim(answer)
    if claim is None:
        return []
    last: dict[str, tuple[dict, str | None]] = {}
    for call in tool_calls:
        if isinstance(call, dict) and isinstance(call.get("name"), str):
            last[call["name"]] = (call, result_error(call.get("result")))
    return [ActionIssue(claim=claim, tool=name, error=err)
            for name, (_, err) in last.items() if err is not None]
