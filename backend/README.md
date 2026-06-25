# backend — FastAPI (계층형)

```
backend/
├── app/
│   ├── api/        라우터(HTTP 입출력)            ← 표현 계층
│   ├── data/       데이터 수집/가공               ← 데이터/서비스 계층 (도메인별 하위패키지)
│   ├── quant/      계산 로직(metrics, backtest…)  ← 도메인 계층
│   ├── models/     Pydantic 스키마               ← 데이터 모델
│   ├── core/       설정(config)
│   └── main.py     앱 진입점(라우터·스케줄러 와이어링)
├── scripts/        데이터 적재 CLI(ingest…)
├── tests/          import 스모크 테스트
├── pyproject.toml  pytest 설정(+ dev 의존성)
└── requirements.txt
```

## data/ 도메인 하위패키지

수집/가공 모듈이 많아 도메인별로 묶었다. import 는 `from app.data.<도메인>.<모듈> import …`.

| 하위패키지 | 담는 모듈 |
|-----------|-----------|
| `infra/` | store(DB 접근), lawd_codes, global_universe |
| `loaders/` | krx, naver, us (외부 시세 로더) |
| `macro/` | ecos, macro, rates, money_supply, money_analysis, moneyflow, realeconomy, realestate, rent, korea_flow, crossasset |
| `market/` | brokers, investor, institutional, foreign_view, naver_sector, asset_detail, crisis |
| `fundamentals/` | dart, dart_financials, financials, fundamentals_crawler, finnhub |
| `intel/` | global_intel, global_map, industry, industry_research, futuretheme, insight |
| `news/` | news, feed, livepulse |
| `reports/` | report, market_report, daily_archive |
| `schedulers/` | growth_scheduler, industry_scheduler, price_scheduler, report_scheduler |

## 실행 / 테스트

```powershell
# 개발 서버 (backend\ 에서)
& .venv\Scripts\python.exe -m uvicorn app.main:app --reload

# 테스트 (backend\ 에서 — pythonpath 는 pyproject 가 처리)
& .venv\Scripts\python.exe -m pip install -e ".[dev]"   # 최초 1회(pytest)
& .venv\Scripts\python.exe -m pytest -q
```

`tests/test_imports.py` 는 `app.main` 과 `app.data.*` 전 모듈을 실제로 import 해
패키지 재배치/import 회귀를 자동으로 잡는다.
