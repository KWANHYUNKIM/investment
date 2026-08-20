"""Alembic 실행 환경.

세 가지를 여기서 처리한다.

**접속정보는 앱 설정에서 읽는다.** alembic.ini 에 URL 을 적으면 git 에 올라가고,
앱과 마이그레이션이 서로 다른 DB 를 보는 사고가 난다.

**스키마를 먼저 만든다.** 이 프로젝트는 도메인별로 PostgreSQL 스키마를 나누는데,
스키마가 없으면 첫 마이그레이션이 통째로 실패한다. Alembic 은 스키마를 자동으로
만들어 주지 않는다.

**소유자 권한으로 붙는다.** 앱 엔진은 접속 즉시 제한된 역할로 갈아입는데, 그 역할을
만드는 게 마이그레이션이라 순환이 생긴다. DDL 은 소유자, 일상 쿼리는 제한 역할 —
권한이 갈리는 것 자체가 목적이기도 하다.

**타입 변경을 감지한다.** ``compare_type`` 을 켜지 않으면 float→NUMERIC 같은 변경이
자동생성에서 조용히 빠진다 — 이 프로젝트에서 가장 중요한 변경이 바로 그것이다.
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import text

from app.core.config import get_settings
from app.db.base import ALL_SCHEMAS, Base
from app.db import models  # noqa: F401 — import 만으로 metadata 에 테이블이 등록된다
from app.db.session import create_admin_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _include_object(obj, name, type_, reflected, compare_to):
    """우리 스키마 밖은 건드리지 않는다.

    같은 DB 에 다른 도구가 만든 표(예: 확장 기능 테이블)가 있을 때, 자동생성이
    그걸 '지워야 할 것' 으로 판단해 DROP 을 써 넣는 사고를 막는다.
    """
    schema = getattr(obj, "schema", None)
    if type_ == "table" and schema not in ALL_SCHEMAS:
        return False
    return True


def run_migrations_offline() -> None:
    """DB 없이 SQL 만 뽑는다 — 운영 반영을 DBA 가 검토해야 할 때 쓴다."""
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        include_object=_include_object,
        compare_type=True,
        version_table_schema="ops",
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_admin_engine()
    with engine.connect() as connection:
        # 스키마가 없으면 아무것도 못 만든다. 마이그레이션 본체가 아니라 여기서 만든다 —
        # 리비전마다 반복할 일이 아니고, 되돌릴 대상도 아니기 때문이다.
        for schema in ALL_SCHEMAS:
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_object=_include_object,
            compare_type=True,               # float → NUMERIC 을 놓치지 않는다
            compare_server_default=True,
            # 버전 표도 ops 에 둔다. public 에 두면 스키마 구획이 반쪽이 된다.
            version_table_schema="ops",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
