"""관리종목·상폐 스크리너 데이터 배치 (매일 야간 1회, 기본 04:10).

이 스크리너는 세 가지 외부 데이터에 의존하는데, 지금까지 그걸 채우는 배치가
어디에도 걸려 있지 않았다. 그래서 ``data/market_class.json`` 이 없으면 시장 구분
자체를 몰라 **매출·영업손실·법인세 요건이 통째로 적용되지 않는** 상태로 돌아간다.
이 데몬이 그 구멍을 메운다.

  ① 시장구분·소속부(FinanceDataReader 상장목록)
  ② 위험종목의 DART 공시 스캔(감사의견·불성실공시·거래정지 …)
  ③ 위험종목의 반기 자본계정(코스닥 자본잠식은 "사업연도(반기)말" 기준)

원가모델 배치(03:30) 다음에 돌도록 04:10 을 기본값으로 둔다. DELISTING_BATCH=false 로 끔.
"""
from __future__ import annotations

import time

from app.core.config import get_settings
from app.data.market import delisting
from app.data.schedulers import runner

_state = {
    "running": False,
    "ticks": 0,
    "runs": 0,
    "last_run": None,
    "last_build_date": None,
    "last_summary": None,
    "last_error": None,
}


def _due(now: time.struct_time, last_date: str | None) -> bool:
    s = get_settings()
    if last_date == time.strftime("%Y-%m-%d", now):
        return False
    return (now.tm_hour, now.tm_min) >= (s.delisting_batch_hour, s.delisting_batch_minute)


def _tick() -> None:
    now = time.localtime()
    if not _due(now, _state["last_build_date"]):
        return
    _state["last_summary"] = delisting.refresh_all()
    _state["runs"] += 1
    _state["last_build_date"] = time.strftime("%Y-%m-%d", now)


def _first_fill_if_empty() -> None:
    """시장구분 캐시가 아예 없으면(첫 기동) 시각을 기다리지 않고 한 번 채운다 —
    없는 동안엔 스크리너가 요건 절반을 못 보기 때문."""
    if delisting.load_market_class():
        return
    try:
        _state["last_summary"] = delisting.refresh_all()
        _state["runs"] += 1
        _state["last_build_date"] = time.strftime("%Y-%m-%d")
    except Exception as e:  # noqa: BLE001
        _state["last_error"] = f"{type(e).__name__}: {str(e)[:120]}"


def _extra_status(s) -> dict:
    board = delisting.board()
    return {
        "schedule": "%02d:%02d 매일" % (s.delisting_batch_hour, s.delisting_batch_minute),
        "market_class_ready": board.get("market_class_ready"),
        "half_ready": board.get("half_ready"),
        "market_stats_ready": board.get("market_stats_ready"),
        "alerts_generated_at": board.get("alerts_generated_at"),
    }


_sched = runner.Scheduler(
    thread_name="delisting-scheduler",
    state=_state,
    tick=_tick,
    enabled=lambda s: s.delisting_batch,
    interval=lambda s: s.delisting_batch_check_interval,
    settle=120.0,  # 원가모델 배치·DB 초기화가 자리잡은 뒤
    before_loop=_first_fill_if_empty,
    extra_status=_extra_status,
)

status = _sched.status
start = _sched.start
