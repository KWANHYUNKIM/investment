"""종합 투자 점수 스크리너 (composite stock score).

전 종목을 세 축으로 백분위 점수화해 "지금 살 만한" 후보를 정렬한다. 종목별 무거운
계산 없이, 이미 보드 단위로 집계된 맵(재무·시세·수급)만 사용해 한 번에 스캔한다.

  - 가치(value)   : 저PER·저PBR·고ROE·고배당 (백분위)
  - 모멘텀(momentum): 최근 1개월 수익률·당일 등락 (백분위)
  - 수급(flow)     : 외국인 순매수·외국인 지분율 상승 (백분위)
종합 = 0.45·가치 + 0.35·모멘텀 + 0.20·수급. 캐시 5분.
"""
from __future__ import annotations

import threading
import time

import numpy as np
import pandas as pd

from app.data.infra import store

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 300.0


def _pctrank(s: pd.Series, ascending: bool = True) -> pd.Series:
    """백분위(0~100). ascending=False면 값이 클수록 높은 점수."""
    return s.rank(pct=True, ascending=ascending) * 100.0


def _build() -> dict:
    quotes = store.latest_quotes(market="KR")
    if quotes is None or quotes.empty:
        return {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "count": 0, "rows": []}

    funds = store.fundamentals_latest_map()
    flows = store.latest_investor_flow_map(market="KR")
    secmap = store.sector_map()  # 실제 업종(WICS); securities.sector는 시장명

    df = quotes.copy()
    df["sector"] = df["ticker"].map(lambda t: secmap.get(t)).fillna(df["sector"])
    # 유동성 필터: 거래량 하위 30% 제거(잡주 배제)
    if "volume" in df.columns:
        vol_floor = df["volume"].fillna(0).quantile(0.30)
        df = df[df["volume"].fillna(0) >= vol_floor]

    def fval(t, k):
        r = funds.get(t)
        if not r:
            return np.nan
        v = r.get(k)
        try:
            v = float(v)
            return np.nan if v != v else v
        except (TypeError, ValueError):
            return np.nan

    df["per"] = df["ticker"].map(lambda t: fval(t, "per"))
    df["pbr"] = df["ticker"].map(lambda t: fval(t, "pbr"))
    df["roe"] = df["ticker"].map(lambda t: fval(t, "roe"))
    df["div_yield"] = df["ticker"].map(lambda t: fval(t, "div_yield"))

    def fflow(t):
        r = flows.get(t)
        if not r:
            return (np.nan, np.nan)
        fo = r.get("foreigner")
        fr, frp = r.get("foreign_ratio"), r.get("foreign_ratio_prev")
        try:
            fo = float(fo)
        except (TypeError, ValueError):
            fo = np.nan
        try:
            dfr = float(fr) - float(frp)
        except (TypeError, ValueError):
            dfr = np.nan
        return (fo, dfr)

    fo_dfr = df["ticker"].map(fflow)
    df["foreigner"] = fo_dfr.map(lambda x: x[0])
    df["foreign_ratio_chg"] = fo_dfr.map(lambda x: x[1])

    # 1개월 수익률
    df["ret_1m"] = (df["close"] - df["close_1m"]) / df["close_1m"] * 100.0
    df["chg_pct"] = (df["close"] - df["prev_close"]) / df["prev_close"] * 100.0

    # 재무가 아예 없는 종목은 제외(가치 점수 불가)
    df = df[df["per"].notna() | df["pbr"].notna() | df["roe"].notna()]
    if df.empty:
        return {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "count": 0, "rows": []}

    # --- 가치 점수 ---
    per_pos = df["per"].where(df["per"] > 0)   # 적자 PER 제외
    pbr_pos = df["pbr"].where(df["pbr"] > 0)
    v_per = _pctrank(per_pos, ascending=False)   # 낮을수록 고점수
    v_pbr = _pctrank(pbr_pos, ascending=False)
    v_roe = _pctrank(df["roe"], ascending=True)  # 높을수록 고점수
    v_div = _pctrank(df["div_yield"], ascending=True)
    value = pd.concat([v_per, v_pbr, v_roe, v_div], axis=1).mean(axis=1, skipna=True)

    # --- 모멘텀 점수 (1개월 70% + 당일 30%) ---
    m_1m = _pctrank(df["ret_1m"], ascending=True)
    m_day = _pctrank(df["chg_pct"], ascending=True)
    momentum = (m_1m * 0.7).add(m_day * 0.3, fill_value=0)
    # 한쪽만 있는 경우를 위해 유효 가중치로 나눠 0~100 스케일 유지
    wsum = (m_1m.notna() * 0.7).add(m_day.notna() * 0.3, fill_value=0)
    momentum = (momentum / wsum.replace(0, float("nan")))

    # --- 수급 점수 ---
    f_fo = _pctrank(df["foreigner"], ascending=True)
    f_fr = _pctrank(df["foreign_ratio_chg"], ascending=True)
    flow = pd.concat([f_fo, f_fr], axis=1).mean(axis=1, skipna=True)

    df["value_score"] = value.round(0)
    df["momentum_score"] = momentum.round(0)
    df["flow_score"] = flow.fillna(50).round(0)  # 수급 없으면 중립 50
    df["total_score"] = (
        df["value_score"].fillna(50) * 0.45
        + df["momentum_score"].fillna(50) * 0.35
        + df["flow_score"] * 0.20
    ).round(1)

    df = df.sort_values("total_score", ascending=False)

    def num(v):
        try:
            v = float(v)
            return None if v != v else round(v, 2)
        except (TypeError, ValueError):
            return None

    rows = []
    for r in df.head(60).to_dict("records"):
        rows.append({
            "ticker": r["ticker"], "name": r.get("name"), "sector": r.get("sector"),
            "close": num(r.get("close")), "chg_pct": num(r.get("chg_pct")),
            "ret_1m": num(r.get("ret_1m")),
            "per": num(r.get("per")), "pbr": num(r.get("pbr")),
            "roe": num(r.get("roe")), "div_yield": num(r.get("div_yield")),
            "value_score": num(r.get("value_score")),
            "momentum_score": num(r.get("momentum_score")),
            "flow_score": num(r.get("flow_score")),
            "total_score": num(r.get("total_score")),
        })
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": int(len(df)),
        "weights": {"가치": 0.45, "모멘텀": 0.35, "수급": 0.20},
        "rows": rows,
        "note": "가치·모멘텀·수급 백분위 종합 점수(전 종목 대비). 참고용 스크리너이며 투자 권유가 아닙니다.",
    }


def screen() -> dict:
    with _lock:
        if _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]
    out = _build()
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = out
    return out
