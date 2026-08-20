"""지역 상권 — 업종 구성으로 성격을 가르는 규칙이 맞는가.

이 판정이 틀리면 화면이 "노원구는 업무지역" 같은 소리를 하게 된다. 그런데 숫자가
그럴듯하게 나오기 때문에 눈으로는 안 걸린다. 그래서 **아는 동네의 실제 값**으로
고정한다 — 실측으로 받아 온 여섯 지역의 구성비를 그대로 넣고, 아는 답이 나오는지 본다.
"""
from __future__ import annotations

import pytest

from app.data.macro import commerce as C

# 실제 API 로 받은 값(2026-08). 지어낸 숫자가 아니라 이 판정이 맞다는 근거다.
REAL = {
    "종로구": {"G2": 5488, "I1": 1037, "I2": 6722, "L1": 540, "M1": 3199,
               "N1": 1466, "P1": 1080, "Q1": 475, "R1": 497, "S2": 1120},
    "강남구": {"G2": 9542, "I1": 795, "I2": 12657, "L1": 3645, "M1": 20477,
               "N1": 3364, "P1": 6163, "Q1": 3048, "R1": 1723, "S2": 4891},
    "노원구": {"G2": 3529, "I1": 125, "I2": 4470, "L1": 565, "M1": 1098,
               "N1": 504, "P1": 1882, "Q1": 706, "R1": 910, "S2": 1885},
}


def test_office_district_is_recognised() -> None:
    """종로·강남은 사무실이 있어야 존재하는 업종이 두껍다."""
    for name in ("종로구", "강남구"):
        got = C.classify(REAL[name])
        assert got["character"] == "업무·상업", f"{name} 이 {got['character']} 로 나왔다"
        assert got["work_index"] >= 1.2


def test_residential_district_is_recognised() -> None:
    """노원구는 학원·병원·미용실이 두꺼운 순수 주거지다."""
    got = C.classify(REAL["노원구"])
    assert got["character"] == "주거"
    assert got["work_index"] < 0.7


def test_the_two_are_far_apart() -> None:
    """경계를 어디에 두든 이 둘은 갈려야 한다 — 안 갈리면 지표가 무의미하다."""
    office = C.classify(REAL["강남구"])["work_index"]
    home = C.classify(REAL["노원구"])["work_index"]
    assert office > home * 3, f"업무 {office} vs 주거 {home} — 차이가 너무 작다"


def test_shares_sum_to_one_hundred() -> None:
    got = C.classify(REAL["강남구"])
    assert abs(sum(got["shares"].values()) - 100.0) < 0.5


def test_empty_region_says_so_instead_of_guessing() -> None:
    """자료가 없는 지역을 '주거' 로 단정하면 안 된다 — 모른다고 해야 한다."""
    got = C.classify({})
    assert got["character"] == "자료 없음"
    assert got["work_index"] is None


def test_no_living_categories_holds_judgement() -> None:
    """분모가 0 이면 지수가 무한대가 된다. 그때는 판단을 보류한다."""
    got = C.classify({"M1": 100, "N1": 50})
    assert got["work_index"] is None
    assert got["character"] == "판단 보류"


# --- 수집 ---------------------------------------------------------------------
def test_failed_fetch_is_not_written_as_zero(monkeypatch) -> None:
    """0 은 '그 업종이 없다', None 은 '못 받았다' 다. 섞으면 수집이 덜 된 지역이
    '상권이 없는 지역' 으로 보인다."""
    saved: dict = {}
    monkeypatch.setattr(C, "load", lambda: {})
    monkeypatch.setattr(C, "save", lambda cells: saved.update(cells))
    monkeypatch.setattr(C, "count_stores", lambda lawd, code=None: None)
    monkeypatch.setattr(C, "missing", lambda: [("11680", "I2")])

    C.refresh(budget=1)
    assert saved == {}


def test_ranking_skips_partially_collected_regions(monkeypatch) -> None:
    """일부 업종만 받은 지역을 순위에 섞으면 지수가 거짓이 된다."""
    monkeypatch.setattr(C, "load", lambda: {
        "11110": {c: {"count": REAL["종로구"][c], "at": 0} for c, _ in C.CATEGORIES},
        "11350": {"M1": {"count": 1000, "at": 0}},        # 한 업종만 받은 상태
    })
    out = C.ranking()
    assert [r["lawd"] for r in out["items"]] == ["11110"]


def test_character_filter(monkeypatch) -> None:
    monkeypatch.setattr(C, "load", lambda: {
        "11110": {c: {"count": REAL["종로구"][c], "at": 0} for c, _ in C.CATEGORIES},
        "11350": {c: {"count": REAL["노원구"][c], "at": 0} for c, _ in C.CATEGORIES},
    })
    assert [r["region"] for r in C.ranking("주거")["items"]] == ["노원구"]
    assert [r["region"] for r in C.ranking("업무·상업")["items"]] == ["종로구"]
