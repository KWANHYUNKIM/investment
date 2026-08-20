"""Application configuration loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Directory holding the DuckDB file and parquet datasets.
    data_dir: Path = Path("../data")

    # Frontend dev origin allowed through CORS.
    frontend_origin: str = "http://localhost:3000"

    # Annual risk-free rate used in Sharpe / Sortino calculations.
    risk_free_rate: float = 0.03

    # 관리자 계정(쉼표구분 아이디). 관리자 페이지·블로그 생성 등 운영기능 접근 허용.
    admin_usernames: str = ""

    # DART (전자공시) open API key — enables 5% major-holder names by ticker.
    dart_api_key: str = ""

    # Finnhub (finnhub.io) free API key — enables 해외 종목 펀더멘털(영업이익률·시총·
    # 섹터·국가) for the 글로벌 경쟁지도. yfinance가 429로 막혀 그 대체 소스로 쓴다.
    finnhub_api_key: str = ""

    # 공공데이터포털(data.go.kr) 무료 키 — 국토부 아파트 매매 실거래가(RTMS).
    # 한국 경제 흐름 탭의 '부동산 거래액·거래량'(월별·지역별) 집계에 쓴다.
    data_go_kr_key: str = ""

    # 한국은행 ECOS 무료 키 — 거시 통화/신용/주택 지표(M2·가계신용·주택매매가격지수).
    # 한국 경제 흐름 탭의 '국내 돈 흐름' 하드데이터로 쓴다.
    ecos_api_key: str = ""

    # Anthropic Claude API 키 — 'AI 주가 예측' 탭에서 Claude Fable 5로 최근 시세를 넣고
    # 향후 주가 시나리오(강세/기준/약세) 경로를 예측한다. 없으면 예측 탭만 비활성.
    anthropic_api_key: str = ""

    # 이메일 인증(회원가입·비밀번호 찾기) 발송용 SMTP. 미설정이면 개발모드로
    # 코드를 응답에 노출(테스트용) — 외부 배포 전 반드시 설정할 것.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""   # 미설정 시 smtp_user 사용

    # --- PostgreSQL ---------------------------------------------------------
    # 사용자 데이터(계정·가계부·포트폴리오)와 기준정보의 시스템 오브 레코드.
    # 시세·재무 같은 분석용 대용량 시계열은 DuckDB 에 남긴다(app/db/models/market.py 참고).
    #
    # 로컬:  docker compose -f ops/postgres/docker-compose.yml up -d
    database_url: str = "postgresql+psycopg://investment:investment_local_only@localhost:5432/investment"
    # 풀 크기는 스케줄러 수를 고려해 정한다 — 배치가 커넥션을 물면 웹 요청이 굶는다.
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_echo: bool = False
    # 앱이 갈아입을 역할. 비우면 접속 계정 그대로 쓴다(마이그레이션·검증용).
    # 운영에서 비워 두면 RLS 가 적용되지 않으므로 반드시 채운다.
    db_app_role: str = "app_rw"

    # 가계부를 어느 저장소로 읽고 쓸지. json(기존 파일) | postgres.
    # 스위치를 남겨 두는 이유는 되돌릴 수 있어야 하기 때문이다 — 옮긴 직후에 문제가
    # 드러나면 설정 한 줄로 원래 파일로 돌아갈 수 있어야 한다(파일은 지우지 않는다).
    budget_storage: str = "json"

    # 시군구 월별 집계 누적 저장소(매매·전세·월세 × 평형). 24개월 × 250곳 × 3유형 =
    # 18,000콜이라 한 번에 못 받는다. 지난 달은 다시 안 바뀌므로 없는 칸만 예산 안에서
    # 조금씩 채우고, 신고 기한이 남은 최근 두 달만 다시 받는다.
    realestate_stats: bool = True
    realestate_stats_months: int = 24
    # 예산은 일일 한도에서 역산한다. 개발계정 1,000건/일에서 지도 워밍이 쓰는 몫을
    # 빼면 시간당 30건 정도가 안전선이다(30 × 24 = 720). 운영계정(10만건/일)으로
    # 올리면 여기를 크게 키워 하루 만에 다 채울 수 있다.
    realestate_stats_budget: int = 30
    realestate_stats_interval: float = 3600.0   # 1시간마다 이어 받기
    # 최근 달을 얼마 만에 다시 받을지. 1,500칸을 순번제로 도는 주기의 기준이 된다.
    realestate_stats_stale_hours: float = 24.0

    # NAVER API HUB (ncloud 콘솔) — 검색어 트렌드로 지역별 부동산 **관심도**를 만든다.
    # 거래량은 관심의 결과라 늦고, 검색은 먼저 튄다.
    #
    # 옛 developers.naver.com 경로는 신규 등록이 막혔다(앱 설정에서 고르면 "신규로
    # 등록할 수 없는 API"). 지금은 지도와 **같은 ncloud 콘솔**에서 발급한 API Gateway
    # 인증키를 쓴다 — Access Key ID 10자 / Secret 40자. 이름만 client_id 로 남겨 둔다.
    naver_client_id: str = ""
    naver_client_secret: str = ""

    # 앵커 키워드. 데이터랩은 요청마다 최대값을 100 으로 잡는 상대값만 주므로, 모든
    # 요청에 같은 키워드를 끼워 넣고 그 값으로 나눠야 요청 간 비교가 성립한다.
    # 전국구 대형 키워드를 쓰면 지역값이 전부 0.0x 로 뭉개지므로 중간 규모 지역을 쓴다.
    naver_interest_anchor: str = "성남시 아파트"
    naver_interest_months: int = 12

    # --- 가계부: 카드사 이용대금명세서 메일 자동 수집 (IMAP 수신) ---------------
    # 카드사가 매달 보내는 e-메일 명세서를 받은편지함에서 직접 읽어 파싱한다. 카드사
    # 공식 API 는 개인에게 열려 있지 않고, 승인문자는 할부·취소·청구월을 못 잡아서
    # 명세서가 개인이 얻을 수 있는 가장 정확한 원본이다.
    #
    # 네이버: imap.naver.com / 993, 메일 환경설정에서 IMAP 사용을 먼저 켜야 한다.
    # 지메일: imap.gmail.com / 993, 계정 비밀번호가 아니라 '앱 비밀번호' 를 넣는다.
    budget_mail: bool = False              # 스케줄러 스위치 (자격증명 없으면 어차피 안 돎)
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    imap_folder: str = "INBOX"
    imap_ssl: bool = True

    # 어느 계정의 가계부로 넣을지. 스케줄러는 로그인 세션이 없어 물어볼 데가 없다.
    budget_mail_user: str = "admin"
    budget_mail_days: int = 45              # 받은편지함을 며칠치까지 훑을지
    budget_mail_max: int = 40               # 한 번에 살펴볼 최대 메일 수
    budget_mail_check_interval: float = 1800.0   # 30분마다 (명세서는 월 1회라 급할 것 없다)

    # 첨부 파일 비밀번호 후보(쉼표 구분). 카드사 명세서는 보통 생년월일 6자리 등으로
    # 잠겨 온다. 앞에서부터 하나씩 시도하고, 다 실패하면 대기함에 '암호 필요' 로 남긴다.
    budget_mail_passwords: str = ""

    # 전용 파서로 읽혔고 청구월까지 확정된 것만 자동 등록. 나머지는 대기함으로 보내
    # 사람이 확인한 뒤 넣는다(카드사마다 금액의 의미가 달라 조용히 넣으면 못 찾는다).
    budget_mail_autoimport: bool = True

    # 인증코드를 HTTP 응답에 노출할지(=SMTP 미설정 시 dev_code). 기본 False.
    # True 로 켜면 이메일 인증이 무력화되므로 로컬 개발에서만, 절대 공개 배포에선 금지.
    # (공개 URL 노출 시 누구나 send-code→reset-password 로 계정 탈취 가능)
    auth_expose_dev_code: bool = False

    # Demo mode: synthesize small intraday ticks on top of the settled snapshot
    # so the live grid visibly moves without a brokerage streaming API.
    mock_ticks: bool = True

    # Background price scheduler: periodically snapshot the whole KR board and
    # upsert today's OHLCV bar into DuckDB, so the price series accumulates
    # forward without a manual ingest run. Set PRICE_INGEST=false to disable.
    price_ingest: bool = True
    # Seconds between price snapshots (default 5 min). Intraday ticks refresh
    # today's bar in place; each new trading day appends a fresh row.
    price_ingest_interval: float = 300.0

    # Daily report archive: persist a full market + per-stock daily report as one
    # JSON file per trading day, so the history accumulates instead of evaporating
    # with the 10-min cache. Set REPORT_ARCHIVE=false to disable the snapshotter.
    report_archive: bool = True
    # How often the snapshotter wakes to check whether today's report exists yet
    # (it writes at most once per trading day). Default hourly.
    report_archive_interval: float = 3600.0
    # How many stocks get the deep news (국내+해외) + investor-cause analysis each
    # day. They are picked by trading significance (most-traded ∪ top gainers ∪ top
    # losers); every other stock is still archived at the price / investor-flow
    # level. Each deep stock costs a live domestic+global news fetch, so this is a
    # speed/coverage knob (≈0.4s/stock).
    report_deep_n: int = 100

    # Industry / competition map: refresh company industry profiles (KRX-DESC) and
    # snapshot per-industry research (tech/M&A/contracts/perf/strategy) on a daily
    # cadence so the competitive picture accumulates. Set INDUSTRY_MAP=false to off.
    industry_map: bool = True
    industry_map_interval: float = 6 * 3600.0  # how often the scheduler checks
    industry_top_k: int = 6        # companies analysed per industry (news fetch)
    industry_snapshot_n: int = 30  # industries persisted in each daily snapshot

    # 미래 성장테마 + 실시간 시황: 백그라운드로 주기적으로 뉴스를 다시 크롤링해 캐시를
    # 데우고, 미래 성장테마는 하루 1개 JSON으로 누적 저장한다. GROWTH_SCHEDULER=false로 끔.
    growth_scheduler: bool = True
    growth_scheduler_interval: float = 1800.0  # 30분마다 테마/시황 갱신

    # 개장 예측 아카이브: 매 세션 예측을 저장하고, 다음 세션 실제 개장과 대조해
    # 적중/실패를 채점한다(자동 반복). PREMARKET_ARCHIVE=false로 끔.
    premarket_archive: bool = True
    premarket_archive_interval: float = 1800.0  # 30분마다 기록·채점 점검

    # 급등락 원인 규명: 급등/급락 종목·업종을 감지하고 관련 뉴스(+선택 AI)로 원인을 찾아
    # 스냅샷을 주기적으로 기록(자동 반복). MOVERS=false로 끔.
    movers: bool = True
    movers_interval: float = 900.0        # 15분마다 감지·원인 규명·기록
    movers_threshold: float = 5.0         # |등락률| 이 % 이상이면 급등락으로 간주
    movers_top_n: int = 8                 # 원인(뉴스) 규명할 상위 급등·급락 종목 수

    # 부동산 실거래 지도 프리워밍: 서버가 켜지면 백그라운드로 국토부 실거래(최신월)를
    # 미리 받아 디스크 캐시에 채워둔다. 그러면 사용자가 탭 여는 순간 캐시에서 즉시 렌더.
    # DATA_GO_KR_KEY 가 있어야 동작. REALESTATE_WARM=false 로 끔.
    realestate_warm: bool = True
    realestate_warm_interval: float = 6 * 3600.0  # 6시간마다 갱신(캐시 TTL 12h보다 짧게)

    # 원가모델 전 종목 배치(I1): 매일 야간 1회 전 종목 analyze 를 돌려
    # data/company_costmodels.json 을 원자적으로 교체 → 목록(레벨1)이 추정 대신
    # DART 실측으로 뜬다. 재무제표는 분기 갱신이지만 원자재 시세·차이분해는 매일
    # 바뀌므로 하루 1회가 적정(docs/원가분석_개편계획.md §8). COSTMODEL_BATCH=false 로 끔.
    costmodel_batch: bool = True
    costmodel_batch_hour: int = 3          # 실행 시각(로컬, 24h)
    costmodel_batch_minute: int = 30
    costmodel_batch_sleep: float = 1.0     # 종목 간 대기(초) — DART rate limit 완충
    costmodel_batch_check_interval: float = 600.0  # 실행 시각 도달 여부 점검 주기

    # 증시 보고서 블로그 글 자동 발행: 평일 장 마감 뒤 하루 1편을 만들어
    # data/blog_posts/ 에 저장한다(마크다운 + HTML). 장 마감 15:30 + 마감 시세·투자자
    # 수급이 반영될 여유를 둬 기본 16:20. BLOG_AUTOPUBLISH=false 로 끔.
    blog_autopublish: bool = True
    blog_publish_hour: int = 16
    blog_publish_minute: int = 20
    blog_publish_check_interval: float = 600.0

    # 관리종목·상폐 스크리너 데이터 배치: 시장구분(FDR 상장목록)·위험종목 공시 스캔·
    # 반기 자본계정을 매일 야간 갱신한다. 시장구분 캐시가 없으면 매출·영업손실·법인세
    # 요건이 아예 적용되지 않으므로 이 배치가 스크리너 정확도의 전제다.
    delisting_batch: bool = True
    delisting_batch_hour: int = 4          # 원가모델 배치(03:30) 다음
    delisting_batch_minute: int = 10
    delisting_batch_check_interval: float = 600.0

    @property
    def duckdb_path(self) -> Path:
        return self.data_dir / "market.duckdb"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "daily_reports"

    @property
    def future_themes_dir(self) -> Path:
        return self.data_dir / "future_themes"

    @property
    def movers_dir(self) -> Path:
        return self.data_dir / "movers"

    @property
    def premarket_dir(self) -> Path:
        return self.data_dir / "premarket"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.future_themes_dir.mkdir(parents=True, exist_ok=True)
        self.premarket_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
