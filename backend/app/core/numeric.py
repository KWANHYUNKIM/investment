"""Numeric coercion helpers shared across domains."""
from __future__ import annotations

import math


def json_float(v) -> float | None:
    """JSON-safe float: ``None`` for missing/NaN/non-numeric values.

    Promoted from the per-module ``_f`` helpers so every domain shapes numbers
    identically (NaN → null) instead of re-implementing the guard.
    """
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f
