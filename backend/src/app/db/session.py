"""엔진·세션 — 커넥션 풀과 트랜잭션 경계를 한 곳에서 정한다.

FastAPI 에서 가장 흔히 틀리는 것들을 여기서 막는다.

**요청마다 세션 하나.** 세션을 전역으로 두면 요청들이 같은 트랜잭션을 공유해, 한
요청의 롤백이 다른 요청의 저장을 날린다.

**커넥션 풀 크기를 정해 둔다.** 기본값으로 두면 스케줄러 10개가 각자 커넥션을 물고
늘어져 웹 요청이 굶는다. 이 앱은 백그라운드 배치가 많아 특히 그렇다.

**보안 설정은 트랜잭션 안에 둔다.** 이게 실제로 이 프로젝트에서 터진 문제다 —
접속 시점에 ``SET ROLE`` 로 역할을 바꿨더니 커넥션이 풀에서 재사용될 때 풀려서,
두 번째 요청부터 행 수준 보안이 통째로 무력해졌다. 세션 단위 설정은 반대 방향으로도
위험하다: 앞 요청의 정체성이 풀을 타고 다음 요청으로 샌다. ``SET LOCAL`` 은 트랜잭션이
끝나면 자동으로 되돌아가므로 두 문제가 같이 사라진다.
"""
from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    s = get_settings()
    engine = create_engine(
        s.database_url,
        pool_size=s.db_pool_size,
        max_overflow=s.db_max_overflow,
        pool_pre_ping=True,          # 끊긴 커넥션을 조용히 골라낸다
        pool_recycle=1800,           # 30분마다 갈아 끼운다(방화벽 타임아웃 회피)
        echo=s.db_echo,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_connection_defaults(dbapi_conn, _rec):
        """커넥션 수명 내내 유지돼도 **안전한 것만** 여기 둔다.

        시각은 전부 UTC 로 저장·해석한다. 서버 시간대에 기대면 컨테이너를 옮기는
        순간 과거 데이터의 의미가 달라진다.

        역할·사용자 같은 보안 설정은 여기 두지 않는다 — 풀에서 재사용될 때 어떻게
        되는지에 안전이 걸리면 안 된다. 그건 ``bind_request_context`` 가 맡는다.
        """
        with dbapi_conn.cursor() as cur:
            cur.execute("SET TIME ZONE 'UTC'")
            # 한 문장이 오래 잡고 있으면 뒤가 전부 막힌다 — 배치 실수의 폭발을 제한한다.
            cur.execute("SET statement_timeout = '30s'")
            cur.execute("SET idle_in_transaction_session_timeout = '60s'")

    return engine


def create_admin_engine() -> Engine:
    """소유자 권한 그대로 붙는 엔진 — **마이그레이션 전용**.

    앱은 트랜잭션마다 제한된 역할로 갈아입는데, 그 역할을 만드는 것이 마이그레이션이다.
    DDL 은 소유자만, 일상 조회·수정은 제한된 역할만 — 권한이 갈리는 것 자체가 목적이다.
    """
    s = get_settings()
    return create_engine(s.database_url, pool_pre_ping=True, future=True)


@lru_cache(maxsize=1)
def get_sessionmaker() -> sessionmaker[Session]:
    # expire_on_commit=False: 커밋 뒤에도 객체를 읽을 수 있게 한다. True 면 응답을
    # 직렬화하는 순간 다시 SELECT 가 나가고, 세션이 이미 닫혔으면 터진다.
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


def bind_request_context(session: Session, user_id: int | None) -> None:
    """이 트랜잭션이 **누구의 것인지** DB 에 알린다. 행 수준 보안이 이 값을 본다.

    두 문장 다 트랜잭션 지역 설정이다(``SET LOCAL`` / ``set_config(..., true)``).

    역할을 먼저 바꾸는 이유: PostgreSQL 은 슈퍼유저·테이블 소유자에게 행 수준 보안을
    **적용하지 않는다.** 정책을 다 켜 놓고도 소유자 계정으로 붙으면 남의 행이 그대로
    보인다 — 켠 줄 알고 있어서 더 위험한 종류의 구멍이다.

    사용자를 못 정하면 빈 값을 넣는다. 그러면 정책이 **모든 행을 막는 쪽**으로
    실패한다 — 못 정했을 때 다 보이는 것보다 아무것도 안 보이는 게 옳다.
    """
    s = get_settings()
    if s.db_app_role:
        session.execute(text(f'SET LOCAL ROLE "{s.db_app_role}"'))
    session.execute(text("SELECT set_config('app.current_user_id', :uid, true)"),
                    {"uid": str(user_id) if user_id is not None else ""})


def session_scope() -> Iterator[Session]:
    """FastAPI 의존성. 성공하면 커밋, 예외면 롤백 — 라우터가 신경 쓰지 않게 한다.

    사용자 컨텍스트는 인증을 거친 뒤 ``bind_request_context`` 로 붙인다. 여기서
    일괄로 붙이지 않는 이유는 이 의존성이 로그인 전 요청에도 쓰이기 때문이다.
    """
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
