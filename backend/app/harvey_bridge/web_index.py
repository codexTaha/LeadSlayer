"""Encapsulated live web & LinkedIn X-Ray index backing HunterSwarm and MarketAuditor."""

from __future__ import annotations

import asyncio
from typing import Iterable

import httpx

from app.config import settings

_SERP_ENDPOINT = "https://google.serper.dev/search"
_key_cursor = 0


def has_live_web_index() -> bool:
    """Return True when the encapsulated live web index backend is configured."""
    return bool(settings.serper_api_key_pool)


def _next_index_key() -> str:
    global _key_cursor
    pool = settings.serper_api_key_pool
    if not pool:
        return ""
    key = pool[_key_cursor % len(pool)]
    _key_cursor += 1
    return key


async def query_live_web_index(
    queries: Iterable[str],
    *,
    num_per_query: int = 10,
    pages_per_query: int = 1,
    timeout_s: float = 10.0,
) -> tuple[str, list[str]]:
    """
    Executes targeted web search queries and returns normalized discovery notes
    plus unique destination URLs ready for structured extraction and Harvey verification.
    """
    clean_queries = [q.strip() for q in queries if q and q.strip()]
    if not clean_queries or not has_live_web_index():
        return "", []

    # Free-tier SERP accounts cap `num` at 10 per request; paginate cleanly when needed.
    per_page = max(1, min(10, int(num_per_query)))
    max_pages = max(1, min(3, int(pages_per_query)))

    tasks: list[tuple[str, int]] = []
    for q in clean_queries:
        for page in range(1, max_pages + 1):
            tasks.append((q, page))

    semaphore = asyncio.Semaphore(4)
    all_items: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        async def _run_one(query_str: str, page_num: int) -> list[dict[str, str]]:
            api_key = _next_index_key()
            if not api_key:
                return []
            payload: dict[str, object] = {"q": query_str, "num": per_page}
            if page_num > 1:
                payload["page"] = page_num
            async with semaphore:
                resp = await client.post(
                    _SERP_ENDPOINT,
                    headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
            rows: list[dict[str, str]] = []
            for item in data.get("organic") or []:
                link = (item.get("link") or "").strip()
                title = (item.get("title") or "").strip()
                snippet = (item.get("snippet") or "").strip()
                if link:
                    rows.append({"title": title, "link": link, "snippet": snippet, "query": query_str})
            return rows

        results = await asyncio.gather(
            *[_run_one(q, p) for q, p in tasks],
            return_exceptions=True,
        )

    for res in results:
        if isinstance(res, Exception) or not isinstance(res, list):
            continue
        for row in res:
            url = row["link"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            all_items.append(row)

    if not all_items:
        return "", []

    notes_lines = [
        f"- {item['title']} | URL: {item['link']} | Signal: {item['snippet']}"
        for item in all_items
    ]
    return "\n".join(notes_lines), list(seen_urls)
