from typing import Any


class GeminiAPIUnavailableError(Exception):
    """Raised when Gemini API is unavailable, rate-limited (429), or overloaded (503)."""

    def __init__(
        self,
        user_message: str = "Gemini API limit reached or service is temporarily overloaded. Please wait a short while and try again.",
        status_code: int | None = None,
        raw_error: str = "",
    ):
        super().__init__(user_message)
        self.user_message = user_message
        self.status_code = status_code
        self.raw_error = raw_error

    def __str__(self) -> str:
        details = []
        if self.status_code:
            details.append(f"status={self.status_code}")
        if self.raw_error:
            details.append(f"error={self.raw_error}")
        suffix = f" ({', '.join(details)})" if details else ""
        return f"{self.user_message}{suffix}"


def is_transient_api_error(exc: Exception) -> tuple[bool, int | None]:
    """
    Detect if an exception is transient (429, 500, 503, RESOURCE_EXHAUSTED, overloaded, timeout).
    Returns (is_transient, status_code).
    """
    if isinstance(exc, (TimeoutError,)):
        return True, 408

    err_str = str(exc).lower()

    # Check status code attribute if present
    status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if isinstance(status_code, int):
        if status_code in (429, 500, 502, 503, 504):
            return True, status_code
        return False, status_code

    if "429" in err_str or "resource_exhausted" in err_str or "rate limit" in err_str or "quota" in err_str:
        return True, 429
    if "503" in err_str or "service unavailable" in err_str or "overloaded" in err_str:
        return True, 503
    if "500" in err_str or "internal server error" in err_str:
        return True, 500
    if "502" in err_str or "504" in err_str or "gateway" in err_str or "timeout" in err_str or "timed out" in err_str:
        return True, 504

    return False, None
