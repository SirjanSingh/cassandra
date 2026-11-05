"""In-process pub/sub for pipeline events -> dashboard SSE feed (FR-DB1, FR-L2).

Deliberately simple: the dashboard subscribes and Cassandra publishes. For the
single-node demo this is sufficient; a real deployment would back this with
Pub/Sub. (Out of scope per PRD non-goals.)
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from .models import PipelineEvent


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[PipelineEvent]] = []

    async def publish(self, event: PipelineEvent) -> None:
        for q in list(self._subscribers):
            await q.put(event)

    async def subscribe(self) -> AsyncIterator[PipelineEvent]:
        q: asyncio.Queue[PipelineEvent] = asyncio.Queue()
        self._subscribers.append(q)
        try:
            while True:
                yield await q.get()
        finally:
            self._subscribers.remove(q)


bus = EventBus()
