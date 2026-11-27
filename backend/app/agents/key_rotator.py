from __future__ import annotations

import asyncio
import time

from app.config import settings


class KeyRotator:
    """
    Round-robin API key pool with separate cooldown tracking for standard inference
    vs. search-grounding calls (so a Search 404/429 on a newer key never quarantines
    that key for standard LLM/embedding calls).

    Usage::

        key = key_rotator.next_key()
        client = genai.Client(api_key=key)
    """

    _COOLDOWN_S: float = 65.0
    _SEARCH_COOLDOWN_S: float = 300.0

    def __init__(self, keys: list[str]) -> None:
        self._keys: list[str] = [k for k in keys if k] or [""]
        self._index: int = 0
        self._search_index: int = 0
        self._blocked_until: dict[str, float] = {k: 0.0 for k in self._keys}
        self._search_blocked_until: dict[str, float] = {k: 0.0 for k in self._keys}
        self._lock = asyncio.Lock()

    def next_key(self) -> str:
        """Return the next available key for standard inference / embeddings."""
        now = time.monotonic()
        for _ in range(len(self._keys)):
            key = self._keys[self._index % len(self._keys)]
            self._index += 1
            if now >= self._blocked_until.get(key, 0.0):
                return key
        return self._keys[self._index % len(self._keys)]

    def next_search_key(self) -> str | None:
        """Return the next key whose search-grounding quota is not quarantined, or None if all are."""
        now = time.monotonic()
        for _ in range(len(self._keys)):
            key = self._keys[self._search_index % len(self._keys)]
            self._search_index += 1
            if now >= self._search_blocked_until.get(key, 0.0) and now >= self._blocked_until.get(key, 0.0):
                return key
        return None

    def mark_throttled(self, key: str) -> None:
        """Quarantine a key temporarily for standard inference after a 429/quota error."""
        if key:
            self._blocked_until[key] = time.monotonic() + self._COOLDOWN_S

    def mark_search_throttled(self, key: str, cooldown_s: float | None = None) -> None:
        """Quarantine a key ONLY for search-grounding calls without blocking standard inference."""
        if key:
            wait = self._SEARCH_COOLDOWN_S if cooldown_s is None else max(1.0, cooldown_s)
            self._search_blocked_until[key] = time.monotonic() + wait

    def mark_ok(self, key: str) -> None:
        """Clear any residual inference cooldown after a successful call."""
        if key:
            self._blocked_until[key] = 0.0

    def mark_search_ok(self, key: str) -> None:
        """Clear any residual search cooldown after a successful search-grounded call."""
        if key:
            self._search_blocked_until[key] = 0.0

    @property
    def pool_size(self) -> int:
        return len(self._keys)

    def __repr__(self) -> str:
        now = time.monotonic()
        blocked = sum(1 for t in self._blocked_until.values() if t > now)
        search_blocked = sum(1 for t in self._search_blocked_until.values() if t > now)
        return f"<KeyRotator keys={self.pool_size} blocked={blocked} search_blocked={search_blocked}>"


key_rotator = KeyRotator(settings.gemini_api_key_pool)
