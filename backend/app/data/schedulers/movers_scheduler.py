"""In-process scheduler for 급등락 원인 규명.

주기적으로 급등락 스냅샷을 새로 만들고(원인 뉴스+선택 AI), 이력에 기록한다. 같은 프로세스라
DuckDB writer를 공유한다. MOVERS=false로 끔. 주말/장외에도 가볍게 돌지만, 값이 안 바뀌면
이력은 dedupe 된다.
"""
from __future__ import annotations

import datetime as _dt
import threading
import time

from app.core.config import get_settings
from app.data.market import market_movers
from app.data.market import movers_archive

_state = {
    "running": False,
    "ticks": 0,
    "records": 0,
    "last_run": None,
    "last_error": None,
}


def status() -> dict:
    s = get_settings()
    return {**{k: _state[k] for k in _state}, "interval_sec": s.movers_interval, "enabled": s.movers}


def _is_market_window() -> bool:
    # 한국장(평일 08:30~16:30 KST) 근처에서만 기록해 불필요한 호출을 줄인다.
    now = _dt.datetime.utcnow() + _dt.timedelta(hours=9)  # KST
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return 8 * 60 + 30 <= minutes <= 16 * 60 + 30


def _tick() -> None:
    if not _is_market_window():
        return
    snap = market_movers.snapshot(force=True)
    movers_archive.record(snap)
    _state["records"] += 1


def _loop() -> None:
    time.sleep(60)  # let startup settle
    while True:
        interval = get_settings().movers_interval
        try:
            _tick()
            _state["ticks"] += 1
            _state["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _state["last_error"] = None
        except Exception as e:  # noqa: BLE001
            _state["last_error"] = f"{type(e).__name__}: {str(e)[:120]}"
        time.sleep(interval)


def start() -> None:
    if _state["running"]:
        return
    if not get_settings().movers:
        return
    _state["running"] = True
    threading.Thread(target=_loop, daemon=True, name="movers-scheduler").start()
