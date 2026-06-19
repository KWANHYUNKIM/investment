"""기관 수급 추적 — 기관이 '언제 담고 언제 던졌나' + '왜 팔았을까' 유추.

기관(organ)은 자금이 무거워(대규모) 개미와 달리 분할로 들어오고 분할로 빠져나가는
'프로세스'가 있다. 어느 기관(연기금·투신…)인지는 KRX 비공개라 알 수 없지만, 누적된
**기관 순매수 시계열**(investor_flow)을 종목별로 묶으면 매집/이탈 국면과 그 시점을
유추할 수 있다. '왜 팔았/샀을까'는 그 구간의 주가 흐름·외국인 동반 여부·밸류·모멘텀을
조합해 규칙 기반으로 추정 문장을 만든다(확정 인과가 아닌 推定).
"""
from __future__ import annotations

import threading
import time

from app.data import store

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 600.0  # 10분

_MIN_DAYS = 5            # 최소 누적일수
_MIN_AMT = 30.0         # 의미있는 순매수 금액 임계(억)
_TOPN = 25              # 매집/이탈 각 상위 개수


def _num(v) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def _why(behavior: str, price_chg: float | None, net: float, foreign_net: float, sig: dict) -> list[str]:
    """기관이 왜 담았/던졌는지 추정 문장(規則 기반)."""
    out: list[str] = []
    per = _num(sig.get("per"))
    pbr = _num(sig.get("pbr"))
    roe = _num(sig.get("roe"))
    pfh = _num(sig.get("pct_from_high"))
    ret_1m = _num(sig.get("ret_1m"))
    fr_word = "외국인도 동반 순매도" if foreign_net < 0 else "외국인은 순매수(엇갈림)" if foreign_net > 0 else ""

    if behavior in ("이탈·분산", "손절 추정"):
        if price_chg is not None and price_chg < -3:
            out.append(f"주가가 {price_chg:.1f}% 하락하는 구간에서 기관이 순매도 — 추세 악화에 손절·비중 축소로 추정")
        elif price_chg is not None and price_chg > 3:
            out.append(f"주가 +{price_chg:.1f}% 상승 구간에서 기관 순매도 — 목표가 도달·차익 실현 추정")
        else:
            out.append("뚜렷한 주가 방향 없이 기관 순매도 — 포트폴리오 리밸런싱·자금 회수 추정")
        if fr_word:
            out.append(fr_word)
        if per is not None and per > 30:
            out.append(f"밸류에이션 부담(PER {per:.0f}배)")
        if pfh is not None and pfh > -5:
            out.append("전고점 부근 — 차익 실현 빌미")
    elif behavior in ("매집", "저가 매집 추정"):
        if price_chg is not None and price_chg < -3:
            out.append(f"주가 {price_chg:.1f}% 하락에도 기관이 순매수 — 낙폭과대·저가 분할 매집 추정")
        elif price_chg is not None and price_chg > 3:
            out.append(f"상승 추세(+{price_chg:.1f}%)에서 기관 순매수 지속 — 모멘텀·실적 기대 추정")
        else:
            out.append("기관 순매수 우위 — 저평가·배당·수급 개선 기대 추정")
        if foreign_net > 0:
            out.append("외국인도 동반 순매수(쌍끌이)")
        if per is not None and 0 < per <= 12:
            out.append(f"밸류에이션 매력(PER {per:.0f}배)")
        if pbr is not None and 0 < pbr < 1:
            out.append(f"저PBR({pbr:.2f}배)")
        if roe is not None and roe >= 12:
            out.append(f"높은 수익성(ROE {roe:.0f}%)")
        if pfh is not None and pfh <= -25:
            out.append(f"고점 대비 {pfh:.0f}% — 낙폭과대 매력")
        if ret_1m is not None and ret_1m >= 15:
            out.append(f"최근 1개월 +{ret_1m:.0f}% 모멘텀")
    if not out:
        out.append("뚜렷한 촉매는 확인되지 않음")
    return out[:4]


def _assemble() -> dict:
    df = store.organ_flow_frame()
    if df is None or df.empty:
        return {"as_of": time.strftime("%Y-%m-%d %H:%M:%S"), "accumulating": [], "distributing": [], "window_days": 0}

    # 이름/섹터 + 시그널(밸류·모멘텀)
    try:
        screen = {r["ticker"]: r for r in store.screen_table_prices()}
    except Exception:
        screen = {}

    records: list[dict] = []
    window_days = 0
    for tk, sub in df.groupby("ticker"):
        sub = sub.sort_values("date")
        n = len(sub)
        if n < _MIN_DAYS:
            continue
        window_days = max(window_days, n)
        close = sub["close"].astype(float)
        organ = sub["organ"].astype(float).fillna(0.0)
        foreigner = sub["foreigner"].astype(float).fillna(0.0)
        amt = (organ * close / 1e8)            # 일별 기관 순매수 금액(억)
        f_amt = (foreigner * close / 1e8)
        net = float(amt.sum())
        if abs(net) < _MIN_AMT:
            continue
        dates = sub["date"].tolist()
        amt_list = amt.tolist()
        # 최대 매수일 / 최대 매도일
        i_buy = int(amt.values.argmax())
        i_sell = int(amt.values.argmin())
        max_buy = {"date": dates[i_buy], "amt": round(amt_list[i_buy], 1)}
        max_sell = {"date": dates[i_sell], "amt": round(amt_list[i_sell], 1)}
        # 최근 vs 이전 추세
        recent = float(amt.tail(3).sum())
        prior = float(amt.head(max(1, n - 3)).sum())
        price_chg = round((float(close.iloc[-1]) / float(close.iloc[0]) - 1.0) * 100.0, 1) if float(close.iloc[0]) else None
        foreign_net = float(f_amt.sum())

        # 국면 분류
        if net > 0:
            behavior = "저가 매집 추정" if (price_chg is not None and price_chg < -3) else "매집"
        else:
            if recent < 0 and prior > 0:
                behavior = "손절 추정" if (price_chg is not None and price_chg < 0) else "이탈·분산"
            else:
                behavior = "이탈·분산"

        sig = screen.get(tk, {})
        rec = {
            "ticker": tk,
            "name": sig.get("name") or tk,
            "sector": sig.get("sector"),
            "net_amt": round(net, 1),               # 기간 기관 순매수(억)
            "buy_amt": round(float(amt[amt > 0].sum()), 1),
            "sell_amt": round(float(amt[amt < 0].sum()), 1),
            "recent_amt": round(recent, 1),
            "days": n,
            "price_chg": price_chg,                  # 기간 주가 변화(%)
            "foreign_net": round(foreign_net, 1),    # 같은 기간 외국인 순매수(억)
            "max_buy": max_buy,
            "max_sell": max_sell,
            "behavior": behavior,
            "change_pct": _num(sig.get("change_pct")),
            "per": _num(sig.get("per")), "pbr": _num(sig.get("pbr")),
            "ret_1m": _num(sig.get("ret_1m")), "pct_from_high": _num(sig.get("pct_from_high")),
            "why": _why(behavior, price_chg, net, foreign_net, sig),
        }
        records.append(rec)

    accumulating = sorted([r for r in records if r["net_amt"] > 0], key=lambda r: r["net_amt"], reverse=True)[:_TOPN]
    distributing = sorted([r for r in records if r["net_amt"] < 0], key=lambda r: r["net_amt"])[:_TOPN]
    return {
        "as_of": time.strftime("%Y-%m-%d %H:%M:%S"),
        "window_days": window_days,
        "universe": len(records),
        "accumulating": accumulating,
        "distributing": distributing,
    }


def track(force: bool = False) -> dict:
    with _lock:
        if not force and _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]
    data = _assemble()
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = data
    return data
