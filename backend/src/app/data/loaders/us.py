"""US / global equity loader built on yfinance.

yfinance returns adjusted OHLCV via Yahoo Finance. Fundamentals come from the
`.info` dict, which is best-effort (Yahoo changes fields often) — we pull the
common valuation ratios and guard every field.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

MARKET = "US"


def fetch_prices(ticker: str, start: str | date, end: str | date) -> pd.DataFrame:
    """Daily OHLCV for one ticker, normalised to the store schema."""
    import yfinance as yf

    raw = yf.download(
        ticker,
        start=str(start),
        end=str(end),
        progress=False,
        auto_adjust=True,
        threads=False,
    )
    if raw is None or raw.empty:
        return pd.DataFrame()
    # yfinance may return a MultiIndex column when given a single ticker.
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    df = raw.reset_index().rename(
        columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["market"] = MARKET
    df["ticker"] = ticker
    return df[["market", "ticker", "date", "open", "high", "low", "close", "volume"]]


def fetch_fundamentals(ticker: str, on: str | date | None = None) -> pd.DataFrame:
    """Snapshot of valuation fundamentals from Yahoo's info dict."""
    import yfinance as yf

    info = {}
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:  # noqa: BLE001 — yfinance raises a zoo of errors
        return pd.DataFrame()
    if not info:
        return pd.DataFrame()

    snapshot_date = pd.to_datetime(on).date() if on else date.today()
    row = {
        "market": MARKET,
        "ticker": ticker,
        "date": snapshot_date,
        "per": _num(info.get("trailingPE")),
        "pbr": _num(info.get("priceToBook")),
        "psr": _num(info.get("priceToSalesTrailing12Months")),
        "eps": _num(info.get("trailingEps")),
        "bps": _num(info.get("bookValue")),
        "roe": _pct(info.get("returnOnEquity")),
        "div_yield": _pct(info.get("dividendYield")),
        "market_cap": _num(info.get("marketCap")),
    }
    return pd.DataFrame([row])


def fetch_security(ticker: str) -> dict:
    import yfinance as yf

    info = {}
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:  # noqa: BLE001
        info = {}
    return {
        "market": MARKET,
        "ticker": ticker,
        "name": info.get("shortName") or info.get("longName") or ticker,
        "sector": info.get("sector"),
    }


def _num(v) -> float | None:
    try:
        if v is None or pd.isna(v):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _pct(v) -> float | None:
    """Yahoo returns ratios as fractions (0.12 = 12%); store as percent."""
    n = _num(v)
    return round(n * 100, 2) if n is not None else None
