# gui — PySide6 데스크톱 GUI (Qt Model/View · MVC)

실무에서 흔한 구조로 구성한 Qt 데스크톱 앱. 기존 FastAPI 백엔드(`backend/`)를
HTTP 로 호출해 **종목 스크리닝 결과를 테이블로 표시/정렬**한다.

## 계층 구조 (MVC + Qt Model/View)

```
gui/
├── config.py                # 설정(백엔드 URL 등)
├── services/                # 데이터 접근 계층 — 백엔드 API 호출
│   └── api_client.py        #   ScreeningApiClient, ApiError
├── models/                  # Qt 모델 — View 에 데이터 공급
│   └── screening_model.py   #   ScreeningTableModel(QAbstractTableModel)
├── views/                   # View — 위젯/UI 만 (로직 없음)
│   └── screening_view.py    #   ScreeningView (콤보/스핀/버튼/테이블)
├── controllers/             # Controller — View↔service↔model 연결
│   └── screening_controller.py
├── workers.py               # QThreadPool 워커 (API 호출로 UI 안 멈추게)
└── main.py                  # 진입점(계층 조립)
```

데이터 흐름:

```
[View] 조회 클릭 ─search_requested▶ [Controller]
                                      │ Worker(스레드)로
                                      ▼
                                  [Service] ── HTTP ──▶ FastAPI(/api/screen)
                                      │ 결과
                                      ▼
                                  [Model.set_records] ──자동 통지──▶ [QTableView]
```

> **MVVM 과 차이:** 강의(`mvvm/`)처럼 Binder 를 손수 만들지 않는다. Qt 가
> 모델↔뷰 동기화를 내장 제공하므로, 모델이 `set_records` 에서 리셋을 통지하면
> View 가 알아서 갱신된다. 이것이 Python GUI 의 자연스러운 방식이다.

## 설치 / 실행

```powershell
# 1) 의존성 (기존 backend venv 에 이미 PySide6 설치됨)
& backend\.venv\Scripts\python.exe -m pip install -r gui\requirements.txt

# 2) 백엔드 먼저 실행 (별도 터미널)
& backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload   # backend\ 에서

# 3) GUI 실행 (프로젝트 루트에서)
& backend\.venv\Scripts\python.exe -m gui.main
```

환경변수:
- `INVEST_API_URL` — 백엔드 주소 (기본 `http://127.0.0.1:8000`)
- `INVEST_API_TIMEOUT` — 요청 타임아웃 초 (기본 `20`)

데이터가 없다는 에러가 뜨면 백엔드 ingest 스크립트로 펀더멘털을 먼저 적재해야 한다.

## 새 화면 추가하는 법

같은 4계층을 반복하면 된다:
1. `services/` 에 API 호출 메서드 추가
2. `models/` 에 해당 화면용 Qt 모델 추가
3. `views/` 에 위젯 + 입력 시그널 추가
4. `controllers/` 에서 셋을 연결, `main.py` 에서 조립
