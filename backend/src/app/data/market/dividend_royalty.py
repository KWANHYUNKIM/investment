"""배당 성장주 레퍼런스 — 배당왕(Kings)·배당귀족(Aristocrats)·월배당 포트.

미국 배당 성장주 개념:
  - 배당왕(Dividend Kings):       50년 이상 연속 배당 증액 기업
  - 배당귀족(Dividend Aristocrats): 25년 이상 연속 증액 + S&P 500 편입 기업
  - 월배당(Monthly payers):        매월 배당을 지급하는 종목/ETF

이 목록은 공개·검증된 준(準)정적 데이터라 큐레이션한다(연 1회 수준 갱신). 실시간
미국 시세/배당은 무료 소스(yfinance 등)가 현재 차단돼 수익률은 조사 시점(as_of)
기준 근사값이며 화면에 그 사실을 표기한다. 수치는 리서치로 검증해 채운다.
"""
from __future__ import annotations

# 조사 기준 시점 (수익률/연속연수의 기준).
AS_OF = "2025-12"


def _k(ticker, name, sector, years, yld):
    return {"ticker": ticker, "name": name, "sector": sector, "years": years, "yield": yld}


# 배당왕(Dividend Kings) — 50년 이상 연속 배당 증액 (2025-12 기준)
KINGS: list[dict] = [
    _k("AWR", "American States Water", "Utilities", 70, 2.7),
    _k("NWN", "Northwest Natural Holding", "Utilities", 69, 4.2),
    _k("DOV", "Dover", "Industrials", 69, 1.1),
    _k("GPC", "Genuine Parts", "Consumer Discretionary", 69, 3.2),
    _k("EMR", "Emerson Electric", "Industrials", 68, 1.7),
    _k("PG", "Procter & Gamble", "Consumer Staples", 68, 2.9),
    _k("PH", "Parker-Hannifin", "Industrials", 68, 0.8),
    _k("CINF", "Cincinnati Financial", "Financials", 65, 2.1),
    _k("KO", "Coca-Cola", "Consumer Staples", 63, 2.9),
    _k("CL", "Colgate-Palmolive", "Consumer Staples", 63, 2.6),
    _k("JNJ", "Johnson & Johnson", "Health Care", 62, 2.5),
    _k("KVUE", "Kenvue", "Consumer Staples", 62, 4.8),
    _k("LOW", "Lowe's Companies", "Consumer Discretionary", 61, 2.0),
    _k("NDSN", "Nordson", "Industrials", 61, 1.4),
    _k("HRL", "Hormel Foods", "Consumer Staples", 59, 5.0),
    _k("TR", "Tootsie Roll Industries", "Consumer Staples", 58, 1.0),
    _k("CWT", "California Water Service", "Utilities", 58, 2.7),
    _k("TNC", "Tennant Company", "Industrials", 58, 1.6),
    _k("SCL", "Stepan Company", "Materials", 57, 3.3),
    _k("ABM", "ABM Industries", "Industrials", 57, 2.3),
    _k("SWK", "Stanley Black & Decker", "Industrials", 57, 4.6),
    _k("FRT", "Federal Realty Investment Trust", "Real Estate", 57, 4.5),
    _k("CBSH", "Commerce Bancshares", "Financials", 56, 2.1),
    _k("SYY", "Sysco", "Consumer Staples", 56, 2.9),
    _k("FUL", "H.B. Fuller", "Materials", 55, 1.6),
    _k("BKH", "Black Hills", "Utilities", 55, 3.8),
    _k("NFG", "National Fuel Gas", "Utilities", 54, 2.6),
    _k("MO", "Altria Group", "Consumer Staples", 54, 7.2),
    _k("UVV", "Universal Corporation", "Consumer Staples", 54, 6.0),
    _k("TGT", "Target", "Consumer Discretionary", 54, 4.7),
    _k("ITW", "Illinois Tool Works", "Industrials", 54, 2.6),
    _k("MSEX", "Middlesex Water", "Utilities", 53, 2.4),
    _k("ABT", "Abbott Laboratories", "Health Care", 53, 2.0),
    _k("ABBV", "AbbVie", "Health Care", 53, 3.1),
    _k("BDX", "Becton Dickinson", "Health Care", 53, 2.1),
    _k("PPG", "PPG Industries", "Materials", 53, 2.7),
    _k("KMB", "Kimberly-Clark", "Consumer Staples", 53, 4.9),
    _k("PEP", "PepsiCo", "Consumer Staples", 53, 3.8),
    _k("MSA", "MSA Safety", "Industrials", 52, 1.3),
    _k("GRC", "Gorman-Rupp", "Industrials", 52, 1.5),
    _k("GWW", "W.W. Grainger", "Industrials", 52, 0.9),
    _k("ADM", "Archer-Daniels-Midland", "Consumer Staples", 52, 3.5),
    _k("WMT", "Walmart", "Consumer Staples", 52, 0.9),
    _k("SPGI", "S&P Global", "Financials", 52, 0.8),
    _k("NUE", "Nucor", "Materials", 52, 1.4),
    _k("RPM", "RPM International", "Materials", 51, 2.0),
    _k("ED", "Consolidated Edison", "Utilities", 51, 3.4),
    _k("RLI", "RLI Corp.", "Financials", 51, 1.0),
    _k("ADP", "Automatic Data Processing", "Industrials", 50, 2.6),
    _k("UBSI", "United Bankshares", "Financials", 50, 3.9),
    _k("MGEE", "MGE Energy", "Utilities", 50, 2.3),
]

# 배당귀족(Dividend Aristocrats) — 25년 이상 연속 증액 + S&P500 편입 (2025-12 기준)
ARISTOCRATS: list[dict] = [
    _k("GPC", "Genuine Parts Company", "Consumer Discretionary", 69, 3.46),
    _k("DOV", "Dover Corporation", "Industrials", 69, 0.99),
    _k("PG", "Procter & Gamble", "Consumer Staples", 69, 2.83),
    _k("EMR", "Emerson Electric", "Industrials", 69, 1.59),
    _k("CINF", "Cincinnati Financial", "Financials", 65, 2.07),
    _k("LOW", "Lowe's Companies", "Consumer Discretionary", 65, 2.34),
    _k("JNJ", "Johnson & Johnson", "Health Care", 63, 2.14),
    _k("KO", "Coca-Cola", "Consumer Staples", 63, 2.60),
    _k("NDSN", "Nordson Corporation", "Industrials", 63, 1.15),
    _k("CL", "Colgate-Palmolive", "Consumer Staples", 62, 2.32),
    _k("KVUE", "Kenvue", "Consumer Staples", 62, 4.42),
    _k("HRL", "Hormel Foods", "Consumer Staples", 58, 4.64),
    _k("FRT", "Federal Realty Investment Trust", "Real Estate", 57, 3.59),
    _k("SWK", "Stanley Black & Decker", "Industrials", 57, 3.71),
    _k("SYY", "Sysco Corporation", "Consumer Staples", 56, 2.71),
    _k("TGT", "Target Corporation", "Consumer Discretionary", 54, 3.26),
    _k("ABBV", "AbbVie", "Health Care", 53, 2.72),
    _k("ABT", "Abbott Laboratories", "Health Care", 53, 2.49),
    _k("BDX", "Becton Dickinson", "Health Care", 53, 2.70),
    _k("GWW", "W.W. Grainger", "Industrials", 53, 0.71),
    _k("ITW", "Illinois Tool Works", "Industrials", 53, 2.37),
    _k("PPG", "PPG Industries", "Materials", 53, 2.45),
    _k("NUE", "Nucor Corporation", "Materials", 52, 0.95),
    _k("SPGI", "S&P Global", "Financials", 52, 0.86),
    _k("WMT", "Walmart", "Consumer Staples", 52, 0.88),
    _k("ADM", "Archer-Daniels-Midland", "Consumer Staples", 52, 2.44),
    _k("KMB", "Kimberly-Clark", "Consumer Staples", 52, 4.72),
    _k("PEP", "PepsiCo", "Consumer Staples", 52, 4.39),
    _k("ED", "Consolidated Edison", "Utilities", 51, 3.18),
    _k("ADP", "Automatic Data Processing", "Industrials", 50, 2.68),
    _k("MCD", "McDonald's", "Consumer Discretionary", 49, 2.78),
    _k("PNR", "Pentair", "Industrials", 49, 1.75),
    _k("SHW", "Sherwin-Williams", "Materials", 47, 0.98),
    _k("MDT", "Medtronic", "Health Care", 47, 3.39),
    _k("CLX", "Clorox Company", "Consumer Staples", 47, 5.18),
    _k("BEN", "Franklin Resources", "Financials", 44, 4.07),
    _k("APD", "Air Products and Chemicals", "Materials", 43, 2.44),
    _k("AFL", "Aflac", "Financials", 42, 1.96),
    _k("XOM", "ExxonMobil", "Energy", 42, 2.77),
    _k("CTAS", "Cintas Corporation", "Industrials", 42, 0.89),
    _k("BF.B", "Brown-Forman", "Consumer Staples", 41, 3.54),
    _k("AMCR", "Amcor", "Materials", 41, 5.5),
    _k("ATO", "Atmos Energy", "Utilities", 41, 2.26),
    _k("CAH", "Cardinal Health", "Health Care", 40, 0.88),
    _k("MKC", "McCormick & Company", "Consumer Staples", 39, 3.69),
    _k("CVX", "Chevron", "Energy", 38, 3.76),
    _k("TROW", "T. Rowe Price Group", "Financials", 38, 4.44),
    _k("ERIE", "Erie Indemnity", "Financials", 37, 2.59),
    _k("LIN", "Linde", "Materials", 33, 1.24),
    _k("ECL", "Ecolab", "Materials", 33, 1.09),
    _k("CAT", "Caterpillar", "Industrials", 32, 0.70),
    _k("AOS", "A. O. Smith", "Industrials", 32, 2.45),
    _k("ROP", "Roper Technologies", "Industrials", 32, 1.00),
    _k("WST", "West Pharmaceutical Services", "Health Care", 32, 0.25),
    _k("GD", "General Dynamics", "Industrials", 32, 1.71),
    _k("ALB", "Albemarle Corporation", "Materials", 31, 1.37),
    _k("ESS", "Essex Property Trust", "Real Estate", 31, 3.48),
    _k("EXPD", "Expeditors International", "Industrials", 31, 0.84),
    _k("O", "Realty Income", "Real Estate", 31, 5.14),
    _k("CB", "Chubb", "Financials", 31, 1.10),
    _k("BRO", "Brown & Brown", "Financials", 31, 0.95),
    _k("IBM", "IBM", "Information Technology", 30, 3.19),
    _k("NEE", "NextEra Energy", "Utilities", 30, 2.83),
    _k("CHD", "Church & Dwight", "Consumer Staples", 29, 1.26),
    _k("CHRW", "C.H. Robinson Worldwide", "Industrials", 27, 1.21),
    _k("FAST", "Fastenal", "Industrials", 26, 2.14),
    _k("SJM", "J.M. Smucker", "Consumer Staples", 25, 3.93),
    _k("FDS", "FactSet Research Systems", "Financials", 25, 1.83),
    _k("ES", "Eversource Energy", "Utilities", 25, 4.23),
]

# 월배당(Monthly payers) — 매월 배당 지급 종목·ETF (2025-12 기준)
MONTHLY: list[dict] = [
    {"ticker": "O", "name": "Realty Income", "type": "REIT", "yield": 5.3, "freq": "monthly"},
    {"ticker": "MAIN", "name": "Main Street Capital", "type": "BDC", "yield": 8.0, "freq": "monthly"},
    {"ticker": "STAG", "name": "STAG Industrial", "type": "REIT", "yield": 4.3, "freq": "monthly"},
    {"ticker": "LTC", "name": "LTC Properties", "type": "REIT", "yield": 5.7, "freq": "monthly"},
    {"ticker": "ADC", "name": "Agree Realty", "type": "REIT", "yield": 4.2, "freq": "monthly"},
    {"ticker": "SLG", "name": "SL Green Realty", "type": "REIT", "yield": 5.4, "freq": "monthly"},
    {"ticker": "EPR", "name": "EPR Properties", "type": "REIT", "yield": 6.8, "freq": "monthly"},
    {"ticker": "GOOD", "name": "Gladstone Commercial", "type": "REIT", "yield": 9.6, "freq": "monthly"},
    {"ticker": "GLAD", "name": "Gladstone Capital", "type": "BDC", "yield": 9.5, "freq": "monthly"},
    {"ticker": "GAIN", "name": "Gladstone Investment", "type": "BDC", "yield": 5.9, "freq": "monthly"},
    {"ticker": "LAND", "name": "Gladstone Land", "type": "REIT", "yield": 5.6, "freq": "monthly"},
    {"ticker": "PSEC", "name": "Prospect Capital", "type": "BDC", "yield": 19.0, "freq": "monthly"},
    {"ticker": "DX", "name": "Dynex Capital", "type": "REIT", "yield": 14.6, "freq": "monthly"},
    {"ticker": "AGNC", "name": "AGNC Investment", "type": "REIT", "yield": 13.9, "freq": "monthly"},
    {"ticker": "APLE", "name": "Apple Hospitality REIT", "type": "REIT", "yield": 6.8, "freq": "monthly"},
    {"ticker": "JEPI", "name": "JPMorgan Equity Premium Income ETF", "type": "ETF", "yield": 8.2, "freq": "monthly"},
    {"ticker": "JEPQ", "name": "JPMorgan Nasdaq Equity Premium Income ETF", "type": "ETF", "yield": 10.7, "freq": "monthly"},
    {"ticker": "QYLD", "name": "Global X NASDAQ 100 Covered Call ETF", "type": "ETF", "yield": 11.8, "freq": "monthly"},
    {"ticker": "RYLD", "name": "Global X Russell 2000 Covered Call ETF", "type": "ETF", "yield": 12.0, "freq": "monthly"},
    {"ticker": "XYLD", "name": "Global X S&P 500 Covered Call ETF", "type": "ETF", "yield": 10.6, "freq": "monthly"},
    {"ticker": "DIV", "name": "Global X SuperDividend U.S. ETF", "type": "ETF", "yield": 6.6, "freq": "monthly"},
    {"ticker": "SDIV", "name": "Global X SuperDividend ETF", "type": "ETF", "yield": 8.0, "freq": "monthly"},
    {"ticker": "SPHD", "name": "Invesco S&P 500 High Dividend Low Vol ETF", "type": "ETF", "yield": 4.3, "freq": "monthly"},
    {"ticker": "PFFD", "name": "Global X U.S. Preferred ETF", "type": "ETF", "yield": 6.3, "freq": "monthly"},
]


def _yields(rows: list[dict]) -> list[float]:
    return [r["yield"] for r in rows if r.get("yield") is not None]


def lookup(ticker: str) -> dict | None:
    """티커의 배당왕/귀족/월배당 등재 정보. {name, sector, years, yield, tier}."""
    t = (ticker or "").strip().upper()
    for r in KINGS:
        if r["ticker"].upper() == t:
            return {**r, "tier": "king", "tier_label": "배당왕(50년+)"}
    for r in ARISTOCRATS:
        if r["ticker"].upper() == t:
            return {**r, "tier": "aristocrat", "tier_label": "배당귀족(25년+)"}
    for r in MONTHLY:
        if r["ticker"].upper() == t:
            return {**r, "tier": "monthly", "tier_label": "월배당"}
    return None


def board() -> dict:
    ky = _yields(KINGS)
    ay = _yields(ARISTOCRATS)
    my = _yields(MONTHLY)
    avg_monthly = round(sum(my) / len(my), 2) if my else None
    return {
        "as_of": AS_OF,
        "kings": {
            "count": len(KINGS),
            "criteria": "50년 이상 연속 배당 증액",
            "avg_yield": round(sum(ky) / len(ky), 2) if ky else None,
            "rows": sorted(KINGS, key=lambda r: -(r.get("years") or 0)),
        },
        "aristocrats": {
            "count": len(ARISTOCRATS),
            "criteria": "25년 이상 연속 증액 + S&P 500 편입",
            "avg_yield": round(sum(ay) / len(ay), 2) if ay else None,
            "rows": sorted(ARISTOCRATS, key=lambda r: -(r.get("years") or 0)),
        },
        "monthly": {
            "count": len(MONTHLY),
            "criteria": "매월 배당 지급 종목·ETF",
            "avg_yield": avg_monthly,
            "rows": sorted(MONTHLY, key=lambda r: -(r.get("yield") or 0)),
        },
        "note": ("배당왕/귀족/월배당은 검증된 준정적 큐레이션 목록입니다. 미국 실시간 "
                 "시세·배당 무료 소스가 차단돼, 배당수익률·연속연수는 "
                 f"{AS_OF or '조사 시점'} 기준 근사값입니다."),
    }


def monthly_portfolio(invest: float, tax: float = 0.154) -> dict:
    """월배당 종목 동일가중 포트폴리오의 월 배당(세전/세후) 추정.

    미국 배당소득 원천징수(15%)와 국내 종합과세는 개인 상황마다 달라, 여기서는
    참고용으로 국내 배당소득세율(15.4%)을 세후 근사에 사용한다.
    """
    my = _yields(MONTHLY)
    blended = sum(my) / len(my) if my else 0.0
    annual_gross = invest * blended / 100
    annual_net = annual_gross * (1 - tax)
    return {
        "invest": invest,
        "blended_yield": round(blended, 2),
        "annual_gross": round(annual_gross),
        "annual_net": round(annual_net),
        "monthly_gross": round(annual_gross / 12),
        "monthly_net": round(annual_net / 12),
        "n_holdings": len(MONTHLY),
        "note": "동일가중·블렌드 배당수익률 기준 추정. 세후는 국내 배당소득세 15.4% 적용 근사값.",
    }
