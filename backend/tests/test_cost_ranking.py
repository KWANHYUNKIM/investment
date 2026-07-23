"""원가 경쟁력 랭킹 회귀 테스트 — 배치 파일을 스텁으로 갈아끼워 순수 계산만 검증.

랭킹은 "괜찮은 순"이라는 판단을 숫자로 내놓는 기능이라, 배점 합·정렬·제외 규칙이
조용히 어긋나면 알아채기 어렵다. 그래서 규칙 자체를 값으로 고정한다.
"""
from __future__ import annotations

import pytest

from app.data.fundamentals import cost_ranking as cr


def _row(**kw) -> dict:
    base = {
        "company": "테스트", "sector": "음식료·음료", "basis": "DART 실측",
        "cogs_ratio": 0.70, "op_margin": 0.06, "revenue_eok": 10000, "year": 2025,
        "cogs_3y": [0.70, 0.71, 0.72], "op_3y": [0.06, 0.05, 0.05],
        "efficiency_pp": -1.0, "price_variance_pp": 2.0,
        "audit_score": 100, "recon_status": "ok",
    }
    base.update(kw)
    return base


@pytest.fixture
def stub_batch(monkeypatch):
    def _install(companies: dict):
        monkeypatch.setattr(cr.ccm, "load_batch",
                            lambda: {"built_at": "2026-07-23 15:00", "as_of": "2026-07",
                                     "companies": companies})
    return _install


def test_weights_sum_to_100():
    assert sum(cr.WEIGHTS.values()) == 100


def test_missing_batch_is_reported_not_crashed(monkeypatch):
    monkeypatch.setattr(cr.ccm, "load_batch", lambda: None)
    r = cr.ranking()
    assert r["available"] is False and r["rows"] == []


def test_estimated_only_companies_are_excluded(stub_batch):
    stub_batch({
        "000001": _row(company="실측사"),
        "000002": _row(company="추정사", basis="추정(수작업 KB)"),
    })
    r = cr.ranking()
    assert [x["company"] for x in r["rows"]] == ["실측사"]
    assert r["excluded"] == 1


def test_improving_cost_ratio_scores_higher_than_worsening(stub_batch):
    """3년 원가율이 내려간 회사가 올라간 회사보다 원가추세 점수가 높아야 한다."""
    stub_batch({
        "000001": _row(company="개선", cogs_3y=[0.68, 0.70, 0.72]),   # −4.0%p
        "000002": _row(company="악화", cogs_3y=[0.76, 0.74, 0.72]),   # +4.0%p
    })
    rows = {x["company"]: x for x in cr.ranking()["rows"]}
    assert rows["개선"]["parts"]["cost_trend"]["score"] > rows["악화"]["parts"]["cost_trend"]["score"]
    assert rows["개선"]["cogs_delta_3y_pp"] == -4.0
    assert rows["악화"]["cogs_delta_3y_pp"] == 4.0
    assert rows["개선"]["parts"]["cost_trend"]["score"] == cr.WEIGHTS["cost_trend"]  # 만점


def test_defending_margin_scores_pass_through(stub_batch):
    """능률·기타차이가 음수(=원자재 상승을 판가로 방어)면 전가력 점수가 높다."""
    stub_batch({
        "000001": _row(company="방어", efficiency_pp=-2.0),
        "000002": _row(company="전이", efficiency_pp=+2.0),
    })
    rows = {x["company"]: x for x in cr.ranking()["rows"]}
    assert rows["방어"]["parts"]["pass_through"]["score"] == cr.WEIGHTS["pass_through"]
    assert rows["전이"]["parts"]["pass_through"]["score"] == 0


def test_pass_through_is_normalised_by_material_pressure(stub_batch):
    """전가력은 '압력 대비 방어율'이라 압력이 같아도 잔차가 다르면 갈린다.

    잔차(efficiency_pp)를 그대로 쓰면 원가추세와 같은 신호를 두 번 세게 된다
    (실측 상관 0.46). 압력으로 나눠 정규화한 이유.
    """
    stub_batch({
        "000001": _row(company="완전방어", price_variance_pp=4.0, efficiency_pp=-4.0),  # 100%
        "000002": _row(company="절반방어", price_variance_pp=4.0, efficiency_pp=-2.0),  # 50%
        "000003": _row(company="전이", price_variance_pp=4.0, efficiency_pp=+1.0),      # -25%
    })
    rows = {x["company"]: x for x in cr.ranking()["rows"]}
    assert rows["완전방어"]["defense_ratio"] == 1.0
    assert rows["절반방어"]["defense_ratio"] == 0.5
    assert (rows["완전방어"]["parts"]["pass_through"]["score"]
            > rows["절반방어"]["parts"]["pass_through"]["score"]
            > rows["전이"]["parts"]["pass_through"]["score"])


def test_pass_through_is_neutral_when_no_material_pressure(stub_batch):
    """원자재가 오히려 내렸으면 '전가력'을 물을 수 없다 → 중립 + 사유."""
    stub_batch({"000001": _row(company="압력없음", price_variance_pp=-2.0, efficiency_pp=3.0)})
    part = cr.ranking()["rows"][0]["parts"]["pass_through"]
    assert part["estimated"] is True
    assert part["score"] == cr.WEIGHTS["pass_through"] / 2
    assert "판단 보류" in part["detail"]


def test_headline_ignores_neutral_parts_and_needs_a_clear_edge(stub_batch):
    """'최고 항목=강점'으로 뽑으면 거의 모두 만점인 신뢰도가 계속 강점으로 나온다."""
    stub_batch({
        "000001": _row(company="고른회사", cogs_3y=[0.72, 0.72, 0.72],
                       price_variance_pp=-1.0, op_margin=0.06),
    })
    assert cr.ranking()["rows"][0]["headline"] in ("항목별로 고르게 중간",
                                                   "안정성 강점 · 뚜렷한 약점 없음",
                                                   "신뢰도 강점 · 뚜렷한 약점 없음")


def test_missing_inputs_become_neutral_and_flagged(stub_batch):
    """자료가 없는 항목은 0점이 아니라 중립(배점 절반) + estimated 표시."""
    stub_batch({"000001": _row(company="자료없음", cogs_3y=[], efficiency_pp=None,
                               audit_score=None, recon_status=None)})
    row = cr.ranking()["rows"][0]
    assert row["parts"]["cost_trend"]["estimated"] is True
    assert row["parts"]["cost_trend"]["score"] == cr.WEIGHTS["cost_trend"] / 2
    assert set(row["estimated_parts"]) >= {"cost_trend", "pass_through", "stability"}


def test_rows_are_sorted_by_score_with_ranks(stub_batch):
    stub_batch({
        "000001": _row(company="하", op_margin=0.01, cogs_3y=[0.80, 0.76, 0.72],
                       efficiency_pp=2.0, audit_score=40, recon_status="mismatch"),
        "000002": _row(company="상", op_margin=0.20, cogs_3y=[0.60, 0.66, 0.72],
                       efficiency_pp=-2.0, audit_score=100, recon_status="ok"),
        "000003": _row(company="중"),
    })
    rows = cr.ranking()["rows"]
    assert [x["rank"] for x in rows] == [1, 2, 3]
    assert rows[0]["company"] == "상" and rows[-1]["company"] == "하"
    assert rows[0]["score"] > rows[1]["score"] > rows[2]["score"]
    assert rows[0]["score"] <= 100


def test_sector_filter_and_limit(stub_batch):
    stub_batch({
        "000001": _row(company="식품A", sector="음식료·음료"),
        "000002": _row(company="화학A", sector="화학·정유·에너지"),
    })
    only = cr.ranking(sector="화학·정유·에너지")
    assert [x["company"] for x in only["rows"]] == ["화학A"]
    assert len(cr.ranking(limit=1)["rows"]) == 1


def test_profitability_is_ranked_within_sector(stub_batch):
    """업종마다 정상 마진이 다르므로 수익성은 업종 내 백분위로 본다."""
    stub_batch({
        # 저마진 업종 안에서는 6%가 1등
        "000001": _row(company="유통상", sector="유통·리테일", op_margin=0.06),
        "000002": _row(company="유통중", sector="유통·리테일", op_margin=0.02),
        "000003": _row(company="유통하", sector="유통·리테일", op_margin=0.01),
        # 고마진 업종 안에서는 같은 6%가 꼴찌
        "000004": _row(company="게임하", sector="IT·게임", op_margin=0.06),
        "000005": _row(company="게임중", sector="IT·게임", op_margin=0.25),
        "000006": _row(company="게임상", sector="IT·게임", op_margin=0.40),
    })
    rows = {x["company"]: x for x in cr.ranking()["rows"]}
    assert (rows["유통상"]["parts"]["profitability"]["score"]
            > rows["게임하"]["parts"]["profitability"]["score"])
