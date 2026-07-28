"""In-process scheduler for 급등락 원인 규명.

주기적으로 급등락 스냅샷을 새로 만들고(원인 뉴스+선택 AI), 이력에 기록한다. 같은 프로세스라
DuckDB writer를 공유한다. MOVERS=false로 끔. 주말/장외에도 가볍게 돌지만, 값이 안 바뀌면
이력은 dedupe 된다.
"""
from __future__ import annotations

import datetime as _dt

from app.data.market import market_movers
from app.data.market import movers_archive
from app.data.schedulers import runner

_state = {
    "running": False,
    "ticks": 0,
    "records": 0,
    "last_run": None,
    "last_error": None,
}


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


_sched = runner.Scheduler(
    thread_name="movers-scheduler",
    state=_state,
    tick=_tick,
    enabled=lambda s: s.movers,
    interval=lambda s: s.movers_interval,
    settle=60.0,  # let startup settle
    extra_status=lambda s: {"interval_sec": s.movers_interval, "enabled": s.movers},
)

# api/ops.py 와 main.py 는 모듈의 status()/start() 를 호출한다.
status = _sched.status
start = _sched.start
