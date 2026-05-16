"""Watcher sub-agent (FR-W1..W4).

Pulls spans created since the durable cursor, filters to candidate span trees,
emits Incidents. Invoked by the scheduled trace-poller (functions/trace_poller).
"""

from __future__ import annotations

from datetime import datetime, timezone

from .config import get_settings
from .events import bus
from .models import Incident, PipelineEvent, Stage
from .phoenix_mcp import PhoenixMCP
from .state import get_state


class Watcher:
    def __init__(self, mcp: PhoenixMCP | None = None) -> None:
        self.s = get_settings()
        self.mcp = mcp or PhoenixMCP(self.s)
        self.state = get_state()

    async def poll(self) -> list[Incident]:
        """One poll cycle. Returns fresh, not-yet-seen incidents (FR-W2/3/4, FR-L3)."""
        since = self.state.get_cursor()
        incidents: list[Incident] = []

        async with self.mcp.session() as phx:
            spans = await phx.query_spans(self.s.patient_project, since)

        newest = since
        for span in spans:
            if not span.span_id or self.state.seen(span.span_id):
                continue
            if not (span.input_text and span.output_text):
                continue  # FR-W3: only candidate LLM/tool trees
            inc = Incident.from_span(span)
            incidents.append(inc)
            await bus.publish(
                PipelineEvent(
                    incident_id=inc.incident_id,
                    stage=Stage.WATCHED,
                    title="New span observed",
                    detail=span.input_text[:160],
                    phoenix_url=self.mcp.span_url(span),
                )
            )
            if newest is None or span.started_at > newest:
                newest = span.started_at

        self.state.set_cursor(newest or datetime.now(timezone.utc))
        return incidents
