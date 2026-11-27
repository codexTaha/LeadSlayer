from __future__ import annotations

import asyncio
import re


class GeminiAPIUnavailableError(Exception):
    """Raised when live Gemini API calls fail due to quota, overload, or network error."""

    def __init__(
        self,
        user_message: str = (
            "Gemini API limit reached or service is temporarily overloaded. "
            "Please wait a short while and try again."
        ),
        status_code: int | None = None,
        raw_error: str = "",
    ) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.status_code = status_code
        self.raw_error = raw_error


def is_daily_quota_error(exc: Exception) -> bool:
    """Returns True when the API exhausted a daily quota (do NOT sleep/retry)."""
    msg = str(exc)
    if "GenerateRequestsPerDay" in msg or "per day" in msg.lower():
        return True
    match = re.search(r"retryDelay['\":\s]+([0-9.]+)s", msg, re.IGNORECASE)
    if match and float(match.group(1)) > 90.0:
        return True
    return False


def is_transient_api_error(exc: Exception) -> tuple[bool, int | None]:
    """Detect retryable HTTP 429/500/503/504, RESOURCE_EXHAUSTED, overload, or timeout errors."""
    if is_daily_quota_error(exc):
        return False, 429

    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return True, 504

    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(code, int) and code in (429, 500, 502, 503, 504):
        return True, code

    msg = str(exc).lower()
    if "429" in msg or "resource_exhausted" in msg or "quota" in msg or "rate limit" in msg:
        return True, 429
    if "503" in msg or "overloaded" in msg or "unavailable" in msg:
        return True, 503
    if "timeout" in msg or "timed out" in msg:
        return True, 504

    match = re.search(r"\b(429|500|502|503|504)\b", msg)
    if match:
        return True, int(match.group(1))

    return False, None
