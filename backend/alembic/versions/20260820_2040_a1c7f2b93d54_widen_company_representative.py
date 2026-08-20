"""widen company representative

대표자명을 64자로 잡았는데 실데이터가 넘친다. 공동대표는 이름 하나가 아니라
"A and B (individual representative directors)" 처럼 한 칸에 여러 명과 직위 설명이
들어오기 때문이다(실측 최대 67자). 이관이 그 한 행에서 멈췄다.

64는 "사람 이름"을 가정한 폭이었고, 이 칸이 담는 건 사람 이름이 아니라 **대표자 표기**다.
데이터가 정의를 바로잡은 셈이라 다른 자유서술 칸(homepage 255)과 같은 폭으로 맞춘다.

Revision ID: a1c7f2b93d54
Revises: 03139a655c31
Create Date: 2026-08-20 20:40:00.000000+09:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c7f2b93d54'
down_revision: Union[str, None] = '03139a655c31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'company_profile', 'representative',
        existing_type=sa.String(length=64),
        type_=sa.String(length=255),
        existing_nullable=True,
        schema='market',
    )


def downgrade() -> None:
    # 되돌리면 67자짜리 행이 잘린다. 자르지 않고 실패하게 두는 편이 낫다 —
    # 조용히 잘린 대표자명은 나중에 원본과 대조할 때만 드러난다.
    op.alter_column(
        'company_profile', 'representative',
        existing_type=sa.String(length=255),
        type_=sa.String(length=64),
        existing_nullable=True,
        schema='market',
    )
