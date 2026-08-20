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
from app.db.models import (AppUser, Holding, PageViewDaily, WatchItem, WealthProfile)
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


__all__ = ["enabled", "stats_load", "stats_save", "watchlist_load", "watchlist_save",
           "wealth_load", "wealth_save"]
