import asyncio
import os
from typing import Any
import numpy as np

from google import genai
from google.genai import types

from app.config import settings
from app.memory.cache import BoundedTTLEmbeddingCache
from app.memory.exceptions import GeminiAPIUnavailableError, is_transient_api_error


class GeminiEmbedder:
    """
    Production-grade embedder using Google gemini-embedding-2 (768d).
    Integrates BoundedTTLEmbeddingCache, 25-item chunked batching, gentle retries,
    and strict L2 normalization. Never produces fake/dummy embeddings.
    """

    def __init__(
        self,
        model: str = "gemini-embedding-2",
        output_dimensionality: int = 768,
        batch_size: int = 25,
        max_retries: int = 1,
        cache: BoundedTTLEmbeddingCache | None = None,
        client: genai.Client | None = None,
        api_key: str | None = None,
    ):
        self.model = model
        self.output_dimensionality = output_dimensionality
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.cache = cache or BoundedTTLEmbeddingCache(
            ttl_seconds=settings.embedding_cache_ttl_seconds,
            max_entries=settings.embedding_cache_max_entries,
            dim=self.output_dimensionality,
        )
        self._api_key = api_key or settings.gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
        self._client = client

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            if not self._api_key:
                raise GeminiAPIUnavailableError(
                    user_message="GEMINI_API_KEY is not configured. Please provide a valid Gemini API key.",
                    status_code=401,
                    raw_error="Missing API key",
                )
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    async def embed_texts(self, texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> tuple[np.ndarray, int]:
        """
        Embed a list of text strings into an (N, 768) float32 L2-normalized matrix.
        Returns:
            (embeddings_matrix, live_api_calls_count)
        """
        n = len(texts)
        if n == 0:
            return np.zeros((0, self.output_dimensionality), dtype=np.float32), 0

        # Step 1: Compute keys and query cache
        keys = [
            BoundedTTLEmbeddingCache.compute_key(
                model_id=self.model,
                dim=self.output_dimensionality,
                task_type=task_type,
                text=t,
            )
            for t in texts
        ]

        cached_map = await self.cache.get_many(keys)
        missed_indices = [i for i, k in enumerate(keys) if k not in cached_map]

        api_calls_made = 0
        newly_computed: dict[str, list[float]] = {}

        # Step 2: Batch missed texts in chunks of self.batch_size
        if missed_indices:
            for start_idx in range(0, len(missed_indices), self.batch_size):
                batch_subset_idx = missed_indices[start_idx : start_idx + self.batch_size]
                batch_texts = [texts[idx] for idx in batch_subset_idx]

                vectors = await self._call_embed_batch_with_retry(batch_texts, task_type)
                api_calls_made += 1

                for local_i, global_idx in enumerate(batch_subset_idx):
                    k = keys[global_idx]
                    vec = vectors[local_i]
                    newly_computed[k] = vec

            if newly_computed:
                await self.cache.put_many(newly_computed, flush=True)

        # Step 3: Assemble ordered result matrix
        result = np.zeros((n, self.output_dimensionality), dtype=np.float32)
        for i, k in enumerate(keys):
            if k in cached_map:
                result[i] = cached_map[k]
            elif k in newly_computed:
                result[i] = newly_computed[k]
            else:
                raise GeminiAPIUnavailableError(
                    user_message="Embedding retrieval failed unexpectedly.",
                    raw_error=f"Key {k} missing from both cache and newly computed entries",
                )

        # Step 4: Strict L2-normalization
        norms = np.maximum(np.linalg.norm(result, axis=1, keepdims=True), 1e-12)
        normalized_result = (result / norms).astype(np.float32)
        return normalized_result, api_calls_made

    async def _call_embed_batch_with_retry(self, batch_texts: list[str], task_type: str) -> list[list[float]]:
        attempts = 0
        last_exc: Exception | None = None

        config = types.EmbedContentConfig(
            output_dimensionality=self.output_dimensionality,
            task_type=task_type,
        )

        formatted_contents = [
            types.Content(parts=[types.Part.from_text(text=t)])
            for t in batch_texts
        ]

        while attempts <= self.max_retries:
            try:
                # Use async client
                response = await self.client.aio.models.embed_content(
                    model=self.model,
                    contents=formatted_contents,
                    config=config,
                )
                if not response.embeddings or len(response.embeddings) != len(batch_texts):
                    raise GeminiAPIUnavailableError(
                        user_message="Gemini embed service returned incomplete embeddings batch.",
                        raw_error=f"Expected {len(batch_texts)} embeddings, got {len(response.embeddings) if response.embeddings else 0}",
                    )
                return [emb.values for emb in response.embeddings]

            except Exception as exc:
                last_exc = exc
                is_transient, status_code = is_transient_api_error(exc)
                if is_transient and attempts < self.max_retries:
                    attempts += 1
                    await asyncio.sleep(1.5)
                    continue
                else:
                    break

        # Failed after retries or non-transient error
        raw_err = str(last_exc) if last_exc else "Unknown embedding error"
        is_trans, status = is_transient_api_error(last_exc) if last_exc else (False, None)
        raise GeminiAPIUnavailableError(
            user_message="Gemini API limit reached or service is temporarily overloaded. Please wait a short while and try again.",
            status_code=status or 503,
            raw_error=raw_err,
        )
