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

import time

import pandas as pd
import FinanceDataReader as fdr

from app.core.numeric import json_float
from app.data.infra import store
from app.data.schedulers import runner

_state = {
    "running": False,
    "ticks": 0,
    "rows_written": 0,
    "last_run": None,
    "last_rows": 0,
    "last_date": None,
    "last_error": None,
}


def _board_rows(board: str, snap_date) -> tuple[list[dict], list[dict]]:
    """Return (price_rows, security_rows) for one board's current snapshot."""
    df = fdr.StockListing(board)
    price_rows: list[dict] = []
    sec_rows: list[dict] = []
    for r in df.itertuples(index=False):
        code = getattr(r, "Code", None)
        if not code:
            continue
        close = json_float(getattr(r, "Close", None))
        if close is None or close <= 0:
            continue  # suspended / no print today — skip rather than store a 0 bar
        ticker = str(code)
        price_rows.append(
            {
                "market": "KR",
                "ticker": ticker,
                "date": snap_date,
                "open": json_float(getattr(r, "Open", None)),
                "high": json_float(getattr(r, "High", None)),
                "low": json_float(getattr(r, "Low", None)),
                "close": close,
                "volume": json_float(getattr(r, "Volume", None)),
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


def _tick() -> None:
    n = _snapshot_once()
    _state["last_rows"] = n
    _state["rows_written"] += n


# settle 없음 — 시세는 기동 즉시 한 번 받아 두는 게 낫다(그래야 첫 화면이 오늘 값).
_sched = runner.Scheduler(
    thread_name="price-scheduler",
    state=_state,
    tick=_tick,
    enabled=lambda s: s.price_ingest,
    interval=lambda s: s.price_ingest_interval,
    extra_status=lambda s: {"interval_sec": s.price_ingest_interval},
)

status = _sched.status
start = _sched.start
