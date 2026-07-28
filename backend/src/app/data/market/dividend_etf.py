"""배당·인덱스 ETF 레퍼런스 + S&P500 적립 계산기.

배당 성장형(VIG·SCHD·DGRO·NOBL·DGRW)·고배당(VYM·HDV·DVY·SPHD·SPYD)·커버드콜
인컴(JEPI·JEPQ·QYLD)·S&P500 적립형(VOO·SPY·IVV)을 한데 모아, 배당수익률·배당성장률·
운용보수·전략을 비교한다. 값은 검증된 준정적 데이터(리서치)로 채운다.

S&P500 적립형: 매월 일정액을 적립할 때의 미래가치를 복리로 추정한다(장기 기대수익률
기반). 실제 수익률은 변동한다.
"""
from __future__ import annotations

AS_OF = "2026-06"


def _e(ticker, name, category, yld, cagr, expense, inception, freq, strategy):
    return {"ticker": ticker, "name": name, "category": category, "yield": yld,
            "div_cagr_5y": cagr, "expense": expense, "inception": inception,
            "freq": freq, "strategy": strategy}


# {"ticker","name","category","yield","div_cagr_5y","expense","inception","freq","strategy"}
ETFS: list[dict] = [
    _e("VIG", "Vanguard Dividend Appreciation ETF", "배당성장", 1.51, 10.15, 0.04, 2006, "quarterly", "10년 이상 배당 늘린 미국 대형 우량주 추종"),
    _e("SCHD", "Schwab U.S. Dividend Equity ETF", "배당성장", 3.35, 9.2, 0.06, 2011, "quarterly", "10년 이상 배당 지급한 고품질·고배당주 100종목"),
    _e("DGRO", "iShares Core Dividend Growth ETF", "배당성장", 2.10, None, 0.08, 2014, "quarterly", "5년 이상 배당 성장한 미국 배당주 저비용 코어"),
    _e("NOBL", "ProShares S&P 500 Dividend Aristocrats ETF", "배당성장", 2.26, None, 0.35, 2013, "quarterly", "25년 이상 배당 늘린 S&P500 배당귀족주"),
    _e("DGRW", "WisdomTree U.S. Quality Dividend Growth Fund", "배당성장", 1.34, None, 0.28, 2013, "monthly", "수익성·성장성 우량주 중심 배당성장, 월배당"),
    _e("SDY", "SPDR S&P Dividend ETF", "배당성장", 2.44, None, 0.35, 2005, "quarterly", "20년 이상 연속 배당 늘린 고배당 귀족주"),
    _e("VYM", "Vanguard High Dividend Yield ETF", "고배당", 2.35, 5.6, 0.04, 2006, "quarterly", "평균 이상 배당수익률 미국 대형주 광범위 보유"),
    _e("HDV", "iShares Core High Dividend ETF", "고배당", 2.7, 0.8, 0.08, 2011, "quarterly", "재무 건전성 높은 고배당 미국주 75종목"),
    _e("DVY", "iShares Select Dividend ETF", "고배당", 3.79, 4.64, 0.38, 2003, "quarterly", "지속 배당 실적 기반 고배당 미국주 100종목"),
    _e("SPHD", "Invesco S&P 500 High Dividend Low Volatility ETF", "고배당", 4.5, None, 0.30, 2012, "monthly", "S&P500 내 고배당·저변동 50종목, 월배당"),
    _e("SPYD", "SPDR Portfolio S&P 500 High Dividend ETF", "고배당", 4.44, None, 0.07, 2015, "quarterly", "S&P500 최고배당 80종목 저비용 인컴"),
    _e("JEPI", "JPMorgan Equity Premium Income ETF", "커버드콜인컴", 8.1, None, 0.35, 2020, "monthly", "미국 대형주+옵션 프리미엄으로 월 인컴 창출"),
    _e("JEPQ", "JPMorgan Nasdaq Equity Premium Income ETF", "커버드콜인컴", 11.98, None, 0.35, 2022, "monthly", "나스닥100+커버드콜로 고배당 월 인컴"),
    _e("QYLD", "Global X NASDAQ 100 Covered Call ETF", "커버드콜인컴", 11.5, None, 0.60, 2013, "monthly", "나스닥100 커버드콜 매도, 고배당 월지급"),
    _e("VOO", "Vanguard S&P 500 ETF", "S&P500", 1.08, 8.19, 0.03, 2010, "quarterly", "S&P500 지수 초저비용 추종 적립형 대표"),
    _e("SPY", "SPDR S&P 500 ETF Trust", "S&P500", 1.09, None, 0.0945, 1993, "quarterly", "세계 최대·최초 S&P500 추종 ETF"),
    _e("IVV", "iShares Core S&P 500 ETF", "S&P500", 1.09, 10.22, 0.03, 2000, "quarterly", "S&P500 지수 초저비용 코어 추종"),
]

_CATEGORY_ORDER = ["배당성장", "고배당", "커버드콜인컴", "S&P500"]


def board() -> dict:
    groups = []
    for cat in _CATEGORY_ORDER:
        rows = [e for e in ETFS if e.get("category") == cat]
        if not rows:
            continue
        ys = [e["yield"] for e in rows if e.get("yield") is not None]
        groups.append({
            "category": cat,
            "count": len(rows),
            "avg_yield": round(sum(ys) / len(ys), 2) if ys else None,
            "rows": sorted(rows, key=lambda e: -(e.get("yield") or 0)),
        })
    return {
        "as_of": AS_OF,
        "groups": groups,
        "count": len(ETFS),
        "note": ("배당성장 ETF는 배당을 꾸준히 늘리는 우량주, 고배당은 현재 수익률이 높은 "
                 "종목, 커버드콜은 옵션 프리미엄으로 월배당을 극대화(대신 상승 제한), "
                 "S&P500은 시장 전체 적립형입니다. 수익률·보수는 " + (AS_OF or "조사 시점") + " 기준."),
    }


def sp_dca(monthly: float, years: float, annual_return: float = 0.10,
           div_yield: float = 0.015) -> dict:
    """S&P500 매월 적립 시 미래가치 추정(복리).

    annual_return: 연 기대 총수익률(장기 S&P ~10%). div_yield: 배당수익률(참고용).
    """
    n = int(round(years * 12))
    r = annual_return / 12.0
    principal = monthly * n
    # 매월 말 적립 연금의 미래가치
    if r > 0:
        fv = monthly * (((1 + r) ** n - 1) / r)
    else:
        fv = monthly * n
    gain = fv - principal
    # 마지막 해 배당(평가액 × 배당수익률) 참고치
    annual_div = fv * div_yield
    return {
        "monthly": monthly,
        "years": years,
        "annual_return_pct": round(annual_return * 100, 1),
        "principal": round(principal),
        "future_value": round(fv),
        "gain": round(gain),
        "est_annual_dividend": round(annual_div),
        "est_monthly_dividend": round(annual_div / 12),
        "note": ("장기 기대수익률 복리 가정의 추정치입니다. 실제 S&P500 수익률은 해마다 "
                 "크게 변동하며 하락 구간도 있습니다. 배당은 평가액×배당수익률 참고치."),
    }
