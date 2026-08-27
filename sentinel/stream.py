"""One in-process event bus feeding the single /stream SSE endpoint (SOF-161).

The client models nothing about server internals — it just reads JSON events.
Cross-process producers (the standalone slice script) publish via POST /events,
which calls bus.publish() here.
"""
from __future__ import annotations

import asyncio
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._last_score: dict[str, Any] | None = None

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers.add(q)
        # Replay the latest score so a freshly-opened dial isn't blank.
        if self._last_score is not None:
            q.put_nowait(self._last_score)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    async def publish(self, event: dict[str, Any]) -> int:
        if event.get("type") == "score":
            self._last_score = event
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # slow consumer drops events rather than blocking producers
        return len(self._subscribers)


bus = EventBus()
