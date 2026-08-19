"""아직 전용 파서가 없는 카드사용 폴백 — 헤더 이름으로 컬럼을 추정한다.

전용 파서(``shinhan`` 등)가 하나도 손을 들지 않을 때만 쓴다. 카드사마다 컬럼
이름이 달라 '결제금액/이용금액/승인금액' 같은 후보를 넓게 잡되, **금액이 아닌데
금액처럼 생긴 컬럼**(한도·잔액·포인트·누계)은 명시적으로 배제한다. 여기서
헛짚으면 지출이 통째로 틀리기 때문에 배제 목록이 후보 목록보다 중요하다.

헤더조차 못 찾으면 ``loose`` 가 줄 단위 휴리스틱으로 한 번 더 시도한다(사용자가
표를 그냥 복사해 붙여넣은 경우).
"""
from __future__ import annotations

import re

from . import model as M

ISSUER = ""     # 카드사 미상

_H_DATE = ["거래일", "이용일", "승인일", "매출일", "사용일", "일자", "날짜", "거래일시"]
_H_MERCH = ["가맹점", "상호", "이용내역", "적요", "내용", "이용하신곳", "가맹점명", "이용처"]
_H_AMT_STRONG = ["이용금액", "승인금액", "결제금액", "결제 금액", "매출금액", "사용금액",
                 "국내이용금액", "이용하신금액", "청구금액", "거래금액"]
_H_AMT_WEAK = ["금액", "합계"]
_H_AMT_BAD = ["번호", "한도", "잔액", "포인트", "누계", "수수료", "해외", "세금",
              "봉사료", "면세", "적립", "할인", "율"]
_H_KIND = ["거래구분", "이용구분", "결제구분", "할부", "구분", "상태"]
_H_CARD = ["카드명", "카드번호", "이용카드", "카드"]
_H_FEE = ["수수료", "이자"]


def _has(cell: str, cands: list[str], bad: list[str] | None = None) -> bool:
    return any(k in cell for k in cands) and not (bad and any(b in cell for b in bad))


def _find_header(table: list[list[str]]) -> tuple[int, dict[str, int]] | None:
    for i, row in enumerate(table[:20]):
        d = next((j for j, c in enumerate(row) if _has(c, _H_DATE)), -1)
        a = next((j for j, c in enumerate(row) if _has(c, _H_AMT_STRONG, _H_AMT_BAD)), -1)
        if a == -1:
            a = next((j for j, c in enumerate(row) if _has(c, _H_AMT_WEAK, _H_AMT_BAD)), -1)
        if d == -1 or a == -1:
            continue
        return i, {
            "date": d,
            "amount": a,
            "merchant": next((j for j, c in enumerate(row) if _has(c, _H_MERCH)), -1),
            "kind": next((j for j, c in enumerate(row) if _has(c, _H_KIND)), -1),
            "card": next((j for j, c in enumerate(row) if _has(c, _H_CARD)), -1),
            "fee": next((j for j, c in enumerate(row) if _has(c, _H_FEE)), -1),
        }
    return None


def _cell(row: list[str], idx: int) -> str:
    return row[idx].strip() if 0 <= idx < len(row) else ""


def _tx_type(kind: str, merchant: str, amount: float) -> str:
    blob = f"{kind} {merchant}"
    if "취소" in blob or "환불" in blob or amount < 0:
        return M.CANCEL
    if "현금서비스" in blob or "카드론" in blob or "카드대출" in blob:
        return M.CASH
    if "해외" in blob:
        return M.OVERSEAS
    if "할부" in blob or "분할" in blob:
        return M.INSTALLMENT
    return M.LUMP


def parse(sheet) -> list[dict]:
    billing = M.title_month(sheet.text)
    out: list[dict] = []
    for table in sheet.tables:
        found = _find_header(table)
        if not found:
            continue
        hidx, c = found
        for row in table[hidx + 1:]:
            date = M.norm_date(_cell(row, c["date"]))
            amt = M.clean_amt(_cell(row, c["amount"]))
            if not date or amt is None:
                continue
            merchant = _cell(row, c["merchant"]) or "미상"
            kind = _cell(row, c["kind"])
            fee = M.clean_amt(_cell(row, c["fee"])) or 0.0
            ttype = _tx_type(kind, merchant, amt)
            if ttype == M.CANCEL:
                amt = -abs(amt)
            out.append(M.make_tx(
                date=date, merchant=merchant, charged=amt, fee=fee, total=amt,
                # 청구월을 못 찾으면 빈 값 — parse_file 이 추정치를 넣고 사용자가 고친다.
                billing_month=billing, issuer=ISSUER,
                card=M.card_label(_cell(row, c["card"])), tx_type=ttype,
            ))
    return out


# --- 헤더가 아예 없을 때 --------------------------------------------------
_INT = re.compile(r"-?\d+")
_DATEISH = re.compile(r"20\d{2}[.\-/]\d{1,2}[.\-/]\d{1,2}")


def loose(text: str) -> list[dict]:
    """표를 그냥 복사해 붙여넣은 텍스트에서 날짜·가맹점·금액을 추정한다.

    한 줄에서: 날짜 1개, 순수 정수 필드 중 절댓값 최대를 금액, 나머지 중 가장 긴
    텍스트를 가맹점으로 본다. 날짜가 없는 줄(헤더·합계·안내)은 버린다.
    """
    out: list[dict] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        date = M.norm_date(line)
        if not date:
            continue
        # 천 단위 콤마를 먼저 없애야 필드 구분 콤마와 헷갈리지 않는다.
        norm = re.sub(r"(?<=\d),(?=\d)", "", line)
        fields = [f.strip() for f in re.split(r"[\t,]", norm) if f.strip()]

        amounts = []
        for f in fields:
            if _DATEISH.search(f):
                continue
            fx = f.replace(" ", "").replace("원", "")
            if _INT.fullmatch(fx):
                amounts.append(float(fx))
        if not amounts:
            continue
        amount = max(amounts, key=abs)

        cand = [f for f in fields
                if not _DATEISH.search(f) and not _INT.fullmatch(f.replace(" ", "").replace("원", ""))]
        merchant = max(cand, key=len) if cand else "미상"
        out.append(M.make_tx(date=date, merchant=merchant, charged=amount, total=amount,
                             billing_month=date[:7],
                             tx_type=M.CANCEL if amount < 0 else M.LUMP))
    return out
