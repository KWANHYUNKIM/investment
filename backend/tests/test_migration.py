"""인구이동 — 응답 파싱 · 코드 변환 · 순이동 계산.

필드명과 응답 모양은 실제 호출에서 확인한 것이다(2026-08). 특히 ``Response`` 래퍼와
성공코드 ``"0"`` 은 명세에 없던 것이라, 처음 짠 파서가 **조용히 0건**을 돌려줬다.
그 두 가지를 테스트로 박아 둔다.
"""
from __future__ import annotations

import json

import pytest

from app.data.macro import migration as M

GANGNAM = "1168000000"
NOWON = "1135000000"


def _item(to_cd: str, from_cd: str, total: int, ages: dict[int, int] | None = None) -> dict:
    """명세의 필드명 그대로 만든 한 줄."""
    d = {
        "statsYm": "202605",
        "mvinAdmmCd": to_cd, "mvtAdmmCd": from_cd,
        "mvinCtpvNm": "서울특별시", "mvinSggNm": "강남구", "mvinDongNm": "",
        "mvtCtpvNm": "서울특별시", "mvtSggNm": "노원구", "mvtDongNm": "",
        "totNmprCnt": str(total), "maleNmprCnt": str(total // 2),
        "femlNmprCnt": str(total - total // 2),
    }
    for age, n in (ages or {}).items():
        d[f"male{age}AgeNmprCnt"] = str(n)
    return d


def _body(items: list[dict], code: str = "0") -> str:
    """실제 응답 모양 — Response 로 한 겹 싸여 있다."""
    return json.dumps({"Response": {
        "head": {"resultCode": code, "resultMsg": "NORMAL_SERVICE",
                 "totalCount": str(len(items))},
        "items": {"item": items} if items else "",
    }}, ensure_ascii=False)


# --- 파싱 --------------------------------------------------------------------
def test_response_wrapper_is_unwrapped() -> None:
    """본문이 Response 로 싸여 온다. 안 벗기면 head 를 못 찾아 조용히 0건이 된다."""
    rows, total = M.parse(_body([_item(GANGNAM, NOWON, 40)]))
    assert len(rows) == 1 and total == 1
    assert rows[0]["total"] == 40


def test_success_code_is_zero_not_double_zero() -> None:
    """대부분의 포털 API 는 '00' 인데 이건 '0' 이다. '00' 만 통과시키면 전부 실패한다."""
    rows, _ = M.parse(_body([_item(GANGNAM, NOWON, 5)], code="0"))
    assert rows


def test_single_item_is_not_iterated_as_a_dict() -> None:
    """항목이 하나면 list 가 아니라 dict 로 온다. 그대로 돌면 키 문자열을 순회한다."""
    raw = json.dumps({"Response": {"head": {"resultCode": "0", "totalCount": "1"},
                                   "items": {"item": _item(GANGNAM, NOWON, 40)}}})
    rows, _ = M.parse(raw)
    assert len(rows) == 1 and rows[0]["total"] == 40


def test_no_data_code_is_empty_not_error() -> None:
    """resultCode 3 은 '그 구간에 이동이 없다' 다 — 실패가 아니다."""
    assert M.parse(_body([], code="3")) == ([], 0)


def test_error_code_raises_instead_of_returning_zero() -> None:
    """실패를 0건으로 돌려주면 '이동이 없는 지역' 처럼 보인다."""
    raw = json.dumps({"Response": {"head": {"resultCode": "10",
                                            "resultMsg": "INVALID_REQUEST_PARAMETER_ERROR"}}})
    with pytest.raises(M.MigrationError):
        M.parse(raw)


def test_quota_message_is_its_own_error() -> None:
    """한도 초과는 잡아서 '받은 데까지 저장' 해야 한다 — 일반 실패와 구분한다."""
    raw = json.dumps({"Response": {"head": {"resultCode": "22",
                                            "resultMsg": "LIMITED_NUMBER_OF_SERVICE_REQUESTS"}}})
    with pytest.raises(M.QuotaError):
        M.parse(raw)


def test_numbers_with_commas_and_blanks() -> None:
    it = _item(GANGNAM, NOWON, 0)
    it["totNmprCnt"] = "1,234"
    it["maleNmprCnt"] = ""
    rows, _ = M.parse(_body([it]))
    assert rows[0]["total"] == 1234 and rows[0]["male"] == 0


# --- 코드 변환 ---------------------------------------------------------------
def test_borough_rolls_up_to_its_city() -> None:
    """원본은 통합시를 시 단위로만 준다. 분당구를 물으면 성남시로 올라가야 한다."""
    assert M.admm_of("41135") == "4113000000"      # 성남시 분당구 → 성남시
    assert M.admm_of("41111") == "4111000000"      # 수원시 장안구 → 수원시


def test_plain_district_is_unchanged() -> None:
    """구가 곧 시군구인 곳(서울·광역시)은 그대로 올라가야 한다."""
    assert M.admm_of("11680") == "1168000000"      # 강남구
    assert M.admm_of("36110") == "3611000000"      # 세종


def test_renamed_provinces_use_new_codes() -> None:
    """강원 42→51 · 전북 45→52. 옛 코드로 부르면 API 가 조용히 0건을 준다."""
    assert M.admm_of("42110") == "5111000000"      # 춘천시
    assert M.admm_of("45111") == "5211000000"      # 전주시 완산구 → 전주시
    assert "42" not in M.SIDO and "45" not in M.SIDO
    assert "51" in M.SIDO and "52" in M.SIDO
    assert len(M.SIDO) == 17


# --- 나이 구간 ---------------------------------------------------------------
def test_young_counts_both_sexes_in_range() -> None:
    """20~34세만 세고, 남녀를 모두 더한다."""
    it = _item(GANGNAM, NOWON, 100, ages={19: 5, 20: 7, 34: 3, 35: 9})
    it["feml25AgeNmprCnt"] = "4"
    rows, _ = M.parse(_body([it]))
    assert rows[0]["young"] == 7 + 3 + 4          # 19세·35세는 빠진다
    assert rows[0]["age_0_19"] == 5
    assert rows[0]["age_35_49"] == 9


def test_age_buckets_do_not_overlap_or_gap() -> None:
    """구간이 겹치면 합계가 부풀고, 비면 사람이 사라진다."""
    seen: set[int] = set()
    for _name, ages in M.AGE_BUCKETS:
        assert not (seen & set(ages))
        seen |= set(ages)
    assert seen == set(range(0, 111))


# --- 집계 --------------------------------------------------------------------
def test_net_uses_direction_of_each_row() -> None:
    rows, _ = M.parse(_body([
        _item(GANGNAM, NOWON, 300, ages={25: 200}),     # 강남으로 들어옴
        _item(NOWON, GANGNAM, 100, ages={25: 20}),      # 강남에서 나감
    ]))
    s = M.summarize(rows, GANGNAM)
    assert (s["in_total"], s["out_total"], s["net"]) == (300, 100, 200)
    assert s["net_young"] == 180
    assert s["direction"] == "유입" and s["young_direction"] == "청년 유입"


def test_total_up_but_young_leaving_is_reported_separately() -> None:
    """전체는 늘어도 청년이 빠지는 동네가 실제로 있다. 한 숫자로 뭉치면 안 된다."""
    rows, _ = M.parse(_body([
        _item(GANGNAM, NOWON, 300, ages={25: 10}),
        _item(NOWON, GANGNAM, 200, ages={25: 150}),
    ]))
    s = M.summarize(rows, GANGNAM)
    assert s["net"] > 0 and s["net_young"] < 0
    assert s["young_direction"] == "청년 유출"


def test_internal_moves_are_not_flows() -> None:
    """같은 지역 안에서의 이동은 유입도 유출도 아니다 — 규모만 부풀린다."""
    rows, _ = M.parse(_body([_item(GANGNAM, GANGNAM, 500)]))
    assert M.flows(rows, GANGNAM) == {"inbound": [], "outbound": []}
    assert M.summarize(rows, GANGNAM)["churn"] == 0


def test_flows_rank_partners_by_size() -> None:
    SONGPA = "1171000000"
    rows, _ = M.parse(_body([_item(GANGNAM, NOWON, 50), _item(GANGNAM, SONGPA, 400)]))
    f = M.flows(rows, GANGNAM, limit=5)
    assert [b["cd"] for b in f["inbound"]] == [SONGPA, NOWON]


# --- 기간 --------------------------------------------------------------------
def test_months_stop_at_the_start_of_the_dataset() -> None:
    """2022.10 이전을 부르면 API 가 빈 값을 준다 — 아예 목록에서 뺀다."""
    assert all(ym >= "202210" for ym in M.months_back(120))


def test_months_are_contiguous_and_newest_first() -> None:
    got = M.months_back(5)
    assert got == sorted(got, reverse=True)
    assert len(set(got)) == len(got)


# --- 수집 --------------------------------------------------------------------
def test_quota_stop_keeps_what_was_already_saved(monkeypatch) -> None:
    """한도에 걸려도 그 전에 받은 쌍은 저장돼 있어야 한다.

    저장을 마지막에 몰아서 하면 한도에 걸린 순간 그 회차가 통째로 날아간다.
    """
    saved: list = []
    calls = {"n": 0}

    def flaky(ym, f, t):
        calls["n"] += 1
        if calls["n"] > 2:
            raise M.QuotaError("한도 초과")
        return [{"ym": ym, "from_cd": "a", "to_cd": "b", "from_name": "", "to_name": "",
                 "total": 1, "male": 1, "female": 0, "young": 0,
                 "age_0_19": 0, "age_20_34": 0, "age_35_49": 0,
                 "age_50_64": 0, "age_65_plus": 0}]

    import app.db.stores as S
    monkeypatch.setattr(S, "migration_done", lambda: set())
    monkeypatch.setattr(S, "migration_save",
                        lambda ym, f, t, rows: saved.append((ym, f, t)))
    monkeypatch.setattr(M, "collect_pair", flaky)
    # 병렬이면 '몇 번째에 멈추는가' 가 흔들린다. 순서를 보려고 한 줄로 돌린다.
    monkeypatch.setattr(M, "get_settings",
                        lambda: type("S", (), {"migration_budget": 10, "migration_months": 1,
                                               "migration_workers": 1})())

    res = M.refresh()
    assert res["pairs"] == 2 and len(saved) == 2
    assert res["gaps"] > 0


def test_not_approved_is_its_own_error() -> None:
    """403 은 키가 틀린 게 아니라 활용신청이 안 된 것이다 — 안내가 달라야 한다."""
    assert issubclass(M.NotApprovedError, M.MigrationError)
    assert issubclass(M.QuotaError, M.MigrationError)


def test_coverage_reports_stored_rows_not_this_run(monkeypatch) -> None:
    """저장된 전체 행수를 '이번 회차에 받은 수' 가 덮으면 안 된다.

    실제로 그랬다 — 82,077행이 6,451행으로 보였다. 진척이 줄어드는 것처럼 보이면
    수집이 뭔가를 지운다고 의심하게 된다.
    """
    import app.db.stores as S
    monkeypatch.setattr(S, "migration_coverage",
                        lambda: {"pairs": 867, "rows": 82_077, "months": ["202607"]})
    monkeypatch.setitem(M._state, "rows", 6_451)

    cov = M.coverage()
    assert cov["rows"] == 82_077
    assert cov["run"]["rows"] == 6_451
