import asyncio
from collections import OrderedDict
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any


class BoundedTTLEmbeddingCache:
    """
    High-performance in-memory + atomic JSON on-disk cache for Gemini embeddings.
    Guards RAM (max 1000 items) and freshness (6 hour TTL).
    """

    def __init__(
        self,
        cache_path: str | Path = "data/.emb_cache.json",
        ttl_seconds: int = 21600,
        max_entries: int = 1000,
        dim: int = 768,
        max_text_bytes: int = 16384,
    ):
        self.cache_path = Path(cache_path)
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.dim = dim
        self.max_text_bytes = max_text_bytes
        self._entries: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = asyncio.Lock()
        self._dirty = False
        self._load_from_disk()

    @staticmethod
    def compute_key(model_id: str, dim: int, task_type: str, text: str, max_bytes: int = 16384) -> str:
        raw_bytes = text.encode("utf-8")
        if len(raw_bytes) > max_bytes:
            raise ValueError(f"Input text exceeds maximum byte limit of {max_bytes} bytes ({len(raw_bytes)} bytes)")
        normalized_text = " ".join(text.split())
        payload = f"{model_id}:{dim}:{task_type}:{normalized_text}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _purge_expired_locked(self, now: float) -> None:
        expired_keys = [
            k for k, entry in self._entries.items()
            if now - entry.get("created_at", 0.0) > self.ttl_seconds
        ]
        for k in expired_keys:
            del self._entries[k]
            self._dirty = True

    def _load_from_disk(self) -> None:
        if not self.cache_path.exists():
            return
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("dim") != self.dim or data.get("version") != 1:
                return
            entries = data.get("entries", {})
            now = time.time()
            for key, entry in entries.items():
                if now - entry.get("created_at", 0.0) <= self.ttl_seconds:
                    self._entries[key] = entry
                    if len(self._entries) >= self.max_entries:
                        break
        except Exception:
            # Corrupted cache file: start fresh safely
            self._entries.clear()

    def _flush_to_disk_locked(self) -> None:
        if not self._dirty:
            return
        now = time.time()
        self._purge_expired_locked(now)

        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.cache_path.with_suffix(".tmp")
        data = {
            "version": 1,
            "dim": self.dim,
            "entries": dict(self._entries),
        }
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp_path, self.cache_path)
        self._dirty = False

    async def get_many(self, keys: list[str]) -> dict[str, list[float]]:
        async with self._lock:
            now = time.time()
            self._purge_expired_locked(now)

            hits: dict[str, list[float]] = {}
            for k in keys:
                if k in self._entries:
                    entry = self._entries[k]
                    # Check individual expiry
                    if now - entry.get("created_at", 0.0) <= self.ttl_seconds:
                        entry["last_used"] = now
                        self._entries.move_to_end(k)
                        hits[k] = entry["vector"]
                    else:
                        del self._entries[k]
                        self._dirty = True
            return hits

    async def put_many(self, entries: dict[str, list[float]], flush: bool = True) -> None:
        async with self._lock:
            now = time.time()
            self._purge_expired_locked(now)

            for key, vector in entries.items():
                if key in self._entries:
                    self._entries[key]["last_used"] = now
                    self._entries[key]["vector"] = vector
                    self._entries.move_to_end(key)
                else:
                    self._entries[key] = {
                        "created_at": now,
                        "last_used": now,
                        "vector": vector,
                    }
                self._dirty = True

            # Evict oldest LRU if over limit
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
                self._dirty = True

            if flush:
                self._flush_to_disk_locked()

    async def clear(self) -> None:
        async with self._lock:
            self._entries.clear()
            self._dirty = True
            self._flush_to_disk_locked()
            if self.cache_path.exists():
                try:
                    self.cache_path.unlink()
                except OSError:
                    pass
