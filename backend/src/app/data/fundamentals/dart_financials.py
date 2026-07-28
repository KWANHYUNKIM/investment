"""DART 전자공시 전체 재무제표 (전 계정·연도별) — 회계 원장 그대로.

네이버/FnGuide 요약(4년·몇 항목)으로는 부족한, "합병할 때 다 적는" 수준의 전체
재무제표를 DART Open API에서 받아 적재한다. ``fnlttSinglAcntAll`` (단일회사 전체
재무제표)는 한 번 호출에 한 사업연도의 **모든 계정**(재무상태표·손익계산서·현금흐름표,
종목당 ~200개)을 당기/전기/전전기 3개년치로 돌려준다. 그래서 3년 간격 앵커
연도만 호출하면 과거 전체가 빈틈없이 채워진다(2016·2019·2022·2025 → 2014~현재).

연결재무제표(CFS)를 우선 받고, 없으면 별도(OFS)로 폴백한다. 금액 단위는 원(KRW).
"""
from __future__ import annotations

import threading
import time

import pandas as pd
import requests

from app.core.config import get_settings
from app.data.infra import store
from app.data.fundamentals.dart import _load_corp_map, _float, enabled  # 재사용

_BASE = "https://opendart.fss.or.kr/api"
_URL = f"{_BASE}/fnlttSinglAcntAll.json"

# 각 앵커는 당기/전기/전전기(3년)를 준다. 3년 간격 → 무중복 타일링.
# (현재연도 기준 최근 사업연도부터 역순으로 2015 이전까지)
def _anchors(latest_fy: int) -> list[int]:
    ys = []
    y = latest_fy
    while y >= 2015:
        ys.append(y)
        y -= 3
    return ys


_lock = threading.Lock()


def _parse(items: list[dict], anchor: int, fs_div: str) -> list[dict]:
    """DART list rows -> long rows. 한 계정의 당기/전기/전전기를 anchor/-1/-2 연도로 전개."""
    out: list[dict] = []
    cols = (("thstrm_amount", anchor), ("frmtrm_amount", anchor - 1), ("bfefrmtrm_amount", anchor - 2))
    for it in items:
        sj = it.get("sj_div")
        nm = (it.get("account_nm") or "").strip()
        if not sj or not nm:
            continue
        try:
            ordv = int(it.get("ord") or 0)
        except (TypeError, ValueError):
            ordv = 0
        acc_id = (it.get("account_id") or "").strip() or None
        for field, year in cols:
            if year < 2015:
                continue
            amt = _float(it.get(field))
            if amt is None:
                continue
            out.append({
                "ticker": None,  # filled by caller
                "sj_div": sj, "year": year, "account_nm": nm,
                "account_id": acc_id, "ord": ordv, "fs_div": fs_div, "amount": amt,
            })
    return out


def _call(corp: str, year: int, fs_div: str) -> list[dict]:
    try:
        r = requests.get(_URL, params={
            "crtfc_key": get_settings().dart_api_key, "corp_code": corp,
            "bsns_year": str(year), "reprt_code": "11011", "fs_div": fs_div,
        }, timeout=30)
        j = r.json()
    except Exception:
        return []
    if j.get("status") != "000":
        return []
    return j.get("list") or []


def fetch(ticker: str, latest_fy: int | None = None) -> list[dict]:
    """One ticker -> long rows for the full available history. [] on miss."""
    if not enabled():
        return []
    corp = _load_corp_map().get(ticker)
    if not corp:
        return []
    if latest_fy is None:
        latest_fy = _default_latest_fy()

    seen: set[tuple] = set()
    rows: list[dict] = []
    for anchor in _anchors(latest_fy):
        items = _call(corp, anchor, "CFS")
        used = "CFS"
        if not items:
            items = _call(corp, anchor, "OFS")
            used = "OFS"
        if not items:
            continue
        for row in _parse(items, anchor, used):
            key = (row["sj_div"], row["year"], row["account_nm"])
            if key in seen:
                continue
            seen.add(key)
            row["ticker"] = ticker
            rows.append(row)
    return rows


# ── 반기보고서(11012) — 상폐요건의 '반기말' 판정 전용 ──────────────────────
# 코스닥 자본잠식 요건은 "사업연도(반기)말" 기준이라 연간 재무제표만으론 판정할 수
# 없다. 반기 재무상태표에서 자본총계·자본금만 얇게 받아 dart_half 에 적재한다.
# (반기보고서의 BS 는 thstrm_amount 가 당반기말, frmtrm_amount 는 직전 사업연도말이라
#  당기 컬럼만 취한다. 손익 계정은 3개월/누적 구분이 있어 여기선 다루지 않는다.)
_HALF_ACCOUNTS = ("자본총계", "자본금")


def fetch_half(ticker: str, years: list[int] | None = None) -> list[dict]:
    """반기 자본총계·자본금 rows. 미제출 연도는 조용히 건너뛴다. [] on miss."""
    if not enabled():
        return []
    corp = _load_corp_map().get(ticker)
    if not corp:
        return []
    if years is None:
        latest = _default_latest_fy()
        years = [latest + 1, latest, latest - 1]   # +1 은 8월 반기보고서 제출 후 자동 편입

    rows: list[dict] = []
    for y in years:
        for fs in ("CFS", "OFS"):
            items = _call_half(corp, y, fs)
            if not items:
                continue
            got = False
            for it in items:
                if (it.get("sj_div") or "") != "BS":
                    continue
                nm = (it.get("account_nm") or "").strip().replace(" ", "")
                if nm not in _HALF_ACCOUNTS:
                    continue
                amt = _float(it.get("thstrm_amount"))
                if amt is None:
                    continue
                rows.append({"ticker": ticker, "year": y, "account_nm": nm,
                             "fs_div": fs, "amount": amt})
                got = True
            if got:
                break          # 연결이 나왔으면 별도는 안 받는다
    return rows


def _call_half(corp: str, year: int, fs_div: str) -> list[dict]:
    try:
        r = requests.get(_URL, params={
            "crtfc_key": get_settings().dart_api_key, "corp_code": corp,
            "bsns_year": str(year), "reprt_code": "11012", "fs_div": fs_div,
        }, timeout=30)
        j = r.json()
    except Exception:
        return []
    if j.get("status") != "000":
        return []
    return j.get("list") or []


def refresh_half(tickers: list[str], pause: float = 0.05) -> int:
    """위험 종목의 반기 자본계정을 적재(배치). 저장된 회사 수."""
    if not enabled():
        return 0
    n = 0
    for tk in tickers:
        rows = fetch_half(tk)
        if rows:
            try:
                store.upsert_dart_half(pd.DataFrame(rows))
                n += 1
            except Exception:
                pass
        if pause:
            time.sleep(pause)
    return n


def _default_latest_fy() -> int:
    """가장 최근 '확정 사업연도'. 연초엔 직전 보고서가 아직이라 한 해 보수적으로."""
    try:
        d = store.max_price_date() or ""
        y = int(d[:4])
        m = int(d[5:7]) if len(d) >= 7 else 1
    except Exception:
        return 2024
    # 사업보고서는 보통 3월 말 제출 → 4월 이후에 전년도 확정.
    return y - 1 if m >= 4 else y - 2


def get(ticker: str) -> list[dict]:
    """Cached-by-DB single ticker fetch + persist (lazy on first view)."""
    rows = fetch(ticker)
    if rows:
        try:
            store.upsert_dart_financials(pd.DataFrame(rows))
        except Exception:
            pass
    return rows


def refresh_many(tickers: list[str], skip_existing: bool = True,
                 max_new: int = 0, pause: float = 0.05) -> int:
    """Bulk fetch (scheduler/endpoint). Persists per-ticker. Returns # companies stored.

    ``max_new`` (>0) caps how many *new* companies are fetched this run so a daemon
    tick fills the board gradually instead of firing thousands of DART calls at once.
    """
    if not enabled():
        return 0
    latest_fy = _default_latest_fy()
    have = store.dart_financials_tickers() if skip_existing else set()
    n = 0
    for tk in tickers:
        if tk in have:
            continue
        rows = fetch(tk, latest_fy)
        if rows:
            try:
                store.upsert_dart_financials(pd.DataFrame(rows))
                n += 1
            except Exception:
                pass
        if max_new and n >= max_new:
            break
        if pause:
            time.sleep(pause)
    return n
