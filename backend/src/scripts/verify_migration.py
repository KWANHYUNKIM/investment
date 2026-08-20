"""이관 검증 — 원본 JSON 과 PostgreSQL 을 **값으로** 대조한다.

    PYTHONPATH=src python -m scripts.verify_migration

건수만 맞추면 안 된다. 60건이 60건으로 들어갔어도 금액이 틀리면 아무 의미가 없고,
가계부에서 그 오류는 몇 달 뒤 합계가 안 맞을 때야 드러난다.

그래서 세 가지를 본다.
  1. 건수
  2. **합계** — 원본 float 합과 DB NUMERIC 합이 1원 이내인가
  3. 표본 — 몇 건을 골라 필드별로 맞춰 본다

부동소수 합에는 오차가 있으므로 1원까지는 허용한다. 그보다 벌어지면 변환이 틀린 것이다.
(이관 뒤로는 DB 쪽이 정답이다 — 그쪽이 NUMERIC 이라 오차가 없다.)
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.db.models import (AppUser, Holding, InterestPoint, RegionMonthAreaStat,
                           RegionMonthStat, Transaction)
from app.db.session import get_sessionmaker

_ok = 0
_bad = 0


def check(label: str, expected, actual, tol: Decimal | None = None) -> None:
    global _ok, _bad
    if tol is not None:
        good = abs(Decimal(str(expected)) - Decimal(str(actual))) <= tol
    else:
        good = expected == actual
    mark = "OK  " if good else "틀림"
    print(f"  [{mark}] {label:44} 원본 {expected!s:>14}  DB {actual!s:>14}")
    if good:
        _ok += 1
    else:
        _bad += 1


def main() -> None:
    data = Path(get_settings().data_dir)
    s = get_sessionmaker()()
    # 검증은 전 계정을 가로질러 보므로 소유자 권한 그대로 둔다.
    s.execute(text("SELECT set_config('app.current_user_id', '', true)"))

    print("계정")
    auth = json.loads((data / "auth.json").read_text(encoding="utf-8"))
    check("사용자 수", len(auth.get("users", {})),
          s.scalar(select(func.count()).select_from(AppUser)))

    for username in auth.get("users", {}):
        f = data / f"budget_{username}.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        txs = d.get("transactions", [])
        uid = s.scalar(select(AppUser.id).where(AppUser.username == username))

        print(f"\n가계부 ({username})")
        check("거래 건수", len(txs),
              s.scalar(select(func.count()).select_from(Transaction)
                       .where(Transaction.user_id == uid)))

        # 합계 — 이 검증의 핵심. 금액 컬럼 네 개를 각각 본다.
        for field, col in (("amount", Transaction.amount), ("charged", Transaction.charged),
                           ("fee", Transaction.fee), ("total", Transaction.total)):
            src = sum(Decimal(str(t.get(field) or 0)) for t in txs)
            got = s.scalar(select(func.coalesce(func.sum(col), 0))
                           .where(Transaction.user_id == uid))
            check(f"{field} 합계", src, got, tol=Decimal("1"))

        # 표본 — 지문으로 찾아 필드를 맞춘다.
        for t in txs[:3]:
            row = s.scalar(select(Transaction).where(
                Transaction.user_id == uid, Transaction.fingerprint == t["fp"]))
            if row is None:
                check(f"표본 {t['fp'][:12]}", "존재", "없음")
                continue
            check(f"표본 {t.get('merchant', '')[:10]} 금액",
                  Decimal(str(t["amount"])), row.amount, tol=Decimal("0.01"))
            check(f"표본 {t.get('merchant', '')[:10]} 청구월",
                  t.get("billing_month"), row.billing_month)

        hold = json.loads((data / f"watchlist_{username}.json").read_text(encoding="utf-8")) \
            if (data / f"watchlist_{username}.json").exists() else {}
        if hold.get("holdings"):
            print(f"\n포트폴리오 ({username})")
            check("보유 종목 수", len(hold["holdings"]),
                  s.scalar(select(func.count()).select_from(Holding)
                           .where(Holding.user_id == uid)))

    # 부동산 집계·관심도는 예산제로 조금씩 쌓이는 산출물이라, 아직 한 번도 안 돌린
    # 환경에는 원본 파일이 없다. 가계부·포트폴리오와 같이 "없으면 건너뛴다" —
    # 대조할 원본이 없는 것을 실패로 세면 검증 결과가 거짓말이 된다.
    print("\n부동산")
    stats_f = data / "realestate_region_stats.json"
    if stats_f.exists():
        cells = json.loads(stats_f.read_text(encoding="utf-8")).get("cells", {})
        check("월별 집계 셀", len(cells),
              s.scalar(select(func.count()).select_from(RegionMonthStat)))
        check("거래건수 총합", sum(int(c.get("count") or 0) for c in cells.values()),
              s.scalar(select(func.coalesce(func.sum(RegionMonthStat.deal_count), 0))))
        check("평형 세부 행", sum(len(c.get("by_area") or {}) for c in cells.values()),
              s.scalar(select(func.count()).select_from(RegionMonthAreaStat)))
    else:
        print("  [건너뜀] realestate_region_stats.json 없음 — 아직 수집 전")

    interest_f = data / "realestate_interest.json"
    if interest_f.exists():
        interest = json.loads(interest_f.read_text(encoding="utf-8"))
        src_pts = sum(len(i.get("series") or []) for i in interest.get("items", []))
        check("관심도 데이터 점", src_pts,
              s.scalar(select(func.count()).select_from(InterestPoint)))
    else:
        print("  [건너뜀] realestate_interest.json 없음 — 아직 수집 전")

    s.close()
    print(f"\n통과 {_ok} · 실패 {_bad}")
    if _bad:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
