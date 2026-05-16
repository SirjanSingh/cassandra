"""Scheduled trace-poller Cloud Function (FR-W1).

Cloud Scheduler hits this every POLL_INTERVAL_SECONDS. It drives exactly one
supervision cycle. Deploy as a 2nd-gen HTTP function; schedule via Cloud Scheduler.
"""

from __future__ import annotations

import asyncio

import functions_framework

from cassandra.loop_agent import SupervisionPipeline


@functions_framework.http
def poll(request):  # noqa: ANN001 - Cloud Functions signature
    incident = asyncio.run(SupervisionPipeline().run_once())
    if incident is None:
        return {"status": "idle"}, 200
    return {
        "status": "handled",
        "incident_id": incident.incident_id,
        "failure_class": incident.verdict.failure_class.value if incident.verdict else None,
        "delta": incident.experiment.delta if incident.experiment else None,
    }, 200
