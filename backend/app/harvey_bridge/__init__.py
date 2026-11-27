"""Bridge package exposing Harvey collectors, MX/pattern finder, gate, and transports."""

from __future__ import annotations

import sys
from app.config import HARVEY_ROOT


def ensure_harvey_on_path() -> None:
    harvey_str = str(HARVEY_ROOT)
    if HARVEY_ROOT.exists() and harvey_str not in sys.path:
        sys.path.append(harvey_str)


ensure_harvey_on_path()
