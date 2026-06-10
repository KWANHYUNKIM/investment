"""In-process background crawler for fundamentals.

Runs inside the API process (a daemon thread), so it shares the single DuckDB
writer connection — no lock conflicts, no downtime. Each tick it crawls the next
round-robin batch of tickers from Naver and stores a snapshot ONLY when values
changed vs the ticker's latest stored row, so a change-history accumulates over
time without duplicates.
"""
from __future__ import annotations

import threading
import time

import pandas as pd

from app.data import investor, store
from app.data.loaders import naver

BATCH = 12          # tickers refreshed per tick
INTERVAL = 25.0     # seconds between ticks  (~full sweep in ~90 min for 2.7k)

_state = {
    "running": False,
    "idx": 0,
    "tickers": [],
    "sweeps": 0,
    "checked": 0,
    "changed": 0,
    "last_run": None,
    "last_changed_at": None,
}


def status() -> dict:
    return {
        "running": _state["running"],
        "universe": len(_state["tickers"]),
        "checked": _state["checked"],
        "changed_rows": _state["changed"],
        "sweeps": _state["sweeps"],
        "last_run": _state["last_run"],
        "batch": BATCH,
        "interval_sec": INTERVAL,
    }


def _loop() -> None:
    while True:
        try:
            if not _state["tickers"]:
                secs = store.list_securities("KR")
                _state["tickers"] = secs["ticker"].tolist()

            tks = _state["tickers"]
            if tks:
                i = _state["idx"] % len(tks)
                batch = tks[i : i + BATCH]
                _state["idx"] = i + BATCH
                if _state["idx"] >= len(tks):
                    _state["idx"] = 0
                    _state["sweeps"] += 1

                rows = []
                for t in batch:
                    # 1) fundamentals snapshot (store only if changed)
                    try:
                        df = naver.fetch_fundamentals(t)
                        if not df.empty:
                            rows.append(df.iloc[0])
                    except Exception:
                        pass
                    # 2) daily investor net-buy — accumulate to DB (dedup by date)
                    try:
                        inv = investor.investors(t)
                        if inv:
                            store.upsert_investor_flow(
                                pd.DataFrame(
                                    [
                                        {
                                            "market": "KR",
                                            "ticker": t,
                                            "date": pd.to_datetime(r["date"]).date(),
                                            "individual": r.get("individual"),
                                            "foreigner": r.get("foreign"),
                                            "organ": r.get("organ"),
                                            "foreign_ratio": r.get("foreign_ratio"),
                                        }
                                        for r in inv
                                        if r.get("date")
                                    ]
                                )
                            )
                    except Exception:
                        pass
                    _state["checked"] += 1
                    time.sleep(0.05)

                if rows:
                    n = store.upsert_fundamentals_if_changed(pd.DataFrame(rows))
                    if n:
                        _state["changed"] += n
                        _state["last_changed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                _state["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
        time.sleep(INTERVAL)


def start() -> None:
    if _state["running"]:
        return
    _state["running"] = True
    threading.Thread(target=_loop, daemon=True, name="fund-crawler").start()
