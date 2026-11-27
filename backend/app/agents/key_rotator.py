from __future__ import annotations

import asyncio
import time

from app.config import settings


class KeyRotator:
    """
    Round-robin API key pool.  Skips any key that recently returned a 429 / daily-quota
    error and automatically retries it after ``cooldown_s`` seconds.

    Usage::

        client = genai.Client(api_key=key_rotator.next_key())

    The global singleton ``key_rotator`` is pre-wired to ``settings.gemini_api_key_pool``.
    When given a single key (the default), behaviour is identical to before.
    """

    _COOLDOWN_S: float = 65.0  # seconds before retrying a throttled key

    def __init__(self, keys: list[str]) -> None:
        self._keys: list[str] = [k for k in keys if k] or [""]
        self._index: int = 0
        self._blocked_until: dict[str, float] = {k: 0.0 for k in self._keys}
        self._lock = asyncio.Lock()

    def next_key(self) -> str:
        """Return the next available API key (non-async, safe to call from sync context)."""
        now = time.monotonic()
        for _ in range(len(self._keys)):
            key = self._keys[self._index % len(self._keys)]
            self._index += 1
            if now >= self._blocked_until.get(key, 0.0):
                return key
        return self._keys[self._index % len(self._keys)]

    def mark_throttled(self, key: str) -> None:
        """Call when a key returns HTTP 429 or a daily-quota error."""
        if key:
            self._blocked_until[key] = time.monotonic() + self._COOLDOWN_S

    def mark_ok(self, key: str) -> None:
        """Call on a successful response to clear any residual block."""
        if key:
            self._blocked_until[key] = 0.0

    @property
    def pool_size(self) -> int:
        return len(self._keys)

    def __repr__(self) -> str:
        blocked = sum(1 for t in self._blocked_until.values() if t > time.monotonic())
        return f"<KeyRotator keys={self.pool_size} blocked={blocked}>"


key_rotator = KeyRotator(settings.gemini_api_key_pool)
