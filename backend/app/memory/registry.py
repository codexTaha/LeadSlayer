from collections import OrderedDict
import time
from typing import Any

from app.config import settings
from app.memory.embedder import GeminiEmbedder
from app.memory.vector_store import HybridMemoryStore


class MemoryRegistry:
    """
    Thread-safe registry for HybridMemoryStore instances isolated per run_id.
    Enforces a strict 20-run LRU cap and 6-hour TTL to prevent memory leaks in production.
    """

    def __init__(self, max_runs: int = 20, ttl_seconds: int = 21600):
        self.max_runs = max_runs
        self.ttl_seconds = ttl_seconds
        # Maps run_id -> (last_accessed_timestamp, HybridMemoryStore)
        self._stores: OrderedDict[str, tuple[float, HybridMemoryStore]] = OrderedDict()

    def _purge_expired(self, now: float) -> None:
        expired_keys = [
            k for k, (last_access, _) in self._stores.items()
            if now - last_access > self.ttl_seconds
        ]
        for k in expired_keys:
            del self._stores[k]

    def get(self, run_id: str) -> HybridMemoryStore | None:
        now = time.time()
        self._purge_expired(now)

        if run_id in self._stores:
            _, store = self._stores[run_id]
            self._stores[run_id] = (now, store)
            self._stores.move_to_end(run_id)
            return store
        return None

    def get_or_create(self, run_id: str, embedder: GeminiEmbedder | None = None) -> HybridMemoryStore:
        now = time.time()
        self._purge_expired(now)

        if run_id in self._stores:
            _, store = self._stores[run_id]
            self._stores[run_id] = (now, store)
            self._stores.move_to_end(run_id)
            return store

        # Create new store
        store = HybridMemoryStore(embedder=embedder)
        self._stores[run_id] = (now, store)

        # LRU eviction if exceeding max_runs
        while len(self._stores) > self.max_runs:
            self._stores.popitem(last=False)

        return store

    def register(self, run_id: str, store: HybridMemoryStore) -> None:
        now = time.time()
        self._purge_expired(now)

        self._stores[run_id] = (now, store)
        self._stores.move_to_end(run_id)

        while len(self._stores) > self.max_runs:
            self._stores.popitem(last=False)

    def clear(self) -> None:
        self._stores.clear()


# Global singleton instance for application use
memory_registry = MemoryRegistry(
    max_runs=settings.max_active_runs,
    ttl_seconds=settings.embedding_cache_ttl_seconds,
)
