"""가계부 저장소 — ``data/budget_<계정>.json`` 한 파일.

거래 스키마가 넓어졌다(청구월·카드·거래구분·할부·수수료). 예전 파일에는 그 키가
없으므로 읽을 때 ``_migrate`` 가 채운다. 예전 거래는 청구월을 알 수 없어 거래월을
그대로 쓴다 — 새로 올린 명세서만 청구월 기준이 되므로, 섞이는 그 한 달은 화면에서
'거래월 기준' 배지로 구분한다.

같은 명세서를 두 번 올리는 일이 흔해서(카드사가 확정본을 다시 내려준다) 지문
``fp`` 로 중복을 막는다. 중복은 조용히 버리지 않고 몇 건 걸렀는지 돌려준다.
"""
from __future__ import annotations

import threading
import time

from app.core.jsonstore import read_json, user_path, write_json

from . import categories as C
from .cards import model as M

_lock = threading.Lock()

_DEFAULT = {
    "income": {"monthly_net": 0, "extra": 0, "memo": ""},
    "transactions": [],
    "cat_rules": {},        # 가맹점 → 카테고리 (사용자 지정)
    "fixed_rules": {},      # 가맹점 → 고정비 여부 (사용자 지정, True/False)
    "imports": [],          # 업로드 이력 (최근 20건)
}


def _path(user: str) -> str:
    return user_path("budget", user)


def _migrate(txs: list[dict]) -> list[dict]:
    """예전 스키마({id,date,merchant,amount,category})를 새 스키마로 채운다."""
    for t in txs:
        amount = float(t.get("amount") or 0)
        t.setdefault("billing_month", str(t.get("date", ""))[:7])
        t.setdefault("charged", amount)
        t.setdefault("fee", 0.0)
        t.setdefault("total", amount)
        t.setdefault("issuer", "")
        t.setdefault("card", "")
        t.setdefault("tx_type", M.CANCEL if amount < 0 else M.LUMP)
        t.setdefault("installment", None)
        if not t.get("fp"):
            t["fp"] = M.fingerprint(t)
    return txs


def load(user: str) -> dict:
    d = read_json(_path(user), _DEFAULT)
    _migrate(d["transactions"])
    # seq 는 기존 거래 id 최대값에서 이어야 해서 정적 기본값으로 둘 수 없다.
    d.setdefault("seq", max((t.get("id", 0) for t in d["transactions"]), default=0))
    return d


def save(user: str, d: dict) -> None:
    write_json(_path(user), d)


# --- 수입 ------------------------------------------------------------------
def set_income(user: str, monthly_net: float, extra: float = 0, memo: str = "") -> dict:
    with _lock:
        d = load(user)
        d["income"] = {"monthly_net": float(monthly_net or 0), "extra": float(extra or 0),
                       "memo": memo or ""}
        save(user, d)
    return d["income"]


# --- 거래 등록 --------------------------------------------------------------
def add_transactions(user: str, items: list[dict], source: dict | None = None) -> dict:
    """거래를 등록한다. 이미 있는 지문(``fp``)은 건너뛴다.

    ``items`` 는 파서가 만든 정규화 거래(풍부한 필드)도, 손으로 넣은
    ``{date, merchant, amount}`` 도 받는다. 후자는 여기서 정규화한다.
    """
    with _lock:
        d = load(user)
        seq = d.get("seq", 0)
        cat_rules = d.get("cat_rules", {})
        known = {t.get("fp") for t in d["transactions"] if t.get("fp")}

        added, skipped = 0, 0
        for it in items or []:
            tx = _normalize(it)
            if tx is None:
                continue
            if tx["fp"] in known:
                skipped += 1
                continue
            # 사용자가 지정한 가맹점 규칙이 자동 분류보다 우선한다.
            tx["category"] = cat_rules.get(tx["merchant"]) or tx.get("category") \
                or C.categorize(tx["merchant"])
            seq += 1
            tx["id"] = seq
            d["transactions"].append(tx)
            known.add(tx["fp"])
            added += 1

        d["seq"] = seq
        if source:
            d.setdefault("imports", []).insert(0, {
                **source, "added": added, "skipped": skipped,
                "at": time.strftime("%Y-%m-%d %H:%M"),
            })
            d["imports"] = d["imports"][:20]
        save(user, d)
    return {"added": added, "skipped": skipped}


def _normalize(it: dict) -> dict | None:
    """어느 경로로 들어온 거래든 저장 스키마로 맞춘다."""
    date = M.norm_date(it.get("date")) or str(it.get("date", ""))[:10]
    if not date:
        return None
    charged = it.get("charged")
    if charged is None:
        charged = it.get("amount")
    charged = M.clean_amt(charged)
    if charged is None:
        return None
    fee = M.clean_amt(it.get("fee")) or 0.0
    total = M.clean_amt(it.get("total"))
    tx = M.make_tx(
        date=date, merchant=str(it.get("merchant", "")), charged=charged, fee=fee,
        total=total if total is not None else charged,
        billing_month=str(it.get("billing_month") or "")[:7] or date[:7],
        issuer=str(it.get("issuer", "")), card=str(it.get("card", "")),
        tx_type=str(it.get("tx_type") or "") or (M.CANCEL if charged < 0 else M.LUMP),
        installment=it.get("installment") or None,
    )
    if it.get("category"):
        tx["category"] = str(it["category"])
    return tx


# --- 편집 ------------------------------------------------------------------
def delete_transaction(user: str, tx_id: int) -> dict:
    with _lock:
        d = load(user)
        before = len(d["transactions"])
        d["transactions"] = [t for t in d["transactions"] if t.get("id") != tx_id]
        save(user, d)
    return {"ok": before != len(d["transactions"])}


def set_category(user: str, tx_id: int, category: str, apply_all: bool = True) -> dict:
    """거래의 분류를 바꾼다. apply_all 이면 같은 가맹점 규칙으로 저장 + 전부 재분류."""
    category = (category or "").strip() or "기타"
    with _lock:
        d = load(user)
        target = next((t for t in d["transactions"] if t.get("id") == tx_id), None)
        if not target:
            return {"ok": False}
        target["category"] = category
        if apply_all:
            merchant = target.get("merchant")
            d.setdefault("cat_rules", {})[merchant] = category
            for t in d["transactions"]:
                if t.get("merchant") == merchant:
                    t["category"] = category
        save(user, d)
    return {"ok": True, "category": category, "applied_all": apply_all}


def set_fixed(user: str, merchant: str, fixed: bool | None) -> dict:
    """가맹점을 고정비/변동비로 못박는다. ``fixed=None`` 이면 자동 판정으로 되돌린다."""
    merchant = (merchant or "").strip()
    if not merchant:
        return {"ok": False}
    with _lock:
        d = load(user)
        rules = d.setdefault("fixed_rules", {})
        if fixed is None:
            rules.pop(merchant, None)
        else:
            rules[merchant] = bool(fixed)
        save(user, d)
    return {"ok": True, "merchant": merchant, "fixed": fixed}


def clear_month(user: str, month: str, by: str = "billing_month") -> dict:
    """한 달치를 지운다. ``by`` 는 ``billing_month``(청구월) 또는 ``date``(거래월)."""
    key = by if by in ("billing_month", "date") else "billing_month"
    with _lock:
        d = load(user)
        before = len(d["transactions"])
        d["transactions"] = [t for t in d["transactions"]
                             if not str(t.get(key, "")).startswith(month)]
        save(user, d)
    return {"removed": before - len(d["transactions"])}


def clear_import(user: str, issuer: str, billing_month: str) -> dict:
    """방금 잘못 올린 명세서 되돌리기 — 카드사 + 청구월로 한 번에 지운다."""
    with _lock:
        d = load(user)
        before = len(d["transactions"])
        d["transactions"] = [
            t for t in d["transactions"]
            if not (t.get("issuer") == issuer and t.get("billing_month") == billing_month)
        ]
        save(user, d)
    return {"removed": before - len(d["transactions"])}
