"""기업실적분석 (매출·영업이익·당기순이익·영업이익률) — coinfo 재무 데이터.

네이버 종목 종합정보(coinfo)의 "기업실적분석" 표는 FnGuide 위젯
``navercomp.wisereport.co.kr/v2/company/cF1001.aspx`` 를 임베드한 것이다. 그
위젯을 종목별로 긁어 **연간 실적**(최근 4개 사업연도)을 뽑아 DuckDB에 적재하고,
산업 지도(업종별 영업이익)와 종목 상세(연도별 실적표)에서 쓴다.

표 한 줄은 ``<th>항목</th><td><span>숫자</span></td>…`` 꼴이고, 연간/분기 칸은
첫 분기 칸의 ``border-left`` 구분선으로 나뉜다 — 그 인덱스 앞쪽이 연간이다.
숫자 단위는 억원(영업이익률은 %).
"""
from __future__ import annotations

import re
import threading
import time

import httpx
import pandas as pd

from app.data import store

_URL = "https://navercomp.wisereport.co.kr/v2/company/cF1001.aspx?cmp_cd={code}&fin_typ=0&freq_typ=Y"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# 항목명(FnGuide) -> 우리 컬럼명
_ROWS = {
    "매출액": "sales",
    "영업이익": "op_profit",
    "당기순이익": "net_income",
    "영업이익률": "op_margin",
}

_lock = threading.Lock()
_mem: dict[str, dict] = {}  # ticker -> parsed series (process cache)
TTL = 24 * 3600.0


def _num(s: str) -> float | None:
    s = (s or "").replace(",", "").strip()
    if not s or s in ("-", "N/A"):
        return None
    try:
        f = float(s)
        return None if f != f else f
    except ValueError:
        return None


def _periods(html: str, n_annual: int) -> list[str]:
    """First ``n_annual`` 연간 기간 라벨(YYYY/MM) from the table head, in order."""
    thead = html[html.find("<thead"): html.find("</thead>")]
    trs = re.findall(r"<tr>(.*?)</tr>", thead, re.S)
    if len(trs) < 2:
        return []
    labels = [re.sub(r"<[^>]+>", "", th).strip()[:7]
              for th in re.findall(r"<th[^>]*>(.*?)</th>", trs[1], re.S)]
    labels = [l for l in labels if re.match(r"\d{4}/\d{2}", l)]
    return labels[:n_annual]


def _row_values(html: str, label: str) -> tuple[list[float | None], int]:
    """(span 숫자 리스트, 첫 분기 칸 인덱스) for one 항목 row. divider = 연간 칸 수."""
    m = re.search(r"<th[^>]*>\s*" + re.escape(label) + r"\s*</th>(.*?)</tr>", html, re.S)
    if not m:
        return [], 0
    body = m.group(1)
    tds = re.findall(r"<td[^>]*>", body)
    divider = next((i for i, td in enumerate(tds) if "border-left" in td), len(tds))
    vals = [_num(x) for x in re.findall(r"<span[^>]*>(.*?)</span>", body, re.S)]
    return vals, divider


def fetch(ticker: str) -> dict | None:
    """Scrape one ticker -> {periods:[...], sales/op_profit/net_income/op_margin:[...]}.

    Only 연간 actual 컬럼(구분선 앞)만 담는다. None on failure / empty table.
    """
    try:
        r = httpx.get(_URL.format(code=ticker), headers=_HEADERS, timeout=20)
        r.encoding = "utf-8"
        html = r.text
    except Exception:
        return None
    if "영업이익" not in html:
        return None

    series: dict[str, list] = {}
    divider = 0
    for label, key in _ROWS.items():
        vals, dv = _row_values(html, label)
        if dv:
            divider = max(divider, dv)
        series[key] = vals
    if not divider:
        return None
    out: dict = {"periods": _periods(html, divider)}
    for key, vals in series.items():
        out[key] = vals[:divider]
    # need at least one real 영업이익 figure to be worth storing
    if not any(v is not None for v in out.get("op_profit", [])):
        return None
    return out


def _to_rows(ticker: str, data: dict) -> list[dict]:
    rows = []
    periods = data.get("periods", [])
    for i, period in enumerate(periods):
        def at(k):
            v = data.get(k, [])
            return v[i] if i < len(v) else None
        rows.append({
            "market": "KR", "ticker": ticker, "period": period,
            "sales": at("sales"), "op_profit": at("op_profit"),
            "net_income": at("net_income"), "op_margin": at("op_margin"),
        })
    return rows


def get(ticker: str) -> dict | None:
    """Cached single-ticker financials, fetching + persisting on a miss."""
    with _lock:
        c = _mem.get(ticker)
        if c and time.time() - c["ts"] < TTL:
            return c["data"]
    data = fetch(ticker)
    if data:
        try:
            store.upsert_financials(pd.DataFrame(_to_rows(ticker, data)))
        except Exception:
            pass
        with _lock:
            _mem[ticker] = {"ts": time.time(), "data": data}
    return data


def refresh_many(tickers: list[str], pause: float = 0.0) -> int:
    """Bulk scrape (used by the scheduler). Persists as it goes. Returns # stored."""
    n = 0
    rows: list[dict] = []
    for tk in tickers:
        data = fetch(tk)
        if data:
            rows.extend(_to_rows(tk, data))
            with _lock:
                _mem[tk] = {"ts": time.time(), "data": data}
            n += 1
        if len(rows) >= 200:
            try:
                store.upsert_financials(pd.DataFrame(rows))
            except Exception:
                pass
            rows = []
        if pause:
            time.sleep(pause)
    if rows:
        try:
            store.upsert_financials(pd.DataFrame(rows))
        except Exception:
            pass
    return n


def latest_op_map() -> dict[str, dict]:
    """ticker -> {period, op_profit, op_margin, sales, net_income, yoy} for the
    most recent stored 사업연도. Powers the 산업 지도 영업이익 컬럼/합계."""
    try:
        df = store.financials_latest()
    except Exception:
        return {}
    out: dict[str, dict] = {}
    for rec in df.to_dict("records"):
        out[rec["ticker"]] = rec
    return out
