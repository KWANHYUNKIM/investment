"""파일 저장소와 PostgreSQL 저장소가 **같은 답을 내는가**.

저장소를 갈아 끼울 때 무서운 건 기능이 죽는 게 아니라 **조용히 달라지는** 것이다.
합계가 몇 원 어긋나거나 고정지출 판정이 뒤집혀도 화면은 멀쩡히 뜬다. 그래서 같은
입력을 두 저장소에 넣고 결과를 맞춰 본다.

두 판이 같은 계약(같은 함수 이름, 같은 dict 모양)을 지키는 게 전환 전략의 전부라,
그 계약이 실제로 지켜지는지도 여기서 고정한다.

PostgreSQL 이 없으면 통째로 건너뛴다.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.db

_TXS = [
    {"date": "2026-08-01", "merchant": "스타벅스 강남점", "amount": 5600,
     "billing_month": "2026-09", "issuer": "신한카드", "card": "본인717",
     "tx_type": "일시불"},
    {"date": "2026-08-03", "merchant": "GS25 역삼", "amount": 3200,
     "billing_month": "2026-09", "issuer": "신한카드", "card": "본인717",
     "tx_type": "일시불"},
    {"date": "2026-08-05", "merchant": "쿠팡", "amount": 15000, "charged": 15000,
     "fee": 450, "total": 45000, "billing_month": "2026-09", "issuer": "신한카드",
     "card": "본인717", "tx_type": "할부",
     "installment": {"months": 3, "seq": 1, "remaining": 30000}},
    {"date": "2026-08-07", "merchant": "넷플릭스", "amount": 17000,
     "billing_month": "2026-09", "issuer": "롯데카드", "card": "본인003",
     "tx_type": "일시불"},
]

_USER = "parity_test_user"


@pytest.fixture
def stores(monkeypatch, tmp_path):
    """두 저장소를 나란히 준비한다. 파일은 임시 경로, DB 는 테스트 전용 계정."""
    from sqlalchemy import delete, select, text

    try:
        from app.data.market.budget import store as store_json
        from app.data.market.budget import store_pg
        from app.db.models import AppUser, Card, ImportBatch, MerchantRule, Transaction
        from app.db.session import get_sessionmaker
        s = get_sessionmaker()()
        s.execute(text("SELECT 1"))
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"PostgreSQL 없음 — 건너뜀 ({type(e).__name__})")

    monkeypatch.setattr(store_json, "_path", lambda u: str(tmp_path / f"budget_{u}.json"))

    # DB 쪽 테스트 계정을 비운다 — 앞선 실행이 남긴 것과 섞이면 대조가 무의미하다.
    s.execute(text("SELECT set_config('app.current_user_id', '', true)"))
    uid = s.scalar(select(AppUser.id).where(AppUser.username == _USER))
    if uid is not None:
        for model in (Transaction, ImportBatch, MerchantRule, Card):
            s.execute(delete(model).where(model.user_id == uid))
        s.commit()
    s.close()

    yield store_json, store_pg

    s = get_sessionmaker()()
    s.execute(text("SELECT set_config('app.current_user_id', '', true)"))
    uid = s.scalar(select(AppUser.id).where(AppUser.username == _USER))
    if uid is not None:
        for model in (Transaction, ImportBatch, MerchantRule, Card):
            s.execute(delete(model).where(model.user_id == uid))
        s.commit()
    s.close()


def _seed(store, user: str) -> dict:
    return store.add_transactions(user, _TXS, source={
        "filename": "test.xls", "issuer": "신한카드",
        "billing_month": "2026-09", "parsed_by": "shinhan"})


def _norm(txs: list[dict]) -> list[tuple]:
    """비교용으로 추린다. id 는 저장소마다 다르므로 뺀다."""
    return sorted((t["date"], t["merchant"], t["amount"], t["charged"], t["fee"],
                   t["total"], t["billing_month"], t["tx_type"], t["category"])
                  for t in txs)


# --- 등록 -------------------------------------------------------------------
def test_same_transactions_land_in_both(stores) -> None:
    js, pg = stores
    a = _seed(js, _USER)
    b = _seed(pg, _USER)
    assert a == b == {"added": 4, "skipped": 0}
    assert _norm(js.load(_USER)["transactions"]) == _norm(pg.load(_USER)["transactions"])


def test_duplicate_import_is_skipped_in_both(stores) -> None:
    """같은 명세서를 두 번 올리는 건 흔한 일이다. 두 저장소가 똑같이 걸러야 한다."""
    js, pg = stores
    _seed(js, _USER)
    _seed(pg, _USER)
    assert _seed(js, _USER) == _seed(pg, _USER) == {"added": 0, "skipped": 4}


def test_money_sums_match(stores) -> None:
    """합계가 몇 원 어긋나도 화면은 멀쩡히 뜬다 — 그래서 여기서 잡아야 한다."""
    js, pg = stores
    _seed(js, _USER)
    _seed(pg, _USER)
    for field in ("amount", "charged", "fee", "total"):
        a = sum(t[field] for t in js.load(_USER)["transactions"])
        b = sum(t[field] for t in pg.load(_USER)["transactions"])
        assert a == b, f"{field} 합계가 다르다: 파일 {a} vs DB {b}"


def test_installment_survives_the_round_trip(stores) -> None:
    """할부 회차가 사라지면 '남은 할부' 와 미래 예정지출이 통째로 틀어진다."""
    js, pg = stores
    _seed(js, _USER)
    _seed(pg, _USER)
    a = next(t for t in js.load(_USER)["transactions"] if t["merchant"] == "쿠팡")
    b = next(t for t in pg.load(_USER)["transactions"] if t["merchant"] == "쿠팡")
    assert a["installment"]["months"] == b["installment"]["months"] == 3
    assert a["installment"]["seq"] == b["installment"]["seq"] == 1


# --- 집계 로직이 그대로 먹는가 -------------------------------------------------
def test_summary_gives_the_same_numbers(stores, monkeypatch) -> None:
    """저장소를 바꿔도 집계 로직은 한 줄도 안 바뀐다 — 그게 이 전환 전략의 전제다.

    집계 모듈은 ``store.load(user)`` 하나만 부르므로, 그 함수를 갈아 끼워 두 저장소를
    같은 코드에 통과시킨다.
    """
    import importlib

    # 패키지에서 ``summary`` 라는 이름은 **함수**를 가리킨다(__init__ 이 그렇게 내보낸다).
    # 모듈을 잡으려면 경로로 직접 불러와야 한다.
    S = importlib.import_module("app.data.market.budget.summary")

    js, pg = stores
    _seed(js, _USER)
    _seed(pg, _USER)

    # summary 는 ``from .store import load`` 로 함수를 직접 들고 있다.
    monkeypatch.setattr(S, "load", js.load)
    a = S.summary(_USER, "2026-09")

    monkeypatch.setattr(S, "load", pg.load)
    b = S.summary(_USER, "2026-09")

    # 집계의 뼈대가 같아야 한다 — 지출·건수·저축여력·네 축 전부.
    for key in ("spent", "count", "refund", "committed", "savings_possible"):
        assert a[key] == b[key], f"{key} 가 다르다: 파일 {a[key]} vs DB {b[key]}"
    assert len(a["transactions"]) == len(b["transactions"])
    for axis in ("by_category", "by_card", "by_tx_type"):
        ka = {(r.get("category") or r.get("card") or r.get("tx_type"), r["amount"])
              for r in a[axis]}
        kb = {(r.get("category") or r.get("card") or r.get("tx_type"), r["amount"])
              for r in b[axis]}
        assert ka == kb, f"{axis} 가 다르다"


def test_fixed_cost_rules_match(stores) -> None:
    """사용자가 못박은 고정비 규칙이 두 저장소에서 같게 읽혀야 한다."""
    js, pg = stores
    _seed(js, _USER)
    _seed(pg, _USER)
    js.set_fixed(_USER, "넷플릭스", True)
    pg.set_fixed(_USER, "넷플릭스", True)
    assert js.load(_USER)["fixed_rules"] == pg.load(_USER)["fixed_rules"]


# --- 편집 -------------------------------------------------------------------
def test_category_change_applies_to_all_in_both(stores) -> None:
    js, pg = stores
    _seed(js, _USER)
    _seed(pg, _USER)
    for store in (js, pg):
        tx = next(t for t in store.load(_USER)["transactions"] if t["merchant"] == "쿠팡")
        store.set_category(_USER, tx["id"], "쇼핑", apply_all=True)
    assert (js.load(_USER)["cat_rules"].get("쿠팡")
            == pg.load(_USER)["cat_rules"].get("쿠팡") == "쇼핑")


def test_clear_import_removes_the_same_rows(stores) -> None:
    """'방금 잘못 올린 명세서 되돌리기' — 두 저장소가 같은 것을 지워야 한다."""
    js, pg = stores
    _seed(js, _USER)
    _seed(pg, _USER)
    a = js.clear_import(_USER, "신한카드", "2026-09")
    b = pg.clear_import(_USER, "신한카드", "2026-09")
    assert a == b == {"removed": 3}
    assert len(js.load(_USER)["transactions"]) == len(pg.load(_USER)["transactions"]) == 1


def test_move_month_matches(stores) -> None:
    """청구월이 한 달 어긋났을 때 통째로 옮기는 동작. 지문이 다시 만들어져야 한다."""
    js, pg = stores
    _seed(js, _USER)
    _seed(pg, _USER)
    a = js.move_month(_USER, "롯데카드", "2026-09", "2026-10")
    b = pg.move_month(_USER, "롯데카드", "2026-09", "2026-10")
    assert a["moved"] == b["moved"] == 1
    for store in (js, pg):
        t = next(t for t in store.load(_USER)["transactions"] if t["issuer"] == "롯데카드")
        assert t["billing_month"] == "2026-10"


def test_delete_matches(stores) -> None:
    js, pg = stores
    _seed(js, _USER)
    _seed(pg, _USER)
    for store in (js, pg):
        tx = store.load(_USER)["transactions"][0]
        assert store.delete_transaction(_USER, tx["id"]) == {"ok": True}
        assert len(store.load(_USER)["transactions"]) == 3


def test_card_cycle_round_trips(stores) -> None:
    """결제 주기 설정이 어긋나면 청구월 계산이 통째로 틀어진다."""
    js, pg = stores
    cfg = {"cycle_start_day": 1, "cycle_end_day": 31, "pay_day": 14, "pay_offset": 1}
    a = js.set_cycle(_USER, "신한카드 본인717", cfg)
    b = pg.set_cycle(_USER, "신한카드 본인717", cfg)
    assert a["cycle"] == b["cycle"]
    assert js.get_cycles(_USER) == pg.get_cycles(_USER)
