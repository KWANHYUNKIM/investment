"""카드 명세서 파싱 회귀 테스트.

여기서 지키려는 건 하나다 — **그 청구월에 실제로 빠지는 돈**이 지출로 잡히는가.
할부·포인트·취소·해외수수료가 그 규칙을 각각 다른 방향으로 흔든다.

픽스처는 실제 명세서 구조만 흉내 낸 합성 데이터다(개인 거래 아님).
"""
from __future__ import annotations

from app.data.market import budget
from app.data.market.budget.cards import model as M
from app.data.market.budget.cards import parse_file, tables

# 신한카드가 내려주는 파일 — 확장자만 .xls 이고 내용은 HTML 표다.
SHINHAN_XLS = """<html xmln:x="urn:schemas-microsoft-com:office:excel"> <head>
<meta http-equiv="content-type" content="application/vnd.ms-excel; charset=UTF-8"></head>
<body><table><tr><td>2026년9월 예정 이용대금명세서(신용카드)</td></tr></table>
<table>
<tr><td>다음달 이용대금명세서목록 마이신한포인트 거래일자</td><td>이용카드</td><td>이용가맹점</td>
<td>거래금액</td><td>적립예정마이신한포인트율</td><td>이용개월</td><td>청구회차</td>
<td>결제 금액</td><td>사용포인트</td><td>수수료(이자)</td><td>결제 후 잔액</td><td>거래구분</td></tr>
<tr><td>2026.07.20</td><td>본인717</td><td>분할납부(TEST SHOP)</td><td>2,475,041</td><td>0.00</td>
<td>6</td><td>1</td><td>412,541</td><td></td><td>57,732</td><td>2,062,500</td><td>할부</td></tr>
<tr><td>2026.07.20</td><td>본인717</td><td>분할납부매출취소(TEST SHOP)</td><td>-2,470,638</td><td>0.00</td>
<td>0</td><td>0</td><td>0</td><td></td><td>0</td><td>0</td><td>일시불</td></tr>
<tr><td>2026.07.26</td><td>본인717</td><td>선비할인마트</td><td>20,300</td><td>0.00</td>
<td>0</td><td>0</td><td>20,000</td><td></td><td>0</td><td>0</td><td>일시불</td></tr>
<tr><td>2026.08.10</td><td>본인717</td><td>ANTHROPIC* CLAUDE SUB</td><td>158,739</td><td>0.00</td>
<td>0</td><td>0</td><td>158,739</td><td></td><td>282</td><td>0</td><td>일시불</td></tr>
<tr><td>합계</td><td></td><td></td><td>183,780</td><td></td><td></td><td></td><td>591,280</td>
<td></td><td>58,014</td><td></td><td></td></tr>
</table></body></html>""".encode("utf-8")


def _by_merchant(txs: list[dict], needle: str) -> dict:
    return next(t for t in txs if needle in t["merchant"])


def test_html_disguised_as_xls_is_detected() -> None:
    """확장자가 .xls 라고 엑셀로 열면 0건이 된다 — 내용으로 판별해야 한다."""
    assert tables.sniff(SHINHAN_XLS, "명세서.xls") == "html"


def test_shinhan_parsed_by_own_parser() -> None:
    rep = parse_file("2026년9월 예정 이용대금명세서(신용카드).xls", SHINHAN_XLS)
    assert rep["issuer"] == "신한카드"
    assert rep["parsed_by"] == "shinhan"
    assert rep["file_kind"] == "html"
    # 청구월은 거래일(7·8월)이 아니라 제목의 '2026년9월'
    assert rep["billing_month"] == "2026-09"
    assert all(t["billing_month"] == "2026-09" for t in rep["transactions"])
    # 합계 행은 거래일이 없어 걸러진다
    assert len(rep["transactions"]) == 4


def test_installment_charges_only_this_round() -> None:
    """할부는 거래 전액이 아니라 이번 회차 결제금액 + 수수료만 이번 달 지출이다."""
    tx = _by_merchant(parse_file("s.xls", SHINHAN_XLS)["transactions"], "분할납부(")
    assert tx["tx_type"] == M.INSTALLMENT
    assert tx["amount"] == 412_541 + 57_732
    assert tx["total"] == 2_475_041          # 전액은 따로 보관
    assert tx["installment"] == {"months": 6, "seq": 1, "remaining": 2_062_500}


def test_points_reduce_the_billed_amount() -> None:
    """거래금액 20,300 / 결제금액 20,000 — 통장에서 나가는 건 20,000."""
    tx = _by_merchant(parse_file("s.xls", SHINHAN_XLS)["transactions"], "선비할인마트")
    assert tx["amount"] == 20_000
    assert tx["total"] == 20_300


def test_cancel_row_does_not_move_money() -> None:
    """취소행은 거래금액이 음수여도 결제금액이 0 — 이번 청구에 영향이 없다."""
    tx = _by_merchant(parse_file("s.xls", SHINHAN_XLS)["transactions"], "매출취소")
    assert tx["tx_type"] == M.CANCEL
    assert tx["amount"] == 0


def test_domestic_lump_sum_with_fee_is_overseas() -> None:
    """국내 일시불엔 수수료가 안 붙는다 — 붙었으면 해외이용수수료다."""
    tx = _by_merchant(parse_file("s.xls", SHINHAN_XLS)["transactions"], "ANTHROPIC")
    assert tx["tx_type"] == M.OVERSEAS
    assert tx["fee"] == 282
    assert tx["amount"] == 158_739 + 282


def test_four_axes_sum_to_the_same_total(tmp_path, monkeypatch) -> None:
    """카테고리·카드·거래구분·고정비는 같은 지출을 다르게 자른 것이라 합계가 같다."""
    user = _isolated_user(tmp_path, monkeypatch)
    budget.import_file(user, "명세서.xls", SHINHAN_XLS)
    s = budget.summary(user)

    spend = sum(c["amount"] for c in s["by_category"])
    assert spend == sum(c["amount"] for c in s["by_card"])
    assert spend == sum(c["amount"] for c in s["by_tx_type"])
    assert spend == s["by_fixed"]["fixed"] + s["by_fixed"]["variable"]
    assert s["month"] == "2026-09"


def test_reimport_is_deduplicated(tmp_path, monkeypatch) -> None:
    """카드사가 확정본을 다시 내려주면 같은 파일을 또 올리게 된다."""
    user = _isolated_user(tmp_path, monkeypatch)
    first = budget.import_file(user, "명세서.xls", SHINHAN_XLS)
    again = budget.import_file(user, "명세서.xls", SHINHAN_XLS)
    assert first["added"] == 4 and first["skipped"] == 0
    assert again["added"] == 0 and again["skipped"] == 4


def test_installment_schedule_projects_remaining_rounds(tmp_path, monkeypatch) -> None:
    user = _isolated_user(tmp_path, monkeypatch)
    budget.import_file(user, "명세서.xls", SHINHAN_XLS)
    inst = budget.installments(user)
    assert inst["count"] == 1
    assert inst["remaining_total"] == 2_062_500
    assert [r["month"] for r in inst["schedule"]] == \
        ["2026-10", "2026-11", "2026-12", "2027-01", "2027-02"]
    assert inst["next_month"] == 412_500      # 2,062,500 ÷ 남은 5회차


def test_unknown_issuer_falls_back_to_header_guessing() -> None:
    csv = ("이용일자,가맹점명,이용금액,할부개월\n"
           "2026-07-01,GS25 역삼점,12300,0\n"
           "2026-07-02,스타벅스 강남,5600,0\n").encode("utf-8")
    rep = parse_file("카드내역.csv", csv)
    assert rep["parsed_by"] == "generic"
    assert [t["amount"] for t in rep["transactions"]] == [12300, 5600]
    assert rep["transactions"][0]["category"] == "장보기/마트"


def test_pasted_table_without_header_still_parses() -> None:
    rep = parse_file("paste.csv", "2026.07.02\t파리바게뜨 센트럴점\t3,500\n".encode("utf-8"))
    assert rep["parsed_by"] == "loose"
    assert rep["transactions"][0]["amount"] == 3500
    assert rep["transactions"][0]["category"] == "카페/간식"


def test_euc_kr_csv_is_decoded() -> None:
    csv = "이용일자,가맹점명,이용금액\n2026-07-01,투썸플레이스,6800\n".encode("cp949")
    rep = parse_file("카드내역.csv", csv)
    assert rep["transactions"][0]["merchant"] == "투썸플레이스"


def _isolated_user(tmp_path, monkeypatch) -> str:
    """가계부 JSON 을 tmp 로 격리 — 실제 data/ 를 건드리지 않는다."""
    from app.data.market.budget import store
    monkeypatch.setattr(store, "_path", lambda user: str(tmp_path / f"budget_{user}.json"))
    return "tester"
