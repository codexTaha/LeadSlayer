from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from app.models.schemas import StreamEvent, StreamEventType


MAX_HISTORY_EVENTS = 500


class EventStreamBus:
    """Per-run async pub/sub event bus with monotonic event_id replay."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._seq = 0
        self._history: list[StreamEvent] = []
        self._subscribers: set[asyncio.Queue[StreamEvent | None]] = set()
        self._closed = False
        self._lock = asyncio.Lock()

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def history(self) -> list[StreamEvent]:
        return list(self._history)

    async def publish(
        self, event_type: StreamEventType, payload: dict[str, Any]
    ) -> StreamEvent:
        async with self._lock:
            self._seq += 1
            event = StreamEvent(
                event_id=self._seq,
                run_id=self.run_id,
                timestamp_ms=int(time.time() * 1000),
                event_type=event_type,
                payload=payload,
            )
            self._history.append(event)
            if len(self._history) > MAX_HISTORY_EVENTS:
                self._history.pop(0)
            for queue in list(self._subscribers):
                queue.put_nowait(event)
            return event

    async def close(self) -> None:
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            for queue in list(self._subscribers):
                queue.put_nowait(None)

    async def subscribe(
        self, last_event_id: int | None = None
    ) -> AsyncIterator[StreamEvent]:
        cutoff = last_event_id or 0
        queue: asyncio.Queue[StreamEvent | None] = asyncio.Queue()

        async with self._lock:
            missed = [ev for ev in self._history if ev.event_id > cutoff]
            already_closed = self._closed
            if not already_closed:
                self._subscribers.add(queue)

        try:
            for ev in missed:
                yield ev
            if already_closed:
                return
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            self._subscribers.discard(queue)
