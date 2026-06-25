# investment — 투자 분석 대시보드

한국/미국 주식 데이터를 수집·분석하고 웹·데스크톱으로 보여주는 프로젝트.
각 구성요소는 그 분야에서 **자연스러운 실무 구조**를 따른다.

```
investment/
├── backend/      FastAPI 백엔드 — 계층형(layered) 구조        [Python]
├── frontend/     Next.js 웹 대시보드                          [TypeScript/React]
├── gui/          PySide6 데스크톱 앱 — Qt Model/View · MVC    [Python]
├── examples/
│   └── mvvm/     학습용: Code Spitz MVVM 패턴 Python 포팅     [Python]
├── docs/         설계 노트/로드맵
└── data/         런타임 생성 데이터(DuckDB·캐시·리포트) — git 제외
```

## 구성요소별 구조와 패턴

### backend/ — 계층형 (웹 백엔드의 표준)
```
backend/app/
├── api/        라우터(HTTP 입출력)          ← 표현 계층
├── data/       수집/가공 — 도메인별 하위패키지 ← 데이터/서비스 계층
│   ├── infra/ loaders/ macro/ market/ fundamentals/
│   └── intel/ news/ reports/ schedulers/
├── quant/      계산 로직(metrics, backtest)  ← 도메인 계층
├── models/     Pydantic 스키마               ← 데이터 모델
├── core/       설정(config)
└── main.py     앱 진입점
```
요청 흐름: `api(라우터) → data/quant(서비스·도메인) → models(스키마)`.
MVVM 을 쓰지 않는다 — 웹 백엔드는 계층 분리가 자연스럽다.
하위패키지 구성과 테스트는 [backend/README.md](backend/README.md).

### gui/ — MVC + Qt Model/View (데스크톱의 표준)
```
gui/
├── services/     백엔드 API 호출(데이터 접근)
├── models/       Qt 모델(QAbstractTableModel) — View 에 데이터 공급
├── views/        위젯/UI 만
├── controllers/  View↔service↔model 연결
├── workers.py    QThreadPool 워커(UI 안 멈춤)
└── main.py       진입점(계층 조립)
```
Qt 가 모델↔뷰 동기화를 내장 제공하므로 바인더를 직접 만들 필요가 없다.
자세한 내용은 [gui/README.md](gui/README.md).

### examples/mvvm/ — 학습용 MVVM 직접 구현
바닐라 JS 강의의 Scanner/Binder/ViewModel 을 Python 으로 옮긴 것.
"바인딩이 없는 환경에서 MVVM 을 손수 구현"하는 패턴 학습용.
자세한 내용은 [examples/mvvm/README.md](examples/mvvm/README.md).

> **패턴 선택 요약:** 웹 백엔드 = 계층형 / 데스크톱 GUI = MVC·Qt Model/View /
> MVVM = (Python 에선 드묾) 학습 목적의 직접 구현. 자세한 배경은 대화 기록 참고.

## 실행

모든 Python 명령은 **프로젝트 루트**에서, backend 가상환경의 파이썬으로 실행한다.

```powershell
# 백엔드 (별도 터미널, backend\ 에서)
& backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload

# 웹 프론트엔드 (frontend\ 에서)
npm install; npm run dev

# 데스크톱 GUI (루트에서, 백엔드가 떠 있어야 함)
& backend\.venv\Scripts\python.exe -m gui.main

# MVVM 데모 (루트에서)
& backend\.venv\Scripts\python.exe -m examples.mvvm.demo
```
