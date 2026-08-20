"""시군구 월별 집계를 예산껏 이어 받는 스케줄러.

24개월 × 250 시군구 × 3개 거래유형 = 18,000칸인데 data.go.kr 개발계정은 **하루
1,000건**이다. 한 번에 받으려 들면 429 가 나고, 그날 남은 다른 기능(지도·전월세)까지
같이 막힌다. 그래서 한 시간에 250칸씩 이어 받는다 — 며칠 걸려 다 차고, 그 뒤로는
새 달 하나씩만 받으므로 부담이 사라진다.

지난 달 값은 다시 바뀌지 않아 한 번 받으면 끝이다. 최근 두 달만 신고 기한(계약 후
30일)이 남아 계속 자라므로 그 구간만 다시 받는다.

REALESTATE_STATS=false 로 끄고, REALESTATE_STATS_BUDGET 으로 한 회차 분량을 조절한다.
"""
from __future__ import annotations

from app.core.config import get_settings
from app.data.schedulers import runner

_state = {
    "running": False,
    "ticks": 0,
    "filled": 0,          # 지금까지 채운 칸 수(누적)
    "remaining": None,    # 남은 칸 수
    "last_run": None,
    "skipped_reason": None,
    "last_error": None,
}


def _tick() -> None:
    from app.data.macro import region_stats

    if not get_settings().data_go_kr_key:
        _state["skipped_reason"] = "DATA_GO_KR_KEY 미설정"
        return
    _state["skipped_reason"] = None

    res = region_stats.refresh()
    _state["filled"] += res.get("filled", 0)
    _state["remaining"] = res.get("remaining")


def _extra_status(s) -> dict:
    from app.data.macro import region_stats
    return {
        "enabled": s.realestate_stats,
        "months": s.realestate_stats_months,
        "budget": s.realestate_stats_budget,
        "interval_min": round(s.realestate_stats_interval / 60),
        "coverage": region_stats.coverage(),
    }


_sched = runner.Scheduler(
    thread_name="region-stats-scheduler",
    state=_state,
    tick=_tick,
    enabled=lambda s: s.realestate_stats,
    interval=lambda s: s.realestate_stats_interval,
    # 지도 워밍(실거래 250콜)과 겹치면 둘 다 한도를 다투게 된다. 뒤로 물려 시작한다.
    settle=300.0,
    extra_status=_extra_status,
)

status = _sched.status
start = _sched.start
