"""In-process background scheduler that accumulates daily price bars into DuckDB.

Mirrors ``fundamentals_crawler``: runs as a daemon thread inside the API process
so it shares the single DuckDB writer connection — no lock conflicts, no second
process competing for the file lock. Each tick it pulls the whole KOSPI + KOSDAQ
board in two cheap ``fdr.StockListing`` calls and upserts today's OHLCV bar into
the ``prices`` table.

Because the ``prices`` primary key is ``(market, ticker, date)``, intraday ticks
refresh today's bar in place (no duplicates) and every new trading day appends a
fresh row — so the series accumulates forward over time on its own.

This is *not* a backfill job: historical bars are loaded once via
``scripts/ingest_fdr.py``. The scheduler only keeps the store current going
forward. Disable with ``PRICE_INGEST=false``; tune the cadence with
``PRICE_INGEST_INTERVAL`` (seconds).
"""
from __future__ import annotations

import threading
import time

import pandas as pd
import FinanceDataReader as fdr

from app.core.config import get_settings
from app.data.infra import store

_state = {
    "running": False,
    "ticks": 0,
    "rows_written": 0,
    "last_run": None,
    "last_rows": 0,
    "last_date": None,
    "last_error": None,
}


def status() -> dict:
    s = get_settings()
    return {
        "running": _state["running"],
        "ticks": _state["ticks"],
        "rows_written": _state["rows_written"],
        "last_run": _state["last_run"],
        "last_rows": _state["last_rows"],
        "last_date": _state["last_date"],
        "last_error": _state["last_error"],
        "interval_sec": s.price_ingest_interval,
    }


def _num(v) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        return None if f != f else f  # drop NaN
    except (TypeError, ValueError):
        return None


def _board_rows(board: str, snap_date) -> tuple[list[dict], list[dict]]:
    """Return (price_rows, security_rows) for one board's current snapshot."""
    df = fdr.StockListing(board)
    price_rows: list[dict] = []
    sec_rows: list[dict] = []
    for r in df.itertuples(index=False):
        code = getattr(r, "Code", None)
        if not code:
            continue
        close = _num(getattr(r, "Close", None))
        if close is None or close <= 0:
            continue  # suspended / no print today — skip rather than store a 0 bar
        ticker = str(code)
        price_rows.append(
            {
                "market": "KR",
                "ticker": ticker,
                "date": snap_date,
                "open": _num(getattr(r, "Open", None)),
                "high": _num(getattr(r, "High", None)),
                "low": _num(getattr(r, "Low", None)),
                "close": close,
                "volume": _num(getattr(r, "Volume", None)),
            }
        )
        sec_rows.append(
            {
                "market": "KR",
                "ticker": ticker,
                "name": getattr(r, "Name", None),
                "sector": board,
            }
        )
    return price_rows, sec_rows


def _snapshot_once() -> int:
    """One full board snapshot → upsert into DuckDB. Returns rows written.

    Skips weekends: the board snapshot still serves the last settled close on
    Sat/Sun, and stamping that with the weekend date would inject phantom bars
    for non-trading days into the series.
    """
    lt = time.localtime()
    if lt.tm_wday >= 5:  # 5=Sat, 6=Sun
        return 0
    snap_date = time.strftime("%Y-%m-%d", lt)

    prices: list[dict] = []
    secs: list[dict] = []
    for board in ("KOSPI", "KOSDAQ"):
        p, s = _board_rows(board, snap_date)
        prices.extend(p)
        secs.extend(s)

    if not prices:
        return 0

    # Keep the universe table fresh, then write today's bars.
    store.upsert_securities(pd.DataFrame(secs))
    n = store.upsert_prices(pd.DataFrame(prices))
    _state["last_date"] = snap_date
    return n


def _loop() -> None:
    while True:
        interval = get_settings().price_ingest_interval
        try:
            n = _snapshot_once()
            _state["ticks"] += 1
            _state["last_rows"] = n
            _state["rows_written"] += n
            _state["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _state["last_error"] = None
        except Exception as e:  # upstream hiccup — keep the loop alive
            _state["last_error"] = f"{type(e).__name__}: {str(e)[:120]}"
        time.sleep(interval)


def start() -> None:
    """Launch the scheduler thread once, if enabled in settings."""
    if _state["running"]:
        return
    if not get_settings().price_ingest:
        return
    _state["running"] = True
    threading.Thread(target=_loop, daemon=True, name="price-scheduler").start()
