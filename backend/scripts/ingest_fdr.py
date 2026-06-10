"""Full-universe KR ingest via FinanceDataReader.

pykrx's universe-enumeration endpoints (ticker list, cross-section, fundamentals)
are broken against the current KRX, so we use FinanceDataReader to (a) list the
whole KOSPI + KOSDAQ universe and (b) pull each name's daily OHLCV history.

Run from backend/:
    python -m scripts.ingest_fdr            # 2019-01-01 .. 2025-12-31
    python -m scripts.ingest_fdr --start 2015-01-01 --end 2025-12-31

Resumable: tickers already present in the prices table are skipped.
"""
from __future__ import annotations

import argparse
import time

import pandas as pd
import FinanceDataReader as fdr

from app.data import store

START = "2019-01-01"
END = "2025-12-31"


def universe() -> pd.DataFrame:
    frames = []
    for board in ["KOSPI", "KOSDAQ"]:
        df = fdr.StockListing(board)[["Code", "Name"]].copy()
        df["sector"] = board
        frames.append(df)
    u = pd.concat(frames, ignore_index=True)
    u = u.rename(columns={"Code": "ticker", "Name": "name"})
    u["market"] = "KR"
    # Drop SPACs and obvious non-common-stock vehicles; keep everything else.
    u = u[~u["name"].str.contains("스팩", na=False)]
    u = u.drop_duplicates(subset=["ticker"]).reset_index(drop=True)
    return u[["market", "ticker", "name", "sector"]]


def to_long(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    out = df.reset_index().rename(
        columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    out["date"] = pd.to_datetime(out["date"]).dt.date
    out["market"] = "KR"
    out["ticker"] = ticker
    cols = ["market", "ticker", "date", "open", "high", "low", "close", "volume"]
    return out[[c for c in cols if c in out.columns]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=START)
    ap.add_argument("--end", default=END)
    ap.add_argument(
        "--force",
        action="store_true",
        help="re-fetch the [start,end] window for ALL universe tickers (upsert), "
        "instead of skipping tickers already present — use to extend/refresh data",
    )
    args = ap.parse_args()

    store.init_db()

    u = universe()
    store.upsert_securities(u)
    print(f"Universe: {len(u)} tickers ({args.start} .. {args.end}) force={args.force}", flush=True)

    if args.force:
        todo = u["ticker"].tolist()
    else:
        with store.connection() as c:
            done = set(c.execute("SELECT DISTINCT ticker FROM prices").df()["ticker"].tolist())
        todo = [t for t in u["ticker"].tolist() if t not in done]
    print(f"Ingesting {len(todo)} tickers", flush=True)

    ok = fail = empty = 0
    for i, t in enumerate(todo, 1):
        try:
            df = fdr.DataReader(t, args.start, args.end)
            if df is None or df.empty or "Close" not in df.columns:
                empty += 1
            else:
                store.upsert_prices(to_long(df, t))
                ok += 1
        except Exception as e:
            fail += 1
            if fail <= 20:
                print(f"  ! {t}: {type(e).__name__} {str(e)[:60]}", flush=True)
        if i % 100 == 0:
            print(f"[{i}/{len(todo)}] ok={ok} empty={empty} fail={fail}", flush=True)
        time.sleep(0.05)

    print(f"\nDONE ok={ok} empty={empty} fail={fail}", flush=True)
    print(store.coverage().to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
