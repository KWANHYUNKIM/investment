"""관리종목·상폐 요건 판정 회귀 테스트 — DB·네트워크 없이 ``_assess`` 만 검증.

**현행 규정 기준**(2022.10 재무요건 실질심사 전환 + 2026.7 퇴출제도 개혁 시행).
등급이 한 칸만 밀려도 "실질심사 대상인데 관리위험으로 표시"되는 사고가 나므로
sev 값을 직접 못박는다. 규정 개정이 잦은 영역이라 개정 시 여기부터 고친다.
"""
from __future__ import annotations

from app.data.market import delisting as dl

EOK = 1e8


def _ser(op=None, sales=None, equity=None, capital=None, pretax=None) -> dict:
    return {"op": op or {}, "sales": sales or {}, "equity": equity or {},
            "capital": capital or {}, "pretax": pretax or {}, "_srank": {}, "_prank": {}}


def _texts(a: dict) -> str:
    return " | ".join(r["text"] for r in a["reasons"])


# ── 매출액 요건 (1회 미달 = 관리 / 2년 연속 = 실질심사) ────────────────────
def test_sales_miss_once_is_management_level():
    a = dl._assess("000001", _ser(sales={2025: 20 * EOK, 2024: 60 * EOK}),
                   {"market": "KOSDAQ", "dept": "벤처기업부"}, "테스트")
    assert a["level"] == 2 and "관리종목 요건" in _texts(a)


def test_sales_miss_two_years_goes_to_substantive_review():
    """2022.10 개정 — 재무요건 상장폐지는 형식요건이 아니라 실질심사로 전환됐다."""
    a = dl._assess("000001", _ser(sales={2025: 20 * EOK, 2024: 25 * EOK}),
                   {"market": "KOSDAQ", "dept": "벤처기업부"}, "테스트")
    assert a["level"] == 3 and "2년 연속 — 상장적격성 실질심사 대상" in _texts(a)


def test_sales_threshold_differs_by_market():
    """유가 50억 · 코스닥 30억 — 40억 매출은 유가에서만 관리종목 요건."""
    ser = _ser(sales={2025: 40 * EOK})
    assert dl._assess("000001", ser, {"market": "KOSPI", "dept": ""}, "테")["level"] == 2
    kq = dl._assess("000001", ser, {"market": "KOSDAQ", "dept": ""}, "테")
    assert kq["level"] == 1 and "2027.1 상향 기준 50억 미달 예고" in _texts(kq)


def test_sales_upcoming_threshold_is_only_advisory():
    """현행 기준은 넘고 2027.1 상향 기준엔 미달 → 주의(예고)로만."""
    a = dl._assess("000001", _ser(sales={2025: 70 * EOK}), {"market": "KOSPI", "dept": ""}, "테")
    assert a["level"] == 1 and "미달 예고" in _texts(a)


def test_tech_special_exempts_sales_and_op_loss():
    a = dl._assess("000001", _ser(sales={2025: 5 * EOK, 2024: 5 * EOK},
                                  op={2025: -1 * EOK, 2024: -1 * EOK, 2023: -1 * EOK,
                                      2022: -1 * EOK, 2021: -1 * EOK}),
                   {"market": "KOSDAQ", "dept": "기술성장기업부"}, "테")
    assert a["level"] == 1                      # 유예 — 상폐/관리로 올리지 않는다
    assert "요건 유예" in _texts(a)


# ── 장기간 영업손실 (코스닥 4년 관리 · 5년 상폐 요건은 2022.10 삭제) ───────
def test_op_loss_five_years_is_no_longer_a_delisting_ground():
    four = {y: -1 * EOK for y in (2025, 2024, 2023, 2022)}
    a4 = dl._assess("000001", _ser(op=four), {"market": "KOSDAQ", "dept": ""}, "테")
    assert a4["level"] == 2
    a5 = dl._assess("000001", _ser(op={**four, 2021: -1 * EOK}),
                    {"market": "KOSDAQ", "dept": ""}, "테")
    assert a5["level"] == 2 and "2022.10 삭제" in _texts(a5)


def test_op_loss_not_applied_to_kospi():
    five = {y: -1 * EOK for y in (2025, 2024, 2023, 2022, 2021)}
    assert dl._assess("000001", _ser(op=five), {"market": "KOSPI", "dept": ""}, "테") is None


# ── 자본잠식 (2022.10 이후 연 단위 · 완전자본잠식만 반기말 포함) ──────────
def test_kospi_impairment_50pct_then_two_years():
    one = dl._assess("000001", _ser(equity={2025: 40 * EOK, 2024: 100 * EOK},
                                    capital={2025: 100 * EOK, 2024: 100 * EOK}),
                     {"market": "KOSPI", "dept": ""}, "테")
    assert one["level"] == 2
    two = dl._assess("000001", _ser(equity={2025: 40 * EOK, 2024: 30 * EOK},
                                    capital={2025: 100 * EOK, 2024: 100 * EOK}),
                     {"market": "KOSPI", "dept": ""}, "테")
    assert two["level"] == 3 and "실질심사" in _texts(two)


def test_kosdaq_equity_below_1bn_is_condition_b():
    """(B) 자기자본 10억원 미만 — 잠식률이 멀쩡해도 관리종목 요건."""
    a = dl._assess("000001", _ser(equity={2025: 5e8}, capital={2025: 5e8}),
                   {"market": "KOSDAQ", "dept": ""}, "테")
    assert a["level"] == 2 and "(B) 자기자본" in _texts(a)


def test_kosdaq_condition_b_two_consecutive_goes_to_review():
    a = dl._assess("000001", _ser(equity={2025: 4e8, 2024: 5e8},
                                  capital={2025: 5e8, 2024: 5e8}),
                   {"market": "KOSDAQ", "dept": ""}, "테")
    assert a["level"] == 3 and "2회 연속 — 상장적격성 실질심사 대상" in _texts(a)


def test_half_period_only_counts_for_full_impairment():
    """잠식률 요건은 연 단위(2022.10). 반기말은 2026.7 개혁의 완전자본잠식만."""
    partial = dl._assess("000001", _ser(equity={2025: 100 * EOK}, capital={2025: 100 * EOK}),
                         {"market": "KOSDAQ", "dept": ""}, "테",
                         half={2026: {"자본총계": 30 * EOK, "자본금": 100 * EOK}})
    assert partial is None                      # 반기 70% 잠식은 요건이 아니다

    full = dl._assess("000001", _ser(equity={2025: 100 * EOK}, capital={2025: 100 * EOK}),
                      {"market": "KOSDAQ", "dept": ""}, "테",
                      half={2026: {"자본총계": -1 * EOK, "자본금": 100 * EOK}})
    assert full["level"] == 3 and "반기말도 심사" in _texts(full)


def test_full_impairment_is_delisting():
    a = dl._assess("000001", _ser(equity={2025: -10 * EOK}, capital={2025: 100 * EOK}),
                   {"market": "KOSDAQ", "dept": ""}, "테")
    assert a["level"] == 3 and "완전자본잠식" in _texts(a)


# ── 법인세비용차감전계속사업손실 (코스닥) ──────────────────────────────────
def _pretax_ser(loss_years: set[int]) -> dict:
    eq = {y: 100 * EOK for y in (2025, 2024, 2023)}
    pretax = {y: (-60 * EOK if y in loss_years else 1 * EOK) for y in (2025, 2024, 2023)}
    return _ser(equity=eq, capital=dict(eq), pretax=pretax)


def test_pretax_loss_non_consecutive_is_management():
    """최근 3년 중 2회(비연속) — 관리종목 요건까지."""
    a = dl._assess("000001", _pretax_ser({2025, 2023}),
                   {"market": "KOSDAQ", "dept": "벤처기업부"}, "테")
    assert a["level"] == 2 and "최근 3년 2회" in _texts(a)


def test_pretax_loss_two_consecutive_goes_to_review():
    """2회 **연속** — 실질심사 대상(2022.10 전환)."""
    a = dl._assess("000001", _pretax_ser({2025, 2024}),
                   {"market": "KOSDAQ", "dept": "벤처기업부"}, "테")
    assert a["level"] == 3 and "2회 연속 — 상장적격성 실질심사 대상" in _texts(a)


# ── 비재무 요건 (시가총액 · 동전주 · 거래량) ───────────────────────────────
def test_market_cap_shortfall_by_state():
    """코스닥 시총 기준은 2026.7 부터 200억 — 100억은 미달이다."""
    ser = _ser(equity={2025: 100 * EOK}, capital={2025: 100 * EOK})
    base = {"market": "KOSDAQ", "dept": ""}

    def mk(state, streak):
        return {"market_cap": 100 * EOK, "cap_state": {"state": state, "streak": streak}}

    assert dl._assess("000001", ser, base, "테", mkt=mk("watch", 10))["level"] == 1
    assert dl._assess("000001", ser, base, "테", mkt=mk("manage", 35))["level"] == 2
    assert dl._assess("000001", ser, base, "테", mkt=mk("delist", 130))["level"] == 3


def test_market_cap_next_threshold_is_advisory():
    """현행 200억은 넘고 2027.1 기준 300억엔 미달 → 예고(주의)."""
    a = dl._assess("000001", _ser(equity={2025: 100 * EOK}, capital={2025: 100 * EOK}),
                   {"market": "KOSDAQ", "dept": ""}, "테",
                   mkt={"market_cap": 250 * EOK, "cap_state": {"state": "none", "streak": 0}})
    assert a["level"] == 1 and "300억 미달 예고" in _texts(a)


def test_penny_stock_requirement():
    """동전주(주가 1,000원 미만) 요건 — 2026.7 신설."""
    ser = _ser(equity={2025: 100 * EOK}, capital={2025: 100 * EOK})
    base = {"market": "KOSDAQ", "dept": ""}

    def mk(state, streak):
        return {"market_cap": 500 * EOK, "close": 820,
                "cap_state": {"state": "none", "streak": 0},
                "penny_state": {"state": state, "streak": streak}}

    assert dl._assess("000001", ser, base, "테", mkt=mk("watch", 5))["level"] == 1
    m = dl._assess("000001", ser, base, "테", mkt=mk("manage", 40))
    assert m["level"] == 2 and "동전주 요건" in _texts(m)
    assert dl._assess("000001", ser, base, "테", mkt=mk("delist", 140))["level"] == 3


def test_shortfall_state_machine():
    """30일 연속 미달 → 관리, 지정 후 90일간 45일 연속 회복 실패 → 상폐."""
    assert dl._shortfall_state([False] * 50)["state"] == "none"
    assert dl._shortfall_state([True] * 20)["state"] == "watch"
    assert dl._shortfall_state([True] * 35)["state"] == "manage"
    # 지정 후 90일이 지났는데 회복 최장연속이 44일 → 상폐
    assert dl._shortfall_state([True] * 30 + [False] * 44 + [True] * 46)["state"] == "delist"
    # 45일 연속 회복하면 살아남는다
    assert dl._shortfall_state([True] * 30 + [False] * 45 + [True] * 45)["state"] == "manage"


def test_market_stats_uses_effective_date_and_derives_shares():
    """시세 → 시총/동전주 상태 산출. DB 없이 스텁 커넥션으로 검증.

    핵심 두 가지: ① 상장주식수를 '최신 시총 ÷ 최신 종가'로 역산한다,
    ② 2026.7 신설·상향 요건은 **시행일 이후** 시세만으로 30일/90일을 센다
       (소급하면 시행 첫날부터 상폐 판정이 나온다).
    """
    import pandas as pd

    dates = pd.date_range("2026-01-02", periods=200, freq="D")   # 시행일 전후를 모두 포함
    px = [500.0] * len(dates)                                    # 내내 동전주 + 저시총
    px_df = pd.DataFrame({"ticker": ["000001"] * len(dates), "date": dates,
                          "close": px, "volume": [1000.0] * len(dates)})
    cap_df = pd.DataFrame({"ticker": ["000001"], "market_cap": [5e9]})   # 50억 → 200억 미달

    class _Stub:
        def __init__(self):
            self._n = 0

        def execute(self, sql):
            self._n += 1
            self._last = cap_df if "market_cap" in sql else px_df
            return self

        def df(self):
            return self._last

    stats = dl._market_stats({"000001": {"market": "KOSDAQ"}}, _Stub())["000001"]
    assert stats["shares"] == round(5e9 / 500.0)                 # ① 역산
    eff_days = sum(1 for d in dates if str(d)[:10] >= dl._RULE_EFFECTIVE)
    assert stats["cap_state"]["streak"] == eff_days              # ② 시행일 이후만 카운트
    assert stats["penny_state"]["streak"] == eff_days
    assert stats["cap_state"]["streak"] < len(dates)             # 소급하지 않았다


def test_volume_shortfall_stays_advisory():
    """유동주식수 미공시라 상장주식수 근사 — 과탐 방향이므로 '주의'로만."""
    a = dl._assess("000001", _ser(equity={2025: 100 * EOK}, capital={2025: 100 * EOK}),
                   {"market": "KOSDAQ", "dept": ""}, "테",
                   mkt={"market_cap": 500 * EOK, "cap_state": {"state": "none", "streak": 0},
                        "vol_ratio": 0.002})
    assert a["level"] == 1 and "상장주식수 근사" in _texts(a)


# ── 공시 기반 요건 (감사의견 · 불성실공시) ─────────────────────────────────
def test_annual_audit_opinion_is_delisting_half_review_is_management():
    ser = _ser(equity={2025: 100 * EOK}, capital={2025: 100 * EOK})
    annual = [{"kind": "감사의견", "sev": 3, "date": "20260315", "report_nm": "감사보고서(의견거절)"}]
    half = [{"kind": "감사의견", "sev": 2, "date": "20250815", "report_nm": "반기검토보고서(의견거절)"}]
    assert dl._assess("000001", ser, {"market": "KOSDAQ", "dept": ""}, "테", alerts=annual)["level"] == 3
    a = dl._assess("000001", ser, {"market": "KOSDAQ", "dept": ""}, "테", alerts=half)
    assert a["level"] == 2 and "(C)" in _texts(a)


def test_unfaithful_disclosure_counts():
    ser = _ser(equity={2025: 100 * EOK}, capital={2025: 100 * EOK})
    one = [{"kind": "관리·상폐", "sev": 3, "date": "20260101", "report_nm": "불성실공시법인지정"}]
    a1 = dl._assess("000001", ser, {"market": "KOSDAQ", "dept": ""}, "테", alerts=one)
    assert a1["level"] == 1 and "10점" in _texts(a1)      # 2026 개혁: 벌점 15 → 10점
    a2 = dl._assess("000001", ser, {"market": "KOSDAQ", "dept": ""}, "테", alerts=one * 2)
    assert a2["level"] == 2 and "공시의무 위반" in _texts(a2)


def test_stale_alerts_do_not_trigger_requirements():
    """3년 전 감사의견 거절로 지금 상폐 요건이라고 말하면 안 된다(18개월 창)."""
    ser = _ser(equity={2025: 100 * EOK}, capital={2025: 100 * EOK})
    stale = [{"kind": "감사의견", "sev": 3, "date": "20230201", "report_nm": "감사보고서(의견거절)"}]
    assert dl._assess("000001", ser, {"market": "KOSDAQ", "dept": ""}, "테", alerts=stale) is None


def test_disclosure_classifier_splits_opinion_from_restatement():
    assert dl._classify_disclosure("감사보고서제출(의견거절)") == (3, "감사의견")
    assert dl._classify_disclosure("반기검토보고서(범위제한 한정)") == (2, "감사의견")
    assert dl._classify_disclosure("[정정]사업보고서") == (2, "감사·정정")
    assert dl._classify_disclosure("연결재무제표기준영업(잠정)실적") == (1, "잠정실적")
    # 사유가 '해소'된 공시를 상폐 사유로 잡으면 안 된다(실제 오탐이었다)
    assert dl._classify_disclosure("기타경영사항(자율공시)(감사의견거절 사유 해소에 대한 확인)") is None


# ── 제외 대상 ──────────────────────────────────────────────────────────────
def test_spac_and_foreign_are_excluded():
    ser = _ser(sales={2025: 1 * EOK, 2024: 1 * EOK})
    assert dl._assess("000001", ser, {"market": "KOSDAQ", "dept": "SPAC(소속부없음)"}, "머스트스팩") is None
    assert dl._assess("000001", ser, {"market": "KOSDAQ", "dept": "외국기업"}, "테") is None
