"""시군구 월별 집계 — 예산 안에서 쌓고, 틀린 값을 지어내지 않는가.

이 저장소가 존재하는 이유는 하나다: 24개월 × 250 시군구 × 3개 거래유형 = 18,000콜을
data.go.kr **하루 1,000건** 안에서 소화해야 한다. 그래서 '무엇을 다시 받고 무엇을
안 받는가' 가 이 모듈의 전부이고, 여기서 틀리면 한도가 말라 다른 기능까지 멈춘다.
"""
from __future__ import annotations

import time

import pytest

from app.data.macro import region_stats as RS


@pytest.fixture
def store(monkeypatch, tmp_path):
    """디스크를 임시 경로로 돌린다 — 실제 수집물을 건드리지 않게."""
    monkeypatch.setattr(RS, "_path", lambda: str(tmp_path / "stats.json"))
    return tmp_path


# --- 평형 구간 --------------------------------------------------------------
def test_area_buckets_split_at_market_boundaries() -> None:
    """60㎡·85㎡ 는 청약·세제가 갈리는 실제 경계다. 임의로 자르면 시장과 어긋난다."""
    assert RS._bucket(59.9) == "40~60"
    assert RS._bucket(60.0) == "60~85"
    assert RS._bucket(84.9) == "60~85"
    assert RS._bucket(85.0) == "85~135"


def test_missing_area_is_not_forced_into_a_bucket() -> None:
    """면적이 없는 계약을 아무 칸에나 넣으면 그 평형 평균이 오염된다."""
    assert RS._bucket(None) is None


# --- 거래유형별 금액의 뜻 ---------------------------------------------------
def test_sale_uses_deal_price() -> None:
    deals = [{"amount_eok": 10.0, "area": 70.0}, {"amount_eok": 20.0, "area": 70.0}]
    got = RS._agg(deals, "sale")
    assert got["count"] == 2
    assert got["avg_eok"] == 15.0
    assert got["by_area"]["60~85"]["count"] == 2


def test_jeonse_uses_deposit_not_deal_price() -> None:
    """전세엔 거래가가 없다. 보증금을 안 쓰면 전 구간이 통째로 비어 버린다."""
    deals = [{"deposit_eok": 5.0, "area": 50.0}, {"deposit_eok": 7.0, "area": 50.0}]
    got = RS._agg(deals, "jeonse")
    assert got["count"] == 2
    assert got["avg_eok"] == 6.0


def test_wolse_keeps_deposit_and_rent_apart() -> None:
    """월세는 보증금과 월세가 다른 돈이다. 하나로 뭉개면 평균이 무의미해진다."""
    deals = [{"deposit_eok": 1.0, "monthly_manwon": 100, "area": 45.0},
             {"deposit_eok": 3.0, "monthly_manwon": 200, "area": 45.0}]
    got = RS._agg(deals, "wolse")
    assert got["avg_eok"] == 2.0              # 보증금 평균
    assert got["avg_rent_manwon"] == 150      # 월세 평균은 따로


def test_empty_month_yields_no_average_rather_than_zero() -> None:
    """거래가 없던 달의 평균을 0 으로 적으면 '0억에 팔렸다' 가 된다."""
    got = RS._agg([], "sale")
    assert got["count"] == 0
    assert got["avg_eok"] is None


# --- 무엇을 다시 받는가 -----------------------------------------------------
def test_recent_two_months_are_refetched(store) -> None:
    """신고 기한이 계약 후 30일이라 최근 두 달은 계속 자란다. 한 번 받고 끝내면
    이번 달 막대가 영원히 낮게 남는다."""
    stale = RS._stale_months()
    assert len(stale) == 2
    assert time.strftime("%Y%m") in stale


def test_settled_month_is_not_refetched(store, monkeypatch) -> None:
    """지난 달은 다시 바뀌지 않는다 — 다시 받으면 한도만 태운다."""
    old = RS.months_back(24)[0]
    monkeypatch.setattr(RS, "SIGUNGU", [("11215", "서울", "광진구")])
    RS._save({"cells": {RS._key("11215", old, "sale"): {"count": 1}}})

    todo = RS.missing(24, ("sale",))
    assert (("11215", old, "sale") in todo) is False


def test_newest_months_are_filled_first(store, monkeypatch) -> None:
    """오래된 달부터 채우면 예산을 다 쓰고도 화면엔 아무것도 안 나타난다."""
    monkeypatch.setattr(RS, "SIGUNGU", [("11215", "서울", "광진구")])
    todo = RS.missing(6, ("sale",))
    yms = [ym for _lawd, ym, _t in todo]
    assert yms == sorted(yms, reverse=True)


def test_budget_caps_one_round(store, monkeypatch) -> None:
    """한 번에 다 받으려 들면 429 가 나고 그날 다른 기능까지 같이 막힌다."""
    monkeypatch.setattr(RS, "SIGUNGU", [(f"1121{i}", "서울", f"구{i}") for i in range(9)])
    calls = []

    def fake_fetch(lawd, ym, trade, memo=None):
        calls.append((lawd, ym, trade))
        return {"count": 1, "amount_eok": 1.0, "avg_eok": 1.0,
                "avg_rent_manwon": None, "by_area": {}}

    monkeypatch.setattr(RS, "fetch_cell", fake_fetch)
    res = RS.refresh(budget=5, months=6, trades=("sale",))
    assert len(calls) == 5
    assert res["filled"] == 5
    assert res["gaps"] > 0


def test_stale_refresh_does_not_starve_the_backfill(store, monkeypatch) -> None:
    """이번에 실제로 터진 버그. 최근 두 달(250곳×2달×3유형=1,500칸)을 '없는 칸' 과
    같은 줄에 세우면 예산이 매번 거기서 다 타고 과거는 영영 안 채워진다.

    120칸을 채웠는데 남은 칸이 그대로 18,000 이었던 게 그 증상이다.
    """
    monkeypatch.setattr(RS, "SIGUNGU", [(f"1121{i}", "서울", f"구{i}") for i in range(20)])
    recent = RS.months_back(2)

    # 최근 두 달은 이미 다 받아 뒀지만 오래돼서 갱신 대상이다.
    old_ts = 0
    RS._save({"cells": {RS._key(f"1121{i}", ym, "sale"): {"count": 1, "at": old_ts}
                        for i in range(20) for ym in recent}})

    got = []
    monkeypatch.setattr(RS, "fetch_cell",
                        lambda lawd, ym, t, memo=None:
                            got.append((lawd, ym, t)) or {"count": 1, "by_area": {}})
    RS.refresh(budget=8, months=12, trades=("sale",))

    older = [c for c in got if c[1] not in recent]
    assert older, "예산이 전부 최근 달 갱신에 쓰여 과거가 한 칸도 안 채워졌다"
    assert len(older) >= 6      # 3/4 은 과거 채우기 몫


def test_jeonse_and_wolse_share_one_api_call(store, monkeypatch) -> None:
    """전세와 월세는 같은 API 가 한 번에 돌려주는 같은 응답이다. 따로 부르면 호출이
    그대로 두 배가 되고(18,000 vs 12,000), 하루 1,000건 한도에서 그 차이는 6일이다."""
    monkeypatch.setattr(RS, "SIGUNGU", [("11215", "서울", "광진구")])
    http = []

    def fake_rent(lawd, ym):
        http.append((lawd, ym))
        return ([{"deposit_eok": 5.0, "monthly_manwon": 0, "area": 70.0, "rent_type": "전세"},
                 {"deposit_eok": 1.0, "monthly_manwon": 90, "area": 45.0, "rent_type": "월세"}], True)

    from app.data.macro import rent as rent_mod
    monkeypatch.setattr(rent_mod, "month_deals", fake_rent)
    RS.refresh(budget=4, months=1, trades=("jeonse", "wolse"))

    assert len(http) == 1, "전세·월세를 각각 불러 호출이 두 배가 됐다"
    cells = RS.load()["cells"]
    ym = RS.months_back(1)[0]
    assert cells[RS._key("11215", ym, "jeonse")]["count"] == 1
    assert cells[RS._key("11215", ym, "wolse")]["avg_rent_manwon"] == 90


def test_consecutive_failures_stop_the_round(store, monkeypatch) -> None:
    """연속 실패는 대개 한도 초과다. 계속 두드리면 다음 날까지 막힌다."""
    monkeypatch.setattr(RS, "SIGUNGU", [(f"1121{i}", "서울", f"구{i}") for i in range(9)])
    calls = []

    def always_fail(lawd, ym, trade, memo=None):
        calls.append(1)
        return None

    monkeypatch.setattr(RS, "fetch_cell", always_fail)
    res = RS.refresh(budget=200, months=6, trades=("sale",))
    assert len(calls) == 20          # 20번 연속 실패하면 멈춘다
    assert res["filled"] == 0


def test_failed_cell_is_not_written_as_zero(store, monkeypatch) -> None:
    """실패를 0 으로 적으면 '거래 없음' 과 구분되지 않아 그래프가 거짓말을 한다."""
    monkeypatch.setattr(RS, "SIGUNGU", [("11215", "서울", "광진구")])
    monkeypatch.setattr(RS, "fetch_cell", lambda *a: None)
    RS.refresh(budget=3, months=6, trades=("sale",))
    assert RS.load()["cells"] == {}


# --- 조회 -------------------------------------------------------------------
def test_series_skips_unfetched_months(store) -> None:
    """아직 안 받은 달을 0 으로 그리면 '거래 급감' 으로 읽힌다. 아예 빼야 한다."""
    yms = RS.months_back(6)
    RS._save({"cells": {
        RS._key("11215", yms[-1], "sale"): {"count": 10, "avg_eok": 15.0},
        RS._key("11215", yms[-3], "sale"): {"count": 20, "avg_eok": 14.0},
    }})
    got = RS.series("11215", "sale", months=6)
    assert [m["ym"] for m in got["months"]] == [yms[-3], yms[-1]]


def test_series_marks_provisional_months(store) -> None:
    yms = RS.months_back(6)
    RS._save({"cells": {RS._key("11215", yms[-1], "sale"): {"count": 10}}})
    got = RS.series("11215", "sale", months=6)
    assert got["months"][0]["provisional"] is True


def test_series_does_not_fetch(store, monkeypatch) -> None:
    """지역을 누를 때마다 수집이 돌면 화면이 멈추고 한도도 순식간에 마른다."""
    def boom(*a, **k):
        raise AssertionError("조회가 수집을 유발했다")

    monkeypatch.setattr(RS, "fetch_cell", boom)
    assert RS.series("11215", "sale", months=6)["months"] == []
