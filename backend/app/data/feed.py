"""Live market snapshot via FinanceDataReader.

This is the closest thing to "real-time" available without a brokerage API:
`fdr.StockListing` returns the current price / change / volume for the whole
KOSPI + KOSDAQ board in a single call, refreshed from the data source. We cache
the result briefly so frequent client polling doesn't hammer the upstream.

NOTE: this is delayed/EOD-settled data, not tick-by-tick streaming. True
intraday streaming requires a broker websocket API (account + credentials).
"""
from __future__ import annotations

import threading
import time

import FinanceDataReader as fdr

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "rows": []}
TTL_SECONDS = 10.0


def _num(v) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        return None if f != f else f  # drop NaN
    except (TypeError, ValueError):
        return None


def _fetch() -> list[dict]:
    rows: list[dict] = []
    for board in ("KOSPI", "KOSDAQ"):
        df = fdr.StockListing(board)
        cols = set(df.columns)
        chg_col = "Changes" if "Changes" in cols else None
        pct_col = "ChagesRatio" if "ChagesRatio" in cols else ("ChangesRatio" if "ChangesRatio" in cols else None)
        for r in df.itertuples(index=False):
            code = getattr(r, "Code", None)
            if not code:
                continue
            rows.append(
                {
                    "ticker": str(code),
                    "name": getattr(r, "Name", None),
                    "sector": board,
                    "price": _num(getattr(r, "Close", None)),
                    "change": _num(getattr(r, chg_col, None)) if chg_col else None,
                    "change_pct": _num(getattr(r, pct_col, None)) if pct_col else None,
                    "volume": _num(getattr(r, "Volume", None)),
                }
            )
    return rows


def live_quotes(force: bool = False) -> tuple[float, list[dict]]:
    """Return (timestamp, rows). Cached for TTL_SECONDS to throttle upstream."""
    with _lock:
        now = time.time()
        if not force and _cache["rows"] and (now - _cache["ts"] < TTL_SECONDS):
            return _cache["ts"], _cache["rows"]
        try:
            rows = _fetch()
            _cache["ts"] = now
            _cache["rows"] = rows
        except Exception:
            # On upstream failure, serve the last good snapshot if we have one.
            if _cache["rows"]:
                return _cache["ts"], _cache["rows"]
            raise
        return _cache["ts"], _cache["rows"]
