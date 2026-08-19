"""롯데카드 결제예정금액 파서 (일시불 / 할부).

신한과 마찬가지로 확장자만 ``.xls`` 이고 내용은 HTML 표인데, **구조가 다르다.**
컬럼 9개:

    이용일자 | 이용카드 | 가맹점명 | 이용금액 | 청구원금 | 수수료·이자 | 연체이자 | 회차 | 잔여원금

**어느 금액을 지출로 잡는가.** ``청구원금 + 수수료·이자 + 연체이자`` 다.
``이용금액`` 은 거래 전액이라 할부면 이번 달 나갈 돈과 다르다(``total`` 로 따로 보관).

**청구월이 파일에 없다.** 제목은 '일시불 결제예정금액' 뿐이고 파일명 뒤 숫자는
내려받은 시각(``_20260819092636``)이지 결제일이 아니다. 그래서 청구월을 비워
돌려주고, 등록 화면에서 사용자가 고르게 한다. 여기서 거래월을 청구월인 척
채우면 청구월 기준인 신한 내역과 같은 달에 섞여 합계의 뜻이 무너진다.

**합계 행 함정.** 마지막 '합계' 행은 셀 수가 헤더보다 적어(colspan) 컬럼이 한 칸씩
밀려 있다. 날짜 칸이 '합계'라 날짜 파싱에서 걸러지므로 따로 처리하지 않는다.
"""
from __future__ import annotations

from . import model as M

ISSUER = "롯데카드"


def detect(sheet) -> bool:
    text = sheet.text or ""
    if "롯데카드" in text or "lottecard" in text.lower():
        return True
    joined = " ".join(" ".join(r) for r in sheet.rows[:20])
    # 롯데 특유의 조합 — '청구원금'과 '잔여원금'을 같이 쓰는 카드사가 드물다.
    return "청구원금" in joined and "잔여원금" in joined and "이용일자" in joined


def _col(cells: list[str], *needles: str, exclude: tuple[str, ...] = ()) -> int:
    for j, c in enumerate(cells):
        if any(n in c for n in needles) and not any(x in c for x in exclude):
            return j
    return -1


def _find_header(table: list[list[str]]) -> tuple[int, dict[str, int]] | None:
    for i, row in enumerate(table[:20]):
        date = _col(row, "이용일자", "이용일")
        principal = _col(row, "청구원금")
        if date == -1 or principal == -1:
            continue
        return i, {
            "date": date,
            "charged": principal,
            "merchant": _col(row, "가맹점"),
            "card": _col(row, "이용카드", "카드"),
            "total": _col(row, "이용금액", exclude=("청구", "잔여")),
            "fee": _col(row, "수수료", "이자", exclude=("연체",)),
            "late": _col(row, "연체"),
            "seq": _col(row, "회차"),
            "remaining": _col(row, "잔여원금", "잔여", "잔액"),
        }
    return None


def _cell(row: list[str], idx: int) -> str:
    return row[idx].strip() if 0 <= idx < len(row) else ""


def _seq_months(raw: str) -> tuple[int, int]:
    """회차 칸은 '3/12' 또는 '3' 로 온다 → (회차, 개월). 비었으면 (0, 0)."""
    nums = [int(n) for n in "".join(ch if ch.isdigit() else " " for ch in raw).split()]
    if len(nums) >= 2:
        return nums[0], nums[1]
    return (nums[0], 0) if nums else (0, 0)


def parse(sheet) -> list[dict]:
    text = sheet.text or ""
    # 같은 포맷으로 일시불용·할부용 파일이 따로 나온다 — 파일명/제목으로 구분한다.
    filename = text.split("\n", 1)[0]
    section_installment = "할부" in filename or "할부 결제예정" in text or "할부결제예정" in text
    # '결제예정금액' 에는 청구월이 없다. 지어내지 말고 비워 둔다(호출부가 추정치를 넣고
    # '추정' 으로 표시한다). 거래일을 청구월인 척 채우면 청구월 기준인 신한 내역과
    # 같은 달에 섞여 그 달 합계가 무엇을 뜻하는지 알 수 없어진다.
    billing = M.title_month(text)

    out: list[dict] = []
    for table in sheet.tables:
        found = _find_header(table)
        if not found:
            continue
        hidx, c = found
        for row in table[hidx + 1:]:
            date = M.norm_date(_cell(row, c["date"]))
            if not date:
                continue                       # 헤더 반복 · 합계 행
            charged = M.clean_amt(_cell(row, c["charged"]))
            total = M.clean_amt(_cell(row, c["total"]))
            if charged is None and total is None:
                continue
            if charged is None:
                charged = total
            if total is None:
                total = charged
            fee = (M.clean_amt(_cell(row, c["fee"])) or 0.0) \
                + (M.clean_amt(_cell(row, c["late"])) or 0.0)
            seq, months = _seq_months(_cell(row, c["seq"]))
            remaining = M.clean_amt(_cell(row, c["remaining"])) or 0.0
            merchant = _cell(row, c["merchant"])

            if charged < 0 or "취소" in merchant or "환불" in merchant:
                ttype = M.CANCEL
            elif section_installment or remaining > 0 or months > 1 or seq > 0:
                ttype = M.INSTALLMENT
            else:
                ttype = M.LUMP
            inst = ({"months": months, "seq": seq, "remaining": round(remaining)}
                    if ttype == M.INSTALLMENT else None)

            out.append(M.make_tx(
                date=date, merchant=merchant, charged=charged, fee=fee, total=total,
                billing_month=billing, issuer=ISSUER,
                card=M.card_label(_cell(row, c["card"])), tx_type=ttype, installment=inst,
            ))
    return out
