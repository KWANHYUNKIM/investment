"""In-process background scheduler that pre-warms the 부동산 실거래 지도.

The map endpoint already serves stale-while-revalidate: it returns whatever is in
the disk cache instantly and kicks a background refresh when stale. The only slow
moment is the *first* fill — collecting ~250 국토부 실거래 calls (rate-limited, with
429 backoff) plus OSM geocoding (throttled ~1.1s/call). If that happens the moment
a user first opens the tab, they stare at "수집 중…" for a while.

This scheduler moves that cost *before* the user arrives: on startup (and every
few hours after) it fills the transaction cache and the sigungu geocode cache in a
daemon thread. Then opening the tab renders from cache immediately — no Elastic-
search or extra infra needed; the bottleneck was ingestion, not query.

Requires ``DATA_GO_KR_KEY`` (공공데이터포털 아파트 실거래가 API). Without it there is
nothing to fetch and the scheduler idles. Disable with ``REALESTATE_WARM=false``;
tune cadence with ``REALESTATE_WARM_INTERVAL`` (seconds).
"""
from __future__ import annotations

from app.core.config import get_settings
from app.data.macro import realestate_map
from app.data.schedulers import runner

_state = {
    "running": False,
    "ticks": 0,
    "last_run": None,
    "last_regions": 0,
    "last_error": None,
}


def _tick() -> None:
    """One warm cycle: geocode cache first (so coords resolve), then transactions."""
    if not get_settings().data_go_kr_key:
        _state["last_error"] = "DATA_GO_KR_KEY 미설정 — backend/.env 에 실거래 API 키를 넣으세요."
        return
    # 좌표 캐시(시군구) — 이미 채워졌으면 즉시 반환(빠짐없이 캐시 재사용)
    realestate_map.warm_geocode()
    # 국토부 실거래(최신 완성월) 수집 → map_latest.json 갱신 (blocking)
    realestate_map.map_warm()
    cache = realestate_map._load_map() or {}
    _state["last_regions"] = len(cache.get("regions", []))
    _state["last_error"] = None


# settle 없음 — 첫 채우기가 느려서(실거래 ~250콜 + 지오코딩) 기동 즉시 시작한다.
# 키가 없으면 _tick 이 last_error 에 사유를 써 넣고 빠진다(러너가 틱 시작에만 비우므로 남는다).
_sched = runner.Scheduler(
    thread_name="realestate-scheduler",
    state=_state,
    tick=_tick,
    enabled=lambda s: s.realestate_warm,
    interval=lambda s: s.realestate_warm_interval,
    extra_status=lambda s: {
        "interval_sec": s.realestate_warm_interval,
        "has_key": bool(s.data_go_kr_key),
    },
)

status = _sched.status
start = _sched.start
