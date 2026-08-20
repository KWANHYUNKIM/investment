"""파일 저장소를 PostgreSQL 로 갈아 끼우는 얇은 층 — 포트폴리오 · 자산계획 · 방문통계.

가계부(``budget/store_pg.py``)와 같은 전략인데 규모가 훨씬 작다. 이 셋은 저장소
이음매가 ``_load(user)`` / ``_save(user, d)`` **한 쌍**뿐이라, 그 두 함수만 바꾸면
나머지 로직(시세 붙이기·진단·집계)은 손댈 게 없다.

각 함수는 파일 저장소가 쓰던 것과 **똑같은 모양의 dict** 를 주고받는다. 호출부가
어느 저장소인지 몰라야 되돌리기도 쉽다.

읽기에서 ``float()`` 으로 되돌리는 것도 같은 이유다 — 화면·진단 로직이 float 를
기대한다. 저장은 ``NUMERIC`` 으로 정확하게, 계산은 기존 코드 그대로.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (AppUser, Holding, InterestPoint, InterestRun,
                           PageViewDaily, Region, RegionMonthAreaStat,
                           RegionMonthStat, WatchItem, WealthProfile)
from app.db.session import bind_request_context, get_sessionmaker


def enabled() -> bool:
    """PostgreSQL 저장소를 쓸지. 가계부와 같은 스위치를 따른다.

    도메인마다 스위치를 따로 두면 절반만 옮겨진 상태를 사람이 관리해야 한다.
    한 번에 넘기고, 문제가 있으면 한 번에 되돌린다.
    """
    return get_settings().budget_storage == "postgres"


def _session(user: str) -> tuple[Session, int]:
    """세션 + 사용자 id. 행 수준 보안 컨텍스트까지 걸어서 돌려준다."""
    s = get_sessionmaker()()
    uid = s.scalar(select(AppUser.id).where(AppUser.username == user))
    if uid is None:
        row = AppUser(username=user, created_by="app")
        s.add(row)
        s.flush()
        uid = row.id
    bind_request_context(s, uid)
    return s, uid


def _f(v) -> float:
    return float(v) if v is not None else 0.0


def _dec(v):
    """float → Decimal. ``str`` 을 거쳐야 저장이 오차를 심지 않는다."""
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except Exception:  # noqa: BLE001
        return None


# --- 관심종목 · 보유 ----------------------------------------------------------
def watchlist_load(user: str) -> dict:
    """``{"watch": [티커…], "holdings": [{ticker, qty, avg}…]}`` — 파일과 같은 모양."""
    s, uid = _session(user)
    try:
        watch = s.scalars(
            select(WatchItem.ticker).where(WatchItem.user_id == uid)
            .order_by(WatchItem.created_at, WatchItem.id)).all()
        holds = s.scalars(
            select(Holding).where(Holding.user_id == uid)
            .order_by(Holding.ticker)).all()
        return {
            "watch": list(watch),
            "holdings": [{"ticker": h.ticker, "qty": _f(h.quantity),
                          "avg": _f(h.avg_price)} for h in holds],
        }
    finally:
        s.close()


def watchlist_save(user: str, d: dict) -> None:
    """전체 교체. 파일 저장소가 그렇게 동작했고 호출부가 그 계약에 기대고 있다.

    한 트랜잭션 안에서 지우고 넣으므로, 중간에 죽어도 반쯤 지워진 상태로 남지 않는다 —
    파일 저장소에는 없던 보장이다.
    """
    s, uid = _session(user)
    try:
        want = [t for t in (d.get("watch") or []) if t]
        s.execute(delete(WatchItem).where(
            WatchItem.user_id == uid, WatchItem.ticker.notin_(want) if want else True))
        for ticker in want:
            s.execute(pg_insert(WatchItem.__table__).values(
                user_id=uid, market="KR", ticker=ticker,
            ).on_conflict_do_nothing(index_elements=["user_id", "market", "ticker"]))

        holds = d.get("holdings") or []
        keep = [h["ticker"] for h in holds if h.get("ticker")]
        s.execute(delete(Holding).where(
            Holding.user_id == uid, Holding.ticker.notin_(keep) if keep else True))
        for h in holds:
            if not h.get("ticker"):
                continue
            stmt = pg_insert(Holding.__table__).values(
                user_id=uid, market="KR", ticker=h["ticker"],
                quantity=Decimal(str(h.get("qty") or 0)),
                avg_price=Decimal(str(h.get("avg") or 0)),
                currency="KRW")
            s.execute(stmt.on_conflict_do_update(
                index_elements=["user_id", "market", "ticker"],
                set_={"quantity": stmt.excluded.quantity,
                      "avg_price": stmt.excluded.avg_price}))
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# --- 자산계획 ----------------------------------------------------------------
_PROFILE_NUM = ("annual_income", "monthly_income", "monthly_saving",
                "current_assets", "goal_amount")
_PROFILE_PLAIN = ("age", "married", "homeless", "has_child", "goal_years")


def wealth_load(user: str) -> dict:
    s, uid = _session(user)
    try:
        row = s.scalar(select(WealthProfile).where(WealthProfile.user_id == uid))
        if row is None:
            return {"profile": {}, "holdings": [], "holdings_horizon": None}
        profile = {k: getattr(row, k) for k in _PROFILE_PLAIN
                   if getattr(row, k) is not None}
        profile.update({k: _f(getattr(row, k)) for k in _PROFILE_NUM
                        if getattr(row, k) is not None})
        return {"profile": profile, "holdings": [],
                "holdings_horizon": row.holdings_horizon}
    finally:
        s.close()


def wealth_save(user: str, d: dict) -> None:
    s, uid = _session(user)
    try:
        row = s.scalar(select(WealthProfile).where(WealthProfile.user_id == uid))
        if row is None:
            row = WealthProfile(user_id=uid)
            s.add(row)
        prof = d.get("profile") or {}
        for k in _PROFILE_PLAIN:
            if k in prof:
                setattr(row, k, prof[k])
        for k in _PROFILE_NUM:
            if k in prof and prof[k] is not None:
                setattr(row, k, Decimal(str(prof[k])))
        if d.get("holdings_horizon") is not None:
            row.holdings_horizon = d["holdings_horizon"]
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# --- 방문통계 ----------------------------------------------------------------
# 사용자별 데이터가 아니라 RLS 대상이 아니다. 세션도 사용자 컨텍스트 없이 연다.
def stats_load() -> dict:
    """파일 저장소가 쓰던 네 축을 DB 한 표에서 되만든다.

    ``by_view``·``by_day`` 는 ``by_view_day`` 를 접으면 나오는 값이라 저장하지 않는다.
    같은 사실을 세 벌 들고 있으면 언젠가 서로 어긋나기 때문이다(파일 저장소가 그랬다).
    """
    s = get_sessionmaker()()
    try:
        rows = s.execute(select(PageViewDaily.view_name, PageViewDaily.view_date,
                                PageViewDaily.view_count)).all()
        by_view: dict[str, int] = {}
        by_day: dict[str, int] = {}
        by_view_day: dict[str, dict[str, int]] = {}
        total = 0
        for view, day, n in rows:
            key = day.isoformat()
            by_view[view] = by_view.get(view, 0) + n
            by_day[key] = by_day.get(key, 0) + n
            by_view_day.setdefault(view, {})[key] = n
            total += n
        return {"total": total, "by_view": by_view, "by_day": by_day,
                "by_view_day": by_view_day}
    finally:
        s.close()


def stats_save(d: dict) -> None:
    """``by_view_day`` 만 반영한다 — 나머지는 파생값이라 저장할 이유가 없다."""
    s = get_sessionmaker()()
    try:
        for view, days in (d.get("by_view_day") or {}).items():
            for day, n in days.items():
                try:
                    d0 = dt.date.fromisoformat(day)
                except ValueError:
                    continue
                stmt = pg_insert(PageViewDaily.__table__).values(
                    view_name=view[:32], view_date=d0, view_count=int(n or 0))
                s.execute(stmt.on_conflict_do_update(
                    index_elements=["view_name", "view_date"],
                    set_={"view_count": stmt.excluded.view_count}))
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# --- 부동산 월별 집계 ---------------------------------------------------------
def _region_ids(s: Session):
    rows = s.execute(select(Region.id, Region.lawd_cd)).all()
    return ({lawd: rid for rid, lawd in rows}, {rid: lawd for rid, lawd in rows})


def region_stats_load() -> dict:
    """``{"updated":…, "cells": {"lawd|ym|trade": {...}}}`` — 파일과 같은 모양.

    평형별 세부는 자식 표에 있으므로 한 번에 끌어와 붙인다. 셀마다 따로 물으면
    266번 왕복하게 된다.
    """
    s = get_sessionmaker()()
    try:
        _, by_id = _region_ids(s)
        areas = {}
        for a in s.scalars(select(RegionMonthAreaStat)).all():
            areas.setdefault(a.month_stat_id, {})[a.area_bucket] = {
                "count": a.deal_count,
                "avg_eok": _f(a.avg_price) if a.avg_price is not None else None}

        cells = {}
        updated = None
        for m in s.scalars(select(RegionMonthStat)).all():
            lawd = by_id.get(m.region_id)
            if not lawd:
                continue
            cells[f"{lawd}|{m.year_month}|{m.trade_type}"] = {
                "count": m.deal_count,
                "amount_eok": _f(m.total_amount) if m.total_amount is not None else 0.0,
                "avg_eok": _f(m.avg_price) if m.avg_price is not None else None,
                "avg_rent_manwon": (_f(m.avg_monthly_rent)
                                    if m.avg_monthly_rent is not None else None),
                "by_area": areas.get(m.id, {}),
                # 수집 시각. '무엇을 다시 받을지' 를 정하는 근거라 반드시 살려야 한다.
                "at": int(m.fetched_at.timestamp()) if m.fetched_at else 0,
            }
            if m.updated_at and (updated is None or m.updated_at > updated):
                updated = m.updated_at
        return {"updated": updated.strftime("%Y-%m-%d %H:%M:%S") if updated else None,
                "cells": cells}
    finally:
        s.close()


def region_stats_save(d: dict) -> None:
    """셀을 UPSERT 한다. 파일 저장소는 통째로 덮어썼지만 여기서는 바뀐 것만 올린다."""
    s = get_sessionmaker()()
    try:
        by_lawd, _ = _region_ids(s)
        for key, cell in (d.get("cells") or {}).items():
            try:
                lawd, ym, trade = key.split("|")
            except ValueError:
                continue
            rid = by_lawd.get(lawd)
            if rid is None:
                continue
            fetched = dt.datetime.fromtimestamp(cell.get("at") or 0, tz=dt.timezone.utc)
            stmt = pg_insert(RegionMonthStat.__table__).values(
                region_id=rid, year_month=ym, trade_type=trade,
                deal_count=int(cell.get("count") or 0),
                total_amount=_dec(cell.get("amount_eok")),
                avg_price=_dec(cell.get("avg_eok")),
                avg_monthly_rent=_dec(cell.get("avg_rent_manwon")),
                fetched_at=fetched)
            s.execute(stmt.on_conflict_do_update(
                index_elements=["region_id", "year_month", "trade_type"],
                set_={"deal_count": stmt.excluded.deal_count,
                      "total_amount": stmt.excluded.total_amount,
                      "avg_price": stmt.excluded.avg_price,
                      "avg_monthly_rent": stmt.excluded.avg_monthly_rent,
                      "fetched_at": stmt.excluded.fetched_at}))
            mid = s.scalar(select(RegionMonthStat.id).where(
                RegionMonthStat.region_id == rid,
                RegionMonthStat.year_month == ym,
                RegionMonthStat.trade_type == trade))
            for bucket, v in (cell.get("by_area") or {}).items():
                astmt = pg_insert(RegionMonthAreaStat.__table__).values(
                    month_stat_id=mid, area_bucket=bucket,
                    deal_count=int(v.get("count") or 0),
                    avg_price=_dec(v.get("avg_eok")))
                s.execute(astmt.on_conflict_do_update(
                    index_elements=["month_stat_id", "area_bucket"],
                    set_={"deal_count": astmt.excluded.deal_count,
                          "avg_price": astmt.excluded.avg_price}))
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# --- 부동산 검색 관심도 --------------------------------------------------------
def interest_load():
    """가장 최근 수집 한 벌. **지수·순위·추세는 저장하지 않고 여기서 다시 만든다.**

    파일 저장소는 그 셋을 점들과 함께 저장했는데, 같은 사실을 두 벌 들고 있으면
    언젠가 어긋난다. 전부 점에서 나오는 값이라 계산이 정답이다.
    """
    s = get_sessionmaker()()
    try:
        run = s.scalar(select(InterestRun).order_by(InterestRun.id.desc()))
        if run is None:
            return None
        regions = {r.id: r for r in s.scalars(select(Region)).all()}

        grouped = {}
        keywords = {}
        for p in s.scalars(select(InterestPoint)
                           .where(InterestPoint.run_id == run.id)
                           .order_by(InterestPoint.period)).all():
            grouped.setdefault(p.region_id, []).append(
                {"period": p.period.isoformat(), "ratio": _f(p.ratio_to_anchor)})
            keywords[p.region_id] = p.keyword

        items = []
        for rid, series in grouped.items():
            reg = regions.get(rid)
            if reg is None:
                continue
            items.append({
                "lawd": reg.lawd_cd, "sido": reg.sido, "region": reg.name,
                "keyword": keywords.get(rid, ""),
                "index": round(sum(x["ratio"] for x in series) / len(series), 4)
                if series else 0.0,
                "series": series,
            })

        # 순위·추세는 도메인 모듈의 규칙을 그대로 쓴다 — 규칙이 두 곳에 있으면 갈라진다.
        from app.data.macro import interest as I
        I._rank(items)

        return {
            "updated": (run.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        if run.created_at else None),
            "anchor": run.anchor_keyword,
            "unit": run.time_unit,
            "period": {"start": run.period_start.isoformat(),
                       "end": run.period_end.isoformat()},
            "count": len(items),
            "dropped": [],
            "items": items,
        }
    finally:
        s.close()


def interest_save(data: dict) -> None:
    """수집 한 벌을 저장한다. 앵커·기간이 같으면 같은 수집으로 보고 점만 갱신한다 —
    매번 새 실행을 만들면 점이 그대로 두 배가 된다(이관에서 실제로 그랬다)."""
    s = get_sessionmaker()()
    try:
        by_lawd, _ = _region_ids(s)
        period = data.get("period") or {}
        start = dt.date.fromisoformat(str(period.get("start", "2000-01-01"))[:10])
        end = dt.date.fromisoformat(str(period.get("end", "2000-01-01"))[:10])
        anchor = data.get("anchor") or "?"

        run = s.scalar(select(InterestRun).where(
            InterestRun.anchor_keyword == anchor,
            InterestRun.period_start == start,
            InterestRun.period_end == end))
        if run is None:
            run = InterestRun(anchor_keyword=anchor,
                              time_unit=data.get("unit") or "month",
                              period_start=start, period_end=end,
                              region_count=len(data.get("items") or []),
                              source="naver_api_hub")
            s.add(run)
            s.flush()

        for item in data.get("items") or []:
            rid = by_lawd.get(item.get("lawd"))
            if rid is None:
                continue
            for p in item.get("series") or []:
                try:
                    d0 = dt.date.fromisoformat(str(p.get("period"))[:10])
                except (TypeError, ValueError):
                    continue
                stmt = pg_insert(InterestPoint.__table__).values(
                    run_id=run.id, region_id=rid, period=d0,
                    keyword=item.get("keyword") or "",
                    ratio_to_anchor=_dec(p.get("ratio")) or Decimal(0))
                s.execute(stmt.on_conflict_do_update(
                    index_elements=["run_id", "region_id", "period"],
                    set_={"ratio_to_anchor": stmt.excluded.ratio_to_anchor,
                          "keyword": stmt.excluded.keyword}))
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


__all__ = ["enabled", "interest_load", "interest_save", "region_stats_load",
           "region_stats_save", "stats_load", "stats_save", "watchlist_load",
           "watchlist_save", "wealth_load", "wealth_save"]
