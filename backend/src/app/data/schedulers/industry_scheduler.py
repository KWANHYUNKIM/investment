"""In-process scheduler for the industry/competition map.

Mirrors the other daemons (same process → shares the DuckDB writer). On a slow
cadence it (1) refreshes the company industry profiles from KRX-DESC if they're
missing or a new trading day has arrived, and (2) snapshots the per-industry
research feed to JSON so the competitive picture accumulates. Disable with
``INDUSTRY_MAP=false``.
"""
from __future__ import annotations

import threading
import time

from app.core.config import get_settings
from app.data.fundamentals import dart
from app.data.fundamentals import dart_financials
from app.data.fundamentals import financials
from app.data.fundamentals import finnhub
from app.data.intel import global_map
from app.data.infra import global_universe
from app.data.intel import industry
from app.data.intel import industry_research
from app.data.infra import store

_state = {
    "running": False,
    "ticks": 0,
    "profiles": 0,
    "financials": 0,
    "dart_financials": 0,
    "foreign_fin": 0,
    "snapshots": 0,
    "last_run": None,
    "last_profile_refresh": None,
    "last_financials_refresh": None,
    "last_snapshot_date": None,
    "last_error": None,
}


def status() -> dict:
    s = get_settings()
    return {
        **{k: _state[k] for k in _state},
        "interval_sec": s.industry_map_interval,
        "top_k": s.industry_top_k,
        "snapshot_n": s.industry_snapshot_n,
        "snapshot_dates": industry_research.list_dates(),
    }


def _tick() -> None:
    # 1) profiles: build once, then refresh when a new trading day lands.
    date = store.max_price_date()
    need = store.company_profile_count() == 0 or _state["last_profile_refresh"] != date
    if need:
        n = industry.refresh_profiles()
        if n:
            _state["profiles"] = n
            _state["last_profile_refresh"] = date

    # 1b) financials (기업실적분석): full sweep once per trading day. Refresh tickers
    #     missing financials first, so a fresh DB fills in fast; otherwise re-sweep
    #     everything daily to catch new 분기/연간 실적.
    fin_need = store.financials_count() == 0 or _state["last_financials_refresh"] != date
    if fin_need:
        prof = store.company_profiles()
        tickers = [str(t) for t in prof["ticker"].tolist()]
        n = financials.refresh_many(tickers)
        if n:
            _state["financials"] = store.financials_count()
            _state["last_financials_refresh"] = date
            industry.invalidate()  # 영업이익 합계가 반영되도록 그룹 캐시 무효화

    # 1c) DART 전체 재무제표: 빠진 종목을 매 틱 조금씩 채운다(틱당 상한). 일일 한도·
    #     daemon 부하를 고려해 한 번에 다 긁지 않고 점진 적재.
    if dart.enabled():
        prof = store.company_profiles()
        tickers = [str(t) for t in prof["ticker"].tolist()]
        try:
            stored = dart_financials.refresh_many(tickers, skip_existing=True, max_new=400)
            if stored:
                _state["dart_financials"] = store.dart_financials_count()
        except Exception:
            pass

    # 1d) 해외 경쟁사 펀더멘털(Finnhub): 키가 있으면 하루 1회 갱신(글로벌 경쟁지도).
    if finnhub.enabled():
        fin_date = _state.get("last_foreign_refresh")
        if store.foreign_fin_count() == 0 or fin_date != date:
            try:
                got = finnhub.refresh_many(global_universe.all_foreign_symbols())
                if got:
                    _state["foreign_fin"] = store.foreign_fin_count()
                    _state["last_foreign_refresh"] = date
                    global_map.invalidate()
            except Exception:
                pass

    # 2) research snapshot once per (trading) day.
    res = industry_research.snapshot()
    if res.get("status") == "saved":
        _state["snapshots"] += 1
        _state["last_snapshot_date"] = res.get("date")


def _loop() -> None:
    time.sleep(45)  # let startup settle (DB init + first price snapshot)
    while True:
        interval = get_settings().industry_map_interval
        try:
            _tick()
            _state["ticks"] += 1
            _state["last_run"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _state["last_error"] = None
        except Exception as e:
            _state["last_error"] = f"{type(e).__name__}: {str(e)[:120]}"
        time.sleep(interval)


def start() -> None:
    if _state["running"]:
        return
    if not get_settings().industry_map:
        return
    _state["running"] = True
    threading.Thread(target=_loop, daemon=True, name="industry-scheduler").start()
