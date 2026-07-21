"""관리종목·상폐 스크리너 캐시 빌드.

  1) 시장/소속부 분류(FinanceDataReader) → data/market_class.json
  2) 위험 종목 DART 공시 스캔(감사 정정·관리종목 경보) → data/delisting_alerts.json

앱 서버가 DuckDB를 물고 있으면 위험 종목 산출용 조회가 잠기므로, --db 로 읽기전용
복사본 경로를 넘기면 그걸로 위험 종목을 계산한다(없으면 store 커넥션 사용).

사용:
    python -m scripts.build_delisting                 # 시장분류 + 공시스캔
    python -m scripts.build_delisting --market-only   # 시장분류만
    python -m scripts.build_delisting --db /tmp/copy.duckdb
"""
from __future__ import annotations

import argparse

from app.data.market import delisting as dl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market-only", action="store_true")
    ap.add_argument("--db", type=str, default="", help="읽기전용 DuckDB 복사본 경로")
    ap.add_argument("--min-level", type=int, default=1)
    ap.add_argument("--bgn", type=str, default="20230101")
    args = ap.parse_args()

    print("시장/소속부 분류 갱신(FDR)…")
    cls = dl.refresh_market_class()
    from collections import Counter
    depts = Counter(v["dept"] for v in cls.values() if v["dept"])
    print(f"  {len(cls)}종목 · 관리종목 {sum(1 for v in cls.values() if '관리' in v['dept'])} · "
          f"투자주의환기 {sum(1 for v in cls.values() if '투자주의' in v['dept'])} · "
          f"기술성장 {sum(1 for v in cls.values() if '기술성장' in v['dept'])}")

    if args.market_only:
        return

    conn = None
    if args.db:
        import duckdb
        conn = duckdb.connect(args.db, read_only=True)
        print(f"위험 종목 산출(복사본 {args.db})…")
    else:
        print("위험 종목 산출(store DB)…")
    tickers = dl.at_risk_tickers(min_level=args.min_level, conn=conn)
    print(f"  스캔 대상 {len(tickers)}종목")

    print("DART 공시 스캔(감사 정정·관리종목)…")
    payload = dl.refresh_alerts(tickers, bgn=args.bgn)
    hit = len(payload["map"])
    print(f"완료: {hit}종목에서 경보 공시 발견 → {dl._alerts_path()}")


if __name__ == "__main__":
    main()
