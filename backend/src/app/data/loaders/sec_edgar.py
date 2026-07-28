"""SEC EDGAR (미국 증권거래위) XBRL 재무·배당 로더.

미국 종목의 배당 진단용. 무료·무키:
  • company_tickers.json  — 티커 → CIK(중앙색인키) 매핑 (디스크 캐시, 주 1회 갱신)
  • companyfacts API      — 종목별 전체 XBRL 사실(매출·순이익·영업현금흐름·주당배당)

미국 회계 태깅(us-gaap) 표준 계정으로 연도별(회계연도, FY) 값을 뽑는다. 배당은
연간 지급 주당배당금(DPS). XBRL은 대략 2009년부터라 그 이전은 데이터 없음.
"""
from __future__ import annotations

import json
import os
import time

import requests

from app.core.config import get_settings

_UA = {"User-Agent": "investment-dashboard (contact: research@example.com)"}
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

# us-gaap 계정 폴백(회사마다 태그가 달라 순서대로 시도, 처음 값 있는 것 사용)
_REVENUE = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
            "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax"]
_NET_INCOME = ["NetIncomeLoss", "ProfitLoss"]
_OCF = ["NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"]
_DPS = ["CommonStockDividendsPerShareDeclared", "CommonStockDividendsPerShareCashPaid"]

_tickers_cache: dict[str, str] | None = None


def _ticker_map() -> dict[str, str]:
    """티커(대문자) → 10자리 CIK. 디스크 캐시 7일."""
    global _tickers_cache
    if _tickers_cache is not None:
        return _tickers_cache
    path = str(get_settings().data_dir / "sec_tickers.json")
    fresh = os.path.exists(path) and (time.time() - os.path.getmtime(path) < 7 * 86400)
    if fresh:
        try:
            with open(path, encoding="utf-8") as fh:
                _tickers_cache = json.load(fh)
            return _tickers_cache
        except Exception:
            pass
    r = requests.get(_TICKERS_URL, headers=_UA, timeout=30)
    r.raise_for_status()
    raw = r.json()
    m = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in raw.values()}
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(m, fh)
    except Exception:
        pass
    _tickers_cache = m
    return m


def is_us_ticker(ticker: str) -> bool:
    """미국 티커 형태(영문자)면 True. 한국은 6자리 숫자."""
    t = (ticker or "").strip().upper()
    return bool(t) and not t.isdigit()


def cik_for(ticker: str) -> str | None:
    return _ticker_map().get((ticker or "").strip().upper())


def _annual(us: dict, concepts: list[str], per_share: bool = False) -> dict[int, float]:
    """계정 폴백을 순회하며 회계연도(FY)별 연간값 {year: val} 반환.

    연간 흐름/기간 계정은 10-K·fp=FY, 기간길이 300~400일만 채택(분기·누적 제외).
    같은 연도 여러 값이면 가장 최근 종료일 값 사용.
    """
    for c in concepts:
        node = us.get(c)
        if not node:
            continue
        units = node.get("units", {})
        key = "USD/shares" if per_share else "USD"
        arr = units.get(key)
        if not arr:
            # 단위 키가 다르면 첫 단위 사용
            arr = next(iter(units.values()), None)
        if not arr:
            continue
        best: dict[int, tuple[str, float]] = {}
        for x in arr:
            if x.get("form") not in ("10-K", "10-K/A"):
                continue
            if x.get("fp") != "FY":
                continue
            fy = x.get("fy")
            if not fy:
                continue
            start, end = x.get("start"), x.get("end")
            if start and end:  # 기간 계정: 연간(≈1년)만
                try:
                    days = (int(end[:4]) - int(start[:4])) * 365 + (int(end[5:7]) - int(start[5:7])) * 30
                    if not (300 <= days <= 400):
                        continue
                except (ValueError, TypeError):
                    pass
            val = x.get("val")
            if val is None:
                continue
            prev = best.get(fy)
            if prev is None or (end or "") > prev[0]:
                best[fy] = (end or "", float(val))
        out = {y: v[1] for y, v in best.items()}
        if out:
            return out
    return {}


def fundamentals(ticker: str) -> dict | None:
    """미국 종목 연도별 매출/순이익/영업현금흐름/주당배당금(DPS).

    반환: {"revenue":{year:val}, "net_income":{...}, "op_cash_flow":{...},
           "dps":{year:val}}  (모두 없으면 None). 금액 USD, DPS USD/주.
    """
    cik = cik_for(ticker)
    if not cik:
        return None
    try:
        r = requests.get(_FACTS_URL.format(cik=cik), headers=_UA, timeout=30)
        r.raise_for_status()
        j = r.json()
        us = (j.get("facts") or {}).get("us-gaap", {})
        entity_name = j.get("entityName")
    except Exception:
        return None
    if not us:
        return None
    # DPS: Declared 우선 + CashPaid 로 빈 연도 보완
    dps = _annual(us, ["CommonStockDividendsPerShareDeclared"], per_share=True)
    paid = _annual(us, ["CommonStockDividendsPerShareCashPaid"], per_share=True)
    for y, v in paid.items():
        dps.setdefault(y, v)
    return {
        "name": entity_name,
        "revenue": _annual(us, _REVENUE),
        "net_income": _annual(us, _NET_INCOME),
        "op_cash_flow": _annual(us, _OCF),
        "dps": dps,
    }
