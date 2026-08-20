"""지역 상권 수집 — 빈 칸만 예산껏 채운다.

시군구 250 × 업종 10 = 2,500칸인데, 원본(소상공인 상가정보)이 **분기 갱신**이라
한 번 받으면 한동안 유효하다. 실거래 집계처럼 최근 구간을 되받을 이유가 없어서
'없는 칸' 만 채우고 끝낸다.

같은 data.go.kr 한도를 실거래 집계와 나눠 쓰므로 예산을 작게 잡았다. 다 차면 이
스케줄러는 아무것도 하지 않는다.

COMMERCE=false 로 끈다.
"""
from __future__ import annotations

from app.core.config import get_settings
from app.data.schedulers import runner

_state = {
    "running": False,
    "ticks": 0,
    "filled": 0,
    "gaps": None,
    "last_run": None,
    "skipped_reason": None,
    "last_error": None,
}


def _tick() -> None:
    from app.data.macro import commerce

    if not commerce.configured():
        _state["skipped_reason"] = "DATA_GO_KR_KEY 미설정"
        return
    _state["skipped_reason"] = None

    res = commerce.refresh()
    _state["filled"] += res.get("filled", 0)
    _state["gaps"] = res.get("gaps")


def _extra_status(s) -> dict:
    from app.data.macro import commerce
    return {
        "enabled": s.commerce,
        "budget": s.commerce_budget,
        "interval_min": round(s.commerce_interval / 60),
        "coverage": commerce.coverage(),
    }


_sched = runner.Scheduler(
    thread_name="commerce-scheduler",
    state=_state,
    tick=_tick,
    enabled=lambda s: s.commerce,
    interval=lambda s: s.commerce_interval,
    # 실거래 집계·지도 워밍과 한도를 다투지 않게 가장 뒤로 물린다.
    settle=420.0,
    extra_status=_extra_status,
)

status = _sched.status
start = _sched.start
