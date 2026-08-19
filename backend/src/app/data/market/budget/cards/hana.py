"""하나카드 '카드이용내역 조회' 파서.

이건 **진짜 엑셀(OLE2 .xls)** 이다. 카드사마다 확장자와 실제 포맷의 관계가 제각각이라
(신한·롯데는 HTML, 하나는 BIFF, 삼성은 xlsx) ``tables`` 가 내용으로 판별한다.

    이용일 | 이용시간 | 이용카드 | 승인번호 | 가맹점명 | 승인금액 | 포인트 사용 |
    이용구분 | 할부 기간 | 매입 | 매입금액 | 매입할인 금액 | 매입취소금액 | 상태

**어느 금액을 지출로 잡는가.** ``매입금액`` 이다. 승인금액 14,160 이 매입에서
14,047 + 매입할인 113 으로 갈리는데, 통장에서 빠지는 건 매입금액 쪽이다.
할인율이 가맹점마다 다르므로(0.8% · 4% · 0%) 고정 비율로 역산하면 안 된다.

**아직 매입 전인 건.** ``미매입`` 이면 매입금액이 0 이다. 이건 '공짜'가 아니라
'아직 안 넘어왔다' 는 뜻이라 승인금액을 쓴다. 매입금액을 그대로 쓰면 최근 며칠치
지출이 통째로 0 원이 된다.

**청구월이 없다.** 이 파일은 명세서가 아니라 기간 조회 결과라 결제일 정보가 없다.
청구월을 비워 돌려주고 등록 화면에서 사용자가 고른다.
"""
from __future__ import annotations

from . import model as M

ISSUER = "하나카드"


def detect(sheet) -> bool:
    text = sheet.text or ""
    if "하나카드" in text or "hanacard" in text.lower():
        return True
    joined = " ".join(" ".join(r) for r in sheet.rows[:20])
    # '매입할인 금액' + '승인번호' 조합은 이 포맷 말고 본 적이 없다.
    return "승인번호" in joined and "매입할인" in joined and "가맹점명" in joined


def _col(cells: list[str], *needles: str, exclude: tuple[str, ...] = ()) -> int:
    for j, c in enumerate(cells):
        if any(n in c for n in needles) and not any(x in c for x in exclude):
            return j
    return -1


def _find_header(table: list[list[str]]) -> tuple[int, dict[str, int]] | None:
    for i, row in enumerate(table[:20]):
        date = _col(row, "이용일", exclude=("시간",))
        approved = _col(row, "승인금액")
        if date == -1 or approved == -1:
            continue
        return i, {
            "date": date,
            "approved": approved,
            "merchant": _col(row, "가맹점"),
            "card": _col(row, "이용카드"),
            "point": _col(row, "포인트"),
            "kind": _col(row, "이용구분"),
            "months": _col(row, "할부"),
            # '매입' · '매입금액' · '매입할인 금액' · '매입취소금액' 이 전부 '매입' 으로 시작한다.
            "captured": _col(row, "매입", exclude=("금액", "할인", "취소")),
            "capture_amt": _col(row, "매입금액"),
            "discount": _col(row, "매입할인"),
            "cancel_amt": _col(row, "매입취소"),
            "status": _col(row, "상태"),
        }
    return None


def _cell(row: list[str], idx: int) -> str:
    return row[idx].strip() if 0 <= idx < len(row) else ""


def _months(raw: str) -> int:
    """할부 기간은 '-' 또는 '3개월' 로 온다."""
    digits = "".join(ch for ch in raw if ch.isdigit())
    return int(digits) if digits else 0


def parse(sheet) -> list[dict]:
    out: list[dict] = []
    for table in sheet.tables:
        found = _find_header(table)
        if not found:
            continue
        hidx, c = found
        for row in table[hidx + 1:]:
            date = M.norm_date(_cell(row, c["date"]))
            if not date:
                continue                       # 제목 · 조회기간 · 합계 · '이하 여백'
            approved = M.clean_amt(_cell(row, c["approved"]))
            if approved is None:
                continue
            captured = M.clean_amt(_cell(row, c["capture_amt"]))
            point = M.clean_amt(_cell(row, c["point"])) or 0.0
            cancel = M.clean_amt(_cell(row, c["cancel_amt"])) or 0.0
            status = _cell(row, c["status"])
            kind = _cell(row, c["kind"])
            merchant = _cell(row, c["merchant"])
            months = _months(_cell(row, c["months"]))
            settled = "미매입" not in _cell(row, c["captured"])

            if "취소" in status or "취소" in kind or cancel > 0:
                ttype = M.CANCEL
                charged = -abs(cancel or captured or approved)
            else:
                # 매입된 건은 할인 반영된 매입금액, 아직 안 넘어온 건은 승인금액.
                charged = captured if (settled and captured) else max(0.0, approved - point)
                if "해외" in kind:
                    ttype = M.OVERSEAS
                elif "현금서비스" in kind or "카드론" in kind or "카드대출" in kind:
                    ttype = M.CASH
                elif "할부" in kind or months > 1:
                    ttype = M.INSTALLMENT
                else:
                    ttype = M.LUMP

            # 이 조회에는 회차·잔액이 없다 — 개월만 남기고 잔액 0 으로 두면
            # 할부 스케줄 추정에서 알아서 빠진다(없는 값을 지어내지 않는다).
            inst = {"months": months, "seq": 0, "remaining": 0} if ttype == M.INSTALLMENT else None

            out.append(M.make_tx(
                date=date, merchant=merchant, charged=charged, fee=0.0, total=approved,
                billing_month="",              # 조회 결과라 청구월을 알 수 없다
                issuer=ISSUER, card=M.card_label(_cell(row, c["card"])),
                tx_type=ttype, installment=inst,
            ))
    return out
