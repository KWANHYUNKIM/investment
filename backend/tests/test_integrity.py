"""§15 전 항목 파싱·진실성 스코어의 **회귀 방지** 테스트.

여기 있는 규칙은 전부 실제 사업보고서에서 한 번씩 물렸던 것들이다. 표를 잘못 읽으면
검증이 "틀렸다"가 아니라 **"정확히 두 배"** 같은 모양으로 나타나서, 눈으로는 그럴듯해 보인다.
그래서 판정이 아니라 **판별 규칙 자체**를 고정해 둔다.
"""
from __future__ import annotations

from app.data.fundamentals import dart_doc as dd
from app.data.fundamentals import dart_full as dfm
from app.data.fundamentals import integrity as ig
from app.data.fundamentals import report_notes as rn


# --- 합계행/열 판별 ---------------------------------------------------------
def test_is_total_catches_company_specific_names() -> None:
    """'계(*)'(삼성전자)·'부문계'(농심)를 놓치면 부문 합이 정확히 두 배가 된다."""
    for s in ("계", "계(*)", "합 계", "합계(주1)", "부문계", "소계", "총계", "매출총계", "전체"):
        assert dd.is_total(s), s


def test_is_total_keeps_real_segments() -> None:
    """'…계'로 끝난다고 다 합계가 아니다 — 진짜 부문을 지우면 안 된다."""
    for s in ("화장품", "관계기업", "공통및기타", "세계로", "기계장치", "LG에너지솔루션", "조정ㆍ제거"):
        assert not dd.is_total(s), s


# --- 성격별 비용 분류 -------------------------------------------------------
def test_cost_nature_material_vs_inventory_change() -> None:
    """POSCO는 재료비를 「원재료사용액 및 재고자산의 변동 등」 한 줄로 적는다.

    이걸 '재고변동'으로 보면 40조가 통째로 원가 구성에서 빠져 총비용이 반토막 난다.
    반대로 순수 변동분(LG화학·삼성전자)은 비용이 아니라 조정이라 빠져야 한다.
    """
    assert rn._cat_of("원재료사용액 및 재고자산의 변동 등") == "재료비"
    assert rn._cat_of("재고자산 매입액") == "재료비"
    assert rn._cat_of("제품, 반제품, 상품 및 재공품의 변동") == "재고변동"
    assert rn._cat_of("재고자산의 변동") == "재고변동"
    assert rn._cat_of("종업원급여") == "노무비"
    assert rn._cat_of("감가상각비 및 무형자산상각비") == "감가상각"


# --- 부문 표: 합계열을 부문으로 세지 않는가 ---------------------------------
_SEG_HTML = """
<TABLE><TBODY>
<TR><TD>구분</TD><TD>DX 부문</TD><TD>DS 부문</TD><TD>내부거래조정등</TD><TD>계(*)</TD></TR>
<TR><TD>매출액</TD><TE>100,000</TE><TE>60,000</TE><TE>(10,000)</TE><TE>150,000</TE></TR>
<TR><TD>영업이익</TD><TE>10,000</TE><TE>8,000</TE><TE>-</TE><TE>18,000</TE></TR>
</TBODY></TABLE>
"""


def test_segments_exclude_total_column() -> None:
    out = dfm._segments("(단위: 백만원)" + _SEG_HTML)
    assert out is not None
    names = {r["name"] for r in out["rows"]}
    assert "계(*)" not in names and "계" not in names
    # 100,000 + 60,000 − 10,000 = 150,000 (백만원)
    assert round(out["total_revenue_won"] / 1e6) == 150_000


def test_segments_read_te_cells() -> None:
    """서식 표는 <TE>(추출값) 셀로 온다 — TD/TH만 읽으면 데이터가 통째로 빈다."""
    grid = dd._grid(_SEG_HTML)
    assert grid[1][1] == "100,000"


# --- 단위 사전 --------------------------------------------------------------
def test_unit_dictionary_refuses_unknown_units() -> None:
    """환산이 확실한 것만 계산한다. 복합 캡션은 **계산하지 않는다**(§15.4)."""
    assert dfm._output_unit("천개") == ("ea", 1e3)
    assert dfm._output_unit("ton") == ("kg", 1000.0)
    assert dfm._output_unit("완제의약품-백만정, 수액-백만bag") is None
    assert dfm._price_unit("원/Kg") == ("kg", 1.0)
    assert dfm._price_unit("원/EA") == ("ea", 1.0)
    assert dfm._price_unit("원/㎥") is None


# --- 스코어 산식 ------------------------------------------------------------
def test_score_excludes_unavailable_from_denominator() -> None:
    """확인불가를 감점하면 '공시를 적게 한 회사가 유리'해지는 역설이 생긴다(§15.1)."""
    c = ig._Checks()
    c.add("X1", "치명 일치", ig.CRIT, "ok", "")
    c.add("X7", "중대 관찰", ig.MAJOR, "warn", "")
    c.add("X30", "참고 확인불가", ig.INFO, "na", "")

    checked = [r for r in c.rows if r["status"] in ig.CREDIT]
    w = sum(r["weight"] for r in checked)
    score = round(sum(r["weight"] * ig.CREDIT[r["status"]] for r in checked) / w * 100)
    assert w == 5 + 3                      # 참고 1점은 분모에서 빠진다
    assert score == round((5 * 1.0 + 3 * 0.5) / 8 * 100)   # 관찰은 절반만 인정


def test_trend_checks_are_dropped_only_by_material_consolidation_change() -> None:
    """연결범위 변동은 3년 비교를 무효로 만들지만, 매출 0.3%짜리 인수까지 그러면 안 된다."""
    assert "X9" in ig._TREND_CODES and "X15" in ig._TREND_CODES
    assert "X1" not in ig._TREND_CODES      # 단년 항등식은 영향 없음
