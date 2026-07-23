"""미래가치 4문(門) 회귀 테스트 — DB 없이 지표·점수·반증 규칙만 검증.

이 모듈의 존재 이유는 "적자인 이유가 미래 투자인가, 수요 소멸인가"를 가르는 것이다.
그 판정과 **반증 신호의 등급 상한**이 조용히 어긋나면 소멸 중인 회사가 미래가치
후보로 올라간다. 그래서 규칙을 값으로 고정한다.
"""
from __future__ import annotations

from app.data.fundamentals import future_value as fv

EOK = 1e8


def _year(sales, op, *, capex=0.0, intan=0.0, cash=0.0, cfo=0.0, cff=0.0,
          assets=1000 * EOK, ppe=100 * EOK, debt=0.0, interest=None) -> dict:
    d = {"sales": sales, "op": op, "assets": assets, "cash": cash, "ppe": ppe,
         "capex": capex, "intan_buy": intan, "cfo": cfo, "cff": cff,
         "debt_s": debt, "debt_l": 0.0, "bond": 0.0}
    if interest is not None:
        d["interest"] = interest
    return d


def _rows(*years) -> list:
    """최신 우선 [(year, dict), ...] — _metrics 가 받는 형태."""
    return [(2025 - i, y) for i, y in enumerate(years)]


def test_weights_sum_to_100_with_news_smallest():
    """1~3문은 크게, 뉴스가 섞이는 4문은 가장 작게."""
    assert sum(fv.WEIGHTS.values()) == 100
    assert fv.WEIGHTS["market"] == min(fv.WEIGHTS.values())
    for k in ("reinvest", "conversion", "endurance"):
        assert fv.WEIGHTS[k] > fv.WEIGHTS["market"] * 2


def test_reinvest_rate_is_capped_to_kill_small_denominator_blowups():
    """매출이 작으면 재투자율이 160% 같은 값으로 폭발한다(실제로 나왔다)."""
    m = fv._metrics(_rows(
        _year(10 * EOK, -5 * EOK, capex=16 * EOK),
        _year(10 * EOK, -5 * EOK, capex=16 * EOK),
        _year(10 * EOK, -5 * EOK, capex=16 * EOK)))
    assert m["reinvest_raw"] > 1.0
    assert m["reinvest_rate"] == fv._REINVEST_CAP
    assert m["reinvest_capped"] is True


def test_conversion_is_withheld_when_reinvestment_is_tiny():
    """재투자가 매출의 3% 미만이면 전환 배수가 불안정해 판단을 보류한다."""
    m = fv._metrics(_rows(
        _year(1000 * EOK, 50 * EOK, capex=1 * EOK),
        _year(900 * EOK, 40 * EOK, capex=1 * EOK),
        _year(800 * EOK, 30 * EOK, capex=1 * EOK)))
    assert m["invest_share"] < fv._INVEST_FLOOR
    assert m["conversion"] is None
    part = fv._score(m, [0.05, 0.1, 0.2])["parts"]["conversion"]
    assert part["estimated"] is True and "판단 보류" in part["detail"]


def test_conversion_measures_sales_gain_per_won_invested():
    m = fv._metrics(_rows(
        _year(1300 * EOK, 50 * EOK, capex=100 * EOK),
        _year(1100 * EOK, 40 * EOK, capex=100 * EOK),
        _year(1000 * EOK, 30 * EOK, capex=100 * EOK)))
    assert m["conversion"] == 1.0        # 매출 +300억 ÷ 누적재투자 300억
    assert m["sales_cagr"] > 0


def test_runway_under_12_months_caps_grade_to_D():
    """현금이 1년을 못 버티면 점수가 아무리 높아도 D. 감점이 아니라 상한이다."""
    m = fv._metrics(_rows(
        _year(1000 * EOK, -300 * EOK, capex=200 * EOK, cash=100 * EOK, cfo=-300 * EOK),
        _year(800 * EOK, -200 * EOK, capex=200 * EOK, cash=200 * EOK, cfo=-200 * EOK),
        _year(600 * EOK, -100 * EOK, capex=200 * EOK, cash=300 * EOK, cfo=-100 * EOK)))
    assert m["runway_months"] < fv._RUNWAY_CAP
    caps = [f["cap"] for f in fv._falsifiers(m, None, None)]
    assert "D" in caps
    assert fv._cap("A+", "D") == "D"


def test_dilution_survival_caps_grade_to_C():
    """영업현금 적자인데 재무현금 유입이 반복되면 외부 조달로 연명하는 구조."""
    y = _year(500 * EOK, -100 * EOK, capex=50 * EOK, cash=900 * EOK,
              cfo=-100 * EOK, cff=+150 * EOK)
    m = fv._metrics(_rows(y, dict(y), dict(y)))
    assert m["dilution_years"] == 3
    assert any(f["cap"] == "C" and "연명" in f["text"] for f in fv._falsifiers(m, None, None))


def test_investing_while_sales_shrink_is_a_falsifier():
    """돈은 쓰는데 매출이 줄면 '미래 투자' 서사가 깨진다."""
    m = fv._metrics(_rows(
        _year(800 * EOK, 10 * EOK, capex=100 * EOK, cash=500 * EOK, cfo=50 * EOK),
        _year(900 * EOK, 20 * EOK, capex=100 * EOK, cash=500 * EOK, cfo=50 * EOK),
        _year(1000 * EOK, 30 * EOK, capex=100 * EOK, cash=500 * EOK, cfo=50 * EOK)))
    assert m["conversion"] < 0
    assert any("전환 실패" in f["text"] for f in fv._falsifiers(m, None, None))


def test_delisting_risk_and_bad_audit_cap_the_grade():
    m = fv._metrics(_rows(_year(1000 * EOK, 100 * EOK, capex=50 * EOK, cash=500 * EOK, cfo=100 * EOK),
                          _year(900 * EOK, 90 * EOK, capex=50 * EOK, cash=500 * EOK, cfo=100 * EOK)))
    assert any(f["cap"] == "D" for f in fv._falsifiers(m, risk_level=3, audit=None))
    assert any(f["cap"] == "C" for f in fv._falsifiers(m, risk_level=None, audit=40))
    assert fv._falsifiers(m, risk_level=0, audit=95) == []


def test_loss_making_companies_are_split_by_cause():
    """이 모듈의 존재 이유 — 같은 적자라도 원인이 다르면 다른 판정이 나와야 한다."""
    peers = [0.02, 0.05, 0.10, 0.20]

    future = fv._metrics(_rows(          # 재투자 크고 매출 늘고 현금 넉넉
        _year(1300 * EOK, -50 * EOK, capex=150 * EOK, cash=2000 * EOK, cfo=-100 * EOK),
        _year(1100 * EOK, -60 * EOK, capex=150 * EOK, cash=2000 * EOK, cfo=-100 * EOK),
        _year(1000 * EOK, -70 * EOK, capex=150 * EOK, cash=2000 * EOK, cfo=-100 * EOK)))
    future.update(theme_ready=False)
    fparts = fv._score(future, peers)["parts"]
    assert "미래투자형" in fv._verdict(future, fparts, fv._falsifiers(future, None, None))

    dying = fv._metrics(_rows(           # 재투자 없고 현금도 없다
        _year(600 * EOK, -200 * EOK, cash=50 * EOK, cfo=-200 * EOK),
        _year(800 * EOK, -150 * EOK, cash=100 * EOK, cfo=-150 * EOK),
        _year(1000 * EOK, -100 * EOK, cash=200 * EOK, cfo=-100 * EOK)))
    dying.update(theme_ready=False)
    dparts = fv._score(dying, peers)["parts"]
    assert "소멸형" in fv._verdict(dying, dparts, fv._falsifiers(dying, None, None))


def test_profitable_companies_are_also_split():
    """흑자도 갈린다 — 벌어서 다시 심는 곳 / 그냥 버는 곳 / 줄이는 곳."""
    peers = [0.01, 0.02, 0.03]
    grow = fv._metrics(_rows(
        _year(1300 * EOK, 130 * EOK, capex=150 * EOK, cash=500 * EOK, cfo=200 * EOK, ppe=300 * EOK),
        _year(1100 * EOK, 110 * EOK, capex=150 * EOK, cash=500 * EOK, cfo=200 * EOK, ppe=200 * EOK),
        _year(1000 * EOK, 100 * EOK, capex=150 * EOK, cash=500 * EOK, cfo=200 * EOK, ppe=100 * EOK)))
    grow.update(theme_ready=False)
    v = fv._verdict(grow, fv._score(grow, peers)["parts"], [])
    assert "성장투자형 흑자" in v

    shrink = fv._metrics(_rows(
        _year(1000 * EOK, 100 * EOK, capex=5 * EOK, cash=500 * EOK, cfo=200 * EOK, ppe=100 * EOK),
        _year(1000 * EOK, 100 * EOK, capex=5 * EOK, cash=500 * EOK, cfo=200 * EOK, ppe=200 * EOK),
        _year(1000 * EOK, 100 * EOK, capex=5 * EOK, cash=500 * EOK, cfo=200 * EOK, ppe=300 * EOK)))
    shrink.update(theme_ready=False)
    assert shrink["ppe_shrinking"] is True
    assert "설비 축소" in fv._verdict(shrink, fv._score(shrink, peers)["parts"], [])


def test_missing_market_axis_is_neutral_not_zero():
    """뉴스 테마가 준비 안 됐다고 미래가치를 깎으면 안 된다."""
    m = fv._metrics(_rows(_year(1000 * EOK, 100 * EOK, capex=50 * EOK, cash=500 * EOK, cfo=100 * EOK),
                          _year(900 * EOK, 90 * EOK, capex=50 * EOK, cash=500 * EOK, cfo=100 * EOK)))
    m.update(theme_ready=False)
    part = fv._score(m, [0.05])["parts"]["market"]
    assert part["estimated"] is True and part["score"] == fv.WEIGHTS["market"] / 2
