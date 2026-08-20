"""테스트 공통 설정.

**테스트는 개발자의 ``.env`` 를 타면 안 된다.** 실제로 그렇게 깨졌다 — 가계부
저장소를 PostgreSQL 로 켠 순간, 파일 저장소를 전제로 쓰인 기존 검증 16개가 한꺼번에
실패했다. 기능이 망가진 게 아니라 **테스트가 환경에 의존**하고 있던 것이다.

그래서 여기서 저장소를 파일로 못박는다. 도메인 로직(집계·고정지출 판정·청구월 계산)을
검증하는 데 어느 저장소를 쓰는지는 상관이 없고, 오히려 DB 가 떠 있어야만 돌아가는
검증이 되면 CI 가 통째로 빨개진다.

저장소 자체를 검증하는 것들(``test_db_schema`` · ``test_budget_store_parity``)은
``pytest.mark.db`` 를 달고 직접 DB 에 붙는다 — 그쪽은 이 고정의 영향을 받지 않는다.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _file_backed_budget(monkeypatch):
    """가계부 저장소를 파일로 고정한다.

    ``budget`` 패키지는 import 시점에 저장소를 골라 이름을 묶어 두므로, 설정만
    바꾸면 이미 묶인 이름은 그대로다. 묶인 것까지 되돌린다.
    """
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "budget_storage", "json", raising=False)

    from app.data.market import budget
    from app.data.market.budget import store as store_json

    monkeypatch.setattr(budget, "backing", store_json)
    for name in ("add_transactions", "clear_import", "clear_month", "delete_transaction",
                 "move_month", "recalc_billing_months", "set_category", "set_cycle",
                 "set_fixed", "set_income"):
        monkeypatch.setattr(budget, name, getattr(store_json, name))
