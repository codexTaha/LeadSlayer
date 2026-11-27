from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from collections import OrderedDict
from pathlib import Path

import numpy as np

from app.config import DATA_DIR, settings

MAX_TEXT_BYTES = 16_384


def normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()


def build_cache_key(model_id: str, dim: int, task_type: str, text: str) -> str:
    normalized = normalize_text(text)
    raw = f"{model_id}:{dim}:{task_type}:{normalized}".encode("utf-8")
    if len(raw) > MAX_TEXT_BYTES + 128:
        raise ValueError(f"Embedding input exceeds {MAX_TEXT_BYTES} byte safety cap.")
    return hashlib.sha256(raw).hexdigest()


class BoundedTTLEmbeddingCache:
    """
    Thread/async-safe SHA-256 embedding cache with strict 6-hour TTL
    and 1,000-entry LRU cap so RAM and disk never overload.
    """

    def __init__(
        self,
        cache_path: Path = DATA_DIR / ".emb_cache.json",
        dim: int = settings.embedding_dim,
        ttl_seconds: int = settings.embedding_cache_ttl_seconds,
        max_entries: int = settings.embedding_cache_max_entries,
    ) -> None:
        self._path = cache_path
        self._dim = dim
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._lock = asyncio.Lock()
        self._entries: OrderedDict[str, dict] = OrderedDict()
        self._loaded = False
        self._dirty = False

    def _ensure_loaded_sync(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self._path.exists():
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            if payload.get("version") != 1 or payload.get("dim") != self._dim:
                return
            raw_entries = payload.get("entries", {})
            now = time.time()
            valid_items: list[tuple[str, dict]] = []
            for key, item in raw_entries.items():
                created_at = float(item.get("created_at", 0.0))
                vec = item.get("vector")
                if (
                    now - created_at <= self._ttl_seconds
                    and isinstance(vec, list)
                    and len(vec) == self._dim
                ):
                    valid_items.append((key, item))
            valid_items.sort(key=lambda kv: float(kv[1].get("last_used", 0.0)))
            for key, item in valid_items[-self._max_entries :]:
                self._entries[key] = item
        except (OSError, ValueError, TypeError):
            self._entries.clear()

    def purge_expired(self) -> int:
        self._ensure_loaded_sync()
        now = time.time()
        expired_keys = [
            k
            for k, v in self._entries.items()
            if (now - float(v.get("created_at", 0.0))) > self._ttl_seconds
        ]
        for k in expired_keys:
            self._entries.pop(k, None)
        return len(expired_keys)

    def _evict_if_needed(self) -> None:
        self.purge_expired()
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def _flush_atomic_sync(self) -> None:
        if not self._dirty:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(".json.tmp")
        payload = {
            "version": 1,
            "dim": self._dim,
            "entries": dict(self._entries),
        }
        tmp_path.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp_path, self._path)
        self._dirty = False

    async def get_many(
        self, keys: list[str]
    ) -> tuple[dict[str, np.ndarray], list[int]]:
        async with self._lock:
            self._ensure_loaded_sync()
            self.purge_expired()
            now = time.time()
            hits: dict[str, np.ndarray] = {}
            missing_indices: list[int] = []
            for idx, key in enumerate(keys):
                entry = self._entries.get(key)
                if entry is None:
                    missing_indices.append(idx)
                    continue
                entry["last_used"] = now
                self._entries.move_to_end(key)
                hits[key] = np.asarray(entry["vector"], dtype=np.float32)
            return hits, missing_indices

    async def put_many(
        self, items: dict[str, np.ndarray], flush: bool = True
    ) -> None:
        if not items:
            return
        async with self._lock:
            self._ensure_loaded_sync()
            now = time.time()
            for key, vec in items.items():
                arr = np.asarray(vec, dtype=np.float32)
                self._entries[key] = {
                    "created_at": now,
                    "last_used": now,
                    "vector": [round(float(x), 7) for x in arr.tolist()],
                }
                self._entries.move_to_end(key)
                self._dirty = True
            self._evict_if_needed()
            if flush:
                self._flush_atomic_sync()

    async def clear(self) -> None:
        async with self._lock:
            self._entries.clear()
            self._loaded = True
            self._dirty = False
            if self._path.exists():
                try:
                    self._path.unlink()
                except OSError:
                    pass

    @property
    def size(self) -> int:
        self._ensure_loaded_sync()
        return len(self._entries)
