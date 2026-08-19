"""카드사별 파서 회귀 테스트 — 롯데 · 하나 · 삼성.

네 카드사가 전부 다른 포맷이고, 무엇보다 **어느 컬럼이 그 달에 나갈 돈인지**가
전부 다르다. 여기서 지키는 건 그 한 가지다.

    신한  결제 금액 + 수수료(이자)      ← test_budget_cards.py
    롯데  청구원금 + 수수료·이자 + 연체이자
    하나  매입금액(즉시할인 반영), 미매입이면 승인금액
    삼성  원금 + 이자/수수료

픽스처는 실제 파일의 구조만 흉내 낸 합성 데이터다(개인 거래 아님).
"""
from __future__ import annotations

import io

from app.data.market.budget.cards import model as M
from app.data.market.budget.cards import parse_file

# --- 롯데카드: 확장자만 .xls 인 HTML, 컬럼 9개 -------------------------------
LOTTE_XLS = """<html xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:x="urn:schemas-microsoft-com:office:excel"><head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" /></head><body>
<p class="x-tit1">일시불 결제예정금액</p>
<table>
<tr><th>이용일자</th><th>이용카드</th><th>가맹점명</th><th>이용금액</th><th>청구원금</th>
<th>수수료·이자</th><th>연체이자</th><th>회차</th><th>잔여원금</th></tr>
<tr><td>2026.07.30</td><td>본인 | 9409-****-****-*159</td><td>굽네치킨부사문창점</td>
<td>21,791</td><td>21,791</td><td>0</td><td>0</td><td></td><td>0</td></tr>
<tr><td>2026.08.01</td><td>본인 | 9409-****-****-*159</td><td>(주)에너비즈 둔산주유소</td>
<td>39,800</td><td>39,800</td><td>0</td><td>0</td><td></td><td>0</td></tr>
<tr><td>2026.08.02</td><td>본인 | 9409-****-****-*159</td><td>(주)테스트가전</td>
<td>1,200,000</td><td>200,000</td><td>5,000</td><td>0</td><td>2/6</td><td>800,000</td></tr>
<tr class="x-total"><td>합계</td><td>1,261,591</td><td>261,591</td><td>5,000</td><td>0</td>
<td></td><td>800,000</td></tr>
</table></body></html>""".encode("utf-8")

# --- 하나카드: 진짜 .xls 는 만들기 번거로워 같은 표를 CSV 로 흉내 낸다.
# 파서는 tables 가 만든 행만 보므로 포맷이 달라도 컬럼 해석은 동일하게 검증된다.
HANA_ROWS = (
    "카드이용내역 조회\n"
    "[조회기간: 2026.08.01 ~ 2026.08.19]\n"
    "이용일,이용시간,이용카드,승인번호,가맹점명,승인금액,포인트 사용,이용구분,"
    "할부 기간,매입,매입금액,매입할인 금액,매입취소금액,상태\n"
    "2026.08.16,16:44:27,본인 1650,25212714,선비할인마트,14160,0,일시불,-,매입,14047,113,0,정상\n"
    "2026.08.15,22:03:08,본인 1650,22212614,씨유(CU) 대전문화스토리점,3600,0,일시불,-,미매입,0,0,0,정상\n"
    "2026.08.14,00:14:59,본인 1650,29211514,테스트가구,600000,0,할부,3개월,매입,594000,6000,0,정상\n"
    "2026.08.13,10:09:34,본인 1650,25211414,반품가맹점,5400,0,일시불,-,매입,0,0,5400,취소\n"
    "정상승인건수,,,3\n"
    "이하 여백 (End of document)\n"
).encode("utf-8")


def _samsung_xlsx() -> bytes:
    """삼성 포맷(시트 첫 줄이 구획명, 그 아래 헤더)을 실제 xlsx 로 만든다."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "할부"
    ws.append(["할부"])
    ws.append([])
    ws.append(["이용일", "이용구분", "가맹점", "이용금액", "총할부금액", "이용혜택", "혜택금액",
               "개월", "회차", "원금", "이자/수수료", "포인트명", "적립금액", "입금후잔액"])
    ws.append(["20260517", "본 인 654", "쿠팡", "1,671,290", "", "이자면제", "-25,044",
               "12", "3", 139200, 0, "", 0, 1252800])
    ws.append(["", "", "할부합계", " ", " ", "", " ", " ", " ", 139200, 0, "", 0, 1252800])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _by(txs: list[dict], needle: str) -> dict:
    return next(t for t in txs if needle in t["merchant"])


# --- 롯데 -------------------------------------------------------------------
def test_lotte_is_detected_and_sums_to_the_statement_total() -> None:
    rep = parse_file("일시불 결제예정금액_20260819092636.xls", LOTTE_XLS)
    assert rep["issuer"] == "롯데카드"
    assert rep["parsed_by"] == "lotte"
    assert rep["file_kind"] == "html"
    # 합계 행은 셀 수가 헤더보다 적어 컬럼이 밀려 있다 — 날짜가 없어 걸러져야 한다.
    assert len(rep["transactions"]) == 3


def test_lotte_charges_principal_plus_interest_not_the_purchase_amount() -> None:
    txs = parse_file("일시불 결제예정금액.xls", LOTTE_XLS)["transactions"]
    inst = _by(txs, "테스트가전")
    assert inst["amount"] == 200_000 + 5_000   # 청구원금 + 수수료·이자
    assert inst["total"] == 1_200_000          # 이용금액은 전액이라 지출이 아니다
    assert inst["tx_type"] == M.INSTALLMENT
    assert inst["installment"] == {"months": 6, "seq": 2, "remaining": 800_000}


def test_lotte_masked_card_number_is_shortened_for_the_axis_label() -> None:
    tx = parse_file("일시불 결제예정금액.xls", LOTTE_XLS)["transactions"][0]
    assert tx["card"] == "본인 159"


def test_lotte_billing_month_is_unknown_and_guessed() -> None:
    """'결제예정금액' 에는 청구월이 없다 — 지어내지 말고 추정으로 표시해야 한다."""
    rep = parse_file("일시불 결제예정금액.xls", LOTTE_XLS)
    assert rep["billing_month_known"] is False
    assert rep["billing_month"] == "2026-09"   # 마지막 거래월(2026-08) + 1
    assert "추정" in rep["note"]


# --- 하나 -------------------------------------------------------------------
def test_hana_uses_the_captured_amount_not_the_approved_amount() -> None:
    """승인 14,160 이 매입에서 14,047 + 할인 113 으로 갈린다 — 나가는 건 14,047."""
    txs = parse_file("카드이용내역.csv", HANA_ROWS)["transactions"]
    tx = _by(txs, "선비할인마트")
    assert tx["amount"] == 14_047
    assert tx["total"] == 14_160


def test_hana_unsettled_row_falls_back_to_the_approved_amount() -> None:
    """미매입은 '아직 안 넘어왔다' 는 뜻이지 0 원이 아니다."""
    tx = _by(parse_file("카드이용내역.csv", HANA_ROWS)["transactions"], "씨유")
    assert tx["amount"] == 3_600


def test_hana_cancelled_row_is_negative() -> None:
    tx = _by(parse_file("카드이용내역.csv", HANA_ROWS)["transactions"], "반품가맹점")
    assert tx["tx_type"] == M.CANCEL
    assert tx["amount"] == -5_400


def test_hana_installment_without_round_info_makes_no_fake_schedule() -> None:
    """이 조회에는 회차·잔액이 없다 — 없는 값을 지어내면 할부 예정표가 틀린다."""
    tx = _by(parse_file("카드이용내역.csv", HANA_ROWS)["transactions"], "테스트가구")
    assert tx["tx_type"] == M.INSTALLMENT
    assert tx["installment"] == {"months": 3, "seq": 0, "remaining": 0}


# --- 삼성 -------------------------------------------------------------------
def test_samsung_charges_principal_plus_interest() -> None:
    rep = parse_file("samsungcard_20260801.xlsx", _samsung_xlsx())
    assert rep["issuer"] == "삼성카드"
    assert rep["file_kind"] == "xlsx"
    assert len(rep["transactions"]) == 1      # '할부합계' 행은 날짜가 없어 걸러진다
    tx = rep["transactions"][0]
    assert tx["amount"] == 139_200            # 원금 + 이자/수수료(0)
    assert tx["total"] == 1_671_290
    assert tx["installment"] == {"months": 12, "seq": 3, "remaining": 1_252_800}


def test_samsung_benefit_is_not_double_counted() -> None:
    """'이자면제 -25,044' 는 이미 이자/수수료 0 에 반영돼 있다 — 또 빼면 두 번 깎인다."""
    tx = parse_file("samsungcard_20260801.xlsx", _samsung_xlsx())["transactions"][0]
    assert tx["amount"] == 139_200
    assert tx["amount"] != 139_200 - 25_044


def test_samsung_card_column_is_the_holder_not_the_tx_type() -> None:
    """'이용구분' 이라는 이름과 달리 카드 명의('본 인 654')가 들어온다."""
    tx = parse_file("samsungcard_20260801.xlsx", _samsung_xlsx())["transactions"][0]
    assert tx["card"] == "본인 654"
    assert tx["tx_type"] == M.INSTALLMENT     # 거래구분은 시트 첫 줄('할부')에서 온다


def test_samsung_billing_month_comes_from_the_filename() -> None:
    """5/17 구매 · 12개월 할부 3회차 → 2026-08 청구가 맞다(파일명과 일치)."""
    rep = parse_file("samsungcard_20260801.xlsx", _samsung_xlsx())
    assert rep["billing_month"] == "2026-08"
    assert rep["billing_month_known"] is True


def test_samsung_without_the_dated_filename_is_marked_unknown() -> None:
    rep = parse_file("다운로드.xlsx", _samsung_xlsx())
    assert rep["issuer"] == "삼성카드"          # 컬럼 조합으로도 알아본다
    assert rep["billing_month_known"] is False


# --- 카드사가 서로를 가로채지 않는가 ----------------------------------------
def test_parsers_do_not_claim_each_others_files() -> None:
    from app.data.market.budget.cards import hana, lotte, samsung, shinhan, tables
    from tests.test_budget_cards import SHINHAN_XLS

    files = {
        "shinhan": tables.read("s.xls", SHINHAN_XLS),
        "lotte": tables.read("l.xls", LOTTE_XLS),
        "hana": tables.read("h.csv", HANA_ROWS),
        "samsung": tables.read("samsungcard_20260801.xlsx", _samsung_xlsx()),
    }
    mods = {"shinhan": shinhan, "lotte": lotte, "hana": hana, "samsung": samsung}
    for owner, sheet in files.items():
        claimed = {name for name, mod in mods.items() if mod.detect(sheet)}
        assert claimed == {owner}, f"{owner} 파일을 {claimed} 가 물었다"


# --- 아직 실물을 못 받은 구획 ------------------------------------------------
# 삼성 일시불 시트와 롯데 할부 파일은 표본이 없어 컬럼 구성만 같게 만들어 두고,
# 지금 코드가 어떤 규칙으로 읽는지를 못박아 둔다. 실물이 오면 여기부터 확인한다.

LOTTE_INSTALLMENT_XLS = """<html xmlns:x="urn:schemas-microsoft-com:office:excel"><head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" /></head><body>
<p class="x-tit1">할부 결제예정금액</p>
<table>
<tr><th>이용일자</th><th>이용카드</th><th>가맹점명</th><th>이용금액</th><th>청구원금</th>
<th>수수료·이자</th><th>연체이자</th><th>회차</th><th>잔여원금</th></tr>
<tr><td>2026.06.15</td><td>본인 | 9409-****-****-*159</td><td>테스트가전</td>
<td>1,200,000</td><td>200,000</td><td>5,000</td><td>0</td><td>2/6</td><td>800,000</td></tr>
</table></body></html>""".encode("utf-8")


def test_lotte_installment_file_is_read_as_installment() -> None:
    rep = parse_file("할부 결제예정금액_20260819092636.xls", LOTTE_INSTALLMENT_XLS)
    assert rep["issuer"] == "롯데카드"
    tx = rep["transactions"][0]
    assert tx["tx_type"] == M.INSTALLMENT
    assert tx["amount"] == 205_000              # 청구원금 200,000 + 수수료·이자 5,000
    assert tx["installment"] == {"months": 6, "seq": 2, "remaining": 800_000}


def test_lotte_installment_feeds_the_upcoming_schedule(tmp_path, monkeypatch) -> None:
    """할부 파일이 들어오면 남은 회차가 향후 확정지출로 잡혀야 한다."""
    from app.data.market import budget
    from app.data.market.budget import store
    monkeypatch.setattr(store, "_path", lambda user: str(tmp_path / f"b_{user}.json"))
    budget.import_file("u", "할부 결제예정금액.xls", LOTTE_INSTALLMENT_XLS)
    inst = budget.installments("u")
    assert inst["count"] == 1
    assert inst["remaining_total"] == 800_000
    assert inst["next_month"] == 200_000        # 800,000 ÷ 남은 4회차
    assert len(inst["schedule"]) == 4


def _samsung_lump_xlsx() -> bytes:
    """삼성 일시불 구획 — 할부 컬럼(개월·회차·원금·이자)이 비어 있는 형태로 가정."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "일시불"
    ws.append(["일시불"])
    ws.append([])
    ws.append(["이용일", "이용구분", "가맹점", "이용금액", "총할부금액", "이용혜택", "혜택금액",
               "개월", "회차", "원금", "이자/수수료", "포인트명", "적립금액", "입금후잔액"])
    ws.append(["20260803", "본 인 654", "이마트", "50,000", "", "", "", "", "", "", "", "", 0, ""])
    ws.append(["20260804", "본 인 654", "청구할인가맹점", "30,000", "", "청구할인", "-3,000",
               "", "", "", "", "", 0, ""])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_samsung_lump_sum_section() -> None:
    txs = parse_file("samsungcard_20260901.xlsx", _samsung_lump_xlsx())["transactions"]
    assert [t["tx_type"] for t in txs] == [M.LUMP, M.LUMP]
    assert txs[0]["amount"] == 50_000
    # 원금 컬럼이 비면 음수 혜택금액(청구할인)만 반영한다.
    assert txs[1]["amount"] == 27_000
    assert txs[1]["total"] == 30_000
