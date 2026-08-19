"""카드사별 명세서 파서 — 여기에 모듈 하나를 더 얹으면 카드사가 하나 늘어난다.

카드사마다 컬럼 이름도 다르고 금액의 의미도 다르다. 실제로 받아 본 네 곳이 전부
다른 방식이었다.

    신한  .xls 인데 HTML       거래금액 ≠ 결제 금액(+수수료)   청구월이 제목에 있음
    롯데  .xls 인데 HTML       이용금액 ≠ 청구원금(+수수료·연체이자)  청구월 없음
    하나  진짜 .xls (BIFF)     승인금액 ≠ 매입금액(즉시할인)   청구월 없음
    삼성  진짜 .xlsx           이용금액 ≠ 원금(+이자)          청구월이 파일명에 있음

'범용 파서 하나 + 예외처리' 로는 계속 틀린다. 카드사별 모듈이 자기 파일을
알아보고(``detect``) 자기 규칙으로 읽는(``parse``) 구조로 둔다.

카드사 추가하는 법
------------------
1. ``cards/<카드사>.py`` 를 만들고 세 가지를 노출한다.

       ISSUER = "우리카드"
       def detect(sheet) -> bool:   # sheet.text / sheet.rows 로 판별
       def parse(sheet) -> list[dict]:  # model.make_tx 로 만든 거래 목록

2. 아래 ``_PARSERS`` 에 등록한다(위에서부터 먼저 물어본다).
3. 금액은 반드시 **그 청구월에 실제 빠지는 돈**으로 넣는다(``model`` 문서 참고).
4. 청구월을 파일에서 알 수 없으면 ``billing_month=""`` 로 두고 지어내지 않는다 —
   아래에서 '마지막 거래월 +1' 로 추정하고, 화면에서 사용자가 고친다.

아무도 손을 들지 않으면 ``generic`` 이 헤더 이름으로 추정하고, 그것도 실패하면
줄 단위 휴리스틱(``generic.loose``)까지 내려간다. 어느 단계에서 읽혔는지는
``parsed_by`` 로 돌려주므로 화면에서 "추정으로 읽었습니다" 를 띄울 수 있다.
"""
from __future__ import annotations

from . import generic, hana, lotte, model, samsung, shinhan, tables

# 위에서부터 detect() 를 물어본다. 전용 파서를 항상 generic 보다 앞에 둔다.
_PARSERS = [shinhan, lotte, hana, samsung]

ISSUERS = [m.ISSUER for m in _PARSERS]


def parse_file(filename: str, data: bytes) -> dict:
    """카드사 파일 → 정규화 거래 목록 + 어떻게 읽었는지.

    반환: ``{issuer, billing_month, billing_month_known, file_kind, parsed_by,
    transactions, note}``
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


def _fill_billing_month(txs: list[dict]) -> tuple[bool, str]:
    """청구월을 안 알려준 파일은 '마지막 거래월 +1' 로 채운다.

    지어낸 값이라는 걸 호출부가 알아야 해서 known 플래그를 같이 돌려준다. 화면은
    이 값을 수정 가능한 입력으로 띄우고, 사용자가 고른 달이 최종이다.
    """
    missing = [t for t in txs if not t.get("billing_month")]
    if not missing:
        return True, ""
    last = max((t["date"][:7] for t in txs if t.get("date")), default="")
    guess = model.add_months(last, 1) if last else ""
    for t in missing:
        t["billing_month"] = guess
        t["fp"] = model.fingerprint(t)      # 지문이 청구월을 포함하므로 다시 만든다
    return False, guess


def _report(issuer: str, parsed_by: str, sheet, txs: list[dict], note: str = "") -> dict:
    known, guess = _fill_billing_month(txs)
    months = sorted({t["billing_month"] for t in txs if t.get("billing_month")})
    if not note:
        note = f"{issuer or '카드'} 명세서에서 {len(txs)}건을 읽었습니다."
    if txs and not known:
        note += (f" 파일에 청구월이 없어 마지막 거래월 다음 달({guess or '미상'})로 추정했습니다 — "
                 "실제 결제월과 다르면 아래에서 고치세요.")
    return {
        "issuer": issuer,
        "billing_month": months[-1] if months else "",
        "billing_months": months,
        "billing_month_known": known,
        "file_kind": sheet.kind,
        "parsed_by": parsed_by,
        "transactions": txs,
        "note": note,
    }


__all__ = ["ISSUERS", "parse_file", "model", "tables"]
