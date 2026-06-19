"""In-process scheduler for the live, news-driven feeds (미래 성장테마 · 실시간 시황).

These feeds are otherwise computed on-demand (cache TTL) — meaning they only
refresh when someone opens the tab. This daemon keeps them **continuously**
crawled and tidy: on a slow cadence it (1) re-crawls the future-theme news +
re-maps stocks (warming the cache so a viewer always gets fresh data), (2) warms
the live-pulse + macro caches, and (3) persists one **future-theme snapshot per
trading day** so the picture of "what the era is building" accumulates over time.

Same process → shares the DuckDB writer (no lock conflict). Disable with
``GROWTH_SCHEDULER=false``.
"""
from __future__ import annotations

import threading
import time

from app.core.config import get_settings
from app.data import futuretheme, livepulse, macro, moneyflow, store

_state = {
    "running": False,
    "ticks": 0,
    "theme_refreshes": 0,
    "snapshots": 0,
    "last_run": None,
    "last_snapshot_date": None,
    "last_error": None,
}


def status() -> dict:
    s = get_settings()
    return {
        **{k: _state[k] for k in _state},
        "interval_sec": s.growth_scheduler_interval,
        "snapshot_dates": futuretheme.list_dates(),
    }


def _tick() -> None:
    # 1) 뉴스 재크롤 + 종목 재매핑으로 미래 성장테마 캐시를 데운다(force).
    futuretheme.themes(force=True)
    _state["theme_refreshes"] += 1
    # 2) 실시간 시황·매크로 캐시도 데워 둔다(다음 조회가 즉시 최신).
    try:
        livepulse.pulse(force=True)
    except Exception:
        pass
    try:
        moneyflow.pulse(force=True)  # 글로벌 자금 흐름도 상시 재크롤
    except Exception:
        pass
    try:
        macro.market_macro()
    except Exception:
        pass
    # 3) 거래일당 1회 미래 성장테마 스냅샷 저장(누적).
    res = futuretheme.snapshot()
    if res.get("status") == "saved":
        _state["snapshots"] += 1
        _state["last_snapshot_date"] = res.get("date")


def _loop() -> None:
    time.sleep(60)  # let startup settle (DB init, first price snapshot, profiles)
    while True:
        interval = get_settings().growth_scheduler_interval
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
    if not get_settings().growth_scheduler:
        return
    _state["running"] = True
    threading.Thread(target=_loop, daemon=True, name="growth-scheduler").start()
