"""Live market snapshot via FinanceDataReader.

This is the closest thing to "real-time" available without a brokerage API:
`fdr.StockListing` returns the current price / change / volume for the whole
KOSPI + KOSDAQ board in a single call, refreshed from the data source. We cache
the result briefly so frequent client polling doesn't hammer the upstream.

NOTE: the upstream is delayed/EOD-settled data, not tick-by-tick streaming, and
in this environment it doesn't move at all. So when ``settings.mock_ticks`` is on
(demo mode) we synthesize small intraday ticks on top of the settled snapshot —
a bounded, mean-reverting random walk around each ticker's last settled price —
so the grid visibly "breathes" on every poll. True intraday streaming requires a
broker websocket API (account + credentials).
"""
from __future__ import annotations

import random
import threading
import time

import FinanceDataReader as fdr

from app.core.config import get_settings

_lock = threading.Lock()
# Settled base snapshot from upstream (the anchor the ticks walk around).
_cache: dict = {"ts": 0.0, "rows": []}
TTL_SECONDS = 10.0

# Per-ticker live state for the demo tick generator: ticker -> {"price", "volume"}.
_tick_state: dict[str, dict] = {}
_rng = random.Random(20260615)

# Random-walk tuning (per poll).
_STEP_SIGMA = 0.0018      # ~0.18% typical step
_REVERT = 0.04            # pull back toward the settled price each step
_MAX_DRIFT = 0.06         # never wander more than ±6% from the settled anchor


def _num(v) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        return None if f != f else f  # drop NaN
    except (TypeError, ValueError):
        return None


def _tick_size(price: float) -> int:
    """KRX price-band tick size (2023 revision)."""
    if price < 2_000:
        return 1
    if price < 5_000:
        return 5
    if price < 20_000:
        return 10
    if price < 50_000:
        return 50
    if price < 200_000:
        return 100
    if price < 500_000:
        return 500
    return 1_000


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


def _apply_ticks(base_rows: list[dict]) -> list[dict]:
    """Overlay a bounded mean-reverting random walk on the settled snapshot.

    Each ticker walks around its settled close (the anchor). ``change`` /
    ``change_pct`` are recomputed against the settled previous close so they stay
    internally consistent, and ``volume`` only ever grows (as it does intraday).
    """
    out: list[dict] = []
    for r in base_rows:
        base_price = r["price"]
        if not base_price or base_price <= 0:
            out.append(dict(r))
            continue

        # Settled previous close, so the % change keeps its real meaning.
        prev_close = base_price - (r["change"] or 0.0)
        if prev_close <= 0:
            prev_close = base_price

        st = _tick_state.get(r["ticker"])
        if st is None:
            st = {"price": base_price, "volume": r["volume"] or 0.0}
            _tick_state[r["ticker"]] = st

        live = st["price"]
        # Mean-revert toward the anchor, then add a small random step.
        live += (base_price - live) * _REVERT
        live *= 1.0 + _rng.uniform(-_STEP_SIGMA, _STEP_SIGMA)
        # Clamp drift around the anchor.
        lo, hi = base_price * (1 - _MAX_DRIFT), base_price * (1 + _MAX_DRIFT)
        live = max(lo, min(hi, live))
        # Snap to a realistic KRX tick.
        tick = _tick_size(live)
        live = round(live / tick) * tick
        st["price"] = live

        # Volume only accumulates intraday.
        bump = (r["volume"] or 0.0) * _rng.uniform(0.0, 0.0008)
        st["volume"] = st["volume"] + bump

        change = live - prev_close
        out.append(
            {
                **r,
                "price": float(live),
                "change": round(float(change), 2),
                "change_pct": round(change / prev_close * 100.0, 2),
                "volume": round(st["volume"], 0),
            }
        )
    return out


def _base_snapshot(force: bool) -> tuple[float, list[dict]]:
    """Settled snapshot from upstream, cached for TTL_SECONDS."""
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


def live_quotes(force: bool = False) -> tuple[float, list[dict]]:
    """Return (timestamp, rows).

    The settled snapshot is cached for TTL_SECONDS to throttle upstream; in demo
    mode (settings.mock_ticks) fresh synthetic ticks are layered on every call so
    the grid keeps moving, and the timestamp is the tick time (now).
    """
    with _lock:
        base_ts, base_rows = _base_snapshot(force)
        if not get_settings().mock_ticks:
            return base_ts, base_rows
        return time.time(), _apply_ticks(base_rows)
