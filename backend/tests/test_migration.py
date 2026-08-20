"""인구이동 — 응답 파싱과 순이동 계산.

이 API 는 아직 활용신청 전이라 실호출을 못 한다. 그래서 **필드명은 공식 명세에서
그대로 가져오고**(statsYm·mvinAdmmCd·male0AgeNmprCnt …), 그 모양의 응답을 만들어
계산이 맞는지 본다. 승인되면 fetch 만 살아나고 아래 계산은 그대로 쓰인다.
"""
from __future__ import annotations

import json

import pytest

from app.data.macro import migration as M

GANGNAM = "1168000000"
NOWON = "1135000000"


def _item(to_cd: str, from_cd: str, total: int, young: dict[int, int] | None = None) -> dict:
    """명세의 필드명 그대로 만든 한 줄."""
    d = {
        "statsYm": "202605",
        "mvinAdmmCd": to_cd, "mvtAdmmCd": from_cd,
        "mvinCtpvNm": "서울특별시", "mvinSggNm": "강남구", "mvinDongNm": "",
        "mvtCtpvNm": "서울특별시", "mvtSggNm": "노원구", "mvtDongNm": "",
        "totNmprCnt": str(total), "maleNmprCnt": str(total // 2),
        "femlNmprCnt": str(total - total // 2),
    }
    for age, n in (young or {}).items():
        d[f"male{age}AgeNmprCnt"] = str(n)
    return d


def _body(items: list[dict]) -> str:
    return json.dumps({"head": {"resultCode": "00", "totalCount": str(len(items))},
                       "items": {"item": items}}, ensure_ascii=False)


# --- 파싱 --------------------------------------------------------------------
def test_single_item_is_not_iterated_as_a_dict() -> None:
    """항목이 하나면 포털이 list 가 아니라 dict 를 준다.

    그대로 순회하면 dict 의 **키 문자열**을 돌게 되어 조용히 0건이 된다.
    """
    raw = json.dumps({"head": {"resultCode": "00"},
                      "items": {"item": _item(GANGNAM, NOWON, 40)}})
    rows = M.parse(raw)
    assert len(rows) == 1
    assert rows[0]["total"] == 40


def test_empty_result_is_empty_not_error() -> None:
    assert M.parse(json.dumps({"head": {"resultCode": "00"}, "items": {}})) == []


def test_error_code_raises_instead_of_returning_zero() -> None:
    """실패를 0건으로 돌려주면 '이동이 없는 지역' 처럼 보인다."""
    raw = json.dumps({"head": {"resultCode": "22", "resultMsg": "LIMITED_NUMBER"}})
    with pytest.raises(M.MigrationError):
        M.parse(raw)


def test_numbers_with_commas_and_blanks() -> None:
    it = _item(GANGNAM, NOWON, 0)
    it["totNmprCnt"] = "1,234"
    it["maleNmprCnt"] = ""
    rows = M.parse(_body([it]))
    assert rows[0]["total"] == 1234
    assert rows[0]["male"] == 0


# --- 청년 구간 ---------------------------------------------------------------
def test_young_counts_both_sexes_in_range() -> None:
    """20~34세만 세고, 남녀를 모두 더한다."""
    it = _item(GANGNAM, NOWON, 100, young={19: 5, 20: 7, 34: 3, 35: 9})
    it["feml25AgeNmprCnt"] = "4"
    rows = M.parse(_body([it]))
    assert rows[0]["young"] == 7 + 3 + 4      # 19세·35세는 빠진다


# --- 집계 --------------------------------------------------------------------
def test_net_uses_direction_of_each_row() -> None:
    rows = M.parse(_body([
        _item(GANGNAM, NOWON, 300, young={25: 200}),     # 강남으로 들어옴
        _item(NOWON, GANGNAM, 100, young={25: 20}),      # 강남에서 나감
    ]))
    s = M.summarize(rows, GANGNAM)
    assert (s["in_total"], s["out_total"], s["net"]) == (300, 100, 200)
    assert s["net_young"] == 180
    assert s["direction"] == "유입"
    assert s["young_direction"] == "청년 유입"


def test_total_up_but_young_leaving_is_reported_separately() -> None:
    """전체는 늘어도 청년이 빠지는 동네가 실제로 있다. 한 숫자로 뭉치면 안 된다."""
    rows = M.parse(_body([
        _item(GANGNAM, NOWON, 300, young={25: 10}),
        _item(NOWON, GANGNAM, 200, young={25: 150}),
    ]))
    s = M.summarize(rows, GANGNAM)
    assert s["net"] > 0 and s["net_young"] < 0
    assert s["young_direction"] == "청년 유출"


def test_internal_moves_are_not_flows() -> None:
    """같은 지역 안에서의 이동은 유입도 유출도 아니다."""
    rows = M.parse(_body([_item(GANGNAM, GANGNAM, 500)]))
    f = M.flows(rows, GANGNAM)
    assert f["inbound"] == [] and f["outbound"] == []


def test_flows_rank_partners_by_size() -> None:
    SONGPA = "1171000000"
    rows = M.parse(_body([
        _item(GANGNAM, NOWON, 50),
        _item(GANGNAM, SONGPA, 400),
    ]))
    f = M.flows(rows, GANGNAM, limit=5)
    assert [b["cd"] for b in f["inbound"]] == [SONGPA, NOWON]


def test_not_approved_is_its_own_error() -> None:
    """403 은 키가 틀린 게 아니라 활용신청이 안 된 것이다 — 안내가 달라야 한다."""
    assert issubclass(M.NotApprovedError, M.MigrationError)
