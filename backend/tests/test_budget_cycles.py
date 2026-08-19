"""카드별 결제 주기 — 거래일에서 청구월을 계산하는 규칙.

여기서 지키는 건 두 가지다.

1. 사용자가 말한 그대로 나와야 한다. "7월 18일부터 8월 18일까지 쓴 걸 9월에 낸다."
2. **할부는 거래일이 아니라 회차로 잡는다.** 5월에 산 물건의 3회차는 5월 주기가
   아니라 그로부터 2개월 뒤에 빠진다. 이걸 놓치면 몇 달씩 어긋난다.
"""
from __future__ import annotations

from app.data.market import budget
from app.data.market.budget import cycles as C
from app.data.market.budget import store

# 사용자가 말한 카드 — 7/18 ~ 8/18 이용, 9월 납부
USER_CARD = {"cycle_start_day": 18, "cycle_end_day": 18, "pay_day": 1, "pay_offset": 1}
# 전월 12일 ~ 당월 11일 이용, 당월 25일 결제
D25 = {"cycle_start_day": 12, "cycle_end_day": 11, "pay_day": 25, "pay_offset": 0}
# 전월 1일 ~ 말일 이용, 익월 14일 결제
D14 = {"cycle_start_day": 1, "cycle_end_day": 0, "pay_day": 14, "pay_offset": 1}


def test_users_own_card_window() -> None:
    """7/18 부터 쓴 게 9월에 빠진다."""
    w = C.window_for("2026-09", USER_CARD)
    assert w["start"] == "2026-07-18"
    assert w["pay"] == "2026-09-01"


def test_inclusive_days_do_not_overlap_two_cycles() -> None:
    """시작·종료를 같은 날로 넣으면 하루가 겹친다 — 종료를 당겨 한 주기에만 넣는다.

    안 그러면 18일 거래 하나가 두 달에 동시에 잡힌다.
    """
    assert C.window_for("2026-09", USER_CARD)["end"] == "2026-08-17"
    assert C.billing_month_of("2026-07-17", USER_CARD) == "2026-08"
    assert C.billing_month_of("2026-07-18", USER_CARD) == "2026-09"   # 새 주기 첫날
    assert C.billing_month_of("2026-08-17", USER_CARD) == "2026-09"   # 같은 주기 마지막
    assert C.billing_month_of("2026-08-18", USER_CARD) == "2026-10"


def test_pay_offset_is_not_inferred() -> None:
    """종료일이 같아도 결제월이 다른 카드가 있다 — 추론하면 한 달씩 어긋난다."""
    same_end_next_month = {"cycle_start_day": 12, "cycle_end_day": 11, "pay_day": 25, "pay_offset": 1}
    assert C.window_for("2026-08", D25)["pay"] == "2026-08-25"
    assert C.window_for("2026-09", same_end_next_month)["pay"] == "2026-09-25"
    # 같은 이용기간(2026-08-12 ~ 2026-09-11)인데 결제월만 다르다
    assert C.window_for("2026-09", D25)["start"] == "2026-08-12"
    assert C.window_for("2026-10", same_end_next_month)["start"] == "2026-08-12"


def test_month_end_is_handled() -> None:
    """'말일'(0)은 2월엔 28일, 8월엔 31일이어야 한다."""
    assert C.window_for("2026-09", D14) == {
        "start": "2026-08-01", "end": "2026-08-31", "pay": "2026-09-14"}
    assert C.window_for("2026-03", D14)["end"] == "2026-02-28"


def test_installment_uses_the_round_not_the_purchase_date() -> None:
    """5/17 구매 12개월 할부 — 3회차는 5월 주기가 아니라 2개월 뒤에 빠진다."""
    samsung = {"cycle_start_day": 18, "cycle_end_day": 17, "pay_day": 1, "pay_offset": 1}
    assert [C.billing_month_of("2026-05-17", samsung, n) for n in (1, 2, 3, 4)] == \
        ["2026-06", "2026-07", "2026-08", "2026-09"]
    # 회차를 안 주면 1회차와 같다 — 일시불 경로
    assert C.billing_month_of("2026-05-17", samsung) == "2026-06"


def test_year_boundary() -> None:
    # 12/20 은 12/18 에 시작한 주기(→ 1/17 종료)라 익월인 2월에 빠진다.
    assert C.billing_month_of("2026-12-20", USER_CARD) == "2027-02"
    assert C.billing_month_of("2026-12-17", USER_CARD) == "2027-01"
    assert C.window_for("2027-01", USER_CARD)["start"] == "2026-11-18"


# --- 저장된 거래에 적용 ------------------------------------------------------
def _user(tmp_path, monkeypatch) -> str:
    monkeypatch.setattr(store, "_path", lambda user: str(tmp_path / f"b_{user}.json"))
    return "tester"


def test_setting_a_cycle_recalculates_existing_transactions(tmp_path, monkeypatch) -> None:
    from tests.test_budget_cards import SHINHAN_XLS
    user = _user(tmp_path, monkeypatch)
    budget.import_file(user, "명세서.xls", SHINHAN_XLS)
    assert budget.summary(user)["month"] == "2026-09"      # 명세서 제목이 말한 값

    budget.set_cycle(user, "신한카드 본인717", D25)
    res = budget.recalc_billing_months(user)
    assert res["changed"] > 0
    # 7/20 · 7/26 · 8/10 은 모두 '전월 12일~당월 11일' 주기에 걸려 8월 청구가 된다.
    months = {t["billing_month"] for t in budget.summary(user, "all")["transactions"]}
    assert months == {"2026-08"}


def test_cycle_conflict_is_reported_not_silently_applied(tmp_path, monkeypatch) -> None:
    """명세서가 청구월을 적어 줬는데 설정과 다르면, 덮어쓰지 말고 알려야 한다.

    조용히 덮어쓰면 설정이 한 달 어긋난 채로 다음 파일들까지 같은 오차로 쌓인다.
    """
    from tests.test_budget_cards import SHINHAN_XLS
    user = _user(tmp_path, monkeypatch)
    budget.set_cycle(user, "신한카드 본인717", D25)
    rep = budget.preview_file(user, "명세서.xls", SHINHAN_XLS)
    assert rep["billing_month"] == "2026-09"                # 파일값 그대로
    assert rep["cycle_conflict"]["stated"] == "2026-09"
    assert "2026-08" in rep["cycle_conflict"]["by_cycle"]
    assert "결제일 설정을 확인" in rep["note"]


def test_cycle_fills_in_when_the_file_does_not_say(tmp_path, monkeypatch) -> None:
    """청구월이 없는 카드사(롯데·하나)는 설정이 있으면 추정 대신 계산값을 쓴다."""
    from tests.test_budget_cards_issuers import LOTTE_XLS
    user = _user(tmp_path, monkeypatch)

    before = budget.preview_file(user, "일시불 결제예정금액.xls", LOTTE_XLS)
    assert before["billing_month_known"] is False          # 추정

    budget.set_cycle(user, "롯데카드 본인 159", D25)
    after = budget.preview_file(user, "일시불 결제예정금액.xls", LOTTE_XLS)
    assert after["billing_month_known"] is True
    assert after["cycle_applied"] > 0
    # 일시불(7/30 · 8/1)은 8월 청구, 할부 2회차(8/2 거래)는 1회차의 다음 달인 9월이다.
    assert after["billing_months"] == ["2026-08", "2026-09"]
    inst = next(t for t in after["transactions"] if "테스트가전" in t["merchant"])
    assert inst["billing_month"] == "2026-09"
    assert "카드 설정" in after["note"]


def test_cards_overview_shows_the_window(tmp_path, monkeypatch) -> None:
    from tests.test_budget_cards import SHINHAN_XLS
    user = _user(tmp_path, monkeypatch)
    budget.import_file(user, "명세서.xls", SHINHAN_XLS)
    budget.set_cycle(user, "신한카드 본인717", USER_CARD)

    row = next(c for c in budget.cards_overview(user)["cards"] if c["card"] == "신한카드 본인717")
    assert row["configured"] is True
    assert row["window"]["start"] == "2026-07-18"
    assert row["window"]["pay"] == "2026-09-01"
    assert "익월 1일 결제" in row["describe"]


def test_clearing_a_cycle_stops_auto_calculation(tmp_path, monkeypatch) -> None:
    user = _user(tmp_path, monkeypatch)
    budget.set_cycle(user, "롯데카드 본인 159", D25)
    assert budget.store.get_cycles(user)
    budget.set_cycle(user, "롯데카드 본인 159", None)
    assert not budget.store.get_cycles(user)
