"""인구이동 수집 — 안 받은 (달 × 시도쌍) 을 예산껏 채운다.

한 달치가 시도쌍 289개고 쌍마다 페이지가 붙어서, 12개월을 다 채우는 데 만 콜 가까이
든다. 한 번에 못 받으니 조금씩 밀고, 이미 받은 구간은 ``migration_batch`` 로 건너뛴다.

원본이 **매월 2일**에 전달치를 올린다. 다 채운 뒤에는 새 달이 열릴 때만 일이 생기므로
대부분의 회차는 '받을 구간 없음' 으로 즉시 끝난다.

MIGRATION=false 로 끈다.
"""
from __future__ import annotations

from app.data.schedulers import runner

_state = {
    "running": False,
    "ticks": 0,
    "pairs": 0,
    "rows": 0,
    "gaps": None,
    "last_run": None,
    "skipped_reason": None,
    "last_error": None,
}


def _tick() -> None:
    from app.data.macro import migration

    if not migration.configured():
        _state["skipped_reason"] = "DATA_GO_KR_KEY 미설정"
        return
    _state["skipped_reason"] = None

    res = migration.refresh()
    _state["pairs"] += res.get("pairs", 0)
    _state["rows"] += res.get("rows", 0)
    _state["gaps"] = res.get("gaps")


def _extra_status(s) -> dict:
    from app.data.macro import migration
    return {
        "enabled": s.migration,
        "budget": s.migration_budget,
        "months": s.migration_months,
        "interval_min": round(s.migration_interval / 60),
        "coverage": migration.coverage(),
    }


_sched = runner.Scheduler(
    thread_name="migration-scheduler",
    state=_state,
    tick=_tick,
    enabled=lambda s: s.migration,
    interval=lambda s: s.migration_interval,
    # 상권 수집(420s)보다 더 뒤로. 기동 직후에 무거운 수집이 겹치지 않게 한다.
    settle=540.0,
    extra_status=_extra_status,
)

status = _sched.status
start = _sched.start
