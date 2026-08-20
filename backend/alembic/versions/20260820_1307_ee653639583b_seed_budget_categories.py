"""seed budget categories

카테고리 기준표를 채운다. **비어 있으면 거래를 한 건도 못 넣는다** —
``transaction.category_code`` 가 이 표를 참조하는 외래키라서다.

실제로 그렇게 막혔다. 스키마는 올라갔고 이관도 '성공' 했는데, 거래 60건의 카테고리가
전부 NULL 이었다(이관 스크립트가 카테고리를 안 옮겼고, 그래서 외래키에 안 걸렸다).
새로 등록을 시도한 순간에야 드러났다 — 참조 무결성이 있는데 채워 넣지 않으면 이렇게
**늦게** 터진다.

목록은 애플리케이션의 ``categories.CATEGORIES`` 와 같아야 한다. 화면 드롭다운과 집계
축이 같은 목록을 봐야 하기 때문이다. 여기에 값을 박아 두는 이유는 마이그레이션이
애플리케이션 코드의 현재 상태에 의존하면 안 되기 때문이다 — 리비전은 **그때의 사실**을
남기는 것이지, 나중에 코드가 바뀌면 같이 바뀌는 것이 아니다.

Revision ID: ee653639583b
Revises: dade0747a11f
Create Date: 2026-08-20
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "ee653639583b"
down_revision: Union[str, None] = "dade0747a11f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 순서가 곧 화면의 표시 순서다. '기타' 는 마지막.
_CATEGORIES = [
    "식비/외식",
    "카페/간식",
    "장보기/마트",
    "교통/차량",
    "여행/숙박",
    "통신",
    "주거/공과금",
    "쇼핑",
    "문화/여가",
    "의료/건강",
    "금융/보험",
    "교육/자기계발",
    "구독/기타결제",
    "기타",
]


def upgrade() -> None:
    category = sa.table("category",
                        sa.column("code", sa.String),
                        sa.column("name", sa.String),
                        sa.column("sort_order", sa.Integer),
                        schema="budget")
    # 이미 있으면 건너뛴다 — 리비전을 다시 돌리는 상황(복구·재구축)에서 터지지 않게.
    op.execute(
        sa.dialects.postgresql.insert(category).values([
            {"code": c, "name": c, "sort_order": (i + 1) * 10}
            for i, c in enumerate(_CATEGORIES)
        ]).on_conflict_do_nothing(index_elements=["code"])
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM budget.category WHERE code = ANY(:codes)")
        .bindparams(codes=_CATEGORIES)
    )
