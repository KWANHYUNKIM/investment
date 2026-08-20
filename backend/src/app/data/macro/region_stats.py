"""시군구 × 월 × 거래유형 집계를 **한 번만 받아 쌓아 두는** 저장소.

왜 따로 쌓는가
--------------
지역 추이를 길게 보려면 개월 수만큼 호출이 늘어난다. 24개월 × 250 시군구 × 3개
거래유형이면 18,000콜인데, data.go.kr **개발계정은 하루 1,000건**이다. 매번 새로
받는 구조로는 애초에 불가능하고, 실제로 이 프로젝트는 이미 429(한도초과)를 맞은 적이
있다.

풀리는 지점은 **지난 달은 다시 바뀌지 않는다**는 것이다. 한 번 받아 두면 그 칸은
영원히 유효하므로, 없는 칸만 골라 예산 안에서 조금씩 채우면 며칠에 걸쳐 24개월이
완성되고 그 뒤로는 새 달 하나씩만 받으면 된다.

예외가 최근 두 달이다. 실거래 신고 기한이 계약 후 30일이라 그 구간은 계속 늘어난다.
그래서 최근 두 달만 만료로 보고 다시 받는다 — 이걸 안 하면 이번 달 막대가 영원히
낮게 남는다.

평형은 공짜로 딸려 온다
-----------------------
집계용 API(``_fetch_one``)는 건수·금액만 주지만, 계약 목록 API(``month_deals``)는
**같은 호출 수로** 면적까지 준다. 그래서 목록으로 받아 여기서 평형을 나눈다.
호출을 한 번도 더 쓰지 않고 평형별 시계열이 생긴다.
"""
from __future__ import annotations

import threading
import time

from app.core.config import get_settings
from app.core.jsonstore import read_json, write_json
from app.data.infra.lawd_codes import SIGUNGU

_lock = threading.Lock()

TRADES = ("sale", "jeonse", "wolse")

# 전용면적 구간. 국민주택 규모(85㎡)와 청약·세제가 갈리는 60㎡ 를 경계로 삼는다 —
# 임의로 자르면 '어느 평형이 움직이나' 가 시장의 실제 구획과 어긋난다.
AREA_BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("~40",     0.0,   40.0),
    ("40~60",   40.0,  60.0),
    ("60~85",   60.0,  85.0),     # 국민주택 규모
    ("85~135",  85.0,  135.0),
    ("135~",    135.0, 1e9),
)

_state = {"running": False, "fetched": 0, "filled": 0, "last_run": None, "msg": ""}


def _path() -> str:
    return str(get_settings().data_dir / "realestate_region_stats.json")


def load() -> dict:
    return read_json(_path(), {"updated": None, "cells": {}})


def _save(d: dict) -> None:
    d["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    write_json(_path(), d)


def _key(lawd: str, ym: str, trade: str) -> str:
    return f"{lawd}|{ym}|{trade}"


# --- 기간 -------------------------------------------------------------------
def months_back(n: int) -> list[str]:
    """오래된 달부터 이번 달까지 ``YYYYMM``."""
    now = time.localtime()
    y, m = now.tm_year, now.tm_mon
    out = []
    for i in range(n - 1, -1, -1):
        yy, mm = divmod((y * 12 + (m - 1)) - i, 12)
        out.append(f"{yy:04d}{mm + 1:02d}")
    return out


def _stale_months() -> set[str]:
    """다시 받아야 하는 달 — 신고 기한이 남아 아직 자라는 구간."""
    return set(months_back(2))


# --- 한 칸 채우기 -----------------------------------------------------------
def _bucket(area: float | None) -> str | None:
    if area is None:
        return None
    for label, lo, hi in AREA_BUCKETS:
        if lo <= area < hi:
            return label
    return None


def _agg(deals: list[dict], trade: str) -> dict:
    """계약 목록 → 그 달의 집계 + 평형별 집계.

    금액의 뜻이 거래유형마다 다르다: 매매는 거래가, 전세는 보증금, 월세는 보증금과
    월세가 따로다. 하나로 뭉개면 평균이 무의미해지므로 월세는 둘 다 남긴다.
    """
    def price(d: dict) -> float | None:
        if trade == "sale":
            return d.get("amount_eok")
        return d.get("deposit_eok")          # 전세·월세 모두 보증금

    total = {"count": 0, "sum": 0.0, "rent_sum": 0.0, "rent_n": 0}
    by_area: dict[str, dict] = {}

    for d in deals:
        p = price(d)
        if p is None:
            continue
        total["count"] += 1
        total["sum"] += p
        if trade == "wolse":
            total["rent_sum"] += float(d.get("monthly_manwon") or 0)
            total["rent_n"] += 1
        b = _bucket(d.get("area"))
        if b:
            row = by_area.setdefault(b, {"count": 0, "sum": 0.0})
            row["count"] += 1
            row["sum"] += p

    return {
        "count": total["count"],
        "amount_eok": round(total["sum"], 1),
        "avg_eok": round(total["sum"] / total["count"], 2) if total["count"] else None,
        "avg_rent_manwon": (round(total["rent_sum"] / total["rent_n"])
                            if trade == "wolse" and total["rent_n"] else None),
        "by_area": {b: {"count": v["count"],
                        "avg_eok": round(v["sum"] / v["count"], 2) if v["count"] else None}
                    for b, v in sorted(by_area.items())},
    }


def fetch_cell(lawd: str, ym: str, trade: str,
               memo: dict | None = None) -> dict | None:
    """한 시군구·한 달·한 거래유형. 실패하면 ``None`` — 0 으로 적으면 '거래 없음'과 섞인다.

    ``memo``: 전월세 응답을 회차 안에서 재사용하는 자리. **전세와 월세는 같은 API 가
    한 번에 돌려주는 같은 응답**이라, 따로 부르면 호출이 그대로 두 배가 된다
    (18,000 vs 12,000). 한도가 하루 1,000건인 상황에서 이 차이는 6일이다.
    """
    from app.data.macro import realestate, rent

    if trade == "sale":
        deals, ok = realestate.month_deals(lawd, ym)
    else:
        key = (lawd, ym)
        if memo is not None and key in memo:
            deals, ok = memo[key]
        else:
            deals, ok = rent.month_deals(lawd, ym)
            if memo is not None:
                memo[key] = (deals, ok)
        want = "전세" if trade == "jeonse" else "월세"
        deals = [d for d in deals if d.get("rent_type") == want]
    if not ok:
        return None
    return _agg(deals, trade)


# --- 채우기(예산제) ---------------------------------------------------------
def _due(cells: dict, months: int, trades: tuple[str, ...]) -> tuple[list, list]:
    """(아직 없는 칸, 다시 받을 때가 된 칸).

    둘을 가르는 이유가 이 모듈의 핵심이다. 최근 두 달은 신고가 계속 들어와 값이 자라니
    다시 받아야 하는데, 그 대상이 250곳 × 2달 × 3유형 = **1,500칸**이다. 이걸 '없는 칸'
    과 같은 줄에 세우면 예산이 매번 거기서 다 타 버리고 과거 구간은 영영 안 채워진다
    (처음 구현이 실제로 그랬다 — 120칸을 채웠는데 남은 칸이 그대로 18,000이었다).

    그래서 갱신은 **순번제**로 돌린다. 오래 안 본 칸부터 조금씩 다시 받으면 최근 달
    숫자가 며칠 안에 한 바퀴 갱신되고, 남은 예산은 과거를 채우는 데 쓸 수 있다.
    """
    s = get_settings()
    stale_months = _stale_months()
    cutoff = time.time() - s.realestate_stats_stale_hours * 3600
    gaps, refresh_due = [], []

    for ym in reversed(months_back(months)):        # 최신 달 우선 — 화면이 먼저 채워진다
        for lawd, _sido, _name in SIGUNGU:
            for t in trades:
                cell = cells.get(_key(lawd, ym, t))
                if cell is None:
                    gaps.append((lawd, ym, t))
                elif ym in stale_months and float(cell.get("at") or 0) < cutoff:
                    refresh_due.append((float(cell.get("at") or 0), (lawd, ym, t)))

    refresh_due.sort(key=lambda x: x[0])            # 오래 안 본 것부터
    return gaps, [c for _at, c in refresh_due]


def missing(months: int, trades: tuple[str, ...] = TRADES) -> list[tuple[str, str, str]]:
    """아직 한 번도 못 받은 칸(진행률의 분자로 쓴다)."""
    return _due(load()["cells"], months, trades)[0]


def refresh(budget: int | None = None, months: int | None = None,
            trades: tuple[str, ...] = TRADES) -> dict:
    """예산만큼만 채운다. 나머지는 다음 틱에서 이어 받는다.

    한 번에 다 받으려 들면 data.go.kr 일일 한도(개발계정 1,000건)를 넘겨 429 가 나고,
    그날 남은 다른 기능(지도·전월세)까지 같이 죽는다.

    예산의 일부는 최근 달 갱신에 떼어 둔다 — 전부 과거 채우기에 쓰면 이번 달 숫자가
    신고분을 못 따라가고, 전부 갱신에 쓰면 과거가 안 채워진다.
    """
    s = get_settings()
    budget = int(budget or s.realestate_stats_budget)
    months = int(months or s.realestate_stats_months)

    d = load()
    gaps, due = _due(d["cells"], months, trades)

    quota_refresh = max(1, budget // 4)             # 1/4 은 최근 달 갱신 몫
    todo = due[:quota_refresh] + gaps[:budget - min(len(due), quota_refresh)]
    if not todo:
        _state["msg"] = "채울 칸 없음 — 최신 상태"
        return {"fetched": 0, "filled": 0, "gaps": len(gaps), "note": _state["msg"]}

    cells = d["cells"]
    filled = failed = 0
    stopped = False
    # 전세·월세가 같은 응답을 쓰도록 회차 안에서만 기억한다(회차가 끝나면 버린다 —
    # 오래 들고 있으면 신고분이 반영되지 않은 옛 응답을 재사용하게 된다).
    memo: dict = {}
    for lawd, ym, trade in todo:
        got = fetch_cell(lawd, ym, trade, memo)
        if got is None:
            failed += 1
            # 연속 실패는 대개 429 다 — 계속 두드리면 다음 날까지 막힌다.
            if failed >= 20:
                _state["msg"] = "data.go.kr 연속 실패(한도 초과 추정) — 이번 회차 중단"
                stopped = True
                break
            continue
        failed = 0
        cells[_key(lawd, ym, trade)] = {**got, "at": round(time.time())}
        filled += 1

    with _lock:
        _save(d)

    remaining = max(0, len(gaps) - filled)
    _state.update({"fetched": len(todo), "filled": filled,
                   "last_run": time.strftime("%Y-%m-%d %H:%M:%S")})
    if not stopped:
        _state["msg"] = f"{filled}칸 채움 · 미수집 {remaining}칸"
    # 실제 HTTP 호출 수 = 매매 칸 + (전월세는 (lawd,ym) 당 한 번)
    http_calls = sum(1 for _l, _y, t in todo if t == "sale") + len(memo)
    return {"fetched": len(todo), "filled": filled, "gaps": remaining,
            "http_calls": http_calls,
            "refreshed": min(len(due), quota_refresh), "note": _state["msg"]}


# --- 조회 -------------------------------------------------------------------
def series(lawd: str, trade: str = "sale", months: int | None = None) -> dict:
    """한 시군구의 월별 시계열. **가져오지 않고 쌓인 것만 읽는다.**

    지역을 누를 때마다 수집이 돌면 화면이 멈추고 한도도 순식간에 마른다.
    """
    s = get_settings()
    months = int(months or s.realestate_stats_months)
    cells = load()["cells"]
    stale = _stale_months()

    rows = []
    for ym in months_back(months):
        c = cells.get(_key(lawd, ym, trade))
        if not c:
            continue                    # 아직 안 받은 달은 0 이 아니라 '없음' 이다
        rows.append({
            "ym": ym, "label": f"{ym[:4]}.{ym[4:]}",
            **c,
            "provisional": ym in stale,
        })
    return {"trade": trade, "months": rows, "buckets": [b for b, _, _ in AREA_BUCKETS]}


def coverage(months: int | None = None) -> dict:
    """얼마나 찼는지 — 화면이 '아직 수집 중' 을 정직하게 말할 수 있게."""
    s = get_settings()
    months = int(months or s.realestate_stats_months)
    total = len(SIGUNGU) * months * len(TRADES)
    have = len(load()["cells"])
    return {"have": have, "total": total, "gaps": max(0, total - have),
            "pct": round(have / total * 100, 1) if total else 0.0,
            "months": months, "trades": list(TRADES), **_state}


__all__ = ["AREA_BUCKETS", "TRADES", "coverage", "fetch_cell", "load",
           "missing", "months_back", "refresh", "series"]
