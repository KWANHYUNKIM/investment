"""Data ingestion CLI.

Populate the DuckDB store with prices + fundamentals from pykrx (KR) and
yfinance (US). Run from the backend/ directory so `app` is importable:

    # US tickers
    python -m scripts.ingest us --tickers AAPL,MSFT,SPY --start 2018-01-01
    # Korea tickers
    python -m scripts.ingest kr --tickers 005930,000660 --start 2018-01-01
    # Korea: whole KOSPI universe (slow!) as of a date
    python -m scripts.ingest kr --universe KOSPI --start 2020-01-01

Examples are deliberately small so a first run finishes quickly.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime

from app.data import store
from app.data.loaders import krx, us


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def ingest_us(tickers: list[str], start: str, end: str) -> None:
    for i, t in enumerate(tickers, 1):
        print(f"[US {i}/{len(tickers)}] {t} ...", flush=True)
        sec = us.fetch_security(t)
        store.upsert_securities(_frame([sec]))

        px = us.fetch_prices(t, start, end)
        n_px = store.upsert_prices(px)

        fn = us.fetch_fundamentals(t, end)
        n_fn = store.upsert_fundamentals(fn)
        print(f"    prices={n_px} fundamentals={n_fn}")


def ingest_kr(tickers: list[str], start: str, end: str) -> None:
    # securities (names) for the batch
    secs = []
    for t in tickers:
        from pykrx import stock
        secs.append({"market": "KR", "ticker": t, "name": stock.get_market_ticker_name(t), "sector": None})
    store.upsert_securities(_frame(secs))

    for i, t in enumerate(tickers, 1):
        print(f"[KR {i}/{len(tickers)}] {t} ...", flush=True)
        px = krx.fetch_prices(t, start, end)
        n_px = store.upsert_prices(px)
        krx.pace()
        fn = krx.fetch_fundamentals(t, end)
        n_fn = store.upsert_fundamentals(fn)
        krx.pace()
        print(f"    prices={n_px} fundamentals={n_fn}")


def _frame(rows: list[dict]):
    import pandas as pd
    return pd.DataFrame(rows)


def main() -> None:
    p = argparse.ArgumentParser(description="Ingest market data into DuckDB")
    p.add_argument("market", choices=["us", "kr"])
    p.add_argument("--tickers", help="comma-separated tickers")
    p.add_argument("--universe", help="KR only: KOSPI | KOSDAQ | ALL (fetches the full board)")
    p.add_argument("--start", default="2018-01-01")
    p.add_argument("--end", default=_today())
    args = p.parse_args()

    store.init_db()

    if args.market == "kr" and args.universe:
        listing = krx.list_tickers(args.end.replace("-", ""), board=args.universe)
        store.upsert_securities(listing)
        tickers = listing["ticker"].tolist()
        print(f"Universe {args.universe}: {len(tickers)} tickers")
    else:
        if not args.tickers:
            p.error("--tickers is required (or --universe for KR)")
        tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]

    if args.market == "us":
        ingest_us(tickers, args.start, args.end)
    else:
        ingest_kr(tickers, args.start, args.end)

    print("\nCoverage now:")
    print(store.coverage().to_string(index=False))


if __name__ == "__main__":
    main()
