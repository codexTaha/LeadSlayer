import asyncio
import random
from typing import AsyncIterator, Awaitable, Callable, TypeVar

from app.memory.exceptions import GeminiAPIUnavailableError, is_transient_api_error

T = TypeVar("T")
R = TypeVar("R")


class GentleAdaptiveExecutor:
    """
    High-resilience concurrent task runner tailored for Google Gemini API quotas.
    Features:
    - Bounded concurrency with asyncio.Semaphore (default 5)
    - 60ms launch staggering to prevent burst spikes
    - Shared Cooldown Gate: if ANY worker encounters 429/503, all workers pause
    - Exponential backoff (1.5s, 3.5s) with random jitter
    - Zero fake outputs: raises GeminiAPIUnavailableError if retries are exhausted.
    """

    def __init__(
        self,
        concurrency: int = 5,
        launch_stagger_s: float = 0.06,
        max_retries: int = 2,
    ):
        self.concurrency = concurrency
        self.launch_stagger_s = launch_stagger_s
        self.max_retries = max_retries
        self._semaphore = asyncio.Semaphore(concurrency)
        self._cooldown_event = asyncio.Event()
        self._cooldown_event.set()  # Open by default
        self._cooldown_lock = asyncio.Lock()

    async def _handle_cooldown(self, attempt: int, exc: Exception) -> None:
        async with self._cooldown_lock:
            # If cooldown is currently open, close it and sleep
            if self._cooldown_event.is_set():
                self._cooldown_event.clear()
                err_str = str(exc)
                import re
                match = re.search(r"retry in ([0-9.]+)s", err_str, re.IGNORECASE) or re.search(r"retrydelay['\":\s]+([0-9.]+)s", err_str, re.IGNORECASE)
                if match:
                    sleep_time = float(match.group(1)) + random.uniform(0.5, 1.5)
                else:
                    backoff = 1.5 if attempt == 1 else 3.5
                    jitter = random.uniform(0.0, 0.3)
                    sleep_time = backoff + jitter
                await asyncio.sleep(sleep_time)
                self._cooldown_event.set()
            else:
                # Sibling worker already initiated cooldown, wait for it to clear
                pass

    async def _execute_with_retry(
        self,
        item: T,
        worker_fn: Callable[[T], Awaitable[R]],
    ) -> R:
        attempts = 0
        last_exc: Exception | None = None

        while attempts <= self.max_retries:
            # Wait if shared cooldown gate is paused
            await self._cooldown_event.wait()

            async with self._semaphore:
                try:
                    return await worker_fn(item)
                except Exception as exc:
                    last_exc = exc
                    is_transient, status_code = is_transient_api_error(exc)
                    if is_transient and attempts < self.max_retries:
                        attempts += 1
                        await self._handle_cooldown(attempts, exc)
                        continue
                    else:
                        break

        # If we got here, all retries failed or error was non-transient
        raw_err = str(last_exc) if last_exc else "Unknown executor error"
        is_trans, status = is_transient_api_error(last_exc) if last_exc else (False, None)
        raise GeminiAPIUnavailableError(
            user_message="Gemini API limit reached or service is temporarily overloaded. Please wait a short while and try again.",
            status_code=status or 503,
            raw_error=raw_err,
        )

    async def run_stream(
        self,
        items: list[T],
        worker_fn: Callable[[T], Awaitable[R]],
    ) -> AsyncIterator[tuple[T, R]]:
        """
        Stream executed items as they complete, launching with a stagger.
        Yields (item, result).
        """
        if not items:
            return

        queue: asyncio.Queue[tuple[T, R] | Exception] = asyncio.Queue()

        async def _wrapped_worker(it: T) -> None:
            try:
                res = await self._execute_with_retry(it, worker_fn)
                await queue.put((it, res))
            except Exception as e:
                await queue.put(e)

        # Launch workers with launch_stagger_s
        tasks = []
        for item in items:
            t = asyncio.create_task(_wrapped_worker(item))
            tasks.append(t)
            if self.launch_stagger_s > 0:
                await asyncio.sleep(self.launch_stagger_s)

        # Yield as completed
        completed_count = 0
        total_items = len(items)

        try:
            while completed_count < total_items:
                msg = await queue.get()
                if isinstance(msg, Exception):
                    # Cancel pending tasks
                    for t in tasks:
                        if not t.done():
                            t.cancel()
                    raise msg
                yield msg
                completed_count += 1
        finally:
            for t in tasks:
                if not t.done():
                    t.cancel()
