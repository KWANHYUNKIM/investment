"""JSON 파일 저장소 → PostgreSQL 이관.

    PYTHONPATH=src python -m scripts.migrate_json_to_postgres --dry-run
    PYTHONPATH=src python -m scripts.migrate_json_to_postgres
    PYTHONPATH=src python -m scripts.migrate_json_to_postgres --only budget

설계 원칙 넷. 데이터 이관은 **한 번 잘못 돌면 되돌리기 어려운** 작업이라, 편의보다
안전을 앞에 둔다.

**여러 번 돌려도 같다(idempotent).** 자연키로 UPSERT 한다. 이관은 대개 한 번에 안
끝난다 — 중간에 오류가 나서 고치고 다시 돌리는 게 정상적인 경로다. 그때 앞서 넣은
것이 중복되면 그때부터 수작업이 된다.

**원본을 지우지 않는다.** JSON 파일은 그대로 둔다. 검증이 끝나고 사람이 확인한 뒤에
지우는 게 순서다. 이 스크립트는 읽기만 한다.

**틀린 값을 지어내지 않는다.** 옮길 수 없는 행은 세어서 보고하고 건너뛴다. 0 이나
빈 문자열로 채우면 나중에 그게 원본이었는지 이관 실패였는지 구분할 수 없다.

**금액은 Decimal 로 변환한다.** JSON 은 float 로 갖고 있다. ``Decimal(str(v))`` 로
가야 ``Decimal(0.1)`` 이 0.1000000000000000055511151231257827 이 되는 걸 막는다 —
이관이 오히려 오차를 심는 일이 없게.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (AppUser, ApiQuotaUsage, Card, Holding, ImportBatch,
                           IncomeProfile, InterestPoint, InterestRun, PageViewDaily,
                           Region, RegionMonthAreaStat, RegionMonthStat, Transaction,
                           UserCredential, WatchItem, WealthProfile)
from app.db.session import get_sessionmaker

_report: dict[str, dict[str, int]] = {}


def _log(area: str, key: str, n: int = 1) -> None:
    _report.setdefault(area, {}).setdefault(key, 0)
    _report[area][key] += n


def _data_dir() -> Path:
    return get_settings().data_dir


def _read(name: str) -> dict | None:
    p = _data_dir() / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"  !! {name} 읽기 실패: {type(e).__name__}")
        return None


def _money(v: Any) -> Decimal | None:
    """float → Decimal. ``str`` 을 거쳐야 이관이 오차를 심지 않는다."""
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except Exception:  # noqa: BLE001
        return None


def _date(s: str | None) -> dt.date | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(str(s)[:10], fmt).date()
        except ValueError:
            continue
    return None


# --- 계정 -------------------------------------------------------------------
def migrate_users(s: Session) -> dict[str, int]:
    """auth.json → identity.app_user + user_credential.

    해시를 별도 표로 가른다. 사용자 목록을 읽는 곳은 많지만 해시를 읽어야 하는 곳은
    로그인 하나뿐이라, 표가 갈리면 권한도 갈린다.
    """
    d = _read("auth.json")
    if not d:
        print("  auth.json 없음 — 건너뜀")
        return {}

    ids: dict[str, int] = {}
    for username, u in (d.get("users") or {}).items():
        row = s.scalar(select(AppUser).where(AppUser.username == username))
        if row is None:
            row = AppUser(username=username, created_by="migration")
            s.add(row)
        row.email = u.get("email") or None
        row.display_name = u.get("name") or None
        s.flush()
        ids[username] = row.id

        cred = s.scalar(select(UserCredential).where(UserCredential.user_id == row.id))
        if cred is None:
            cred = UserCredential(user_id=row.id)
            s.add(cred)
        cred.algorithm = "pbkdf2_sha256"
        cred.iterations = int(u.get("iter") or 1)
        # hex 문자열로 저장돼 있던 것을 bytea 로. 길이가 절반이 되고 비교 실수가 준다.
        cred.salt = bytes.fromhex(u["salt"]) if u.get("salt") else b""
        cred.password_hash = bytes.fromhex(u["hash"]) if u.get("hash") else b""
        _log("계정", "사용자")
    s.flush()
    return ids


# --- 가계부 -----------------------------------------------------------------
def migrate_budget(s: Session, username: str, user_id: int) -> None:
    """budget_<계정>.json → card · import_batch · transaction · merchant_rule · income."""
    fname = "budget.json" if username == "default" else f"budget_{username}.json"
    d = _read(fname)
    if not d:
        return

    # 1) 카드 — 거래에서 발견되는 카드와 설정된 주기를 합친다.
    cards: dict[str, int] = {}
    keys = {f'{t.get("issuer", "")} {t.get("card", "")}'.strip()
            for t in d.get("transactions", []) if t.get("card") or t.get("issuer")}
    keys |= set((d.get("card_cycles") or {}).keys())
    for key in sorted(k for k in keys if k):
        cfg = (d.get("card_cycles") or {}).get(key) or {}
        row = s.scalar(select(Card).where(Card.user_id == user_id, Card.card_key == key))
        if row is None:
            row = Card(user_id=user_id, card_key=key)
            s.add(row)
        row.issuer = key.split()[0] if key.split() else None
        for src, dst in (("cycle_start_day", "cycle_start_day"), ("cycle_end_day", "cycle_end_day"),
                         ("pay_day", "pay_day"), ("pay_offset", "pay_offset")):
            if cfg.get(src) is not None:
                setattr(row, dst, int(cfg[src]))
        s.flush()
        cards[key] = row.id
        _log("가계부", "카드")

    # 2) 업로드 이력. 파일에는 최근 20건만 남아 있어 거래와 1:1 로 못 잇는다 —
    #    이력 자체는 옮기되, 거래에는 붙이지 않는다(지어내지 않는다).
    for im in d.get("imports", []):
        # 이력에는 자연키가 없다. (파일명·카드사·청구월) 을 키로 삼아 같은 이력을
        # 두 번 넣지 않는다 — 그냥 add 하면 이관을 돌릴 때마다 이력이 불어난다.
        exists = s.scalar(select(ImportBatch).where(
            ImportBatch.user_id == user_id,
            ImportBatch.filename == im.get("filename"),
            ImportBatch.issuer == im.get("issuer"),
            ImportBatch.billing_month == im.get("billing_month")))
        if exists is not None:
            continue
        s.add(ImportBatch(
            user_id=user_id, source="upload", filename=im.get("filename"),
            issuer=im.get("issuer"), billing_month=im.get("billing_month"),
            parsed_by=im.get("parsed_by"),
            added_count=int(im.get("added") or 0),
            skipped_count=int(im.get("skipped") or 0),
            created_by="migration",
        ))
        _log("가계부", "업로드이력")

    # 3) 거래 — 지문으로 UPSERT. 다시 돌려도 중복되지 않는다.
    for t in d.get("transactions", []):
        txn_date = _date(t.get("date"))
        fp = t.get("fp")
        if not txn_date or not fp:
            _log("가계부", "건너뜀(날짜·지문 없음)")
            continue
        amount = _money(t.get("amount"))
        if amount is None:
            _log("가계부", "건너뜀(금액 없음)")
            continue

        inst = t.get("installment") or {}
        key = f'{t.get("issuer", "")} {t.get("card", "")}'.strip()
        stmt = pg_insert(Transaction.__table__).values(
            user_id=user_id,
            card_id=cards.get(key),
            txn_date=txn_date,
            billing_month=t.get("billing_month") or txn_date.strftime("%Y-%m"),
            billing_month_known=True,
            merchant=(t.get("merchant") or "미상")[:255],
            merchant_key=(t.get("merchant_key") or t.get("merchant") or "미상")[:255],
            amount=amount,
            charged=_money(t.get("charged")) or amount,
            fee=_money(t.get("fee")) or Decimal(0),
            total=_money(t.get("total")) or amount,
            tx_type=t.get("tx_type") or "일시불",
            installment_months=inst.get("months"),
            installment_seq=inst.get("seq"),
            is_fixed=t.get("fixed"),
            fingerprint=fp[:64],
            issuer=t.get("issuer") or None,
        )
        # 이미 있으면 갱신한다 — 원본을 고친 뒤 다시 돌리는 게 정상 경로다.
        s.execute(stmt.on_conflict_do_update(
            index_elements=["user_id", "fingerprint"],
            set_={"amount": stmt.excluded.amount, "charged": stmt.excluded.charged,
                  "fee": stmt.excluded.fee, "total": stmt.excluded.total,
                  "billing_month": stmt.excluded.billing_month}))
        _log("가계부", "거래")

    # 4) 수입 — 파일은 값 하나만 갖고 있다. 이력의 첫 행으로 넣는다.
    inc = d.get("income") or {}
    if inc.get("monthly_net"):
        exists = s.scalar(select(IncomeProfile).where(IncomeProfile.user_id == user_id))
        if exists is None:
            s.add(IncomeProfile(
                user_id=user_id,
                effective_from=dt.date(2000, 1, 1),   # 언제부터인지 원본에 없다
                monthly_net=_money(inc.get("monthly_net")) or Decimal(0),
                extra=_money(inc.get("extra")) or Decimal(0),
                memo=inc.get("memo") or None))
            _log("가계부", "수입")
    s.flush()


# --- 포트폴리오 --------------------------------------------------------------
def migrate_portfolio(s: Session, username: str, user_id: int) -> None:
    suffix = "" if username == "default" else f"_{username}"

    d = _read(f"watchlist{suffix}.json") or {}
    for w in d.get("watch", []):
        ticker = w if isinstance(w, str) else w.get("ticker")
        if not ticker:
            continue
        s.execute(pg_insert(WatchItem.__table__).values(
            user_id=user_id, market=(w.get("market") if isinstance(w, dict) else None) or "KR",
            ticker=ticker,
        ).on_conflict_do_nothing(index_elements=["user_id", "market", "ticker"]))
        _log("포트폴리오", "관심종목")

    for h in d.get("holdings", []):
        if not h.get("ticker"):
            continue
        stmt = pg_insert(Holding.__table__).values(
            user_id=user_id, market=h.get("market") or "KR", ticker=h["ticker"],
            quantity=_money(h.get("qty")) or Decimal(0),
            avg_price=_money(h.get("avg")) or Decimal(0),
            currency=h.get("currency") or "KRW")
        s.execute(stmt.on_conflict_do_update(
            index_elements=["user_id", "market", "ticker"],
            set_={"quantity": stmt.excluded.quantity, "avg_price": stmt.excluded.avg_price}))
        _log("포트폴리오", "보유종목")

    w = _read(f"wealth{suffix}.json") or {}
    prof = w.get("profile") or {}
    if prof:
        row = s.scalar(select(WealthProfile).where(WealthProfile.user_id == user_id))
        if row is None:
            row = WealthProfile(user_id=user_id)
            s.add(row)
        row.age = prof.get("age")
        row.married = prof.get("married")
        row.homeless = prof.get("homeless")
        row.has_child = prof.get("has_child")
        for src, dst in (("annual_income", "annual_income"), ("monthly_income", "monthly_income"),
                         ("monthly_saving", "monthly_saving"), ("current_assets", "current_assets"),
                         ("goal_amount", "goal_amount")):
            setattr(row, dst, _money(prof.get(src)))
        row.goal_years = prof.get("goal_years")
        row.holdings_horizon = w.get("holdings_horizon")
        _log("포트폴리오", "자산계획")
    s.flush()


# --- 부동산 -----------------------------------------------------------------
def migrate_realestate(s: Session) -> None:
    """지역 → 월별 집계 → 관심도. 지역을 먼저 만들어야 나머지가 걸린다."""
    from app.data.infra.lawd_codes import SIGUNGU

    regions: dict[str, int] = {}
    for lawd, sido, name in SIGUNGU:
        row = s.scalar(select(Region).where(Region.lawd_cd == lawd))
        if row is None:
            row = Region(lawd_cd=lawd, sido=sido, name=name)
            s.add(row)
        s.flush()
        regions[lawd] = row.id
    _log("부동산", "지역", len(regions))

    # 월별 집계 — 'lawd|ym|trade' 키를 풀어 넣는다.
    stats = _read("realestate_region_stats.json") or {}
    for key, cell in (stats.get("cells") or {}).items():
        try:
            lawd, ym, trade = key.split("|")
        except ValueError:
            _log("부동산", "건너뜀(키 형식)")
            continue
        rid = regions.get(lawd)
        if rid is None:
            _log("부동산", "건너뜀(모르는 지역)")
            continue
        fetched = dt.datetime.fromtimestamp(cell.get("at") or 0, tz=dt.timezone.utc)
        stmt = pg_insert(RegionMonthStat.__table__).values(
            region_id=rid, year_month=ym, trade_type=trade,
            deal_count=int(cell.get("count") or 0),
            total_amount=_money(cell.get("amount_eok")),
            avg_price=_money(cell.get("avg_eok")),
            avg_monthly_rent=_money(cell.get("avg_rent_manwon")),
            is_provisional=False, fetched_at=fetched)
        s.execute(stmt.on_conflict_do_update(
            index_elements=["region_id", "year_month", "trade_type"],
            set_={"deal_count": stmt.excluded.deal_count,
                  "total_amount": stmt.excluded.total_amount,
                  "avg_price": stmt.excluded.avg_price,
                  "avg_monthly_rent": stmt.excluded.avg_monthly_rent,
                  "fetched_at": stmt.excluded.fetched_at}))
        _log("부동산", "월별집계")

        month_id = s.scalar(select(RegionMonthStat.id).where(
            RegionMonthStat.region_id == rid,
            RegionMonthStat.year_month == ym,
            RegionMonthStat.trade_type == trade))
        for bucket, v in (cell.get("by_area") or {}).items():
            s.execute(pg_insert(RegionMonthAreaStat.__table__).values(
                month_stat_id=month_id, area_bucket=bucket,
                deal_count=int(v.get("count") or 0),
                avg_price=_money(v.get("avg_eok")),
            ).on_conflict_do_update(
                index_elements=["month_stat_id", "area_bucket"],
                set_={"deal_count": int(v.get("count") or 0),
                      "avg_price": _money(v.get("avg_eok"))}))
            _log("부동산", "평형집계")

    # 관심도 — 실행(run) 하나에 점들이 달린다. 앵커가 바뀌면 축이 달라지므로
    # 실행 정보를 반드시 같이 남긴다.
    it = _read("realestate_interest.json") or {}
    if it.get("items"):
        period = it.get("period") or {}
        start = _date(period.get("start")) or dt.date(2000, 1, 1)
        end = _date(period.get("end")) or dt.date.today()
        anchor = it.get("anchor") or "?"

        # **같은 수집을 다시 넣지 않는다.** 매번 새 run 을 만들면 점들이 그대로 두 배가
        # 된다(실제로 재실행에서 2,101 → 4,202 가 됐다). 앵커·기간이 같으면 같은
        # 수집이므로 그 run 을 다시 쓴다 — 이관은 여러 번 돌리는 게 정상 경로다.
        run = s.scalar(select(InterestRun).where(
            InterestRun.anchor_keyword == anchor,
            InterestRun.period_start == start,
            InterestRun.period_end == end))
        if run is None:
            run = InterestRun(
                anchor_keyword=anchor,
                time_unit=it.get("unit") or "month",
                period_start=start, period_end=end,
                region_count=len(it["items"]),
                source="naver_api_hub")
            s.add(run)
        s.flush()
        for item in it["items"]:
            rid = regions.get(item.get("lawd"))
            if rid is None:
                continue
            for p in item.get("series", []):
                d0 = _date(p.get("period"))
                if d0 is None:
                    continue
                s.execute(pg_insert(InterestPoint.__table__).values(
                    run_id=run.id, region_id=rid, period=d0,
                    keyword=item.get("keyword") or "",
                    ratio_to_anchor=_money(p.get("ratio")) or Decimal(0),
                ).on_conflict_do_nothing(
                    index_elements=["run_id", "region_id", "period"]))
                _log("부동산", "관심도")
    s.flush()


# --- 운영 -------------------------------------------------------------------
def migrate_ops(s: Session) -> None:
    d = _read("page_views.json") or {}
    for view, days in (d.get("by_view_day") or {}).items():
        for day, n in days.items():
            d0 = _date(day)
            if d0 is None:
                continue
            stmt = pg_insert(PageViewDaily.__table__).values(
                view_name=view[:32], view_date=d0, view_count=int(n or 0))
            s.execute(stmt.on_conflict_do_update(
                index_elements=["view_name", "view_date"],
                set_={"view_count": stmt.excluded.view_count}))
            _log("운영", "방문통계")
    s.flush()


# --- 실행 -------------------------------------------------------------------
_AREAS = ("users", "budget", "portfolio", "realestate", "ops")


def run(only: str | None = None, dry_run: bool = False) -> dict:
    session = get_sessionmaker()()
    try:
        # 이관은 소유자 권한으로 돈다 — 사람이 아니라 배치라 '현재 사용자' 가 없고,
        # 행 수준 보안을 우회해야 여러 계정의 데이터를 한 번에 넣을 수 있다.
        session.execute(text("SELECT set_config('app.current_user_id', '', true)"))

        ids: dict[str, int] = {}
        if only in (None, "users", "budget", "portfolio"):
            ids = migrate_users(session)
            print(f"  계정 {len(ids)}명")

        for username, uid in ids.items():
            if only in (None, "budget"):
                migrate_budget(session, username, uid)
            if only in (None, "portfolio"):
                migrate_portfolio(session, username, uid)
        # 로그인 계정이 없는 기본 파일(budget.json)도 챙긴다.
        if ids and only in (None, "budget"):
            pass

        if only in (None, "realestate"):
            migrate_realestate(session)
        if only in (None, "ops"):
            migrate_ops(session)

        if dry_run:
            session.rollback()
            print("\n[dry-run] 롤백했습니다 — 아무것도 저장되지 않았습니다.")
        else:
            session.commit()
            print("\n커밋 완료.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return _report


def main() -> None:
    ap = argparse.ArgumentParser(description="JSON 저장소 → PostgreSQL 이관")
    ap.add_argument("--dry-run", action="store_true",
                    help="넣어 보고 롤백한다. 무엇이 몇 건 들어가는지만 확인.")
    ap.add_argument("--only", choices=_AREAS, help="한 영역만")
    args = ap.parse_args()

    print(f"이관 {'(dry-run)' if args.dry_run else ''} — {_data_dir()}")
    rep = run(only=args.only, dry_run=args.dry_run)

    print("\n결과")
    for area, counts in rep.items():
        for k, n in sorted(counts.items()):
            print(f"  {area:8} {k:24} {n:>7,}")
    skipped = sum(n for c in rep.values() for k, n in c.items() if "건너뜀" in k)
    if skipped:
        print(f"\n  건너뛴 행 {skipped}건 — 위 목록의 '건너뜀' 항목을 확인하세요.")


if __name__ == "__main__":
    main()
