"""신한카드 이용대금명세서 파서.

내려받은 파일은 확장자만 ``.xls`` 이고 실제로는 HTML 표다(``tables`` 가 처리).
컬럼은 12개:

    거래일자 | 이용카드 | 이용가맹점 | 거래금액 | 적립예정마이신한포인트율 |
    이용개월 | 청구회차 | 결제 금액 | 사용포인트 | 수수료(이자) | 결제 후 잔액 | 거래구분

**어느 금액을 지출로 잡는가.** ``거래금액`` 이 아니라 ``결제 금액 + 수수료(이자)`` 다.
세 가지가 여기서 갈린다.

* 할부 — 거래금액 2,475,041 이지만 6개월 1회차라 이번 달엔 412,541 + 수수료 57,732 만
  빠진다. 거래금액을 쓰면 그 달 지출이 5배로 부풀고 저축 가능액이 음수로 뒤집힌다.
* 포인트 사용 — 거래금액 22,500 / 결제 금액 22,000 처럼 500 원이 포인트로 빠진다.
  통장에서 나가는 건 22,000 이다.
* 취소 — 취소행은 거래금액이 음수지만 ``결제 금액`` 이 **0** 이다. 이번 청구에
  영향이 없다는 뜻이라 0 으로 잡히는 게 맞다.

**청구월.** 거래일이 아니라 제목의 ``2026년9월 예정 이용대금명세서`` 에서 읽는다.
7/20 에 긁어도 돈은 9월에 빠지므로, 가계부의 달은 청구월이어야 통장과 맞는다.
"""
from __future__ import annotations

from . import model as M

ISSUER = "신한카드"

# 표 밖 제목·머리말에 하나라도 있으면 신한 명세서로 본다.
_SIGNS = ("마이신한포인트", "신한카드", "shinhancard", "신한 카드")


def detect(sheet) -> bool:
    text = (sheet.text or "")
    if any(s in text for s in _SIGNS):
        return True
    # 제목이 잘려 나간 파일 대비 — 신한 특유의 컬럼 조합으로 판별
    joined = " ".join(" ".join(r) for r in sheet.rows[:20])
    return "이용가맹점" in joined and "청구회차" in joined and "결제 후 잔액" in joined


def _col(cells: list[str], *needles: str, exclude: tuple[str, ...] = ()) -> int:
    for j, c in enumerate(cells):
        if any(n in c for n in needles) and not any(x in c for x in exclude):
            return j
    return -1


def _find_header(table: list[list[str]]) -> tuple[int, dict[str, int]] | None:
    """헤더 행을 찾아 컬럼 위치를 매핑한다.

    신한 HTML 은 첫 셀에 안내문이 통째로 들어있고 그 끝에 '거래일자'가 붙어 있어서
    셀이 정확히 일치하지 않는다 — 그래서 전부 부분일치로 찾는다.
    """
    for i, row in enumerate(table[:20]):
        date = _col(row, "거래일자", "이용일자", "매출일자")
        merch = _col(row, "이용가맹점", "가맹점")
        if date == -1 or merch == -1:
            continue
        cols = {
            "date": date,
            "merchant": merch,
            "card": _col(row, "이용카드", "카드명", "카드번호"),
            "total": _col(row, "거래금액", "이용금액", exclude=("결제", "잔액")),
            "months": _col(row, "이용개월", "할부개월"),
            "seq": _col(row, "청구회차", "회차"),
            # '결제 금액' 과 '결제 후 잔액' 이 둘 다 '결제' 로 시작한다 — 잔액을 뺀다.
            "charged": _col(row, "결제 금액", "결제금액", "청구금액", exclude=("잔액", "누계")),
            "fee": _col(row, "수수료", "이자"),
            "remaining": _col(row, "잔액"),
            "kind": _col(row, "거래구분", "이용구분", "결제구분"),
        }
        return i, cols
    return None


def _cell(row: list[str], idx: int) -> str:
    return row[idx].strip() if 0 <= idx < len(row) else ""


def _tx_type(kind: str, merchant: str, total: float, fee: float, months: int) -> str:
    k = kind or ""
    if "취소" in k or "취소" in merchant or "환불" in merchant or total < 0:
        return M.CANCEL
    if "현금서비스" in k or "단기카드대출" in k or "카드론" in k or "장기카드대출" in k:
        return M.CASH
    if "해외" in k:
        return M.OVERSEAS
    if "할부" in k or "분할" in k or months > 1:
        return M.INSTALLMENT
    # 국내 일시불은 수수료가 붙지 않는다 — 붙었다면 해외이용수수료다.
    if fee > 0 and months <= 1:
        return M.OVERSEAS
    return M.LUMP if k else M.ETC


def parse(sheet) -> list[dict]:
    billing = M.norm_month(sheet.text) or ""
    out: list[dict] = []
    for table in sheet.tables:
        found = _find_header(table)
        if not found:
            continue
        hidx, c = found
        for row in table[hidx + 1:]:
            date = M.norm_date(_cell(row, c["date"]))
            if not date:
                continue                       # 헤더 반복·합계·안내 행
            total = M.clean_amt(_cell(row, c["total"]))
            charged = M.clean_amt(_cell(row, c["charged"]))
            if total is None and charged is None:
                continue
            fee = M.clean_amt(_cell(row, c["fee"])) or 0.0
            months = int(M.clean_amt(_cell(row, c["months"])) or 0)
            seq = int(M.clean_amt(_cell(row, c["seq"])) or 0)
            remaining = M.clean_amt(_cell(row, c["remaining"])) or 0.0
            merchant = _cell(row, c["merchant"])
            kind = _cell(row, c["kind"])
            if total is None:
                total = charged
            if charged is None:                # 결제 금액 컬럼이 없는 명세서
                charged = total

            ttype = _tx_type(kind, merchant, total, fee, months)
            inst = None
            if ttype == M.INSTALLMENT or months > 1:
                inst = {"months": months, "seq": seq, "remaining": round(remaining)}

            out.append(M.make_tx(
                date=date, merchant=merchant, charged=charged, fee=fee, total=total,
                billing_month=billing or date[:7], issuer=ISSUER,
                card=_cell(row, c["card"]), tx_type=ttype, installment=inst,
            ))
    return out
