"""The ONE place Cassandra speaks the supervised agent's HTTP contract.

Cassandra's active stages (Evaluator, TraceReplay, RedTeam, the CI gate) drive the
supervised agent over HTTP. They all call through here, so this module IS the
integration contract a third-party agent must implement to be supervisable
end-to-end (docs/WORKFLOWS.md "Bring your own agent"; a ready-to-copy wrapper
lives in examples/adapter_template.py):

    POST {PATIENT_ENDPOINT}
      body:    {"message": str, "session_id": "test", "system_override": str?}
      headers: X-Cassandra-Token: <REPLAY_SHARED_SECRET>   (when configured)
      reply:   {"reply": str, "total_tokens": int, "latency_ms": int}

``session_id="test"`` marks the traffic so the Watcher's feedback-loop filter
drops it (Cassandra must never supervise its own probes). ``system_override``
swaps the agent's system prompt for that single request — it is what makes live
baseline-vs-candidate scoring possible, and the agent must gate it behind
REPLAY_SHARED_SECRET on any public deployment.
"""

from __future__ import annotations

import httpx

from .config import get_settings, replay_auth_headers


async def ask_patient(
    client: httpx.AsyncClient,
    message: str,
    system_override: str | None = None,
    endpoint: str | None = None,
) -> dict:
    """Send one probe to the supervised agent; returns its JSON response dict."""
    body: dict = {"message": message, "session_id": "test"}
    if system_override is not None:
        body["system_override"] = system_override
    r = await client.post(
        endpoint or get_settings().patient_endpoint,
        json=body,
        headers=replay_auth_headers(),
    )
    r.raise_for_status()
    return r.json()
