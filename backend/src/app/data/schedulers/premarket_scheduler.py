"""개장 예측 스케줄러 — 예측 기록·채점을 계속 반복한다.

``report_scheduler`` 와 같은 구조(프로세스 내 데몬 스레드). 매 틱마다:
  1) ``grade_all()`` — 다음 세션 개장이 나온 과거 예측들을 채점(적중/실패·이유),
  2) ``record()``   — 최신 코스피 종가 기준 오늘 예측이 없으면 새로 저장.
이렇게 하루 단위로 예측→검증이 자동 누적된다. PREMARKET_ARCHIVE=false로 끔.
"""
from __future__ import annotations

from app.data.market import premarket_archive
from app.data.schedulers import runner

_state = {
    "running": False,
    "ticks": 0,
    "records": 0,
    "graded": 0,
    "last_run": None,
    "last_status": None,
    "last_error": None,
}


def _tick() -> None:
    g = premarket_archive.grade_all()
    if g.get("graded"):
        _state["graded"] += g["graded"]
    r = premarket_archive.record()
    _state["last_status"] = r.get("status")
    if r.get("status") == "saved":
        _state["records"] += 1


_sched = runner.Scheduler(
    thread_name="premarket-scheduler",
    state=_state,
    tick=_tick,
    enabled=lambda s: s.premarket_archive,
    interval=lambda s: s.premarket_archive_interval,
    settle=45.0,  # startup(DB·첫 보드 스냅샷)이 자리잡은 뒤 시작
    extra_status=lambda s: {
        "interval_sec": s.premarket_archive_interval,
        "dates": premarket_archive.list_dates(),
    },
)

status = _sched.status
start = _sched.start
