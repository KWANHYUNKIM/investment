"""카드 명세서 파서가 공통으로 뱉는 거래 한 건의 모양.

카드사마다 컬럼 이름도, 금액의 **의미**도 다르다. 신한은 `거래금액`(전액)과
`결제 금액`(이번 청구분)을 따로 주고, 할부면 두 값이 다르다. 다른 카드사는
한 컬럼만 주기도 한다. 그래서 파서는 컬럼을 옮겨 담는 게 아니라 **이 스키마의
의미에 맞춰 해석**해야 한다.

핵심 규칙 — ``amount`` 는 *그 청구월에 통장에서 실제로 빠지는 돈*이다.
할부면 이번 회차 결제금액 + 수수료이지 거래 전액이 아니다. 가계부의 '저축 가능액'
계산이 통장 잔고와 어긋나지 않으려면 이 하나를 지켜야 한다.

    date           거래일자 (YYYY-MM-DD)
    billing_month  청구월 (YYYY-MM) — 이 돈이 실제로 빠지는 달
    merchant       가맹점명 (원문 그대로)
    amount         그 달 지출 = charged + fee
    charged        결제 원금 (이번 회차분)
    fee            수수료·이자·해외이용수수료
    total          거래 전액 (할부 원금 총액, 일시불이면 charged 와 같음)
    issuer         카드사 ("신한카드")
    card           카드 식별 ("본인717") — 명의·카드별 분리 축
    tx_type        일시불 | 할부 | 해외 | 취소 | 현금서비스 | 기타
    installment    할부일 때 {months, seq, remaining}, 아니면 None
    category       지출 카테고리 (categories.categorize)
    fp             중복 등록 방지 지문
"""
from __future__ import annotations

import hashlib
import re

# 거래구분 — 명세서 문구가 카드사마다 달라 여기서 하나로 모은다.
LUMP = "일시불"
INSTALLMENT = "할부"
OVERSEAS = "해외"
CANCEL = "취소"
CASH = "현금서비스"
ETC = "기타"

TX_TYPES = [LUMP, INSTALLMENT, OVERSEAS, CANCEL, CASH, ETC]

_DATE = re.compile(r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})")
_DATE_COMPACT = re.compile(r"^(20\d{2})(\d{2})(\d{2})$")
_MONTH = re.compile(r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})")


def norm_date(s) -> str | None:
    """어떤 표기로 오든 ``YYYY-MM-DD``. 날짜가 없으면 None(헤더·합계 행)."""
    t = str(s or "").strip()
    m = _DATE_COMPACT.match(t.replace("-", "").replace(".", "").replace("/", ""))
    if m:
        y, mo, da = m.group(1), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= da <= 31:
            return f"{y}-{mo:02d}-{da:02d}"
    m = _DATE.search(t)
    if not m:
        return None
    y, mo, da = m.group(1), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12 and 1 <= da <= 31):
        return None
    return f"{y}-{mo:02d}-{da:02d}"


def norm_month(s) -> str | None:
    """``2026년9월 예정 이용대금명세서`` → ``2026-09``."""
    m = _MONTH.search(str(s or ""))
    if not m:
        return None
    mo = int(m.group(2))
    return f"{m.group(1)}-{mo:02d}" if 1 <= mo <= 12 else None


def clean_amt(s) -> float | None:
    """``"2,475,041원"`` → 2475041.0. 숫자가 없으면 None.

    빈 셀과 0 을 구분해야 한다 — 신한 취소행은 결제금액이 **0** 이라 '이번 달
    청구 없음'이라는 뜻이고, 빈 셀은 '그 컬럼이 없음'이라는 뜻이다.
    """
    t = str(s if s is not None else "").strip()
    if not t:
        return None
    neg = t.startswith("(") and t.endswith(")")   # 회계식 음수 표기
    t = t.strip("()")
    t = re.sub(r"[^\d.\-]", "", t)
    if not t or t in {"-", ".", "-."}:
        return None
    try:
        v = float(t)
    except ValueError:
        return None
    if v != v:      # NaN
        return None
    return -v if neg else v


def fingerprint(tx: dict) -> str:
    """같은 명세서를 두 번 올려도 거래가 두 배로 늘지 않게 하는 지문.

    회차(seq)까지 넣는 이유: 같은 할부의 1회차와 2회차는 날짜·가맹점·금액이
    모두 같을 수 있는데 **서로 다른 달에 나가는 다른 지출**이다.
    """
    inst = tx.get("installment") or {}
    key = "|".join(str(x) for x in (
        tx.get("issuer", ""), tx.get("card", ""), tx.get("date", ""),
        tx.get("billing_month", ""), tx.get("merchant", ""),
        tx.get("total", ""), tx.get("charged", ""), inst.get("seq", ""),
    ))
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def make_tx(*, date: str, merchant: str, charged: float, fee: float = 0.0,
            total: float | None = None, billing_month: str | None = None,
            issuer: str = "", card: str = "", tx_type: str = LUMP,
            installment: dict | None = None) -> dict:
    """정규화 거래 한 건을 만든다(카테고리·지문은 여기서 채운다)."""
    from ..categories import categorize

    charged = float(charged or 0)
    fee = float(fee or 0)
    tx = {
        "date": date,
        "billing_month": billing_month or (date[:7] if date else ""),
        "merchant": (merchant or "").strip() or "미상",
        "amount": round(charged + fee, 2),
        "charged": round(charged, 2),
        "fee": round(fee, 2),
        "total": round(float(total if total is not None else charged), 2),
        "issuer": issuer,
        "card": card,
        "tx_type": tx_type,
        "installment": installment,
    }
    tx["category"] = categorize(tx["merchant"])
    tx["fp"] = fingerprint(tx)
    return tx
