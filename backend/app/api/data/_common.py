"""Shared helpers for the /api/data domain routers."""
from __future__ import annotations

import math


def _f(v) -> float | None:
    """JSON-safe float (None for NaN/null)."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


_SJ_LABEL = {
    "BS": "재무상태표", "IS": "손익계산서", "CIS": "포괄손익계산서",
    "CF": "현금흐름표", "SCE": "자본변동표",
}
_SJ_ORDER = ["BS", "IS", "CIS", "CF", "SCE"]
