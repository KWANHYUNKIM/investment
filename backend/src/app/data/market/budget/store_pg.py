"""가계부 저장소 — PostgreSQL 판. ``store`` 와 **같은 계약**을 지킨다.

왜 이렇게 갈아 끼우는가
-----------------------
가계부 도메인에는 이미 검증된 로직이 쌓여 있다 — 집계(``summary``), 고정지출 판정
(``recurring``), 청구월 계산(``cycles``), 카드사별 파싱(``cards``). 이것들은 전부
**평평한 dict 목록**을 다룬다. 저장소를 바꾼다고 그 로직을 다시 쓸 이유가 없다.

그래서 이 모듈은 ``store.load(user)`` 와 **똑같은 모양의 dict** 를 돌려주고, 쓰기만
DB 로 보낸다. 호출부(``summary``·``recurring``·``__init__``)는 한 줄도 안 바뀐다.
바뀐 게 적을수록 갈아 끼우다 깨질 곳도 적다.

무엇이 실제로 좋아지는가
------------------------
1. **동시성.** 파일 저장소는 통째로 읽고 통째로 쓴다. 두 요청이 겹치면 나중 쓰기가
   앞 쓰기를 통째로 날린다. 지금은 프로세스 안 락으로 막고 있어 **서버가 둘이 되면
   그대로 깨진다.** DB 는 행 단위로 잠근다.
2. **부분 수정.** 거래 하나를 고치려고 6만 건을 직렬화하지 않는다.
3. **중복 방지가 진짜다.** 지문 UNIQUE 제약이 DB 에 있어, 두 요청이 같은 명세서를
   동시에 올려도 뚫리지 않는다.
4. **행 수준 보안.** 조회에 ``WHERE user_id`` 를 빠뜨려도 남의 행이 안 나온다.

돈은 ``Decimal`` 로 오간다. 화면·집계는 float 를 기대하므로 읽을 때 ``float()`` 으로
되돌린다 — **저장은 정확하게, 계산은 기존 로직 그대로**. 합계를 누적하는 곳이 DB 쪽으로
옮겨가면 그때 Decimal 그대로 쓰면 된다.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import (AppUser, Card, ImportBatch, IncomeProfile, MerchantRule,
                           Transaction)
from app.db.session import bind_request_context, get_sessionmaker

from . import categories as C
from . import cycles
from .cards import model as M
from .store import _normalize, apply_cycles, card_key  # 정규화 규칙은 하나만 둔다


# --- 세션 -------------------------------------------------------------------
def _session(user: str) -> tuple[Session, int]:
    """세션 + 이 사용자의 id. 행 수준 보안 컨텍스트까지 걸어서 돌려준다.

    ``user`` 는 로그인 아이디 문자열이다(기존 API 가 그렇게 넘긴다). DB 는 숫자
    id 로 다루므로 여기서 한 번 바꾼다.
    """
    s = get_sessionmaker()()
    uid = s.scalar(select(AppUser.id).where(AppUser.username == user))
    if uid is None:
        # 계정이 아직 없으면 만든다 — 파일 저장소는 계정 없이도 가계부를 썼다.
        row = AppUser(username=user, created_by="budget")
        s.add(row)
        s.flush()
        uid = row.id
    bind_request_context(s, uid)
    return s, uid


def _f(v: Any) -> float:
    """Decimal → float. 기존 집계 로직이 float 를 기대한다."""
    return float(v) if v is not None else 0.0


# --- 읽기 -------------------------------------------------------------------
def _tx_dict(t: Transaction) -> dict:
    """DB 행 → 기존 저장 스키마. **키 이름을 하나도 바꾸지 않는다.**"""
    inst = None
    if t.installment_months:
        seq = t.installment_seq or 0
        inst = {"months": t.installment_months, "seq": seq,
                "remaining": max(0, t.installment_months - seq)}
    return {
        "id": t.id,
        "date": t.txn_date.isoformat(),
        "billing_month": t.billing_month,
        "merchant": t.merchant,
        "merchant_key": t.merchant_key,
        "amount": _f(t.amount),
        "charged": _f(t.charged),
        "fee": _f(t.fee),
        "total": _f(t.total),
        "category": t.category_code or "기타",
        "issuer": t.issuer or "",
        "card": (t.card.card_key.replace(t.issuer or "", "").strip()
                 if t.card and t.issuer else ""),
        "tx_type": t.tx_type,
        "installment": inst,
        "fixed": t.is_fixed,
        "fp": t.fingerprint,
    }


def load(user: str) -> dict:
    """``store.load`` 와 같은 모양. 집계·판정 로직이 그대로 먹는다."""
    s, uid = _session(user)
    try:
        txs = s.scalars(
            select(Transaction).where(Transaction.user_id == uid)
            .order_by(Transaction.txn_date, Transaction.id)).all()
        cards = s.scalars(select(Card).where(Card.user_id == uid)).all()
        rules = s.scalars(select(MerchantRule).where(MerchantRule.user_id == uid)).all()
        income = s.scalar(
            select(IncomeProfile).where(IncomeProfile.user_id == uid)
            .order_by(IncomeProfile.effective_from.desc()))
        imports = s.scalars(
            select(ImportBatch).where(ImportBatch.user_id == uid)
            .order_by(ImportBatch.created_at.desc()).limit(20)).all()

        return {
            "income": {
                "monthly_net": _f(income.monthly_net) if income else 0,
                "extra": _f(income.extra) if income else 0,
                "memo": (income.memo or "") if income else "",
            },
            "transactions": [_tx_dict(t) for t in txs],
            "cat_rules": {r.merchant_key: r.category_code
                          for r in rules if r.category_code},
            "fixed_rules": {r.merchant_key: r.is_fixed
                            for r in rules if r.is_fixed is not None},
            "card_cycles": {
                c.card_key: cycles.normalize({
                    "cycle_start_day": c.cycle_start_day, "cycle_end_day": c.cycle_end_day,
                    "pay_day": c.pay_day, "pay_offset": c.pay_offset})
                for c in cards if c.cycle_start_day is not None
            },
            "imports": [{
                "filename": im.filename, "issuer": im.issuer,
                "billing_month": im.billing_month, "parsed_by": im.parsed_by,
                "added": im.added_count, "skipped": im.skipped_count,
                "at": im.created_at.strftime("%Y-%m-%d %H:%M") if im.created_at else "",
            } for im in imports],
            "seq": max((t.id for t in txs), default=0),
        }
    finally:
        s.close()


# --- 쓰기 -------------------------------------------------------------------
def _card_id(s: Session, uid: int, key: str) -> int | None:
    if not key:
        return None
    row = s.scalar(select(Card).where(Card.user_id == uid, Card.card_key == key))
    if row is None:
        row = Card(user_id=uid, card_key=key,
                   issuer=key.split()[0] if key.split() else None)
        s.add(row)
        s.flush()
    return row.id


def add_transactions(user: str, items: list[dict], source: dict | None = None) -> dict:
    """거래 등록. 지문이 겹치면 건너뛴다 — 그 판정을 **DB 제약**에 맡긴다.

    파일 저장소는 메모리에서 지문 집합을 만들어 비교했는데, 두 요청이 동시에 오면
    둘 다 '없다' 고 판단해 통과한다. UNIQUE 제약은 그 창을 남기지 않는다.
    """
    s, uid = _session(user)
    try:
        rules = {r.merchant_key: r.category_code
                 for r in s.scalars(select(MerchantRule)
                                    .where(MerchantRule.user_id == uid)).all()
                 if r.category_code}
        added = skipped = 0
        for it in items or []:
            tx = _normalize(it)
            if tx is None:
                continue
            merchant = tx["merchant"]
            category = rules.get(merchant) or tx.get("category") or C.categorize(merchant)
            inst = tx.get("installment") or {}
            stmt = pg_insert(Transaction.__table__).values(
                user_id=uid,
                card_id=_card_id(s, uid, card_key(tx)),
                txn_date=dt.date.fromisoformat(tx["date"]),
                billing_month=tx["billing_month"],
                merchant=merchant[:255],
                merchant_key=(tx.get("merchant_key") or merchant)[:255],
                amount=Decimal(str(tx["amount"])),
                charged=Decimal(str(tx["charged"])),
                fee=Decimal(str(tx.get("fee") or 0)),
                total=Decimal(str(tx["total"])),
                tx_type=tx["tx_type"],
                installment_months=inst.get("months"),
                installment_seq=inst.get("seq"),
                category_code=category,
                fingerprint=tx["fp"][:64],
                issuer=tx.get("issuer") or None,
            ).on_conflict_do_nothing(index_elements=["user_id", "fingerprint"])
            # **rowcount 를 믿지 않는다.** ON CONFLICT DO NOTHING 으로 실제 삽입이 없어도
            # 1 이 돌아왔다(중복은 DB 가 제대로 막았는데 보고만 틀렸다 — 화면에는
            # '4건 등록' 이라고 뜨고 실제로는 0건인 상태). RETURNING 이 값을 주는지로
            # 판단하면 그런 착시가 없다.
            inserted = s.execute(
                stmt.returning(Transaction.__table__.c.id)).scalar()
            if inserted is not None:
                added += 1
            else:
                skipped += 1

        if source:
            s.add(ImportBatch(
                user_id=uid, source=source.get("source") or "upload",
                filename=source.get("filename"), issuer=source.get("issuer"),
                billing_month=source.get("billing_month"),
                parsed_by=source.get("parsed_by"),
                added_count=added, skipped_count=skipped, created_by="app"))
        s.commit()
        return {"added": added, "skipped": skipped}
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def delete_transaction(user: str, tx_id: int) -> dict:
    s, uid = _session(user)
    try:
        n = s.execute(delete(Transaction).where(
            Transaction.user_id == uid, Transaction.id == tx_id)).rowcount
        s.commit()
        return {"ok": bool(n)}
    finally:
        s.close()


def set_category(user: str, tx_id: int, category: str, apply_all: bool = True) -> dict:
    category = (category or "").strip() or "기타"
    s, uid = _session(user)
    try:
        target = s.scalar(select(Transaction).where(
            Transaction.user_id == uid, Transaction.id == tx_id))
        if target is None:
            return {"ok": False}
        target.category_code = category
        if apply_all:
            _upsert_rule(s, uid, target.merchant_key, category=category)
            for t in s.scalars(select(Transaction).where(
                    Transaction.user_id == uid,
                    Transaction.merchant_key == target.merchant_key)).all():
                t.category_code = category
        s.commit()
        return {"ok": True, "category": category, "applied_all": apply_all}
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def _upsert_rule(s: Session, uid: int, merchant_key: str, *,
                 category: str | None = None, fixed: bool | None = ...) -> MerchantRule:
    row = s.scalar(select(MerchantRule).where(
        MerchantRule.user_id == uid, MerchantRule.merchant_key == merchant_key))
    if row is None:
        row = MerchantRule(user_id=uid, merchant_key=merchant_key)
        s.add(row)
    if category is not None:
        row.category_code = category
    if fixed is not ...:
        row.is_fixed = fixed
    return row


def set_fixed(user: str, merchant: str, fixed: bool | None) -> dict:
    merchant = (merchant or "").strip()
    if not merchant:
        return {"ok": False}
    s, uid = _session(user)
    try:
        _upsert_rule(s, uid, merchant, fixed=fixed)
        s.commit()
        return {"ok": True, "merchant": merchant, "fixed": fixed}
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def set_income(user: str, monthly_net: float, extra: float = 0, memo: str = "") -> dict:
    """수입 저장. 파일 저장소는 값을 덮어썼지만 여기서는 **오늘부터 유효한 이력**으로 둔다 —
    급여가 오르면 과거 달의 저축률이 소급해 틀려지는 걸 막는다."""
    s, uid = _session(user)
    try:
        today = dt.date.today()
        row = s.scalar(select(IncomeProfile).where(
            IncomeProfile.user_id == uid, IncomeProfile.effective_from == today))
        if row is None:
            row = IncomeProfile(user_id=uid, effective_from=today)
            s.add(row)
        row.monthly_net = Decimal(str(monthly_net or 0))
        row.extra = Decimal(str(extra or 0))
        row.memo = memo or ""
        s.commit()
        return {"monthly_net": float(row.monthly_net), "extra": float(row.extra),
                "memo": row.memo}
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def clear_month(user: str, month: str, by: str = "billing_month") -> dict:
    s, uid = _session(user)
    try:
        q = delete(Transaction).where(Transaction.user_id == uid)
        if by == "date":
            q = q.where(func.to_char(Transaction.txn_date, "YYYY-MM").like(f"{month}%"))
        else:
            q = q.where(Transaction.billing_month.like(f"{month}%"))
        n = s.execute(q).rowcount
        s.commit()
        return {"removed": n}
    finally:
        s.close()


def clear_import(user: str, issuer: str, billing_month: str) -> dict:
    s, uid = _session(user)
    try:
        n = s.execute(delete(Transaction).where(
            Transaction.user_id == uid,
            Transaction.issuer == issuer,
            Transaction.billing_month == billing_month)).rowcount
        s.commit()
        return {"removed": n}
    finally:
        s.close()


def set_cycle(user: str, card: str, cfg: dict | None) -> dict:
    card = (card or "").strip()
    if not card:
        return {"ok": False}
    s, uid = _session(user)
    try:
        row = s.scalar(select(Card).where(Card.user_id == uid, Card.card_key == card))
        if row is None:
            row = Card(user_id=uid, card_key=card,
                       issuer=card.split()[0] if card.split() else None)
            s.add(row)
        saved = None
        if cfg is None:
            row.cycle_start_day = row.cycle_end_day = row.pay_day = row.pay_offset = None
        else:
            saved = cycles.normalize(cfg)
            row.cycle_start_day = saved["cycle_start_day"]
            row.cycle_end_day = saved["cycle_end_day"]
            row.pay_day = saved["pay_day"]
            row.pay_offset = saved["pay_offset"]
        s.commit()
        return {"ok": True, "card": card, "cycle": saved}
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_cycles(user: str) -> dict:
    return load(user).get("card_cycles", {})


def recalc_billing_months(user: str, card: str | None = None) -> dict:
    """청구월 재계산. 계산은 기존 ``apply_cycles`` 를 그대로 쓰고 결과만 반영한다."""
    s, uid = _session(user)
    try:
        cycles_ = get_cycles(user)
        if card:
            cycles_ = {k: v for k, v in cycles_.items() if k == card}
        if not cycles_:
            return {"changed": 0, "note": "설정된 카드가 없습니다."}

        rows = s.scalars(select(Transaction).where(Transaction.user_id == uid)).all()
        as_dicts = [_tx_dict(t) for t in rows]
        changed = apply_cycles(as_dicts, cycles_)
        by_id = {d["id"]: d for d in as_dicts}
        for t in rows:
            d = by_id.get(t.id)
            if d and (d["billing_month"] != t.billing_month or d["fp"] != t.fingerprint):
                t.billing_month = d["billing_month"]
                t.fingerprint = d["fp"][:64]
        s.commit()
        return {"changed": changed, "cards": list(cycles_)}
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def move_month(user: str, issuer: str, from_month: str, to_month: str) -> dict:
    """한 묶음의 청구월을 통째로 옮긴다. 옮긴 달에 같은 거래가 이미 있으면 합친다."""
    if not to_month or from_month == to_month:
        return {"moved": 0}
    s, uid = _session(user)
    try:
        rows = s.scalars(select(Transaction).where(
            Transaction.user_id == uid,
            Transaction.issuer == issuer,
            Transaction.billing_month == from_month)).all()
        existing = set(s.scalars(select(Transaction.fingerprint)
                                 .where(Transaction.user_id == uid)).all())
        moved = dropped = 0
        for t in rows:
            d = _tx_dict(t)
            existing.discard(t.fingerprint)
            d["billing_month"] = to_month
            new_fp = M.fingerprint(d)[:64]
            if new_fp in existing:      # 이미 있는 거래와 겹치면 합친다
                s.delete(t)
                dropped += 1
                continue
            t.billing_month = to_month
            t.fingerprint = new_fp
            existing.add(new_fp)
            moved += 1
        s.commit()
        return {"moved": moved, "merged": dropped, "to": to_month}
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def save(user: str, d: dict) -> None:      # noqa: ARG001
    """파일 저장소와 계약을 맞추기 위한 자리. DB 판은 각 함수가 직접 커밋한다.

    통째로 덮어쓰는 동작을 흉내 내지 않는다 — 그 방식이 바로 옮겨 온 이유다.
    """
    raise NotImplementedError("PostgreSQL 저장소는 통째로 덮어쓰지 않는다")


__all__ = ["add_transactions", "apply_cycles", "card_key", "clear_import", "clear_month",
           "delete_transaction", "get_cycles", "load", "move_month",
           "recalc_billing_months", "save", "set_category", "set_cycle", "set_fixed",
           "set_income"]
