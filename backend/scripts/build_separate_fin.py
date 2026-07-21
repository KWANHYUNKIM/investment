"""별도재무제표(OFS) 손익 수집 → data/separate_fin.json.

연결(CFS)은 이미 dart_financials 에 있고, 여기서는 같은 해 별도(OFS) 손익을 받아
'연결 손실인데 별도 흑자'(내부거래 이전가격 착시)를 탐지할 수 있게 한다.

앱 서버가 DB를 물고 있으면 유니버스 조회가 막히므로 --db 로 읽기전용 복사본 경로를 준다.

사용:
    python -m scripts.build_separate_fin --db /tmp/copy.duckdb --back 1
"""
from __future__ import annotations

import argparse

from app.data.fundamentals import separate_fin


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=str, default="", help="읽기전용 DuckDB 복사본 경로")
    ap.add_argument("--back", type=int, default=1, help="수집 사업연도 수(최근부터)")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    if args.db:
        import duckdb
        conn = duckdb.connect(args.db, read_only=True)
        tickers = [r[0] for r in conn.execute(
            "select distinct ticker from dart_financials").fetchall()]
    else:
        from app.data.infra import store
        tickers = sorted(store.dart_financials_tickers())
    if args.limit:
        tickers = tickers[: args.limit]

    print(f"별도(OFS) 손익 수집 대상 {len(tickers)}종목 · 최근 {args.back}개 연도…")
    out = separate_fin.refresh(tickers, back=args.back)
    print(f"완료: {len(out)}종목 별도 손익 확보 → {separate_fin._path()}")


if __name__ == "__main__":
    main()
