from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
from google import genai

from app.agents.key_rotator import key_rotator
from app.config import settings
from app.memory.cache import BoundedTTLEmbeddingCache, build_cache_key, normalize_text
from app.memory.exceptions import GeminiAPIUnavailableError, is_transient_api_error


def _l2_normalize_matrix(matrix: np.ndarray) -> np.ndarray:
    if matrix.size == 0:
        return matrix.astype(np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return (matrix / norms).astype(np.float32)


class GeminiEmbedder:
    """Native async batched wrapper around gemini-embedding-2 with 768d MRL + 6h cache."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = settings.gemini_embedding_model,
        dim: int = settings.embedding_dim,
        batch_size: int = 25,
        max_retries: int = 1,
        cache: BoundedTTLEmbeddingCache | None = None,
        client: Any | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else key_rotator.next_key()
        self._model = model
        self._dim = dim
        self._batch_size = batch_size
        self._max_retries = max_retries
        self._cache = cache or BoundedTTLEmbeddingCache(dim=dim)
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            if not self._api_key:
                raise GeminiAPIUnavailableError(
                    user_message="GEMINI_API_KEY is missing. Please configure .env and try again.",
                    status_code=401,
                )
            self._client = genai.Client(
                api_key=self._api_key,
                http_options=genai.types.HttpOptions(
                    retry_options=genai.types.HttpRetryOptions(attempts=1)
                ),
            )
        return self._client

    async def _embed_batch_async(
        self, batch_texts: list[str], task_type: str
    ) -> list[np.ndarray]:
        client = self._get_client()
        contents = [
            genai.types.Content(parts=[genai.types.Part.from_text(text=t)])
            for t in batch_texts
        ]
        config = genai.types.EmbedContentConfig(
            output_dimensionality=self._dim,
            task_type=task_type,
        )
        # Support both real async genai.Client (aio) and sync test stubs seamlessly
        if hasattr(client, "aio") and hasattr(client.aio, "models"):
            response = await client.aio.models.embed_content(
                model=self._model,
                contents=contents,
                config=config,
            )
        else:
            response = await asyncio.to_thread(
                client.models.embed_content,
                model=self._model,
                contents=contents,
                config=config,
            )

        vectors: list[np.ndarray] = []
        for emb in response.embeddings:
            arr = np.asarray(emb.values, dtype=np.float32)
            norm = float(np.linalg.norm(arr))
            if norm > 1e-12:
                arr = arr / norm
            vectors.append(arr.astype(np.float32))
        if len(vectors) != len(batch_texts):
            raise RuntimeError(
                f"Expected {len(batch_texts)} embeddings, received {len(vectors)}."
            )
        return vectors

    async def _embed_batch_with_retry(
        self, batch_texts: list[str], task_type: str
    ) -> list[np.ndarray]:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return await self._embed_batch_async(batch_texts, task_type)
            except GeminiAPIUnavailableError:
                raise
            except Exception as exc:
                last_exc = exc
                transient, status_code = is_transient_api_error(exc)
                if transient and attempt < self._max_retries:
                    await asyncio.sleep(1.5)
                    continue
                if transient or status_code == 429:
                    raise GeminiAPIUnavailableError(
                        user_message=(
                            "Gemini embedding API limit reached or service is temporarily "
                            "overloaded. Please wait a short while and try again."
                        ),
                        status_code=status_code or 429,
                        raw_error=str(exc),
                    ) from exc
                raise GeminiAPIUnavailableError(
                    user_message=(
                        "Gemini embedding API failed or is currently unreachable. "
                        "Please check your API key/network and try again."
                    ),
                    status_code=status_code,
                    raw_error=str(exc),
                ) from exc

        raise GeminiAPIUnavailableError(raw_error=str(last_exc or ""))

    async def embed_texts(
        self,
        texts: list[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
    ) -> tuple[np.ndarray, int]:
        if not texts:
            return np.zeros((0, self._dim), dtype=np.float32), 0

        normalized = [normalize_text(t) for t in texts]
        keys = [
            build_cache_key(self._model, self._dim, task_type, txt)
            for txt in normalized
        ]
        hits, missing_indices = await self._cache.get_many(keys)

        ordered_vectors: list[np.ndarray | None] = [hits.get(k) for k in keys]
        if not missing_indices:
            mat = np.vstack([v for v in ordered_vectors if v is not None])
            return _l2_normalize_matrix(mat), 0

        new_cache_items: dict[str, np.ndarray] = {}
        api_calls = 0

        for start in range(0, len(missing_indices), self._batch_size):
            batch_idx_slice = missing_indices[start : start + self._batch_size]
            batch_texts = [normalized[i] for i in batch_idx_slice]
            api_calls += 1
            vecs = await self._embed_batch_with_retry(batch_texts, task_type)
            for idx_pos, vec in zip(batch_idx_slice, vecs):
                ordered_vectors[idx_pos] = vec
                new_cache_items[keys[idx_pos]] = vec

        await self._cache.put_many(new_cache_items, flush=True)
        mat = np.vstack([v for v in ordered_vectors if v is not None])
        return _l2_normalize_matrix(mat), api_calls
