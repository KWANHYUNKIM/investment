"""Korea (KOSPI/KOSDAQ) loader built on pykrx.

pykrx scrapes KRX/Naver and returns Korean-labelled columns; we normalise
them into the long-format frames our store expects.

Note: pykrx is rate-limited and occasionally flaky. The ingest script calls
these one ticker at a time with light pacing.
"""
from __future__ import annotations

import time
from datetime import date

import pandas as pd

MARKET = "KR"


def _ymd(d: str | date) -> str:
    if isinstance(d, date):
        return d.strftime("%Y%m%d")
    return d.replace("-", "")


def list_tickers(on: str | date, board: str = "ALL") -> pd.DataFrame:
    """Return securities (ticker + name) for a board on a given date.

    board: 'KOSPI' | 'KOSDAQ' | 'ALL'
    """
    from pykrx import stock

    d = _ymd(on)
    boards = ["KOSPI", "KOSDAQ"] if board == "ALL" else [board]
    rows = []
    for b in boards:
        for ticker in stock.get_market_ticker_list(d, market=b):
            rows.append(
                {
                    "market": MARKET,
                    "ticker": ticker,
                    "name": stock.get_market_ticker_name(ticker),
                    "sector": b,  # pykrx has no clean GICS sector; use board as a stand-in
                }
            )
    return pd.DataFrame(rows)


def fetch_prices(ticker: str, start: str | date, end: str | date) -> pd.DataFrame:
    """Daily OHLCV for one ticker, normalised to the store schema."""
    from pykrx import stock

    raw = stock.get_market_ohlcv(_ymd(start), _ymd(end), ticker)
    if raw is None or raw.empty:
        return pd.DataFrame()
    df = raw.rename(
        columns={
            "시가": "open",
            "고가": "high",
            "저가": "low",
            "종가": "close",
            "거래량": "volume",
        }
    )
    df = df.reset_index().rename(columns={"날짜": "date"})
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["market"] = MARKET
    df["ticker"] = ticker
    return df[["market", "ticker", "date", "open", "high", "low", "close", "volume"]]


def fetch_fundamentals(ticker: str, on: str | date) -> pd.DataFrame:
    """Single-date fundamentals snapshot for one ticker.

    Combines pykrx's fundamental endpoint (PER/PBR/EPS/BPS/DIV) with market cap.
    ROE is derived as EPS/BPS when both are available.
    """
    from pykrx import stock

    d = _ymd(on)
    fun = stock.get_market_fundamental(d, d, ticker)
    cap = stock.get_market_cap(d, d, ticker)
    if (fun is None or fun.empty) and (cap is None or cap.empty):
        return pd.DataFrame()

    row: dict = {"market": MARKET, "ticker": ticker, "date": pd.to_datetime(d).date()}
    if fun is not None and not fun.empty:
        r = fun.iloc[0]
        row.update(
            per=_num(r.get("PER")),
            pbr=_num(r.get("PBR")),
            eps=_num(r.get("EPS")),
            bps=_num(r.get("BPS")),
            div_yield=_num(r.get("DIV")),
        )
        if row.get("eps") and row.get("bps"):
            row["roe"] = round(100.0 * row["eps"] / row["bps"], 2)
    if cap is not None and not cap.empty:
        row["market_cap"] = _num(cap.iloc[0].get("시가총액"))
    return pd.DataFrame([row])


def _num(v) -> float | None:
    try:
        if v is None or pd.isna(v) or v == 0:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def pace(seconds: float = 0.3) -> None:
    """Be polite to KRX between requests."""
    time.sleep(seconds)
