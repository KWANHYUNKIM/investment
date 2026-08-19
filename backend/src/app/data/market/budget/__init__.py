"""가계부 — 카드 명세서 취합 · 지출 분리 · 저축/투자 계획.

원래 파일 하나였는데, 카드사가 늘면 늘수록 파싱이 전체를 잡아먹어서 갈랐다.

    cards/       카드사별 명세서 파서 (카드사 추가는 여기에만)
    mailbox      카드사 메일 명세서 자동 수집(IMAP) → 위 파서로 넘김
    categories   가맹점 → 카테고리, 고정비/변동비 판정
    store        data/budget_<계정>.json 읽기·쓰기, 중복 방지
    summary      네 축 집계(카테고리·카드·거래구분·고정비) + 할부 미래 부담 + 계획
    payslip      급여명세서에서 실수령액 추출

이 모듈은 그 다섯을 하나의 API 로 묶는다. 예전 호출부(``budget.summary`` 등)가
그대로 동작하도록 이름을 유지한다.
"""
from __future__ import annotations

from . import cards, categories, cycles, mailbox, payslip, recurring, store
from .categories import CATEGORIES, categorize
from .store import (add_transactions, clear_import, clear_month, delete_transaction,
                    move_month, recalc_billing_months, set_category, set_cycle,
                    set_fixed, set_income)
from .summary import installments, months_of, plan, state, summary

ISSUERS = cards.ISSUERS


def _apply_cycles(user: str, rep: dict) -> dict:
    """카드 설정이 있으면 청구월을 거래일에서 다시 계산한다.

    파일이 청구월을 적어 주더라도(신한·삼성) 설정을 우선하지 않는다 — 대신 둘이
    다르면 ``cycle_conflict`` 로 알려 준다. 설정이 한 달 어긋나 있다는 뜻이라,
    조용히 덮어쓰면 나머지 카드까지 같은 오차로 쌓인다.
    """
    cycles_ = store.get_cycles(user)
    txs = rep["transactions"]
    if not cycles_ or not txs:
        rep["cycle_applied"] = 0
        return rep

    stated = rep["billing_month"] if rep.get("billing_month_known") else ""
    if rep.get("billing_month_known"):
        # 파일이 말한 청구월이 설정과 맞는지만 확인하고 값은 건드리지 않는다.
        probe = [dict(t) for t in txs]
        store.apply_cycles(probe, cycles_)
        got = sorted({t["billing_month"] for t in probe if t["billing_month"]})
        rep["cycle_applied"] = 0
        if got and stated not in got:
            rep["cycle_conflict"] = {"stated": stated, "by_cycle": got}
            rep["note"] += (f" 명세서는 {stated} 청구라는데 카드 설정으로는 "
                            f"{'·'.join(got)} 입니다 — 결제일 설정을 확인하세요.")
        return rep

    changed = store.apply_cycles(txs, cycles_)
    rep["cycle_applied"] = changed
    if changed:
        months = sorted({t["billing_month"] for t in txs if t["billing_month"]})
        rep["billing_month"] = months[-1] if months else rep["billing_month"]
        rep["billing_months"] = months
        rep["billing_month_known"] = True
        rep["note"] = (f"{rep['issuer'] or '카드'} 명세서에서 {len(txs)}건을 읽고, "
                       f"카드 설정(결제일·이용기간)으로 청구월을 "
                       f"{'·'.join(months)} 로 계산했습니다.")
    return rep


def preview_file(user: str, filename: str, data: bytes) -> dict:
    """저장하지 않고 파싱만 — 화면에서 확인한 뒤 등록하게 한다.

    금액의 의미가 카드사마다 달라서(할부·포인트·취소) 바로 저장하면 틀린 걸
    나중에 찾기 어렵다. 먼저 보여주고 사용자가 확인한 것만 넣는다.
    """
    rep = _apply_cycles(user, cards.parse_file(filename or "", data or b""))
    txs = rep["transactions"]
    rep["stats"] = _stats(txs)
    rep["filename"] = filename
    return rep


def fixed_costs(user: str) -> dict:
    """고정지출(계속 결제되는 것) 목록 + 월/연 환산.

    변동비와 같은 자리에 섞어 두면 '얼마를 줄일 수 있는가' 에 답할 수 없어서 따로 뺀다.
    """
    d = store.load(user)
    return recurring.analyze(d["transactions"], d.get("fixed_rules", {}))


def cards_overview(user: str) -> dict:
    """등록된 카드 목록 + 결제 주기 설정 + 이번 청구분의 이용기간.

    화면이 '이 카드는 언제부터 언제까지 쓴 걸 언제 내는가' 를 날짜로 보여줄 수 있게
    설정값과 그 설정이 만들어내는 실제 기간을 함께 준다.
    """
    d = store.load(user)
    conf = d.get("card_cycles", {})
    seen: dict[str, dict] = {}
    for t in d["transactions"]:
        key = store.card_key(t)
        if not key:
            continue
        row = seen.setdefault(key, {"card": key, "issuer": t.get("issuer", ""),
                                    "count": 0, "amount": 0.0, "months": set()})
        row["count"] += 1
        row["amount"] += t.get("amount", 0) or 0
        if t.get("billing_month"):
            row["months"].add(t["billing_month"])

    out = []
    for key, row in sorted(seen.items(), key=lambda kv: -kv[1]["amount"]):
        months = sorted(row.pop("months"))
        cfg = conf.get(key)
        latest = months[-1] if months else ""
        out.append({
            **row, "amount": round(row["amount"]), "months": months,
            "configured": cfg is not None,
            "cycle": cycles.normalize(cfg),
            "describe": cycles.describe(cfg) if cfg else "",
            "window": cycles.window_for(latest, cfg) if (cfg and latest) else {},
            "billing_month": latest,
        })
    return {"cards": out, "defaults": cycles.DEFAULT}


def import_file(user: str, filename: str, data: bytes) -> dict:
    """카드사 파일 업로드 → 파싱 후 바로 등록(중복은 지문으로 거른다)."""
    rep = _apply_cycles(user, cards.parse_file(filename or "", data or b""))
    txs = rep["transactions"]
    res = add_transactions(user, txs, source={
        "filename": filename, "issuer": rep["issuer"],
        "billing_month": rep["billing_month"], "parsed_by": rep["parsed_by"],
    }) if txs else {"added": 0, "skipped": 0}
    return {
        "parsed": len(txs), **res,
        "issuer": rep["issuer"], "billing_month": rep["billing_month"],
        "parsed_by": rep["parsed_by"], "file_kind": rep["file_kind"],
        "note": rep["note"], "stats": _stats(txs), "sample": txs[:8],
    }


def import_csv(user: str, text: str) -> dict:
    """붙여넣은 표/CSV 등록 — 파일 업로드와 같은 경로를 탄다."""
    return import_file(user, "paste.csv", (text or "").encode("utf-8"))


def parse_payslip(filename: str, data: bytes) -> dict:
    return payslip.parse(filename, data)


def _stats(txs: list[dict]) -> dict:
    """파싱 결과를 등록 전에 눈으로 검증할 수 있게 요약한다."""
    spend = sum(t["amount"] for t in txs if t["amount"] > 0)
    by_type: dict[str, float] = {}
    by_card: dict[str, float] = {}
    for t in txs:
        by_type[t["tx_type"]] = by_type.get(t["tx_type"], 0.0) + t["amount"]
        key = f'{t.get("issuer", "")} {t.get("card", "")}'.strip() or "미상"
        by_card[key] = by_card.get(key, 0.0) + t["amount"]
    return {
        "count": len(txs),
        "spend": round(spend),
        # 취소행의 음수 전액을 섞으면 '거래 전액'이 청구액보다 작아져 되레 헷갈린다.
        "total_amount": round(sum(t["total"] for t in txs if t["tx_type"] != cards.model.CANCEL)),
        "fee": round(sum(t["fee"] for t in txs)),
        "by_tx_type": sorted(({"tx_type": k, "amount": round(v)} for k, v in by_type.items()),
                             key=lambda x: -x["amount"]),
        "by_card": sorted(({"card": k, "amount": round(v)} for k, v in by_card.items()),
                          key=lambda x: -x["amount"]),
        "date_range": [min((t["date"] for t in txs), default=""),
                       max((t["date"] for t in txs), default="")],
    }


__all__ = [
    "CATEGORIES", "ISSUERS", "add_transactions", "cards", "cards_overview", "categories",
    "categorize", "clear_import", "clear_month", "cycles", "delete_transaction",
    "import_csv", "import_file", "installments", "mailbox", "months_of", "move_month",
    "fixed_costs", "parse_payslip", "payslip", "plan", "preview_file",
    "recalc_billing_months", "recurring",
    "set_category", "set_cycle", "set_fixed", "set_income", "state", "store", "summary",
]
