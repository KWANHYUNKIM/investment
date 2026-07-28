"""종목별 기술적 매매 신호 + 리스크 관리 (technical signals & risk levels).

가치(펀더멘털·목표주가)는 "무엇을 살까"를 답하지만, 실제 매매는 "언제, 얼마에 사고
어디서 손절/익절할까"가 필요하다. 이 모듈은 이미 저장된 OHLCV(로컬 DuckDB)만으로
대표적 기술적 지표를 계산해 종합 매수/중립/매도 신호와, 변동성(ATR) 기반 손절가·목표가·
손익비, 지지/저항을 산출한다. 외부 호출 없음.

지표: RSI(14) · 이동평균(5/20/60) 배열·골든/데드크로스 · MACD(12/26/9) · 볼린저밴드(20,2)
      · 거래량(20일 평균 대비) · 52주 고저 위치 · ATR(14).
각 신호는 +1(매수)/-1(매도)/0 투표 → 합산해 -100~100 스코어와 판정을 낸다.
"""
from __future__ import annotations

import pandas as pd

from app.data.infra import store


def _f(v) -> float | None:
    try:
        if v is None:
            return None
        x = float(v)
        return None if x != x else x
    except (TypeError, ValueError):
        return None


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, float("nan"))
    return 100 - 100 / (1 + rs)


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()


def _backtest(df: pd.DataFrame) -> dict | None:
    """골든크로스 매수 → 데드크로스 매도 규칙을 전체 이력에 적용한 성과.

    승률·전략 누적수익·매수후보유(Buy&Hold) 대비를 돌려준다. 참고용 단순 규칙.
    """
    close = df["close"].astype(float).reset_index(drop=True)
    if len(close) < 70:
        return None
    ma5 = close.rolling(5).mean()
    ma20 = close.rolling(20).mean()
    diff = (ma5 - ma20)

    trades: list[float] = []
    entry: float | None = None
    for i in range(1, len(close)):
        if pd.isna(diff[i]) or pd.isna(diff[i - 1]):
            continue
        crossed_up = diff[i - 1] <= 0 < diff[i]
        crossed_dn = diff[i - 1] >= 0 > diff[i]
        if entry is None and crossed_up:
            entry = float(close[i])
        elif entry is not None and crossed_dn:
            trades.append((float(close[i]) - entry) / entry)
            entry = None
    # 미청산 포지션은 마지막 종가로 평가
    open_ret = None
    if entry is not None:
        open_ret = (float(close.iloc[-1]) - entry) / entry

    closed = trades
    all_rets = closed + ([open_ret] if open_ret is not None else [])
    if not all_rets:
        return {"trades": 0, "win_rate": None, "strat_return_pct": None,
                "bh_return_pct": round((float(close.iloc[-1]) / float(close.iloc[0]) - 1) * 100, 1),
                "avg_trade_pct": None, "open_position": entry is not None}

    strat = 1.0
    for r in all_rets:
        strat *= (1 + r)
    wins = sum(1 for r in closed if r > 0)
    bh = float(close.iloc[-1]) / float(close.iloc[0]) - 1
    return {
        "trades": len(closed),
        "win_rate": round(wins / len(closed) * 100, 0) if closed else None,
        "strat_return_pct": round((strat - 1) * 100, 1),
        "bh_return_pct": round(bh * 100, 1),
        "avg_trade_pct": round(sum(closed) / len(closed) * 100, 1) if closed else None,
        "open_position": entry is not None,
    }


def signals(ticker: str) -> dict:
    df = store.ohlc(ticker)
    if df is None or df.empty or len(df) < 20:
        return {"ticker": ticker, "note": "가격 데이터가 부족해 매매 신호를 계산할 수 없습니다.",
                "verdict": None, "signals": []}

    df = df.dropna(subset=["close"]).reset_index(drop=True)
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    vol = df["volume"].astype(float)
    n = len(df)
    last = float(close.iloc[-1])
    date = str(df["date"].iloc[-1])[:10]

    # --- 지표 계산 ---
    ma5 = close.rolling(5).mean()
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    rsi = _rsi(close)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_sig = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - macd_sig
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_up = bb_mid + 2 * bb_std
    bb_low = bb_mid - 2 * bb_std
    atr = _atr(df)

    v_ma5 = _f(ma5.iloc[-1])
    v_ma20 = _f(ma20.iloc[-1])
    v_ma60 = _f(ma60.iloc[-1])
    v_rsi = _f(rsi.iloc[-1])
    v_hist = _f(macd_hist.iloc[-1])
    v_hist_prev = _f(macd_hist.iloc[-2]) if n >= 2 else None
    v_atr = _f(atr.iloc[-1])
    vol20 = _f(vol.tail(20).mean())
    v_vol = _f(vol.iloc[-1])
    up_today = bool(close.iloc[-1] >= close.iloc[-2]) if n >= 2 else True

    # 볼린저 %B
    bb_pct = None
    if _f(bb_up.iloc[-1]) is not None and _f(bb_low.iloc[-1]) is not None:
        span = bb_up.iloc[-1] - bb_low.iloc[-1]
        bb_pct = _f((last - bb_low.iloc[-1]) / span * 100) if span else None

    # 52주 고저 위치
    win = close.tail(252)
    lo52, hi52 = float(win.min()), float(win.max())
    pos52 = round((last - lo52) / (hi52 - lo52) * 100, 1) if hi52 > lo52 else None

    # 이동평균 배열
    arrange = "혼조"
    if None not in (v_ma5, v_ma20, v_ma60):
        if v_ma5 > v_ma20 > v_ma60:
            arrange = "정배열"
        elif v_ma5 < v_ma20 < v_ma60:
            arrange = "역배열"

    # 골든/데드크로스 (최근 5일 내 MA5 x MA20)
    cross = None
    if n >= 6 and not ma5.iloc[-6:].isna().any() and not ma20.iloc[-6:].isna().any():
        diff = (ma5 - ma20).tail(6).reset_index(drop=True)
        for i in range(1, len(diff)):
            if diff[i - 1] <= 0 < diff[i]:
                cross = "골든크로스"
            elif diff[i - 1] >= 0 > diff[i]:
                cross = "데드크로스"

    # 거래량
    vol_ratio = round(v_vol / vol20, 2) if (v_vol and vol20) else None

    # --- 신호 투표 ---
    sig: list[dict] = []

    def add(name, score, view):
        sig.append({"name": name, "score": score, "view": view})

    if v_rsi is not None:
        if v_rsi < 30:
            add("RSI", 1, f"RSI {v_rsi:.0f} — 과매도(반등 기대)")
        elif v_rsi > 70:
            add("RSI", -1, f"RSI {v_rsi:.0f} — 과매수(단기 부담)")
        else:
            add("RSI", 0, f"RSI {v_rsi:.0f} — 중립")

    if arrange != "혼조":
        add("이평선 배열", 1 if arrange == "정배열" else -1,
            f"{arrange} (5·20·60일선)")

    if cross:
        add("이평 교차", 1 if cross == "골든크로스" else -1, cross)

    if v_ma20 is not None:
        above = last > v_ma20
        add("20일선", 1 if above else -1,
            f"현재가가 20일선 {'위' if above else '아래'} ({v_ma20:,.0f})")

    if v_hist is not None:
        rising = v_hist_prev is not None and v_hist > v_hist_prev
        if v_hist > 0:
            add("MACD", 1, f"MACD 양(+){' · 확대' if rising else ''}")
        else:
            add("MACD", -1, f"MACD 음(−){' · 축소' if rising else ''}")

    if bb_pct is not None:
        if bb_pct < 20:
            add("볼린저", 1, f"밴드 하단({bb_pct:.0f}%B) — 저점권")
        elif bb_pct > 80:
            add("볼린저", -1, f"밴드 상단({bb_pct:.0f}%B) — 고점권")
        else:
            add("볼린저", 0, f"밴드 중앙({bb_pct:.0f}%B)")

    if vol_ratio is not None and vol_ratio >= 1.5:
        add("거래량", 1 if up_today else -1,
            f"거래량 급증 {vol_ratio:.1f}배 · {'상승' if up_today else '하락'} 동반")

    # --- 종합 ---
    votes = [s["score"] for s in sig]
    pos = sum(1 for v in votes if v > 0)
    neg = sum(1 for v in votes if v < 0)
    denom = max(1, pos + neg)
    score = round((pos - neg) / denom * 100, 0)
    if score >= 40:
        verdict, tone = "매수", "긍정"
    elif score <= -40:
        verdict, tone = "매도", "부정"
    else:
        verdict, tone = "중립", "중립"

    # --- 리스크 관리 (ATR 기반) ---
    stop = target1 = target2 = rr = None
    if v_atr:
        stop = round(last - 2 * v_atr)
        target1 = round(last + 3 * v_atr)
        target2 = round(last + 5 * v_atr)
        risk = last - stop
        reward = target1 - last
        rr = round(reward / risk, 2) if risk > 0 else None
    # 지지/저항 (최근 20일 저·고)
    support = round(float(low.tail(20).min()))
    resistance = round(float(high.tail(20).max()))

    return {
        "ticker": ticker,
        "date": date,
        "close": round(last),
        "verdict": verdict,
        "tone": tone,
        "score": score,
        "rsi": round(v_rsi, 1) if v_rsi is not None else None,
        "ma5": round(v_ma5) if v_ma5 else None,
        "ma20": round(v_ma20) if v_ma20 else None,
        "ma60": round(v_ma60) if v_ma60 else None,
        "ma_arrange": arrange,
        "cross": cross,
        "macd_hist": round(v_hist, 2) if v_hist is not None else None,
        "bb_pct": round(bb_pct, 0) if bb_pct is not None else None,
        "vol_ratio": vol_ratio,
        "pos_52w": pos52,
        "atr": round(v_atr) if v_atr else None,
        "risk": {
            "stop_loss": stop, "target1": target1, "target2": target2,
            "risk_reward": rr, "support": support, "resistance": resistance,
        },
        "signals": sig,
        "backtest": _backtest(df),
        "note": "기술적 지표 기반 참고용 신호이며 투자 권유가 아닙니다. 손절·목표가는 ATR(변동성) 기준 예시.",
    }
