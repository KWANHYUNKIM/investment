# Windows 운영 스크립트

집이든 회사든 **같은 명령 세 개**로 돌린다. 프로젝트 루트에서 실행.

```powershell
.\ops\win\serve.ps1    start | stop | restart | status | logs   [-App backend|frontend|all]
.\ops\win\batch.ps1    costmodel | delisting | verify | report | blog | nightly
.\ops\win\schedule.ps1 install | uninstall | status | run
```

`serve.ps1` 은 기본이 `-App all` 이라 **백엔드와 프론트(npm run dev)를 같이** 띄운다.
둘 다 세션과 분리되므로 터미널을 닫아도 살아 있다(로그 `data\next.log`).

## 왜 스크립트가 필요한가 — DuckDB 단일 쓰기

이 프로젝트의 DuckDB 는 **한 프로세스만 쓰기**로 열 수 있다. 그래서 매번 같은 데서 막힌다.

- 배치가 도는 중에 서버를 띄우면 → 서버가 startup 에서 `IOException` 으로 즉사
- 서버가 떠 있는 중에 배치를 돌리면 → 배치가 DB 를 못 염

`serve.ps1 start` 는 **배치가 끝날 때까지 기다렸다가** 띄우고, `batch.ps1` 의 DB 작업은
**서버를 잠깐 내렸다가 다시 올린다**. 손으로 하면 반드시 한 번은 걸리는 부분이다.

또 하나: 서버를 터미널에서 그냥 띄우면 **터미널이 닫히거나 타임아웃될 때 같이 죽는다**.
`serve.ps1` 은 `Start-Process` 로 세션과 분리해 띄운다(로그 `data\uvicorn.log`).

## 자주 쓰는 흐름

```powershell
# 아침에 앱 켜기 (백엔드 + 프론트)
.\ops\win\serve.ps1 start

# 지금 상태가 어떤지 (서버·API·배치·마지막 배치 시각)
.\ops\win\serve.ps1 status

# 공시 파서가 아직 멀쩡한지 (DART 양식이 바뀌면 여기서 잡힌다)
.\ops\win\batch.ps1 verify          # 품질 경고 있으면 종료코드 1

# 전 종목 재무제표 이상 종목 뽑기 (업종 보정 포함)
.\ops\win\batch.ps1 report -Top 40

# 전 종목 원가모델 다시 계산 (약 20분, 서버 자동 정지→재기동)
.\ops\win\batch.ps1 costmodel

# 오늘의 증시 보고서 블로그 글 발행 (약 10초)
.\ops\win\batch.ps1 blog
.\ops\win\batch.ps1 blog -Date 2026-07-22   # 지난 날짜로

# 서버가 이상할 때
.\ops\win\serve.ps1 logs -Tail 40
.\ops\win\serve.ps1 restart
```

## 자동화 (PC 켜두고 알아서 돌리기)

```powershell
.\ops\win\schedule.ps1 install       # 관리자 권한 필요할 수 있음
.\ops\win\schedule.ps1 status
```

두 개가 등록된다.

| 작업 | 시점 | 내용 |
|---|---|---|
| `Investment-Backend` | 로그온 시 | 백엔드 기동(배치 잠금 대기 포함) |
| `Investment-Nightly` | 매일 03:10 | 원가모델 배치 → 파서 검증 → 감사 리포트 |

> 앱 안에도 스케줄러가 있지만(원가모델 03:30 등) **백엔드가 떠 있을 때만** 돈다.
> PC 를 껐다 켜면 아무것도 안 돌기 때문에 OS 레벨에도 건다.

실행 결과는 `data\logs\<작업>-<시각>.log`, 산출물은:

| 파일 | 내용 |
|---|---|
| `data\company_costmodels.json` | 전 종목 원가모델(감사점수·인건비·재료비 실측 포함) |
| `data\audit_report.json` | 재무제표 이상 종목 랭킹(업종 보정) |
| `data\verify_parsers.json` | 파서 스모크 테스트 결과 |
| `data\blog_posts\<날짜>_market-wrap.md` | **증시 보고서 블로그 원고**(그대로 복사해 올림) |
| `data\blog_posts\<날짜>_market-wrap.json` | 같은 글의 제목·마크다운·HTML·태그 |

## 증시 보고서 블로그 자동 발행

평일 장 마감 뒤 **하루 1편**이 자동으로 만들어져 `data\blog_posts\` 에 쌓인다.

- 앱 내부 스케줄러: 기본 **16:20**(장 마감 15:30 + 마감 시세·수급 반영 여유). `BLOG_AUTOPUBLISH=false` 로 끔
- 서버가 꺼져 있어도 되게: `.\ops\win\batch.ps1 blog` (작업 스케줄러에 걸어도 됨)
- 관리자 API: `POST /api/admin/blog/publish` · `GET /api/admin/blog/posts` · `GET /api/admin/blog/post?date=` · `GET /api/admin/blog/scheduler`

글 구성(있는 데이터만 넣고, 없는 항목은 통째로 빠진다):
한 줄 요약 → 시장 한눈에(등락 종목수·투자자별 순매수) → 시장 분위기 → 핵심 이슈 →
주요 뉴스 → 업종별 등락 → 급등/급락 종목과 이유(주가 차트 임베드) → 매크로·환율 →
일정 → 면책.

> `.md` 는 차트가 base64 로 박혀 있어 파일이 200KB 정도 된다(텍스트만 6천 자 남짓).
> 네이버·티스토리엔 `.json` 안의 `html` 을 붙여넣는 쪽이 깔끔하다.

## 파이썬 스크립트 단독 실행

PowerShell 없이(또는 다른 OS에서) 쓰려면 `backend\` 에서 직접 돌린다.

```powershell
cd backend
$env:PYTHONPATH = (Resolve-Path .).Path
& .\.venv\Scripts\python.exe -m scripts.verify_parsers --tickers 004370,005490
& .\.venv\Scripts\python.exe -m scripts.audit_report --top 30 --json ..\data\audit_report.json
& .\.venv\Scripts\python.exe -m scripts.build_delisting
```

## 이 환경에서 실제로 물렸던 함정 (스크립트가 이미 처리함)

| 함정 | 증상 | 대응 |
|---|---|---|
| **PowerShell 이 선행 0을 제거** | `--tickers 004370` → `4370` 이 전달되어 **결과가 전부 비는데 "정상"으로 표시** | `verify_parsers` 가 6자리로 복원 + 전 소스 비면 실패 처리 |
| **`.ps1` 인코딩** | 한글 주석이 깨지며 `Missing closing ')'` 파서 에러 | 이 폴더의 `.ps1` 은 **UTF-8 BOM** 으로 저장(PS 5.1 은 BOM 없으면 ANSI 로 읽음) |
| **터미널 종료 시 서버 동반 사망** | 백그라운드로 띄운 서버가 타임아웃에 같이 죽음 | `Start-Process` 세션 분리 기동 |
| **DuckDB 잠금** | 서버 startup `IOException` / 배치 실패 | `serve.ps1` 대기, `batch.ps1` 정지→실행→재기동 |
