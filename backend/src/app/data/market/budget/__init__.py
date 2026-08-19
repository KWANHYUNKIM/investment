"""가계부 — 카드 명세서 취합 · 지출 분리 · 저축/투자 계획.

원래 파일 하나였는데, 카드사가 늘면 늘수록 파싱이 전체를 잡아먹어서 갈랐다.

    cards/       카드사별 명세서 파서 (카드사 추가는 여기에만)
    categories   가맹점 → 카테고리, 고정비/변동비 판정
    store        data/budget_<계정>.json 읽기·쓰기, 중복 방지
    summary      네 축 집계(카테고리·카드·거래구분·고정비) + 할부 미래 부담 + 계획
    payslip      급여명세서에서 실수령액 추출

이 모듈은 그 다섯을 하나의 API 로 묶는다. 예전 호출부(``budget.summary`` 등)가
그대로 동작하도록 이름을 유지한다.
"""
from __future__ import annotations

from . import cards, categories, payslip, store
from .categories import CATEGORIES, categorize
from .store import (add_transactions, clear_import, clear_month, delete_transaction,
                    move_month, set_category, set_fixed, set_income)
from .summary import installments, months_of, plan, state, summary

ISSUERS = cards.ISSUERS


def preview_file(filename: str, data: bytes) -> dict:
    """저장하지 않고 파싱만 — 화면에서 확인한 뒤 등록하게 한다.

    금액의 의미가 카드사마다 달라서(할부·포인트·취소) 바로 저장하면 틀린 걸
    나중에 찾기 어렵다. 먼저 보여주고 사용자가 확인한 것만 넣는다.
    """
    rep = cards.parse_file(filename or "", data or b"")
    txs = rep["transactions"]
    rep["stats"] = _stats(txs)
    rep["filename"] = filename
    return rep


def import_file(user: str, filename: str, data: bytes) -> dict:
    """카드사 파일 업로드 → 파싱 후 바로 등록(중복은 지문으로 거른다)."""
    rep = cards.parse_file(filename or "", data or b"")
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
    "CATEGORIES", "ISSUERS", "add_transactions", "cards", "categories", "categorize",
    "clear_import", "clear_month", "delete_transaction", "import_csv", "import_file",
    "installments", "months_of", "move_month", "parse_payslip", "payslip", "plan",
    "preview_file", "set_category", "set_fixed", "set_income", "state", "store", "summary",
]
