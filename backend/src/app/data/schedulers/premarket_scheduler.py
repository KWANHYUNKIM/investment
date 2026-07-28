"""개장 예측 스케줄러 — 예측 기록·채점을 계속 반복한다.

``report_scheduler`` 와 같은 구조(프로세스 내 데몬 스레드). 매 틱마다:
  1) ``grade_all()`` — 다음 세션 개장이 나온 과거 예측들을 채점(적중/실패·이유),
  2) ``record()``   — 최신 코스피 종가 기준 오늘 예측이 없으면 새로 저장.
이렇게 하루 단위로 예측→검증이 자동 누적된다. PREMARKET_ARCHIVE=false로 끔.
"""
from __future__ import annotations

import threading
import time

from app.core.config import get_settings
from app.data.market import premarket_archive

_state = {
    "running": False,
    "ticks": 0,
    "records": 0,
    "graded": 0,
    "last_run": None,
    "last_status": None,
    "last_error": None,
}


def status() -> dict:
    s = get_settings()
    return {
        **{k: _state[k] for k in _state},
        "interval_sec": s.premarket_archive_interval,
        "dates": premarket_archive.list_dates(),
    }


def _tick() -> None:
    g = premarket_archive.grade_all()
    if g.get("graded"):
        _state["graded"] += g["graded"]
    r = premarket_archive.record()
    _state["last_status"] = r.get("status")
    if r.get("status") == "saved":
        _state["records"] += 1


def _loop() -> None:
    time.sleep(45)  # startup(DB·첫 보드 스냅샷)이 자리잡은 뒤 시작
    while True:
        interval = get_settings().premarket_archive_interval
        try:
            _tick()
            _state["ticks"] += 1
            _state["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _state["last_error"] = None
        except Exception as e:  # 업스트림(fdr) 흔들려도 루프는 살려둔다
            _state["last_error"] = f"{type(e).__name__}: {str(e)[:120]}"
        time.sleep(interval)


def start() -> None:
    if _state["running"]:
        return
    if not get_settings().premarket_archive:
        return
    _state["running"] = True
    threading.Thread(target=_loop, daemon=True, name="premarket-scheduler").start()
