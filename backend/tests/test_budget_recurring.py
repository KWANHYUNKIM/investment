"""고정지출 판정 — '계속 나가는 돈'만 골라낸다.

핵심은 **반복만으로는 부족하다**는 것이다. 매달 가는 마트도 반복이지만 금액이
제각각이면 변동비다. 반대로 통신비는 달마다 조금씩 달라도 배수로 튀지 않는다.
그래서 반복 + 금액 유사 + 카테고리/키워드 + 사용자 지정을 함께 본다.
"""
from __future__ import annotations

from app.data.market.budget import recurring as R


def tx(date: str, merchant: str, amount: float, category: str = "기타", **kw) -> dict:
    return {"date": date, "billing_month": date[:7], "merchant": merchant, "amount": amount,
            "charged": amount, "fee": 0.0, "total": amount, "category": category,
            "issuer": "테스트카드", "card": "본인1", "tx_type": "일시불",
            "installment": None, **kw}


def _names(rows: list[dict]) -> set[str]:
    return {r["merchant"] for r in rows}


def test_steady_repeat_is_fixed() -> None:
    """같은 곳에서 여러 달 비슷한 금액 — 가장 확실한 고정지출 신호."""
    txs = [tx("2026-06-05", "넷플릭스", 17000), tx("2026-07-05", "넷플릭스", 17000),
           tx("2026-08-05", "넷플릭스", 17000)]
    out = R.analyze(txs)
    item = out["items"][0]
    assert item["merchant"] == "넷플릭스"
    assert item["source"] == "반복 결제"
    assert item["cadence"] == "매월"
    assert item["monthly"] == 17_000
    assert item["annual"] == 204_000
    assert item["next_expected"] == "2026-09-04"      # 마지막 결제 + 중앙값 간격(30일)


def test_repeat_with_wild_amounts_is_not_fixed() -> None:
    """매달 가는 마트는 고정비가 아니다 — 이걸 안 거르면 장보기가 전부 고정비가 된다."""
    txs = [tx("2026-06-05", "선비할인마트", 6800), tx("2026-07-08", "선비할인마트", 20000),
           tx("2026-08-16", "선비할인마트", 14047)]
    out = R.analyze(txs)
    assert out["items"] == []
    assert _names(out["candidates"]) == {"선비할인마트"}
    assert "금액이 달마다" in out["candidates"][0]["reason"]


def test_small_variation_still_counts_as_steady() -> None:
    """통신비처럼 달마다 조금씩 달라도 고정비다(배수로 튀지 않는다)."""
    txs = [tx("2026-06-11", "KT통신요금", 63000), tx("2026-07-11", "KT통신요금", 66500),
           tx("2026-08-11", "KT통신요금", 65968)]
    assert R.analyze(txs)["items"][0]["source"] == "반복 결제"


def test_one_off_subscription_is_caught_by_category() -> None:
    """한 달치만 있으면 반복을 볼 수 없다 — 구독·공과금 분류로 잡는다."""
    txs = [tx("2026-08-10", "ANTHROPIC* CLAUDE SUB", 159021, "구독/기타결제"),
           tx("2026-08-11", "KT통신요금 자동납부", 65968, "통신"),
           tx("2026-08-05", "동두천왓따부대찌게", 35820, "식비/외식")]
    out = R.analyze(txs)
    assert _names(out["items"]) == {"ANTHROPIC* CLAUDE SUB", "KT통신요금 자동납부"}
    assert all(i["source"] == "구독·공과금 분류" for i in out["items"])


def test_user_override_wins_both_ways() -> None:
    """자동 판정이 틀렸을 때 못박을 수 있어야 한다."""
    txs = [tx("2026-08-05", "월세이체", 700000, "기타"),
           tx("2026-08-10", "ANTHROPIC* CLAUDE SUB", 159021, "구독/기타결제")]
    out = R.analyze(txs, {"월세이체": True, "ANTHROPIC* CLAUDE SUB": False})
    assert _names(out["items"]) == {"월세이체"}
    assert out["items"][0]["source"] == "직접 지정"


def test_totals_and_annual_projection() -> None:
    txs = [tx("2026-06-05", "넷플릭스", 17000, "문화/여가"),
           tx("2026-07-05", "넷플릭스", 17000, "문화/여가"),
           tx("2026-08-11", "KT통신요금", 66000, "통신")]
    out = R.analyze(txs)
    assert out["count"] == 2
    assert out["monthly_total"] == 83_000
    assert out["annual_total"] == 996_000
    assert out["by_category"][0] == {"category": "통신", "monthly": 66000}


def test_cancelled_and_projected_rows_are_ignored() -> None:
    """취소는 나가는 돈이 아니고, 예정분은 아직 일어나지 않은 일이다."""
    txs = [tx("2026-06-05", "넷플릭스", 17000), tx("2026-07-05", "넷플릭스", 17000),
           tx("2026-08-05", "넷플릭스", -17000, tx_type="취소"),
           tx("2026-09-05", "넷플릭스", 17000, projected=True)]
    item = R.analyze(txs)["items"][0]
    assert item["count"] == 2
    assert item["total"] == 34_000


def test_branch_names_are_grouped() -> None:
    """지점·단말기 번호가 달라도 같은 곳으로 묶어야 반복이 보인다."""
    txs = [tx("2026-06-05", "스타벅스 강남2호점", 5600),
           tx("2026-07-05", "스타벅스강남", 5600),
           tx("2026-08-05", "스타벅스 강남", 5600)]
    out = R.analyze(txs)
    assert len(out["items"]) == 1
    assert out["items"][0]["count"] == 3


def test_summary_and_panel_agree(tmp_path, monkeypatch) -> None:
    """요약의 고정비 합계와 고정지출 화면의 합계가 어긋나면 안 된다.

    예전엔 두 곳이 서로 다른 규칙(요약은 '여러 달에 나왔나'만)으로 판정해서
    같은 데이터에 두 숫자가 나왔다.
    """
    from app.data.market import budget
    from app.data.market.budget import store
    monkeypatch.setattr(store, "_path", lambda user: str(tmp_path / f"b_{user}.json"))
    budget.add_transactions("u", [
        tx("2026-08-10", "ANTHROPIC* CLAUDE SUB", 159021, "구독/기타결제"),
        tx("2026-08-11", "KT통신요금 자동납부", 65968, "통신"),
        tx("2026-08-16", "선비할인마트", 14047, "장보기/마트"),
        tx("2026-08-09", "선비할인마트", 6796, "장보기/마트"),
    ])
    s = budget.summary("u", "2026-08")
    board = budget.fixed_costs("u")
    assert s["by_fixed"]["fixed"] == board["monthly_total"] == 224_989
    assert "선비할인마트" not in {i["key"] for i in s["by_fixed"]["items"]}
