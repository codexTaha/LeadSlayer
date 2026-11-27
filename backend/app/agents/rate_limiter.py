from __future__ import annotations

import asyncio
import random
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeVar

from app.agents.key_rotator import KeyRotator, key_rotator
from app.config import settings
from app.memory.exceptions import (
    GeminiAPIUnavailableError,
    is_daily_quota_error,
    is_transient_api_error,
)

T = TypeVar("T")
R = TypeVar("R")


class GentleAdaptiveExecutor:
    """
    Bounded async worker pool designed to keep Gemini API traffic smooth:
    - asyncio.Semaphore concurrency cap
    - Launch stagger so requests never spike at t=0
    - Shared cooldown gate on 429/503 with server Retry-After hint parsing
    - Jittered retries before raising GeminiAPIUnavailableError
    """

    def __init__(
        self,
        concurrency: int = settings.slayer_concurrency,
        launch_stagger_s: float = 0.06,
        max_retries: int = 2,
        backoff_schedule: tuple[float, ...] = (1.5, 3.5),
        max_cooldown_wait_s: float = 45.0,
    ) -> None:
        self._semaphore = asyncio.Semaphore(max(1, concurrency))
        self._launch_stagger_s = launch_stagger_s
        self._max_retries = max_retries
        self._backoff_schedule = backoff_schedule
        self._max_cooldown_wait_s = max_cooldown_wait_s
        self._cooldown_clear = asyncio.Event()
        self._cooldown_clear.set()
        self._cooldown_lock = asyncio.Lock()

    async def _trigger_shared_cooldown(self, attempt: int, exc: Exception) -> None:
        async with self._cooldown_lock:
            if not self._cooldown_clear.is_set():
                return
            self._cooldown_clear.clear()
            try:
                err_str = str(exc)
                match = re.search(
                    r"retry in ([0-9.]+)s", err_str, re.IGNORECASE
                ) or re.search(r"retryDelay['\":\s]+([0-9.]+)s", err_str, re.IGNORECASE)
                if match:
                    sleep_s = min(
                        float(match.group(1)) + random.uniform(0.3, 1.0),
                        self._max_cooldown_wait_s,
                    )
                else:
                    base_wait = self._backoff_schedule[
                        min(attempt, len(self._backoff_schedule) - 1)
                    ]
                    sleep_s = base_wait + random.uniform(0.0, 0.35)
                await asyncio.sleep(sleep_s)
            finally:
                self._cooldown_clear.set()

    async def _run_one(
        self,
        index: int,
        item: T,
        worker_fn: Callable[[T], Awaitable[R]],
    ) -> tuple[T, R]:
        if self._launch_stagger_s > 0 and index > 0:
            await asyncio.sleep(min(index * self._launch_stagger_s, 0.5))

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            await self._cooldown_clear.wait()
            async with self._semaphore:
                await self._cooldown_clear.wait()
                try:
                    result = await worker_fn(item)
                    return item, result
                except GeminiAPIUnavailableError:
                    raise
                except Exception as exc:
                    last_exc = exc
                    transient, status_code = is_transient_api_error(exc)
                    if transient and attempt < self._max_retries:
                        await self._trigger_shared_cooldown(attempt, exc)
                        continue

                    if is_daily_quota_error(exc):
                        raise GeminiAPIUnavailableError(
                            user_message=(
                                "Daily Gemini API quota reached for this key/model. "
                                "Please switch to another API key or retry later."
                            ),
                            status_code=429,
                            raw_error=str(exc),
                        ) from exc
                    if transient or status_code == 429:
                        raise GeminiAPIUnavailableError(
                            user_message=(
                                "Gemini API limit reached or service is temporarily overloaded. "
                                "Please wait a short while and try again."
                            ),
                            status_code=status_code or 429,
                            raw_error=str(exc),
                        ) from exc
                    raise GeminiAPIUnavailableError(
                        user_message=(
                            "Gemini agent call failed or is currently unreachable. "
                            "Please verify your API key/network and try again."
                        ),
                        status_code=status_code,
                        raw_error=str(exc),
                    ) from exc

        raise GeminiAPIUnavailableError(raw_error=str(last_exc or ""))

    async def run_stream(
        self,
        items: list[T],
        worker_fn: Callable[[T], Awaitable[R]],
    ) -> AsyncIterator[tuple[T, R]]:
        if not items:
            return
        tasks = [
            asyncio.create_task(self._run_one(idx, item, worker_fn))
            for idx, item in enumerate(items)
        ]
        try:
            for coro in asyncio.as_completed(tasks):
                yield await coro
        except Exception:
            for t in tasks:
                if not t.done():
                    t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
