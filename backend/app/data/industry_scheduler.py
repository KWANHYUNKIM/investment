"""In-process scheduler for the industry/competition map.

Mirrors the other daemons (same process → shares the DuckDB writer). On a slow
cadence it (1) refreshes the company industry profiles from KRX-DESC if they're
missing or a new trading day has arrived, and (2) snapshots the per-industry
research feed to JSON so the competitive picture accumulates. Disable with
``INDUSTRY_MAP=false``.
"""
from __future__ import annotations

import threading
import time

from app.core.config import get_settings
from app.data import industry, industry_research, store

_state = {
    "running": False,
    "ticks": 0,
    "profiles": 0,
    "snapshots": 0,
    "last_run": None,
    "last_profile_refresh": None,
    "last_snapshot_date": None,
    "last_error": None,
}


def status() -> dict:
    s = get_settings()
    return {
        **{k: _state[k] for k in _state},
        "interval_sec": s.industry_map_interval,
        "top_k": s.industry_top_k,
        "snapshot_n": s.industry_snapshot_n,
        "snapshot_dates": industry_research.list_dates(),
    }


def _tick() -> None:
    # 1) profiles: build once, then refresh when a new trading day lands.
    date = store.max_price_date()
    need = store.company_profile_count() == 0 or _state["last_profile_refresh"] != date
    if need:
        n = industry.refresh_profiles()
        if n:
            _state["profiles"] = n
            _state["last_profile_refresh"] = date

    # 2) research snapshot once per (trading) day.
    res = industry_research.snapshot()
    if res.get("status") == "saved":
        _state["snapshots"] += 1
        _state["last_snapshot_date"] = res.get("date")


def _loop() -> None:
    time.sleep(45)  # let startup settle (DB init + first price snapshot)
    while True:
        interval = get_settings().industry_map_interval
        try:
            _tick()
            _state["ticks"] += 1
            _state["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _state["last_error"] = None
        except Exception as e:
            _state["last_error"] = f"{type(e).__name__}: {str(e)[:120]}"
        time.sleep(interval)


def start() -> None:
    if _state["running"]:
        return
    if not get_settings().industry_map:
        return
    _state["running"] = True
    threading.Thread(target=_loop, daemon=True, name="industry-scheduler").start()
