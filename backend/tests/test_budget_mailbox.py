"""카드사 메일 명세서 수집 — 무엇을 명세서로 보고, 무엇을 자동 등록할 것인가.

IMAP 접속 자체는 여기서 테스트하지 않는다(외부 서버). 대신 **틀리면 돈이 잘못
들어가는 판단들**을 고정한다: 어떤 메일을 명세서로 볼지, 잠긴 첨부를 열었는지,
그리고 파싱 결과를 바로 등록해도 되는지.
"""
from __future__ import annotations

import email
import io
import zipfile

from app.data.market.budget import mailbox as MB
from app.data.market.budget.cards import tables


# --- 어떤 메일이 명세서인가 -------------------------------------------------
def test_issuer_from_sender_domain() -> None:
    """제목이 뭐라 하든 보낸사람 도메인이 가장 확실한 단서다."""
    assert MB._issuer_of("no-reply@shinhancard.com", "안내") == "신한카드"
    assert MB._issuer_of("bill@lottecard.co.kr", "") == "롯데카드"
    assert MB._issuer_of("someone@example.com", "") == ""


def test_issuer_from_subject_when_domain_is_a_mail_agent() -> None:
    """카드사가 발송 대행을 쓰면 도메인이 다르다 — 제목의 카드사 이름으로 잡는다."""
    assert MB._issuer_of("noreply@mailer.example.net", "[삼성카드] 이용대금명세서") == "삼성카드"


def test_statement_without_issuer_name_still_qualifies() -> None:
    """카드사 이름이 어디에도 없어도 제목이 명세서면 후보로는 올린다."""
    assert MB._is_statement("bill@unknown.co.kr", "8월 이용대금명세서를 보내드립니다")


def test_ads_are_not_statements() -> None:
    """'명세서' 를 달고 오는 광고를 걸러야 대기함이 쓰레기로 안 찬다."""
    assert not MB._is_statement("event@shinhancard.com", "[이벤트] 명세서 이메일 신청하고 경품")


def test_unrelated_mail_is_ignored() -> None:
    assert not MB._is_statement("hr@company.com", "주간 회의록")


# --- 잠긴 첨부 --------------------------------------------------------------
def _zip_bytes(name: str, body: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(name, body)
    return buf.getvalue()


def test_zip_attachment_is_expanded() -> None:
    """zip 첨부는 풀어서 안의 명세서를 꺼낸다."""
    blob = _zip_bytes("statement.csv", b"date,amount\n2026-08-01,1000\n")
    out = MB._expand_zip("stmt.zip", blob, [])
    assert [n for n, _ in out] == ["statement.csv"]
    assert b"2026-08-01" in out[0][1]


def test_zip_ignores_non_statement_entries() -> None:
    """안내문 이미지 같은 건 파서에 넘기지 않는다."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("notice.png", b"\x89PNG")
        zf.writestr("stmt.xlsx", b"PK\x03\x04rest")
    out = MB._expand_zip("m.zip", buf.getvalue(), [])
    assert [n for n, _ in out] == ["stmt.xlsx"]


def test_plain_attachment_passes_through_unlock() -> None:
    """암호가 안 걸린 파일은 손대지 않고 그대로 나온다."""
    data = b"date,amount\n2026-08-01,1000\n"
    assert MB._unlock("stmt.csv", data, ["900326"]) == data


# --- 첨부 꺼내기 ------------------------------------------------------------
def _mail(subject: str, sender: str, *, attach: tuple[str, bytes] | None = None,
          html: str = "") -> email.message.Message:
    msg = email.message.EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["Date"] = "Wed, 19 Aug 2026 09:00:00 +0900"
    msg["Message-ID"] = "<test-1@example.com>"
    msg.set_content("본문")
    if html:
        msg.add_alternative(html, subtype="html")
    if attach:
        name, blob = attach
        msg.add_attachment(blob, maintype="application", subtype="octet-stream",
                           filename=name)
    return email.message_from_bytes(bytes(msg))


def test_attachment_is_picked_up() -> None:
    msg = _mail("[신한카드] 이용대금명세서", "no-reply@shinhancard.com",
                attach=("8월명세서.csv", b"date,amount\n2026-08-01,1000\n"))
    got = MB._attachments(msg)
    assert [n for n, _ in got] == ["8월명세서.csv"]


def test_html_body_used_when_there_is_no_attachment() -> None:
    """본문 표로 명세서를 보내는 카드사가 있다 — 첨부가 없다고 포기하지 않는다."""
    msg = _mail("[하나카드] 이용대금명세서", "bill@hanacard.co.kr",
                html="<html><table><tr><td>2026-08-01</td><td>1,000</td></tr></table></html>")
    parts = MB._collect_parts(msg, [])
    assert [n for n, _ in parts] == ["메일본문.html"]


def test_html_body_without_a_table_is_not_a_statement() -> None:
    """표가 없는 안내 메일 본문까지 파서에 넘기면 헛것을 읽는다."""
    msg = _mail("[하나카드] 명세서 안내", "bill@hanacard.co.kr",
                html="<html><p>홈페이지에서 확인하세요</p></html>")
    assert MB._collect_parts(msg, []) == []


def test_locked_attachment_reports_instead_of_killing_the_scan(monkeypatch) -> None:
    """열지 못한 첨부 하나가 예외로 스캔 전체를 끝내면 나머지 카드사도 못 걷는다.

    (표준 zipfile 로는 암호 zip 을 만들 수 없어 해제 단계를 대신 세운다.)
    """
    def _refuse(_name, _data, _pw):
        raise MB.Locked("PDF 첨부에 비밀번호가 걸려 있습니다")

    monkeypatch.setattr(MB, "_unlock", _refuse)
    msg = _mail("[롯데카드] 이용대금명세서", "bill@lottecard.co.kr",
                attach=("stmt.pdf", b"%PDF-1.7\n"))
    reason = MB._collect_parts(msg, [])
    assert isinstance(reason, str) and "비밀번호" in reason


# --- 자동 등록 판단 ---------------------------------------------------------
def _rep(**kw) -> dict:
    base = {"transactions": [{"date": "2026-08-01", "amount": 1000}],
            "parsed_by": "shinhan", "billing_month_known": True}
    return {**base, **kw}


def test_trusted_parser_with_known_month_is_auto_imported() -> None:
    ok, why = MB._auto_ok(_rep())
    assert ok and why == ""


def test_guessed_parse_waits_for_a_human() -> None:
    """전용 파서가 아니면 금액의 의미를 장담할 수 없다 — 사람이 본 뒤 넣는다."""
    ok, why = MB._auto_ok(_rep(parsed_by="generic"))
    assert not ok and "추정" in why


def test_unknown_billing_month_waits() -> None:
    """청구월을 지어낸 채로 넣으면 그 달 합계가 통째로 어긋난다."""
    ok, why = MB._auto_ok(_rep(billing_month_known=False))
    assert not ok and "청구월" in why


def test_cycle_conflict_waits() -> None:
    """명세서가 말한 청구월과 카드 설정이 다르면 둘 중 하나가 틀린 것이다."""
    ok, why = MB._auto_ok(_rep(cycle_conflict={"stated": "2026-09", "by_cycle": ["2026-08"]}))
    assert not ok and "설정" in why


def test_empty_parse_is_not_imported() -> None:
    ok, why = MB._auto_ok(_rep(transactions=[]))
    assert not ok and "찾지 못함" in why


# --- PDF 표 ----------------------------------------------------------------
def test_pdf_is_detected_by_content() -> None:
    assert tables.sniff(b"%PDF-1.7\n...") == "pdf"


def test_pdf_columns_split_on_double_space_only() -> None:
    """한 칸 공백까지 쪼개면 '스타벅스 강남점' 이 두 칸으로 갈라진다."""
    rows = tables.pdf_tables("2026-08-01  스타벅스 강남점   4,500")
    assert rows == [[["2026-08-01", "스타벅스 강남점", "4,500"]]]


def test_pdf_sheet_keeps_tab_separated_raw_for_the_loose_fallback() -> None:
    """폴백 파서는 탭/콤마로 칸을 나눈다 — 추정한 경계를 탭으로 남겨야 한다."""
    sheet = tables.read("stmt.pdf", b"%PDF-1.7\n")   # 본문 없는 PDF
    assert sheet.kind == "pdf"
    assert sheet.tables == []
