"""원가모델 전 종목 배치 스케줄러 (I1) — 매일 야간 1회.

다른 스케줄러들이 "N초마다"인 것과 달리 이건 **하루 한 번 정해진 시각**에 돈다
(기본 03:30). 전 종목 ``analyze`` 는 회사마다 DART 사업보고서 파싱이 붙어 무겁기
때문에, 장중에 돌리면 사용자 조회와 rate limit 을 놓고 다툰다.

동작: ``costmodel_batch_check_interval`` 마다 깨어나 "오늘 몫을 아직 안 돌렸고
지금이 실행시각을 지났는가"만 보고, 맞으면 ``company_costmodel.build_batch()``.
서버가 그 시각에 꺼져 있었다면 켜진 뒤 첫 점검에서 그날 몫을 따라잡는다.
COSTMODEL_BATCH=false 로 끔.
"""
from __future__ import annotations

import threading
import time

from app.core.config import get_settings
from app.data.fundamentals import company_costmodel

_state = {
    "running": False,
    "ticks": 0,
    "builds": 0,
    "last_run": None,
    "last_build_date": None,
    "last_summary": None,
    "last_error": None,
}


def status() -> dict:
    s = get_settings()
    return {
        **{k: _state[k] for k in _state},
        "schedule": "%02d:%02d 매일" % (s.costmodel_batch_hour, s.costmodel_batch_minute),
        "sleep_per_ticker_sec": s.costmodel_batch_sleep,
        "file": company_costmodel.batch_status(),
    }


def _due(now: time.struct_time, last_date: str | None) -> bool:
    """오늘 아직 안 돌렸고, 지금이 예정 시각을 지났으면 True."""
    s = get_settings()
    today = time.strftime("%Y-%m-%d", now)
    if last_date == today:
        return False
    return (now.tm_hour, now.tm_min) >= (s.costmodel_batch_hour, s.costmodel_batch_minute)


def _tick() -> None:
    now = time.localtime()
    if not _due(now, _state["last_build_date"]):
        return
    summary = company_costmodel.build_batch()
    _state["builds"] += 1
    _state["last_build_date"] = time.strftime("%Y-%m-%d", now)
    _state["last_summary"] = summary


def _loop() -> None:
    time.sleep(90)  # startup(DB·프로필 초기화)이 자리잡은 뒤 시작
    # 파일이 이미 있으면 그 날짜를 '마지막 실행'으로 삼아 재시작 때 중복 실행을 막는다.
    b = company_costmodel.batch_status()
    if b.get("available") and b.get("built_at"):
        _state["last_build_date"] = b["built_at"][:10]
    while True:
        try:
            _tick()
            _state["ticks"] += 1
            _state["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _state["last_error"] = None
        except Exception as e:  # DART/DuckDB 가 흔들려도 루프는 살려둔다
            _state["last_error"] = f"{type(e).__name__}: {str(e)[:120]}"
        time.sleep(get_settings().costmodel_batch_check_interval)


def start() -> None:
    if _state["running"]:
        return
    if not get_settings().costmodel_batch:
        return
    _state["running"] = True
    threading.Thread(target=_loop, daemon=True, name="costmodel-scheduler").start()
