"""The ONE place Cassandra speaks the supervised agent's HTTP contract.

Cassandra's active stages (Evaluator, TraceReplay, RedTeam, the CI gate) drive the
supervised agent over HTTP. They all call through here, so this module IS the
integration contract a third-party agent must implement to be supervisable
end-to-end (docs/WORKFLOWS.md "Bring your own agent"; a ready-to-copy wrapper
lives in examples/adapter_template.py):

    POST {PATIENT_ENDPOINT}
      body:    {"message": str, "session_id": "test", "system_override": str?}
      headers: X-Cassandra-Token: <REPLAY_SHARED_SECRET>
      reply:   {"reply": str, "total_tokens": int, "latency_ms": int,
                "tool_calls": [{"name", "args", "result"}, ...]?,
                "override_applied": bool?}

``tool_calls`` is optional but strongly recommended: when present, the active stages
score answers with the deterministic grounding oracle (cassandra_ai/oracle.py) instead
of the LLM judge — reproducible pass/fail verdicts that cite the exact tool call.

``session_id="test"`` marks the traffic so the Watcher's feedback-loop filter
drops it (Cassandra must never supervise its own probes). ``system_override``
swaps the agent's system prompt for that single request — it is what makes live
baseline-vs-candidate scoring possible. The agent must honor it ONLY when
session_id == "test" AND REPLAY_SHARED_SECRET is configured on the agent AND the
X-Cassandra-Token header matches it; with no secret configured, it refuses (fails
closed). ``override_applied`` lets Cassandra notice a refused override: without it,
every "candidate" number would silently measure the agent's live prompt.
"""

from __future__ import annotations

import logging

import httpx

from .config import get_settings, replay_auth_headers

log = logging.getLogger(__name__)

_warned_no_secret = False

_SECRET_HINT = (
    "Set REPLAY_SHARED_SECRET to the same value for Cassandra and for the agent, then "
    "restart both (settings are cached)."
)


class OverrideRejectedError(RuntimeError):
    """The agent reported that it did NOT apply the system_override we sent.

    Every baseline-vs-candidate result (eval, replay, red-team, the CI gate) assumes the
    override was used; carrying on would score the agent's live prompt as if it were the
    candidate, e.g. a CI gate passing a prompt edit that was never actually run.
    """


def _warn_no_secret_once() -> None:
    global _warned_no_secret
    if not _warned_no_secret:
        _warned_no_secret = True
        log.warning(
            "Sending system_override without REPLAY_SHARED_SECRET: agents that follow "
            "Cassandra's adapter contract refuse overrides unless it is set. %s",
            _SECRET_HINT,
        )


async def ask_patient(
    client: httpx.AsyncClient,
    message: str,
    system_override: str | None = None,
    endpoint: str | None = None,
) -> dict:
    """Send one probe to the supervised agent; returns its JSON response dict.

    Raises OverrideRejectedError when a system_override was sent and the agent reports
    `override_applied: false`. Agents that don't report the field are trusted as before.
    """
    body: dict = {"message": message, "session_id": "test"}
    headers = replay_auth_headers()
    if system_override is not None:
        body["system_override"] = system_override
        if not headers:
            _warn_no_secret_once()
    r = await client.post(
        endpoint or get_settings().patient_endpoint,
        json=body,
        headers=headers,
    )
    r.raise_for_status()
    data = r.json()
    if (
        system_override is not None
        and isinstance(data, dict)
        and data.get("override_applied") is False
    ):
        raise OverrideRejectedError(
            "The supervised agent refused the system_override (override_applied=false), so "
            "this probe would have run its live prompt instead of the candidate. "
            + _SECRET_HINT
        )
    return data
