"""Ingest current fundamentals (PER/PBR/EPS/BPS/배당/외인소진율) for all stored
KR tickers from Naver, into the fundamentals table.

Run from backend/ with the API server STOPPED (DuckDB is single-writer):
    python -m scripts.ingest_fundamentals
"""
from __future__ import annotations

from app.data import store
from app.data.loaders import naver


def main() -> None:
    store.init_db()
    secs = store.list_securities(market="KR")
    tickers = secs["ticker"].tolist()
    print(f"Fundamentals ingest: {len(tickers)} tickers", flush=True)

    ok = empty = fail = 0
    for i, t in enumerate(tickers, 1):
        try:
            df = naver.fetch_fundamentals(t)
            if df.empty:
                empty += 1
            else:
                store.upsert_fundamentals(df)
                ok += 1
        except Exception as e:
            fail += 1
            if fail <= 20:
                print(f"  ! {t}: {type(e).__name__} {str(e)[:60]}", flush=True)
        if i % 100 == 0:
            print(f"[{i}/{len(tickers)}] ok={ok} empty={empty} fail={fail}", flush=True)
        naver.pace()

    print(f"\nDONE ok={ok} empty={empty} fail={fail}", flush=True)


if __name__ == "__main__":
    main()
