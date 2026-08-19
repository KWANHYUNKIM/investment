"""카드사별 명세서 파서 — 여기에 모듈 하나를 더 얹으면 카드사가 하나 늘어난다.

카드사마다 컬럼 이름도 다르고 금액의 의미도 다르다(신한은 거래금액과 결제금액이
따로다). 그래서 '범용 파서 하나 + 예외처리' 로는 계속 틀린다. 카드사별 모듈이
자기 파일을 알아보고(``detect``) 자기 규칙으로 읽는(``parse``) 구조로 둔다.

카드사 추가하는 법
------------------
1. ``cards/<카드사>.py`` 를 만들고 세 가지를 노출한다.

       ISSUER = "롯데카드"
       def detect(sheet) -> bool:   # sheet.text / sheet.rows 로 판별
       def parse(sheet) -> list[dict]:  # model.make_tx 로 만든 거래 목록

2. 아래 ``_PARSERS`` 에 등록한다(위에서부터 먼저 물어본다).
3. 금액은 반드시 **그 청구월에 실제 빠지는 돈**으로 넣는다(``model`` 문서 참고).

아무도 손을 들지 않으면 ``generic`` 이 헤더 이름으로 추정하고, 그것도 실패하면
줄 단위 휴리스틱(``generic.loose``)까지 내려간다. 어느 단계에서 읽혔는지는
``parsed_by`` 로 돌려주므로 화면에서 "추정으로 읽었습니다" 를 띄울 수 있다.
"""
from __future__ import annotations

from . import generic, model, shinhan, tables

# 위에서부터 detect() 를 물어본다. 전용 파서를 항상 generic 보다 앞에 둔다.
_PARSERS = [shinhan]

ISSUERS = [m.ISSUER for m in _PARSERS]


def parse_file(filename: str, data: bytes) -> dict:
    """카드사 파일 → 정규화 거래 목록 + 어떻게 읽었는지.

    반환: ``{issuer, billing_month, file_kind, parsed_by, transactions, note}``
    """
    sheet = tables.read(filename or "", data or b"")

    for mod in _PARSERS:
        try:
            if mod.detect(sheet):
                txs = mod.parse(sheet)
                if txs:
                    return _report(mod.ISSUER, mod.__name__.rsplit(".", 1)[-1], sheet, txs)
        except Exception:
            continue        # 한 카드사 파서가 죽어도 나머지·폴백은 살아 있어야 한다

    txs = generic.parse(sheet)
    if txs:
        return _report("", "generic", sheet, txs,
                       note="전용 파서가 없는 카드사입니다 — 컬럼 이름으로 추정해 읽었습니다. "
                            "금액이 맞는지 확인해 주세요.")

    # 줄 단위 휴리스틱은 구분자가 살아 있어야 한다 — 표로 접힌 행이 아니라 원문을 준다.
    text = sheet.raw or "\n".join("\t".join(r) for r in sheet.rows)
    txs = generic.loose(text)
    return _report("", "loose", sheet, txs,
                   note=("표 형태를 알아보지 못해 줄 단위로 추정했습니다. 금액·가맹점을 확인하세요."
                         if txs else
                         "거래를 하나도 찾지 못했습니다. 카드사에서 받은 원본 파일인지 확인해 주세요."))


def _report(issuer: str, parsed_by: str, sheet, txs: list[dict], note: str = "") -> dict:
    months = sorted({t["billing_month"] for t in txs if t.get("billing_month")})
    return {
        "issuer": issuer,
        "billing_month": months[-1] if len(months) == 1 else (months[-1] if months else ""),
        "billing_months": months,
        "file_kind": sheet.kind,
        "parsed_by": parsed_by,
        "transactions": txs,
        "note": note or f"{issuer or '카드'} 명세서에서 {len(txs)}건을 읽었습니다.",
    }


__all__ = ["ISSUERS", "parse_file", "model", "tables"]
