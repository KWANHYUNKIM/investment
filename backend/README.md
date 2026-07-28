# backend — FastAPI (계층형)

**src 레이아웃** — import 되는 패키지는 전부 `src/` 아래에 둔다. 그래야 `backend/` 에서
그냥 파이썬을 띄웠을 때 우연히 소스 디렉터리가 import 되는 일이 없고, 테스트가
설치된 패키지와 같은 경로로 돌아간다.

```
backend/
├── src/                    ← 여기 있는 것만 import 대상 패키지
│   ├── app/
│   │   ├── api/        라우터(HTTP 입출력)            ← 표현 계층
│   │   ├── domains/    도메인별 router·service·repository·schemas
│   │   ├── data/       데이터 수집/가공               ← 데이터/서비스 계층 (도메인별 하위패키지)
│   │   ├── quant/      계산 로직(metrics, backtest…)  ← 도메인 계층
│   │   ├── models/     Pydantic 스키마               ← 데이터 모델
│   │   ├── core/       설정(config)
│   │   └── main.py     앱 진입점(라우터·스케줄러 와이어링)
│   └── scripts/        데이터 적재 CLI(ingest…)
├── tests/                  테스트 (패키지 아님 — src 밖)
├── ops_monitor.py          단독 실행 Ops 모니터(별도 포트, 패키지 무관)
├── .env                    설정 — **CWD=backend 기준**으로 읽는다
├── pyproject.toml          pythonpath=["src"] · packages.find where=["src"]
└── requirements.txt
```

> **작업 디렉터리는 `backend/` 그대로다.** 설정의 `data_dir` 기본값이 `../data`,
> `.env` 도 CWD 기준 상대경로라서 `src/` 로 내려가면 안 된다. `src/` 는 **sys.path**
> 에만 올린다(`PYTHONPATH=backend\src` 또는 uvicorn `--app-dir src`).

## data/ 도메인 하위패키지

수집/가공 모듈이 많아 도메인별로 묶었다. import 는 `from app.data.<도메인>.<모듈> import …`.

| 하위패키지 | 담는 모듈 |
|-----------|-----------|
| `infra/` | store(DB 접근), lawd_codes, global_universe |
| `loaders/` | krx, naver, us (외부 시세 로더) |
| `macro/` | ecos, macro, rates, money_supply, money_analysis, moneyflow, realeconomy, realestate, rent, korea_flow, crossasset |
| `market/` | brokers, investor, institutional, foreign_view, naver_sector, asset_detail, crisis |
| `fundamentals/` | dart, dart_financials, financials, fundamentals_crawler, finnhub, unit_economics, company_costmodel + `products/` |
| `intel/` | global_intel, global_map, industry, industry_research, futuretheme, insight |
| `news/` | news, feed, livepulse |
| `reports/` | report, market_report, daily_archive |
| `schedulers/` | `runner.py`(공용 러너) + *_scheduler 10종 |

### `fundamentals/products/` — 원가분해 지식베이스 (데이터만)

제품 230품목의 원가 구성(유통마진·원재료 믹스·폴백 비율)은 **업종별 모듈**에 나눠 둔
순수 데이터다. 예전엔 이게 `unit_economics.py` 안에 3,458줄 리터럴로 들어가 있어서
그 파일의 88%가 데이터였다(3,900줄 중 로직은 220줄). 품목을 추가할 땐 해당 업종
모듈 하나만 고친다. 업종 순서 = `products/__init__.py` 의 `_MODULES` 순서이고, 그게
곧 화면 드롭다운 순서다.

### `schedulers/runner.py` — 스케줄러 공용 러너

10종의 스케줄러는 하는 일만 다르고 껍데기(데몬 스레드·기동 대기·무한 루프·예외
삼키기·ticks/last_run/last_error 기록·설정에서 주기 읽기)는 같았다. 그 35줄이 모듈마다
복붙되어 있던 것을 `runner.Scheduler` 로 모았다. 각 모듈에 남는 것은 `_state` 선언과
`_tick()`, 그리고 러너 배선뿐이다.

`api/ops.py` 와 `main.py` 는 스케줄러 **모듈**의 `status()`/`start()` 를 호출하므로,
각 모듈은 그 두 이름을 계속 내보낸다(`status = _sched.status`).

## 실행 / 테스트

```powershell
# 개발 서버 (backend\ 에서 — --app-dir 로 src 를 sys.path 에 올린다)
& .venv\Scripts\python.exe -m uvicorn app.main:app --app-dir src --reload

# 배치/CLI (backend\ 에서)
$env:PYTHONPATH = "$PWD\src"
& .venv\Scripts\python.exe -m scripts.verify_parsers

# 테스트 (backend\ 에서 — pythonpath 는 pyproject 가 처리)
& .venv\Scripts\python.exe -m pip install -e ".[dev]"   # 최초 1회(pytest)
& .venv\Scripts\python.exe -m pytest -q
```

운영에서는 위를 직접 치지 않는다 — `ops\win\serve.ps1` / `batch.ps1` 이 `PYTHONPATH`
와 DuckDB 잠금까지 함께 처리한다([ops/win/README.md](../ops/win/README.md)).

`tests/test_imports.py` 는 `app.main` 과 `app.data.*` 전 모듈을 실제로 import 해
패키지 재배치/import 회귀를 자동으로 잡는다.
