# DB 설계 — PostgreSQL 시스템 오브 레코드

FastAPI 를 유지하면서 저장소를 제대로 놓는다. 설계만 적은 문서가 아니라 **실제로
올라가서 도는 스키마**다 — 마이그레이션이 PostgreSQL 17 에 적용됐고, 규칙이 지켜지는지
검증 10개가 DB 에 붙어서 통과한다.

작성 2026-08-20 · 코드 `backend/src/app/db/`, `backend/alembic/`

---

## 1. 지금 무엇이 문제였나 (실측)

전수 조사한 결과다. 추측이 아니라 파일과 테이블을 열어 세었다.

| 저장소 | 내용 | 규모 |
|---|---|---|
| `market.duckdb` | prices, dart_financials, investor_flow, fundamentals, securities … | **437만 + 278만 행** 등 |
| `data/*.json` 16개 | 계정·가계부·관심종목·자산계획·부동산 집계·방문통계 | 최대 750KB |
| `data/dart_business/` | DART 원문·파싱 캐시 | **1,794 MB** (1,634 파일) |
| `data/daily_reports/` 등 | 배치 산출물 | 32MB 외 |

**관계형 DB가 통째로 없다.** 사용자 데이터가 전부 JSON 파일이고, 그래서 이런 것들이 없다.

- **트랜잭션** — 거래 등록 중 죽으면 절반만 반영된다
- **동시성** — 파일을 통째로 읽고 통째로 쓴다. 두 요청이 겹치면 나중 쓰기가 앞 쓰기를 날린다. 지금은 프로세스 안 락으로 막고 있어 **서버가 둘이 되는 순간 깨진다**
- **스키마** — `_migrate()` 함수가 예전 파일에 없는 키를 손으로 채운다
- **타입** — **금액이 float 다.** 0.1 + 0.2 ≠ 0.3 인 세계에서 6만 건을 더하면 원 단위가 조용히 어긋난다
- **권한 경계** — 비밀번호 해시가 사용자 정보와 한 덩어리라 "이 코드는 해시를 못 보게" 가 불가능

---

## 2. 무엇을 옮기고 무엇을 남기나

**전부 옮기지 않는다.** 이게 이 설계의 첫 번째 결정이다.

| 데이터 | 위치 | 이유 |
|---|---|---|
| 계정·가계부·포트폴리오·자산계획 | **PostgreSQL** | 트랜잭션·동시성·권한이 필요하다 |
| 종목·기업 기준정보 | **PostgreSQL** | 다른 표가 참조하는 값이라 무결성이 필요하다 |
| 부동산 지역·집계·관심도 | **PostgreSQL** | 셋이 같은 지역·같은 달을 가리키는데 지금은 못 조인한다 |
| 운영 이력·쿼터·계보 | **PostgreSQL** | 지금 메모리에만 있어 재기동하면 사라진다 |
| **시세·재무 시계열** | **DuckDB 유지** | 아래 |
| DART 원문 1.8GB | **파일 유지** | 원문 보관이지 질의 대상이 아니다 |

시세를 옮기지 않는 이유: 이건 **분석 워크로드**다. 한 종목의 10년치를 통째로 스캔하고
전 종목을 훑어 순위를 매긴다. 컬럼 지향 엔진이 압도적으로 유리하고 DuckDB 는 이미 그
일을 잘 하고 있다. PostgreSQL 로 옮기면 저장공간과 스캔 속도를 둘 다 잃으면서 얻는 게
없다 — 참조 무결성이 필요한 데이터가 아니기 때문이다.

대신 **어디에 무엇이 언제** 만 `ops.dataset_snapshot` 에 남긴다. 안 그러면 나중에
누군가 "왜 시세는 DB에 없죠?" 하고 옮겨 버린다. (이런 이종 저장소 조합을
**polyglot persistence** 라 부른다 — §7 레퍼런스)

---

## 3. 스키마 구획 — 도메인마다 하나

`public` 하나에 25개 표를 쏟지 않는다. 가계부와 시장데이터는 수명도 접근권한도 다르다.

```
identity     app_user · user_credential · email_verification · audit_event
budget       card · category · transaction · import_batch · merchant_rule
             income_profile · mail_message
portfolio    watch_item · holding · wealth_profile
market       security · company_profile
realestate   region · region_month_stat · region_month_area_stat
             interest_run · interest_point
ops          batch_run · api_quota_usage · dataset_snapshot · page_view_daily
```

실질적 이득은 **권한을 스키마 단위로 줄 수 있다**는 것이다. 배치 계정에 `budget` 을
통째로 안 주면 된다. 애플리케이션 코드에서만 경계를 나누면 시간이 지나면서 조인 한
줄로 무너진다.

---

## 4. 관통하는 규칙 여섯

### 4.1 돈은 절대 float 가 아니다

```sql
amount   NUMERIC(18,2)   -- 그 청구월에 실제로 빠지는 돈
charged  NUMERIC(18,2)   -- 이번 회차 원금 (할부면 1회차분)
fee      NUMERIC(18,2)   -- 수수료·이자
total    NUMERIC(18,2)   -- 거래 전액
```

네 개로 나눈 것도 그대로 옮겼다. 하나로 합치면 할부가 있는 순간 지출 합계가 통장과
어긋난다. 검증이 `SELECT 0.1::float8 + 0.2::float8 = 0.3::float8` 이 **false** 임을
DB 에 직접 물어 확인한다.

### 4.2 시각은 전부 `timestamptz`, 저장은 UTC

naive timestamp 를 하나라도 허용하면 서버 시간대가 바뀌는 순간 과거 데이터의 의미가
달라진다. 검증이 `timestamp without time zone` 컬럼이 0개임을 확인한다.

### 4.3 대리키 + 자연키 UNIQUE

자연키(티커·지문·법정동코드)를 PK 로 쓰면 그 값이 바뀌는 날 참조하는 모든 표가 흔들린다.
`BIGINT` 대리키를 PK 로, 자연키는 `UNIQUE` 제약으로 건다.

### 4.4 제약조건 이름을 규칙으로 고정

```python
"uq": "uq_%(table_name)s_%(column_0_N_name)s"
"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
```

이름을 DB 가 알아서 붙이게 두면 환경마다 달라져서(`users_email_key` vs `..._key1`)
**운영에서만 마이그레이션이 실패한다.**

### 4.5 기본값은 서버 쪽에

`default=` (파이썬)만 두면 ORM 을 안 거치는 psql·배치 INSERT 가 전부 깨진다.
실제로 검증이 그걸 잡아서 `server_default` 로 전부 옮겼다.

### 4.6 규칙은 DB 가 지킨다

```sql
CHECK (tx_type IN ('일시불','할부','현금서비스','해외','취소'))
UNIQUE (user_id, fingerprint)        -- 같은 명세서 두 번 등록 차단
CHECK ((installment_months IS NULL) = (installment_seq IS NULL))
```

앱 로직으로만 막으면 두 요청이 동시에 들어올 때 뚫린다.

---

## 5. 행 수준 보안 (RLS) — 이 설계의 핵심

지금은 모든 조회가 코드에서 `WHERE user_id = ?` 를 붙인다. **177개 엔드포인트 중
한 곳이라도 빠뜨리면 남의 가계부가 그대로 나간다.** 리뷰로 막는 종류의 사고가 아니다.

```sql
ALTER TABLE budget.transaction ENABLE ROW LEVEL SECURITY;
ALTER TABLE budget.transaction FORCE ROW LEVEL SECURITY;
CREATE POLICY transaction_owner ON budget.transaction
  USING (user_id = ops.current_user_id())
  WITH CHECK (user_id = ops.current_user_id());
```

이러면 정책에 맞지 않는 행은 **SELECT 결과에서 아예 사라진다.** 코드가 조건을 빠뜨려도
남의 행이 나오지 않는다.

### 여기서 두 번 틀렸다 (그리고 검증이 잡았다)

**① 슈퍼유저는 RLS 를 통째로 우회한다.** 정책을 다 켰는데 검증이 실패했다 — 남의 행이
그대로 보였다. 원인은 정책이 아니라 접속 계정이었다. PostgreSQL 은 슈퍼유저에게 행 수준
보안을 적용하지 않고 `FORCE` 도 슈퍼유저는 못 막는다. Docker 이미지가 `POSTGRES_USER` 를
슈퍼유저로 만들기 때문에 그 계정으로 붙는 한 정책은 장식이다.

→ 권한이 제한된 `app_rw` 역할을 만들고 앱은 그 역할로 동작한다. DDL 만 소유자.

**② 커넥션 풀에서 `SET ROLE` 이 풀린다.** 접속 시점에 역할을 바꿨더니 커넥션이
재사용될 때 풀려서, 두 번째 요청부터 RLS 가 무력해졌다. 세션 단위 설정은 반대로도
위험하다 — 앞 요청의 정체성이 풀을 타고 다음 요청으로 샌다.

→ **트랜잭션 안에서** `SET LOCAL ROLE` + `set_config('app.current_user_id', …, true)`.
트랜잭션이 끝나면 자동으로 되돌아가므로 두 문제가 같이 사라진다.

```python
def bind_request_context(session, user_id):        # app/db/session.py
    session.execute(text(f'SET LOCAL ROLE "{role}"'))
    session.execute(text("SELECT set_config('app.current_user_id', :uid, true)"), ...)
```

사용자를 못 정하면 **빈 값**을 넣는다. 정책이 모든 행을 막는 쪽으로 실패한다 —
못 정했을 때 다 보이는 것보다 아무것도 안 보이는 게 옳다. 검증이 이것도 확인한다.

### 감사기록은 못 고친다

```sql
CREATE TRIGGER trg_audit_event_immutable
BEFORE UPDATE OR DELETE ON identity.audit_event
FOR EACH ROW EXECUTE FUNCTION identity.deny_audit_mutation();
```

권한(`REVOKE UPDATE, DELETE`)으로도 한 번 더 막는다. 사고 조사에서 감사기록 자체가
고쳐질 수 있으면 그 기록은 아무것도 증명하지 못한다.

---

## 6. 실행

```powershell
# 1) DB 띄우기
docker compose -f ops/postgres/docker-compose.yml up -d

# 2) 스키마 적용
cd backend
$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m alembic upgrade head

# 3) 규칙이 지켜지는지 확인 (10개)
.\.venv\Scripts\python.exe -m pytest tests/test_db_schema.py -q
```

마이그레이션 4개가 순서대로 적용된다.

| 리비전 | 내용 |
|---|---|
| `afb6047a7f4d` | 25개 표 · 6개 스키마 |
| `89e0b6964c47` | RLS 정책 · updated_at 트리거 · 감사 불변 트리거 |
| `9509c3c67de8` | 서버 기본값 (검증이 잡은 결함) |
| `dade0747a11f` | `app_rw` 역할 + 권한 (RLS 가 실제로 걸리게) |

### 데이터 이관

```powershell
# 저장 없이 무엇이 몇 건 들어가는지만
.\.venv\Scripts\python.exe -m scripts.migrate_json_to_postgres --dry-run

# 실제 반영 (여러 번 돌려도 안전하다)
.\.venv\Scripts\python.exe -m scripts.migrate_json_to_postgres

# 원본과 값으로 대조 (건수 + 합계 + 표본)
.\.venv\Scripts\python.exe -m scripts.verify_migration
```

실측 결과 — 건너뛴 행 0건, 검증 17개 전부 통과:

| | 건수 |
|---|---:|
| 계정 · 자격증명 | 1 |
| 가계부 거래 · 카드 · 업로드이력 | 60 · 4 · 4 |
| 포트폴리오 보유 · 자산계획 | 1 · 1 |
| 부동산 지역 · 월별집계 · 평형집계 · 관심도 | 250 · 266 · 980 · 2,101 |
| 방문통계 | 72 |

**금액 합계가 원 단위로 일치한다** — `amount` 2,494,227 / `charged` 2,436,213 /
`fee` 58,014 / `total` 3,565,684. 이관이 오차를 심지 않았다는 뜻이다
(`Decimal(str(v))` 로 변환한다. `Decimal(0.1)` 은 0.1000000000000000055… 가 된다).

**세 번 연속 돌려도 건수가 그대로다.** 이관은 한 번에 안 끝나는 게 정상이라 —
오류가 나면 고치고 다시 돌린다 — 재실행에서 중복되면 그때부터 수작업이 된다.
그래서 자연키로 UPSERT 한다. 실제로 첫 구현이 두 곳에서 이 규칙을 어겼고
(관심도 2,101 → 4,202, 업로드이력 4 → 8) 재실행 검증이 잡았다.

**원본 JSON 은 지우지 않는다.** 이관 스크립트는 읽기만 한다. 애플리케이션이
PostgreSQL 을 실제로 쓰기 시작하고 한동안 문제가 없는 걸 확인한 뒤에 지우는 게 순서다.

**아직 안 한 것**: 애플리케이션 코드를 JSON 저장소에서 PostgreSQL 로 갈아 끼우는 일.
177개 엔드포인트가 아직 파일을 읽는다. 도메인 하나씩(가계부부터) 옮기는 게 안전하다.

---

## 7. 레퍼런스

설계 근거로 삼은 것들. 취향이 아니라 여기서 나온 규칙이다.

### PostgreSQL 공식 문서 — 1차 근거

| 주제 | 링크 |
|---|---|
| 행 수준 보안 (정책·FORCE·슈퍼유저 우회) | https://www.postgresql.org/docs/current/ddl-rowsecurity.html |
| 수치 타입 (`NUMERIC` vs `float`) | https://www.postgresql.org/docs/current/datatype-numeric.html |
| 날짜·시각 타입 (`timestamptz`) | https://www.postgresql.org/docs/current/datatype-datetime.html |
| 제약조건 | https://www.postgresql.org/docs/current/ddl-constraints.html |
| 스키마 · `search_path` | https://www.postgresql.org/docs/current/ddl-schemas.html |
| `GRANT` / `ALTER DEFAULT PRIVILEGES` | https://www.postgresql.org/docs/current/sql-alterdefaultprivileges.html |
| 파티셔닝 (지금은 불필요, 언제 쓸지) | https://www.postgresql.org/docs/current/ddl-partitioning.html |

### 도구

| 주제 | 링크 |
|---|---|
| SQLAlchemy 2.0 ORM (Declarative, `Mapped`) | https://docs.sqlalchemy.org/en/20/orm/quickstart.html |
| 제약조건 명명 규칙 | https://docs.sqlalchemy.org/en/20/core/constraints.html#constraint-naming-conventions |
| 커넥션 풀 | https://docs.sqlalchemy.org/en/20/core/pooling.html |
| Alembic 자동생성의 한계 | https://alembic.sqlalchemy.org/en/latest/autogenerate.html |
| Alembic 여러 스키마 다루기 | https://alembic.sqlalchemy.org/en/latest/cookbook.html |
| FastAPI + SQL | https://fastapi.tiangolo.com/tutorial/sql-databases/ |

### 원칙 — 왜 이렇게 나누는가

| 주제 | 출처 |
|---|---|
| **Refactoring Databases** (Ambler & Sadalage) — 진화적 DB 설계, 마이그레이션을 코드처럼 | https://databaserefactoring.com/ |
| Martin Fowler, *Evolutionary Database Design* | https://martinfowler.com/articles/evodb.html |
| Martin Fowler, *Polyglot Persistence* — 워크로드마다 다른 저장소 | https://martinfowler.com/bliki/PolyglotPersistence.html |
| Martin Fowler, *Bounded Context* — 스키마를 도메인으로 나누는 근거 | https://martinfowler.com/bliki/BoundedContext.html |
| **Designing Data-Intensive Applications** (Kleppmann) — 3장 저장·검색, 7장 트랜잭션 | https://dataintensive.net/ |
| The Twelve-Factor App — 설정을 환경에서(§III), 백엔드 서비스(§IV) | https://12factor.net/ |
| SQL Style Guide (Simon Holywell) — 명명·서식 | https://www.sqlstyle.guide/ |

### 보안

| 주제 | 링크 |
|---|---|
| OWASP Database Security Cheat Sheet | https://cheatsheetseries.owasp.org/cheatsheets/Database_Security_Cheat_Sheet.html |
| OWASP Password Storage Cheat Sheet (PBKDF2 반복수·argon2 전환) | https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html |
| CIS PostgreSQL Benchmark (운영 하드닝 체크리스트) | https://www.cisecurity.org/benchmark/postgresql |

---

## 8. 일부러 **안 한** 것

"대기업 구조" 를 흉내 낼 때 흔히 넣지만, 이 데이터 규모에서는 손해인 것들이다.
넣지 않은 이유를 적어 둔다 — 나중에 필요해지면 그때 넣으면 된다.

| 안 한 것 | 왜 | 언제 넣나 |
|---|---|---|
| 테이블 파티셔닝 | 가장 큰 표가 1.8만 행이다. 파티션은 관리 비용부터 붙는다 | `budget.transaction` 이 수천만 행이 될 때 |
| 이력 테이블(temporal) 전면 도입 | 감사 이벤트로 충분하다. 모든 표를 이중화하면 쓰기가 두 배 | 규제 대응이 필요할 때 |
| 읽기 전용 복제본 | 사용자가 한 명이다 | 읽기 부하가 쓰기를 방해할 때 |
| 마이크로서비스 분리 | 스키마 경계로 충분하다. 지금 나누면 조인이 HTTP 호출이 된다 | 배포 주기가 도메인마다 달라질 때 |
| 시세를 PostgreSQL 로 | §2 — 워크로드가 다르다 | 시세에 참조 무결성이 필요해질 때(없다) |
