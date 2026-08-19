"""삼성카드 결제예정내역 파서 (시트마다 일시불 / 할부 / 해외 …).

세 카드사 중 유일하게 **진짜 xlsx** 다(Apache POI 로 만들어져 서식이 없다).
시트 첫 줄에 구획 이름('할부')이 있고 그 아래에 헤더가 온다.

    이용일 | 이용구분 | 가맹점 | 이용금액 | 총할부금액 | 이용혜택 | 혜택금액 |
    개월 | 회차 | 원금 | 이자/수수료 | 포인트명 | 적립금액 | 입금후잔액

**컬럼 이름에 속으면 안 되는 곳.** ``이용구분`` 에 들어오는 값은 거래구분이 아니라
카드 명의다(``본 인 654``). 거래구분은 시트 첫 줄의 구획 이름에 있다.

**어느 금액을 지출로 잡는가.** ``원금 + 이자/수수료`` 다. 예: 쿠팡 1,671,290 원을
12개월 할부로 긁고 3회차면 이번 달은 139,200 원이고 입금후잔액 1,252,800
(= 139,200 × 남은 9회차)이 남는다. ``이용금액`` 을 쓰면 12배가 잡힌다.

``혜택금액`` 은 더하지 않는다 — '이자면제' 같은 혜택은 이미 ``이자/수수료`` 에
반영돼 있어서, 또 빼면 두 번 깎인다. 원금 컬럼이 없는 구획(일시불)에서만
음수 혜택금액(청구할인)을 반영한다.

**청구월.** 파일명 ``samsungcard_20260801.xlsx`` 의 날짜가 결제 기준일이다
(5/17 구매 → 12개월 할부 3회차 = 2026-08 로 맞아떨어진다). 파일명이 다르면
비워 두고 등록 화면에서 사용자가 고른다.
"""
from __future__ import annotations

import re

from . import model as M

ISSUER = "삼성카드"

_FILE_DATE = re.compile(r"(20\d{2})(\d{2})(\d{2})")


def detect(sheet) -> bool:
    text = (sheet.text or "").lower()
    if "samsungcard" in text or "삼성카드" in (sheet.text or ""):
        return True
    joined = " ".join(" ".join(r) for r in sheet.rows[:20])
    return "입금후잔액" in joined and "이자/수수료" in joined and "이용혜택" in joined


def _billing_from_filename(text: str) -> str:
    """파일명 첫 줄의 ``samsungcard_20260801`` → ``2026-08``."""
    first = (text or "").split("\n", 1)[0]
    if "samsungcard" not in first.lower():
        return ""
    m = _FILE_DATE.search(first)
    if not m:
        return ""
    mo = int(m.group(2))
    return f"{m.group(1)}-{mo:02d}" if 1 <= mo <= 12 else ""


def _col(cells: list[str], *needles: str, exclude: tuple[str, ...] = ()) -> int:
    for j, c in enumerate(cells):
        if any(n in c for n in needles) and not any(x in c for x in exclude):
            return j
    return -1


def _find_header(table: list[list[str]]) -> tuple[int, dict[str, int]] | None:
    for i, row in enumerate(table[:20]):
        date = _col(row, "이용일")
        merch = _col(row, "가맹점")
        if date == -1 or merch == -1:
            continue
        return i, {
            "date": date,
            "merchant": merch,
            # '이용구분' 은 이름과 달리 카드 명의가 들어온다.
            "card": _col(row, "이용구분", "카드"),
            "total": _col(row, "이용금액", exclude=("총할부",)),
            "total_inst": _col(row, "총할부금액"),
            "benefit": _col(row, "혜택금액"),
            "months": _col(row, "개월"),
            "seq": _col(row, "회차"),
            "charged": _col(row, "원금"),
            "fee": _col(row, "이자", "수수료"),
            "remaining": _col(row, "입금후잔액", "잔액"),
        }
    return None


def _cell(row: list[str], idx: int) -> str:
    return row[idx].strip() if 0 <= idx < len(row) else ""


def _section(table: list[list[str]], hidx: int) -> str:
    """헤더 위의 한 칸짜리 행이 구획 이름('할부' · '일시불' · '해외이용')."""
    for row in reversed(table[:hidx]):
        vals = [c for c in row if c]
        if len(vals) == 1:
            return vals[0]
    return ""


def _tx_type(section: str, months: int, charged: float) -> str:
    if charged < 0:
        return M.CANCEL
    if "취소" in section:
        return M.CANCEL
    if "해외" in section:
        return M.OVERSEAS
    if "현금서비스" in section or "카드론" in section or "카드대출" in section:
        return M.CASH
    if "할부" in section or months > 1:
        return M.INSTALLMENT
    return M.LUMP


def parse(sheet) -> list[dict]:
    billing = _billing_from_filename(sheet.text)
    out: list[dict] = []
    for table in sheet.tables:
        found = _find_header(table)
        if not found:
            continue
        hidx, c = found
        section = _section(table, hidx)
        for row in table[hidx + 1:]:
            date = M.norm_date(_cell(row, c["date"]))
            if not date:
                continue                       # 구획 제목 · '할부합계' 행
            principal = M.clean_amt(_cell(row, c["charged"]))
            fee = M.clean_amt(_cell(row, c["fee"])) or 0.0
            used = M.clean_amt(_cell(row, c["total"]))
            total_inst = M.clean_amt(_cell(row, c["total_inst"]))
            benefit = M.clean_amt(_cell(row, c["benefit"])) or 0.0
            months = int(M.clean_amt(_cell(row, c["months"])) or 0)
            seq = int(M.clean_amt(_cell(row, c["seq"])) or 0)
            remaining = M.clean_amt(_cell(row, c["remaining"])) or 0.0

            if principal is not None:
                # 할부 — 혜택은 이미 이자/수수료에 반영돼 있어 다시 빼지 않는다.
                charged = principal
            elif used is not None:
                # 일시불 — 음수 혜택금액(청구할인)만 반영한다.
                charged = used + min(0.0, benefit)
            else:
                continue
            total = total_inst if total_inst else (used if used is not None else charged)

            ttype = _tx_type(section, months, charged)
            inst = ({"months": months, "seq": seq, "remaining": round(remaining)}
                    if ttype == M.INSTALLMENT else None)

            out.append(M.make_tx(
                date=date, merchant=_cell(row, c["merchant"]), charged=charged, fee=fee,
                total=total, billing_month=billing, issuer=ISSUER,
                card=M.card_label(_cell(row, c["card"])), tx_type=ttype, installment=inst,
            ))
    return out
