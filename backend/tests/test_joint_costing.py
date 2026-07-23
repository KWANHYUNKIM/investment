"""결합원가 배분(§2.4) 회귀 테스트 — DB·네트워크 없이 순수 함수만 검증.

계획서 §8 결정(기본=상대판매가치법, 보조=부산물 순액차감 NRV)이 코드에서
실제로 그 성질을 갖는지 고정한다. 특히 "상대판매가치법은 품목별 매출총이익률이
동일하게 나온다"는 화면에 문구로 적어둔 성질이라 테스트로 못박는다.
"""
from __future__ import annotations

import pytest

from app.data.fundamentals import joint_costing as jc


def test_non_joint_sector_returns_none() -> None:
    """조별(음식료) 회사엔 결합원가 배분을 만들지 않는다."""
    mix = [{"name": "라면", "pct": 60}, {"name": "스낵", "pct": 40}]
    assert jc.allocate("004370", "음식료·음료", 1000, 1500, mix) is None


def test_joint_ticker_override_beats_sector() -> None:
    """업종 태그가 뭐든 정유사는 '결합'으로 보정된다."""
    p = jc.production_type("010950", "상사·서비스·기타")
    assert p["type"] == "결합" and p["is_joint"] and p["basis"] == "티커 보정"


def test_relative_sales_value_is_proportional_and_equal_margin() -> None:
    """상대판매가치법: 배분액은 매출비중에 비례하고, GM% 는 모든 품목이 같다."""
    mix = [{"name": "경유", "pct": 30}, {"name": "휘발유", "pct": 20}, {"name": "나프타", "pct": 50}]
    r = jc.allocate("010950", "화학·정유·에너지", cogs_eok=1000, revenue_eok=2000, mix=mix)
    assert r is not None and r["method"] == "상대판매가치법"
    alloc = {p["name"]: p["alloc_cogs_eok"] for p in r["products"]}
    assert alloc == {"경유": 300, "휘발유": 200, "나프타": 500}
    assert sum(alloc.values()) == pytest.approx(r["joint_cost_eok"], abs=2)
    gms = {p["gross_margin_pct"] for p in r["products"]}
    assert len(gms) == 1                      # 균등마진 — 이건 이 방법의 정의다
    assert gms.pop() == pytest.approx(50.0)   # (2000-1000)/2000


def test_mix_is_renormalised_to_100() -> None:
    """파싱된 매출비중 합이 100이 아니어도 100 기준으로 재정규화."""
    mix = [{"name": "A", "pct": 30}, {"name": "B", "pct": 10}]   # 합 40
    r = jc.allocate("010950", "화학·정유·에너지", cogs_eok=800, revenue_eok=1000, mix=mix)
    pcts = {p["name"]: p["sales_pct"] for p in r["products"]}
    assert pcts == {"A": 75.0, "B": 25.0}


def test_byproduct_tagging_and_nrv_net_method() -> None:
    """부산품(비중 5% 미만) 태깅 + 순액법: 부산품 원가 0, 주산품 원가는 그만큼 감소."""
    mix = [{"name": "주력", "pct": 96}, {"name": "스크랩", "pct": 4}]
    r = jc.allocate("010130", "철강·비철·소재", cogs_eok=1000, revenue_eok=2000, mix=mix)
    kinds = {p["name"]: p["kind"] for p in r["products"]}
    assert kinds == {"주력": "주산품", "스크랩": "부산품"}

    alt = r["alt"]
    assert alt["available"] is True
    assert alt["byproduct_nrv_eok"] == 80                      # 부산물 매출 = 2000 × 4%
    assert alt["joint_cost_after_eok"] == 920                  # 1000 − 80
    by_name = {p["name"]: p for p in alt["products"]}
    assert by_name["스크랩"]["alloc_cogs_eok"] == 0            # 순액법 — 부산품엔 원가 배분 안 함
    assert by_name["주력"]["alloc_cogs_eok"] == 920            # 주산품이 전부 짊어짐
    # 주산품 GM 은 상대판매가치법(50%)보다 개선된다.
    assert by_name["주력"]["gross_margin_pct"] > 50.0


def test_nrv_unavailable_without_byproduct() -> None:
    """부산품이 없으면 NRV 는 계산하지 않고 이유를 남긴다(수치를 지어내지 않는다)."""
    mix = [{"name": "A", "pct": 60}, {"name": "B", "pct": 40}]
    r = jc.allocate("010950", "화학·정유·에너지", cogs_eok=1000, revenue_eok=2000, mix=mix)
    assert r["alt"]["available"] is False
    assert "공시되지 않아" in r["alt"]["reason"]
    assert r["alt"]["products"] == []


def test_too_few_products_returns_none() -> None:
    """품목이 1개뿐이면 배분할 근거가 없다."""
    assert jc.allocate("010950", "화학·정유·에너지", 1000, 2000, [{"name": "A", "pct": 100}]) is None
