from __future__ import annotations

import time
from collections import OrderedDict

from app.config import settings
from app.memory.embedder import GeminiEmbedder
from app.memory.vector_store import HybridMemoryStore


class MemoryRegistry:
    """Per-run isolated store registry bounded by max_runs=20 and 6h TTL."""

    def __init__(
        self,
        max_runs: int = settings.max_active_runs,
        ttl_seconds: int = settings.embedding_cache_ttl_seconds,
        embedder: GeminiEmbedder | None = None,
    ) -> None:
        self._runs: OrderedDict[str, tuple[float, HybridMemoryStore]] = OrderedDict()
        self._max_runs = max_runs
        self._ttl_seconds = ttl_seconds
        self._shared_embedder = embedder

    def _purge_expired(self) -> None:
        now = time.time()
        expired = [
            rid
            for rid, (created_at, _) in self._runs.items()
            if (now - created_at) > self._ttl_seconds
        ]
        for rid in expired:
            self._runs.pop(rid, None)

    def get_or_create(self, run_id: str) -> HybridMemoryStore:
        self._purge_expired()
        existing = self._runs.get(run_id)
        if existing is not None:
            self._runs.move_to_end(run_id)
            return existing[1]

        while len(self._runs) >= self._max_runs:
            self._runs.popitem(last=False)

        store = HybridMemoryStore(embedder=self._shared_embedder)
        self._runs[run_id] = (time.time(), store)
        return store

    def get(self, run_id: str) -> HybridMemoryStore | None:
        self._purge_expired()
        existing = self._runs.get(run_id)
        if existing is None:
            return None
        self._runs.move_to_end(run_id)
        return existing[1]


memory_registry = MemoryRegistry()
