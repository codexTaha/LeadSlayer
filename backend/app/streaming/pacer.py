from __future__ import annotations

import asyncio
from typing import Any

from app.models.schemas import SlayerVerdict, StreamEventType, TelemetryMetrics
from app.streaming.event_bus import EventStreamBus


class DualLanePacer:
    """
    Separates immediate control/milestone events (0ms) from dramatic Bloodbath
    verdict cascades (~90ms normal, ~25ms adaptive catch-up when backlog > 25).
    """

    def __init__(
        self,
        bus: EventStreamBus,
        normal_delay_s: float = 0.09,
        fast_delay_s: float = 0.025,
        backlog_threshold: int = 25,
    ) -> None:
        self._bus = bus
        self._normal_delay_s = normal_delay_s
        self._fast_delay_s = fast_delay_s
        self._backlog_threshold = backlog_threshold
        self._verdict_queue: asyncio.Queue[tuple[SlayerVerdict, TelemetryMetrics]] = (
            asyncio.Queue()
        )
        self._drain_task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._drain_task is None:
            self._drain_task = asyncio.create_task(self._drain_loop())

    async def emit_immediate(
        self, event_type: StreamEventType, payload: dict[str, Any]
    ) -> None:
        await self._bus.publish(event_type, payload)

    async def enqueue_verdict(
        self, verdict: SlayerVerdict, telemetry: TelemetryMetrics
    ) -> None:
        if self._drain_task is None:
            self.start()
        await self._verdict_queue.put((verdict, telemetry))

    async def _drain_loop(self) -> None:
        try:
            while True:
                verdict, telemetry = await self._verdict_queue.get()
                try:
                    await self._bus.publish(
                        StreamEventType.LEAD_VERDICT,
                        {
                            "verdict": verdict.model_dump(mode="json"),
                            "telemetry": telemetry.model_dump(mode="json"),
                        },
                    )
                    delay = (
                        self._fast_delay_s
                        if self._verdict_queue.qsize() > self._backlog_threshold
                        else self._normal_delay_s
                    )
                    if delay > 0:
                        await asyncio.sleep(delay)
                finally:
                    self._verdict_queue.task_done()
        except asyncio.CancelledError:
            return

    async def flush(self) -> None:
        """Wait until all queued verdicts finish streaming before moving phases."""
        await self._verdict_queue.join()

    async def stop(self) -> None:
        if self._drain_task is not None and not self._drain_task.done():
            self._drain_task.cancel()
            try:
                await self._drain_task
            except asyncio.CancelledError:
                pass
        self._drain_task = None
