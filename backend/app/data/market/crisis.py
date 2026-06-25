"""금융위기 시뮬레이터 — 과거 위기들이 '며칠에 걸쳐' 어떻게 전개됐는지 일단위로 펼치고,
지금 한국 시장이 그 초기 패턴과 얼마나 닮았는지 맞춰본다.

핵심 발상
---------
각 위기의 '방아쇠 날짜(Day 0)'를 0으로 정렬하고 지표를 Day0=100으로 정규화하면,
"위기 후 N일째"라는 공통 시간축 위에 여러 나라·여러 위기의 붕괴 궤적을 겹쳐 그릴 수
있다. 그러면 붕괴 속도(며칠 만에)·깊이(몇 %)를 한눈에 견줄 수 있다.

여기에 '지금'의 한국 궤적(최근 고점 이후)을 같은 축에 올려, 각 과거 위기의 같은 길이
구간과 모양을 비교(상관계수·정규화 오차)해 "지금은 어느 위기와 닮았나"를 랭킹한다.

데이터 (모두 무료·키 불필요)
----------------------------
  · 환율(FX)   : FRED 일별 USD 대비 각국 통화 (1996~). 통화 붕괴 = 통화가치 하락.
                 — 1997 외환위기·2008 모두 일단위로 커버되는 가장 강력한 신호.
  · 주가(STOCK): FRED 일별 — 미국 NASDAQCOM, 일본 NIKKEI225.
                 '지금 한국 주가'는 로컬 DuckDB 시가총액 가중 프록시(최근 구간).
  · 금리(BOND) : FRED — 미국 DGS10(일별), 그리스·스페인·이탈리아 10년물(월별, 유럽위기).

지표 방향: 환율·주가는 '아래로 = 붕괴', 금리는 '위로 = 붕괴(신용경색)'.
"""
from __future__ import annotations

import datetime
import io
import threading
import time
from pathlib import Path

import httpx

from app.core.config import get_settings

# --------------------------------------------------------------------------- #
# 위기 에피소드 — Day 0 = 방아쇠 사건
# --------------------------------------------------------------------------- #
CRISES: list[dict] = [
    {
        "key": "1997_asia", "label": "1997 아시아 외환위기", "day0": "1997-07-02",
        "pre": 240, "post": 320, "color": "#c92a2a",
        "trigger": "태국 바트 변동환율 전환",
        "desc": "태국이 달러 페그를 포기하자 바트·원·링깃이 연쇄 폭락 — 외환위기의 교과서.",
    },
    {
        "key": "2008_gfc", "label": "2008 글로벌 금융위기", "day0": "2008-09-15",
        "pre": 240, "post": 300, "color": "#e8590c",
        "trigger": "리먼 브러더스 파산",
        "desc": "신용경색이 전 세계로 번지며 신흥국 통화·증시가 동반 급락.",
    },
    {
        "key": "2010_euro", "label": "2010 유럽 재정위기", "day0": "2010-04-23",
        "pre": 240, "post": 520, "color": "#1971c2",
        "trigger": "그리스 구제금융 요청",
        "desc": "남유럽 국가신용 불안으로 그리스·스페인·이탈리아 국채금리가 급등.",
    },
    {
        "key": "2020_covid", "label": "2020 코로나 쇼크", "day0": "2020-02-19",
        "pre": 240, "post": 200, "color": "#7048e8",
        "trigger": "팬데믹 증시 고점",
        "desc": "사상 최속 폭락 후 막대한 유동성으로 V자 반등 — 짧고 깊은 충격.",
    },
]
CRISIS_BY_KEY = {c["key"]: c for c in CRISES}

# --------------------------------------------------------------------------- #
# 환율 (FRED, USD 대비). per_usd=True 면 '통화/달러'(값↑=통화약세) → 강도 = base/rate.
# per_usd=False 면 '달러/통화'(값↑=통화강세) → 강도 = rate/base.
# --------------------------------------------------------------------------- #
FX = {
    "KR": {"name": "한국 원", "fred": "DEXKOUS", "per_usd": True,  "color": "#c92a2a"},
    "TH": {"name": "태국 바트", "fred": "DEXTHUS", "per_usd": True,  "color": "#e8590c"},
    "MY": {"name": "말레이시아 링깃", "fred": "DEXMAUS", "per_usd": True, "color": "#f08c00"},
    "IN": {"name": "인도 루피", "fred": "DEXINUS", "per_usd": True, "color": "#2f9e44"},
    "SG": {"name": "싱가포르 달러", "fred": "DEXSIUS", "per_usd": True, "color": "#1098ad"},
    "JP": {"name": "일본 엔", "fred": "DEXJPUS", "per_usd": True, "color": "#9c36b5"},
    "BR": {"name": "브라질 헤알", "fred": "DEXBZUS", "per_usd": True, "color": "#ae3ec9"},
    "MX": {"name": "멕시코 페소", "fred": "DEXMXUS", "per_usd": True, "color": "#e64980"},
    "EU": {"name": "유로", "fred": "DEXUSEU", "per_usd": False, "color": "#1971c2"},
}
# 어떤 위기에 어떤 통화를 보여줄지 (해당 위기의 진앙·전염 통화)
CRISIS_FX = {
    "1997_asia": ["KR", "TH", "MY", "IN", "SG", "JP"],
    "2008_gfc": ["KR", "BR", "MX", "IN", "JP", "EU"],
    "2010_euro": ["EU", "KR", "BR"],
    "2020_covid": ["KR", "BR", "MX", "IN", "JP", "EU"],
}

# 주가 (FRED). 미·일은 일별, 한국 코스피는 월별(일별 과거치는 무료로 못 구함 →
# OECD 월별 한국 주가지수로 '같은 지수' 비교).
STOCK = {
    "US": {"name": "미국 나스닥", "fred": "NASDAQCOM", "freq": "일별", "color": "#e8590c"},
    "JP": {"name": "일본 닛케이225", "fred": "NIKKEI225", "freq": "일별", "color": "#9c36b5"},
    "KRM": {"name": "한국 코스피(월)", "fred": "SPASTT01KRM661N", "freq": "월별", "color": "#c92a2a"},
}
CRISIS_STOCK = {k: ["US", "JP", "KRM"] for k in
                ("1997_asia", "2008_gfc", "2010_euro", "2020_covid")}

# 국채 10년물 (FRED). US만 일별, 나머지는 월별. 방향: 위로=신용악화.
BOND = {
    "US": {"name": "미국 10년물", "fred": "DGS10", "freq": "일별", "color": "#1971c2"},
    "GR": {"name": "그리스 10년물", "fred": "IRLTLT01GRM156N", "freq": "월별", "color": "#c92a2a"},
    "ES": {"name": "스페인 10년물", "fred": "IRLTLT01ESM156N", "freq": "월별", "color": "#e8590c"},
    "IT": {"name": "이탈리아 10년물", "fred": "IRLTLT01ITM156N", "freq": "월별", "color": "#f08c00"},
    "KR": {"name": "한국 10년물", "fred": "IRLTLT01KRM156N", "freq": "월별", "color": "#2f9e44"},
}
CRISIS_BOND = {
    "2010_euro": ["GR", "ES", "IT", "US", "KR"],
    "2008_gfc": ["US", "KR"],
}

# 변동성 (VIX, 일별). 위로 = 공포 급등.
VIX = {"VIX": {"name": "VIX 변동성", "fred": "VIXCLS", "freq": "일별", "color": "#7048e8"}}
CRISIS_VIX = {k: ["VIX"] for k in ("1997_asia", "2008_gfc", "2010_euro", "2020_covid")}

# 신용 스프레드 (하이일드·투자등급 OAS, 일별). 위로 = 신용경색.
CREDIT = {
    "HY": {"name": "美 하이일드 스프레드", "fred": "BAMLH0A0HYM2", "freq": "일별", "color": "#c92a2a"},
    "IG": {"name": "美 투자등급 스프레드", "fred": "BAMLC0A0CM", "freq": "일별", "color": "#1971c2"},
}
CRISIS_CREDIT = {k: ["HY", "IG"] for k in ("2008_gfc", "2010_euro", "2020_covid")}

# 유가 (WTI, 일별). 아래로 = 수요 붕괴(경기침체형).
OIL = {"WTI": {"name": "WTI 유가", "fred": "DCOILWTICO", "freq": "일별", "color": "#e8590c"}}
CRISIS_OIL = {k: ["WTI"] for k in ("1997_asia", "2008_gfc", "2010_euro", "2020_covid")}

# 고용 (실업수당청구 주간 + 실업률 월별). 위로 = 고용 악화.
EMPLOY = {
    "ICSA": {"name": "美 신규 실업수당청구", "fred": "ICSA", "freq": "주간", "color": "#c92a2a"},
    "UNRATE": {"name": "美 실업률", "fred": "UNRATE", "freq": "월별", "color": "#e8590c"},
    "KRU": {"name": "한국 실업률", "fred": "LRHUTTTTKRM156S", "freq": "월별", "color": "#2f9e44"},
}
CRISIS_EMPLOY = {k: ["ICSA", "UNRATE", "KRU"] for k in
                 ("1997_asia", "2008_gfc", "2010_euro", "2020_covid")}

METRICS = {
    "fx": {"label": "환율 (통화가치)", "direction": "down",
           "desc": "USD 대비 통화가치. 아래로 내려갈수록 통화 붕괴(외환위기형)."},
    "stock": {"label": "주가지수", "direction": "down",
              "desc": "대표 주가지수. 아래로 내려갈수록 증시 폭락. (한국=월별)"},
    "bond": {"label": "국채금리 (신용)", "direction": "up",
             "desc": "10년물 국채금리. 위로 올라갈수록 국가신용 불안(금리 급등)."},
    "vix": {"label": "변동성 (VIX)", "direction": "up",
            "desc": "공포지수. 위로 급등할수록 패닉(증시 폭락 동반)."},
    "credit": {"label": "신용 스프레드", "direction": "up",
               "desc": "회사채 가산금리. 위로 벌어질수록 신용경색(자금 경색)."},
    "oil": {"label": "유가 (WTI)", "direction": "down",
            "desc": "원유 가격. 아래로 급락할수록 글로벌 수요 붕괴(침체형)."},
    "employment": {"label": "고용", "direction": "up",
                   "desc": "실업수당청구·실업률. 위로 치솟을수록 고용 충격."},
}

# 지표별 설정 — 레지스트리/위기 구성원/정규화/현재선 소스를 한 곳에 모은다.
# norm: "strength"=환율 강도(역수), "index"=Day0=100 지수화.
METRIC_CFG = {
    "fx":     {"registry": FX,     "members": CRISIS_FX,     "norm": "strength",
               "current_codes": ["KR", "JP", "EU", "BR"]},
    "stock":  {"registry": STOCK,  "members": CRISIS_STOCK,  "norm": "index",
               "current_codes": ["US", "JP", "KRM"]},
    "bond":   {"registry": BOND,   "members": CRISIS_BOND,   "norm": "index",
               "current_codes": ["KR", "US"]},
    "vix":    {"registry": VIX,    "members": CRISIS_VIX,    "norm": "index",
               "current_codes": ["VIX"]},
    "credit": {"registry": CREDIT, "members": CRISIS_CREDIT, "norm": "index",
               "current_codes": ["HY", "IG"]},
    "oil":    {"registry": OIL,    "members": CRISIS_OIL,    "norm": "index",
               "current_codes": ["WTI"]},
    "employment": {"registry": EMPLOY, "members": CRISIS_EMPLOY, "norm": "index",
                   "current_codes": ["ICSA", "UNRATE", "KRU"]},
}


def _lookback_rows(freq: str) -> int:
    """현재선용 최근 행 수(빈도별)."""
    return {"일별": 400, "주간": 140, "월별": 54}.get(freq, 400)


def _anchor_search(freq: str) -> int:
    """현재 기준점(고점/저점) 탐색 범위(빈도별 행 수)."""
    return {"일별": 180, "주간": 40, "월별": 14}.get(freq, 180)

# --------------------------------------------------------------------------- #
# FRED 페치 (+디스크 캐시) — 키 불필요 CSV 다운로드
# --------------------------------------------------------------------------- #
_FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
# NOTE: 브라우저(Mozilla) User-Agent 를 보내면 FRED(Akamai) 봇 차단이 발동해
# 요청 도중 TLS 재협상/챌린지를 걸어 응답 본문 읽기가 무한 대기(ReadTimeout)한다.
# 평범한 비브라우저 UA 로 보내면 CSV 가 정상 반환된다. (절대 브라우저 UA 로 되돌리지 말 것)
_FRED_HEADERS = {
    "User-Agent": "investment-dashboard/1.0 (+httpx)",
    "Accept": "text/csv,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}
_CACHE_TTL = 12 * 3600.0
_lock = threading.Lock()
_mem: dict[str, tuple[float, list[tuple[str, float]]]] = {}


def _cache_dir() -> Path:
    d = get_settings().data_dir / "cache" / "crisis"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _parse_csv(text: str) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    for ln in text.strip().splitlines()[1:]:
        parts = ln.split(",")
        if len(parts) < 2:
            continue
        d, v = parts[0].strip(), parts[1].strip()
        if not v or v == ".":
            continue
        try:
            out.append((d, float(v)))
        except ValueError:
            continue
    return out


# FRED 무료 다운로드는 짧은 시간에 몰아치면 IP를 일시 차단(읽기 타임아웃)한다.
# 그래서 (1) 네트워크 호출 사이 최소 간격을 두고, (2) 같은 series 동시요청은 락으로
# 한 번만 받아오며, (3) 디스크 캐시(12h)에 영구 저장해 요청 때마다 받지 않는다.
_net_lock = threading.Lock()           # 전역: 네트워크 호출 직렬화 + 간격 유지
_last_net = [0.0]
_MIN_INTERVAL = 1.2                     # 초 — 호출 간 최소 간격
_series_locks: dict[str, threading.Lock] = {}


def _series_lock(series: str) -> threading.Lock:
    with _lock:
        lk = _series_locks.get(series)
        if lk is None:
            lk = _series_locks[series] = threading.Lock()
        return lk


def _read_disk(series: str) -> tuple[float, list[tuple[str, float]]] | None:
    path = _cache_dir() / f"{series}.csv"
    try:
        if path.exists():
            return path.stat().st_mtime, _parse_csv(path.read_text(encoding="utf-8"))
    except OSError:
        pass
    return None


def _fetch_net(series: str, start: str, retries: int = 2) -> list[tuple[str, float]]:
    """FRED에서 받아 디스크·메모리에 저장. 백오프 재시도 + 전역 간격 유지."""
    end = datetime.date.today().isoformat()
    for attempt in range(retries):
        # 전역 간격 유지 (버스트 방지)
        with _net_lock:
            wait = _MIN_INTERVAL - (time.time() - _last_net[0])
            if wait > 0:
                time.sleep(wait)
            _last_net[0] = time.time()
        try:
            r = httpx.get(
                _FRED_URL,
                params={"id": series, "cosd": start, "coed": end},
                timeout=40.0,
                headers=_FRED_HEADERS,
            )
            r.raise_for_status()
            rows = _parse_csv(r.text)
            if rows:
                try:
                    (_cache_dir() / f"{series}.csv").write_text(r.text, encoding="utf-8")
                except OSError:
                    pass
                with _lock:
                    _mem[series] = (time.time(), rows)
                return rows
        except (httpx.HTTPError, OSError):
            pass
        time.sleep(1.5 * (attempt + 1))   # 백오프
    return []


def fred_cached(series: str) -> list[tuple[str, float]]:
    """요청 경로용 — 메모리/디스크 캐시만 읽고 네트워크는 절대 건드리지 않는다.
    아직 워밍되지 않은 series는 빈 리스트를 돌려주고(그래프에서 자연히 빠짐),
    네트워크 페치는 백그라운드 warm() 스레드만 담당한다."""
    now = time.time()
    with _lock:
        hit = _mem.get(series)
        if hit:
            return hit[1]
    disk = _read_disk(series)
    if disk:
        with _lock:
            _mem[series] = (now, disk[1])
        return disk[1]
    return []


def fred(series: str, start: str = "1996-01-01") -> list[tuple[str, float]]:
    """FRED 시계열을 (날짜, 값) 리스트로. 메모리→디스크→네트워크 순으로 캐시."""
    now = time.time()
    with _lock:
        hit = _mem.get(series)
        if hit and now - hit[0] < _CACHE_TTL:
            return hit[1]
    disk = _read_disk(series)
    if disk and now - disk[0] < _CACHE_TTL:
        with _lock:
            _mem[series] = (now, disk[1])
        return disk[1]

    # 동시 요청 dogpile 방지: series별 락
    with _series_lock(series):
        # 락 대기 중 다른 스레드가 채웠을 수 있다
        with _lock:
            hit = _mem.get(series)
        if hit and time.time() - hit[0] < _CACHE_TTL:
            return hit[1]
        rows = _fetch_net(series, start)
        if rows:
            return rows

    # 네트워크 실패 시 만료된 디스크 캐시라도 사용
    if disk and disk[1]:
        return disk[1]
    again = _read_disk(series)
    return again[1] if again else []


# --------------------------------------------------------------------------- #
# 정렬·정규화 헬퍼
# --------------------------------------------------------------------------- #
def _to_date(s: str) -> datetime.date:
    return datetime.date.fromisoformat(s)


def _window(rows: list[tuple[str, float]], day0: str, pre: int, post: int) -> list[tuple[int, float]]:
    """Day0을 0으로 한 '달력일' 오프셋 시계열. pre일 전 ~ post일 후 구간을 (day_offset, value)로.

    오프셋을 거래일 인덱스가 아닌 달력일로 잡으면 일·주·월별 시계열이 같은 시간축에
    정렬되어 한 그래프에 겹쳐 그릴 수 있다(예: 일별 나스닥 + 월별 코스피)."""
    if not rows:
        return []
    d0 = _to_date(day0)
    i0 = next((i for i, (d, _v) in enumerate(rows) if _to_date(d) >= d0), None)
    if i0 is None:
        return []
    base = _to_date(rows[i0][0])
    lo_d = base - datetime.timedelta(days=pre)
    hi_d = base + datetime.timedelta(days=post)
    out: list[tuple[int, float]] = []
    for d, v in rows:
        dd = _to_date(d)
        if lo_d <= dd <= hi_d:
            out.append(((dd - base).days, v))
    return out


def _strength(points: list[tuple[int, float]], per_usd: bool) -> list[tuple[int, float]]:
    """환율을 '통화 강도' Day0=100 으로. per_usd면 값↑=약세이므로 역수."""
    base = next((v for d, v in points if d == 0), None)
    if base is None or base == 0:
        # Day0 점이 없으면 가장 이른 점 기준
        base = points[0][1] if points else None
    if not base:
        return []
    out = []
    for d, v in points:
        if v == 0:
            continue
        ratio = (base / v) if per_usd else (v / base)
        out.append((d, round(ratio * 100.0, 3)))
    return out


def _index100(points: list[tuple[int, float]]) -> list[tuple[int, float]]:
    """레벨 시계열을 Day0=100 으로 정규화 (주가·금리 공통, 방향 그대로 유지)."""
    base = next((v for d, v in points if d == 0), None)
    if base is None:
        base = points[0][1] if points else None
    if not base:
        return []
    return [(d, round(v / base * 100.0, 3)) for d, v in points if v is not None]


def _stats(norm: list[tuple[int, float]], direction: str) -> dict:
    """붕괴 깊이·바닥(또는 정점)까지 일수."""
    post = [(d, v) for d, v in norm if d >= 0]
    if not post:
        return {"extreme_day": None, "extreme_v": None, "depth_pct": None}
    if direction == "down":
        d_ext, v_ext = min(post, key=lambda x: x[1])
        depth = round(v_ext - 100.0, 1)        # 음수 = 하락폭
    else:
        d_ext, v_ext = max(post, key=lambda x: x[1])
        depth = round(v_ext - 100.0, 1)        # 양수 = 상승폭
    return {"extreme_day": d_ext, "extreme_v": round(v_ext, 1), "depth_pct": depth}


# --------------------------------------------------------------------------- #
# 유사도 — 현재 궤적 vs 각 위기 곡선
# --------------------------------------------------------------------------- #
def _anchor(norm_levels: list[float], direction: str, search: int = 180) -> int:
    """현재 구간에서 '위기 시작점'으로 볼 기준점: down이면 최근 고점, up이면 최근 저점."""
    n = len(norm_levels)
    lo = max(0, n - search)
    seg = norm_levels[lo:]
    if not seg:
        return max(0, n - 1)
    if direction == "down":
        k = max(range(len(seg)), key=lambda i: seg[i])
    else:
        k = min(range(len(seg)), key=lambda i: seg[i])
    return lo + k


def _corr(a: list[float], b: list[float]) -> float | None:
    n = min(len(a), len(b))
    if n < 5:
        return None
    a, b = a[:n], b[:n]
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return None
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    return cov / (va ** 0.5 * vb ** 0.5)


def _rmse(a: list[float], b: list[float]) -> float | None:
    n = min(len(a), len(b))
    if n < 5:
        return None
    return (sum((a[i] - b[i]) ** 2 for i in range(n)) / n) ** 0.5


def _verdict(score: float) -> str:
    if score >= 80:
        return "매우 유사"
    if score >= 60:
        return "유사"
    if score >= 40:
        return "다소 유사"
    return "약한 유사"


# --------------------------------------------------------------------------- #
# 시리즈 빌더
# --------------------------------------------------------------------------- #
def _build_series(metric: str, crisis_key: str) -> list[dict]:
    cfg = METRIC_CFG[metric]
    reg = cfg["registry"]
    members = cfg["members"].get(crisis_key, [])
    c = CRISIS_BY_KEY[crisis_key]
    direction = METRICS[metric]["direction"]
    out: list[dict] = []
    for code in members:
        meta = reg[code]
        rows = fred_cached(meta["fred"])
        win = _window(rows, c["day0"], c["pre"], c["post"])
        if len(win) < 6:
            continue
        if cfg["norm"] == "strength":
            norm = _strength(win, meta.get("per_usd", False))
        else:
            norm = _index100(win)
        if len(norm) < 6:
            continue
        st = _stats(norm, direction)
        out.append({
            "code": code,
            "crisis": crisis_key,
            "label": f"{meta['name']} · {c['label'][:7]}",
            "name": meta["name"],
            "color": meta["color"],
            "freq": meta.get("freq", "일별"),
            "points": [{"day": d, "v": v} for d, v in norm],
            **st,
        })
    return out


# 현재 궤적 색(과거 위기선과 구분되는 진한 톤). 없으면 레지스트리 색 사용.
_CURRENT_COLORS = {
    "KR": "#111111", "US": "#0b7285", "JP": "#5f3dc4", "EU": "#1864ab",
    "BR": "#a61e4d", "MX": "#a61e4d", "GR": "#862e2e", "ES": "#b35309", "IT": "#9c6312",
    "KRM": "#111111",
}


# 현재 구간 길이(빈도별 행 수) — 아날로그 매칭에 쓰는 '최근 N'
_WINDOW = {"일별": 120, "주간": 52, "월별": 12}
# 투영 시 '향후 며칠'을 예상 변화로 요약할지(빈도별 달력일)
_HORIZON = {"일별": 60, "주간": 60, "월별": 150}


def _recent_series(metric: str, code: str) -> dict | None:
    """현재의 '최근 구간'(고점 앵커 없이 마지막 W개). 아날로그 매칭의 질의 시계열."""
    cfg = METRIC_CFG[metric]
    meta = cfg["registry"][code]
    freq = meta.get("freq", "일별")
    rows = fred_cached(meta["fred"])
    if not rows:
        return None
    rows = rows[-_WINDOW.get(freq, 120):]
    per_usd = cfg["norm"] == "strength" and meta.get("per_usd", False)
    if per_usd:
        pairs = [(d, 1.0 / v) for d, v in rows if v]
    else:
        pairs = [(d, v) for d, v in rows if v is not None]
    if len(pairs) < 8:
        return None
    dates = [d for d, _ in pairs]
    base = pairs[0][1] or 1.0
    norm = [v / base * 100.0 for _, v in pairs]
    return {
        "code": code, "name": meta["name"], "freq": freq,
        "color": _CURRENT_COLORS.get(code, meta.get("color", "#111")),
        "norm": norm, "as_of": str(dates[-1]),
    }


def _slide_best(cur: list[float], cv: list[float]) -> tuple[float, int] | None:
    """현재 구간 cur 를 과거 곡선 cv 위로 슬라이딩하며 상관 최대 위치(코릴, start) 반환."""
    W = len(cur)
    if len(cv) < W:
        return None
    best: tuple[float, int] | None = None
    for start in range(0, len(cv) - W + 1):
        cor = _corr(cur, cv[start:start + W])
        if cor is None:
            continue
        if best is None or cor > best[0]:
            best = (cor, start)
    return best


def _analog_for(metric: str, code: str, series: list[dict]) -> dict | None:
    """아날로그 예측: 현재 최근 구간을 같은 지수의 과거 위기 '전체 타임라인'에 맞춰
    가장 닮은 위치를 찾고(=위기 며칠 전인지), 그 위기의 이후 경로를 예상 시나리오로 투영."""
    rec = _recent_series(metric, code)
    if not rec:
        return None
    cur = rec["norm"]
    W = len(cur)
    direction = METRICS[metric]["direction"]
    same = [s for s in series if s["code"] == code]

    analogs: list[dict] = []
    for s in same:
        cv = [p["v"] for p in s["points"]]
        cd = [p["day"] for p in s["points"]]
        res = _slide_best(cur, cv)
        if res is None:
            continue
        cor, start = res
        end_day = cd[start + W - 1]            # 현재의 끝점이 위기축에서 며칠째인가
        lead = -end_day if end_day < 0 else 0  # 위기까지 남은 일수(음수면 이미 발발 이후)
        phase = f"위기 {abs(end_day)}일 전" if end_day < 0 else f"위기 후 {end_day}일"
        analogs.append({
            "crisis": s["crisis"], "crisis_label": CRISIS_BY_KEY[s["crisis"]]["label"],
            "color": s["color"], "corr": round(cor, 3),
            "lead_days": lead, "phase": phase, "end_day": end_day,
            "_cv": cv, "_cd": cd, "_start": start,
        })
    analogs.sort(key=lambda x: x["corr"], reverse=True)

    base_out = {
        "code": code, "name": rec["name"], "color": rec["color"],
        "label": f"{rec['name']} (현재)", "as_of": rec["as_of"],
        "same_instrument": bool(same),
    }
    if not analogs:
        # 비교할 과거 곡선이 없으면 현재선만(달력일 0..)
        return {**base_out, "points": [{"day": i, "v": round(cur[i], 3)} for i in range(W)],
                "projection": [], "best": None, "analogs": []}

    top = analogs[0]
    cv, cd, start = top["_cv"], top["_cd"], top["_start"]
    seg = cv[start:start + W]
    mcur, mseg = sum(cur) / W, sum(seg) / W
    factor = (mseg / mcur) if mcur else 1.0   # 현재를 위기 곡선 스케일로 맞춤
    aligned = [{"day": cd[start + i], "v": round(cur[i] * factor, 3)} for i in range(W)]
    projection = [{"day": cd[j], "v": round(cv[j], 3)} for j in range(start + W, len(cv))]

    # 예상 변화: 현재 끝점 이후 horizon 일 내 극값 대비 변화율
    end_day, base_v = cd[start + W - 1], cv[start + W - 1]
    horizon = _HORIZON.get(rec["freq"], 60)
    fut = [cv[j] for j in range(start + W, len(cv)) if cd[j] - end_day <= horizon]
    expected = None
    if fut and base_v:
        ext = min(fut) if direction == "down" else max(fut)
        expected = round((ext / base_v - 1) * 100.0, 1)

    best = {
        "crisis": top["crisis"], "crisis_label": top["crisis_label"], "color": top["color"],
        "corr": top["corr"], "lead_days": top["lead_days"], "phase": top["phase"],
        "expected_pct": expected, "horizon": horizon,
    }
    pub = lambda a: {k: a[k] for k in ("crisis", "crisis_label", "color", "corr", "lead_days", "phase")}
    return {**base_out, "points": aligned, "projection": projection,
            "best": best, "analogs": [pub(a) for a in analogs[:6]]}


def _build_currents(metric: str, series: list[dict]) -> list[dict]:
    out: list[dict] = []
    for code in METRIC_CFG[metric]["current_codes"]:
        a = _analog_for(metric, code, series)
        if a:
            out.append(a)
    return out


# --------------------------------------------------------------------------- #
# 캐시 워밍 — 필요한 FRED 시계열을 백그라운드에서 한 번 천천히 받아 디스크에 저장.
# 요청 때마다 FRED를 두드리지 않게 해 throttle(읽기 타임아웃)을 피한다.
# --------------------------------------------------------------------------- #
# 조기경보 전용 추가 시계열(레지스트리에 없는 것)
_WARN_SERIES = ["NFCI", "T10Y2Y", "DRTSCILM", "UMCSENT",
                "TRESEGKRM052N", "MKTGDPKRA646NWDB", "GGGDTPKRA188N",
                "XTEXVA01KRM667S", "XTIMVA01KRM667S"]


def _all_series() -> list[str]:
    ids: list[str] = []
    for reg in (FX, STOCK, BOND, VIX, CREDIT, OIL, EMPLOY):
        for meta in reg.values():
            if meta["fred"] not in ids:
                ids.append(meta["fred"])
    for s in _WARN_SERIES:
        if s not in ids:
            ids.append(s)
    for s in _country_series_ids():
        if s not in ids:
            ids.append(s)
    return ids


_warm_state = {"running": False, "cached": 0, "total": 0, "started": False,
               "last": None, "attempts": 0}


def warm() -> int:
    """필요한 FRED 시계열을 천천히 받아 디스크에 채운다. 성공적으로 캐시된 개수를 반환.
    이미 신선한 디스크 캐시는 건너뛴다."""
    ids = _all_series()
    _warm_state.update(running=True, total=len(ids), attempts=_warm_state["attempts"] + 1)
    cached = 0
    consec_fail = 0
    for s in ids:
        disk = _read_disk(s)
        if disk and disk[1] and time.time() - disk[0] < _CACHE_TTL:
            cached += 1
        elif _fetch_net(s, "1996-01-01", retries=1):
            cached += 1
            consec_fail = 0
        else:
            consec_fail += 1
            # FRED throttle 추정 — 더 두드리지 말고 이번 사이클은 중단, 백오프 후 재시도
            if consec_fail >= 2:
                break
        _warm_state["cached"] = cached
    _warm_state.update(running=False, last=datetime.datetime.now().isoformat(timespec="seconds"))
    return cached


def start() -> None:
    """서버 기동 시 1회 호출 — 백그라운드 워밍 스레드를 띄운다.
    FRED throttle로 일부만 채워지면 5분 뒤 재시도(자가 치유), 전부 채워지면 12h 간격."""
    if _warm_state["started"]:
        return
    _warm_state["started"] = True

    def _loop():
        while True:
            try:
                cached = warm()
            except Exception:
                cached = 0
            full = cached >= _warm_state["total"] and _warm_state["total"] > 0
            time.sleep(_CACHE_TTL if full else 300)
    threading.Thread(target=_loop, name="crisis-warm", daemon=True).start()


def warm_status() -> dict:
    return dict(_warm_state)


# --------------------------------------------------------------------------- #
# 위기 선행징후 (조기경보) — 곡선 모양이 아니라 '전조 증상'을 임계값과 견준다.
#   거품·과열(기대수익 괴리) / 신용경색 / 침체예고(금리차) / 심리·금융여건.
# --------------------------------------------------------------------------- #
_WARN = [
    {"key": "nfci", "label": "금융 스트레스 (NFCI)", "fred": "NFCI", "danger": "high",
     "watch": 0.0, "alert": 0.4, "unit": "",
     "desc": "시카고연준 금융여건지수. 양수면 돈줄이 마르는 중(스트레스)."},
    {"key": "yield", "label": "장단기 금리차 (10Y-2Y)", "fred": "T10Y2Y", "danger": "low",
     "watch": 0.5, "alert": 0.0, "unit": "%p",
     "desc": "0 밑(역전)이면 12~18개월 내 침체 신호. 역사상 모든 침체에 선행."},
    {"key": "lending", "label": "은행 대출태도", "fred": "DRTSCILM", "danger": "high",
     "watch": 10, "alert": 25, "unit": "%",
     "desc": "은행이 기업대출을 조이는 순비율. 양수↑면 신용경색 전조."},
    {"key": "sentiment", "label": "소비심리 (미시간대)", "fred": "UMCSENT", "danger": "low",
     "watch": 75, "alert": 65, "unit": "",
     "desc": "소비심리가 급락하면 수요·소비 둔화."},
    {"key": "credit", "label": "하이일드 스프레드", "fred": "BAMLH0A0HYM2", "danger": "high",
     "watch": 4.5, "alert": 7.0, "unit": "%p", "no_benchmark": True,
     "desc": "회사채 가산금리. 벌어지면 위험회피·신용경색 (현재값만, 과거치 미제공)."},
]
_LEVEL_SCORE = {"ok": 0, "watch": 1, "alert": 2}


def _status(v: float, watch: float, alert: float, danger: str) -> str:
    if danger == "high":
        return "alert" if v >= alert else "watch" if v >= watch else "ok"
    return "alert" if v <= alert else "watch" if v <= watch else "ok"


def _precrisis_avg(rows: list[tuple[str, float]], lo: int = 150, hi: int = 20) -> float | None:
    """과거 위기들 직전(Day0-lo ~ Day0-hi일)의 평균값 — '위기 터지기 직전엔 이랬다'."""
    vals: list[float] = []
    for c in CRISES:
        d0 = _to_date(c["day0"])
        a, b = d0 - datetime.timedelta(days=lo), d0 - datetime.timedelta(days=hi)
        seg = [v for d, v in rows if a <= _to_date(d) <= b]
        if seg:
            vals.append(sum(seg) / len(seg))
    return round(sum(vals) / len(vals), 2) if vals else None


def warning_signs() -> dict:
    """현재 전조지표들을 임계값·과거 위기직전 수준과 견줘 조기경보를 만든다."""
    signs: list[dict] = []
    statuses: list[str] = []

    # 증시 과열도 — 나스닥이 장기추세(400일선) 대비 몇 % 위인가 (거품/기대 괴리 프록시)
    nq = fred_cached("NASDAQCOM")
    if nq and len(nq) >= 420:
        last = nq[-1][1]
        dev = round((last / (sum(v for _, v in nq[-400:]) / 400) - 1) * 100, 1)
        pcv = []
        for c in CRISES:
            d0 = _to_date(c["day0"])
            idx = next((i for i, (d, _) in enumerate(nq) if _to_date(d) >= d0), None)
            if idx and idx >= 400:
                base = sum(v for _, v in nq[idx - 400:idx]) / 400
                pcv.append((nq[idx][1] / base - 1) * 100)
        st = _status(dev, 12, 25, "high")
        signs.append({"key": "overheat", "label": "증시 과열도 (추세 이탈)", "value": dev,
                      "unit": "%", "status": st, "as_of": nq[-1][0], "extra": None,
                      "pre_crisis_avg": round(sum(pcv) / len(pcv), 1) if pcv else None,
                      "desc": "나스닥이 장기추세(400일 평균) 대비 +면 과열·거품(기대수익 괴리)."})
        statuses.append(st)

    for w in _WARN:
        rows = fred_cached(w["fred"])
        if not rows:
            continue
        cur = rows[-1][1]
        st = _status(cur, w["watch"], w["alert"], w["danger"])
        extra = None
        if w["key"] == "yield":
            recent = [v for d, v in rows
                      if (_to_date(rows[-1][0]) - _to_date(d)).days <= 730]
            if recent and min(recent) < 0:
                extra = "최근 2년 내 금리차 역전 발생"
                if st == "ok":
                    st = "watch"
        signs.append({
            "key": w["key"], "label": w["label"], "value": round(cur, 2),
            "unit": w["unit"], "status": st, "as_of": rows[-1][0], "extra": extra,
            "pre_crisis_avg": None if w.get("no_benchmark") else _precrisis_avg(rows),
            "desc": w["desc"],
        })
        statuses.append(st)

    score = round(sum(_LEVEL_SCORE[s] for s in statuses) / (2 * len(statuses)) * 100) if statuses else 0
    level = "위험" if score >= 70 else "경고" if score >= 45 else "주의" if score >= 20 else "낮음"
    return {
        "score": score, "level": level, "signs": signs,
        "as_of": max((s["as_of"] for s in signs), default=None),
        "note": "전조지표를 임계값·과거 위기직전 수준과 비교. 경고가 많을수록 위기 환경에 가깝다는 뜻이며, 시점을 예측하진 않습니다.",
    }


# --------------------------------------------------------------------------- #
# 한국 외환위기 선행징후 (김대종 교수 프레임)
#   외환보유액·통화스와프·국가부채·무역의존도·환율 — 교수의 임계값을 기준선으로.
#   ※ 한 학자의 특정(논쟁적) 시각. 객관적 사실이 아니라 '그 프레임의 점검표'.
# --------------------------------------------------------------------------- #
# 통화스와프는 자동 피드가 없어 알려진 현황을 수동 기입(설명에 근거 명시).
_KR_SWAPS = [
    {"label": "한미 통화스와프", "status": "alert",
     "note": "상설 미체결(2021.12 한시 종료). 교수: 위기 시 달러 방어선 부재가 최대 약점."},
    {"label": "한일 통화스와프", "status": "watch",
     "note": "2023년 100억 달러 복원(상설 아님)."},
]


def korea_fx_warning() -> dict:
    """교수 프레임의 한국 외환위기 전조지표를 현재값·임계값으로 점검."""
    signs: list[dict] = []
    statuses: list[str] = []

    def add(key, label, value, unit, watch, alert, danger, desc, benchmark=None):
        if value is None:
            return
        st = _status(value, watch, alert, danger)
        signs.append({"key": key, "label": label, "value": round(value, 1), "unit": unit,
                      "status": st, "benchmark": benchmark, "desc": desc})
        statuses.append(st)

    fx = fred_cached("DEXKOUS")
    res = fred_cached("TRESEGKRM052N")           # 외환보유액(백만 달러, 월)
    gdp = fred_cached("MKTGDPKRA646NWDB")         # 명목 GDP(달러, 연)
    debt = fred_cached("GGGDTPKRA188N")           # 일반정부부채/GDP(%, 연)
    exp = fred_cached("XTEXVA01KRM667S")          # 수출(달러, 월)
    imp = fred_cached("XTIMVA01KRM667S")          # 수입(달러, 월)

    # 1) 원/달러 환율 — 교수 전망 1,500원
    if fx:
        add("fx", "원/달러 환율", fx[-1][1], "원", 1350, 1450, "high",
            "상승할수록 원화 약세·외화 이탈 압력. 교수 전망 1,500원.", benchmark=1500)

    # 2) 외환보유액/GDP — 교수: 23%로 취약 (BIS 권고 수준까지 확대 주장)
    reserves_b = res[-1][1] / 1000 if res else None         # 십억 달러
    gdp_usd = gdp[-1][1] if gdp else None
    if reserves_b and gdp_usd:
        ratio = reserves_b * 1e9 / gdp_usd * 100
        add("reserves_gdp", "외환보유액 / GDP", ratio, "%", 25, 20, "low",
            f"현재 외환보유액 약 ${reserves_b:.0f}B. 교수: GDP 대비 23%로 취약(BIS 권고 $920B까지 확대 주장).",
            benchmark=None)

    # 3) 국가부채/GDP — IMF 60% 초과 시 위험국 (교수: 2029년 60% 전망)
    if debt:
        add("debt_gdp", "국가부채 / GDP", debt[-1][1], "%", 50, 60, "high",
            "IMF 기준 60% 초과 시 위험국 분류. 교수: 2026년 50%·2029년 60% 전망.", benchmark=60)

    # 4) 무역의존도 = 최근 12개월 (수출+수입) / GDP — 교수: 75%로 세계 2위
    if exp and imp and gdp_usd:
        trade = sum(v for _, v in exp[-12:]) + sum(v for _, v in imp[-12:])
        dep = trade / gdp_usd * 100
        add("trade_dep", "무역의존도", dep, "%", 70, 90, "high",
            "(연 수출+수입)/GDP. 높을수록 대외충격에 민감. 교수: 약 75%로 세계 2위.", benchmark=75)

    # 통화스와프 상태 반영
    statuses += [s["status"] for s in _KR_SWAPS]

    score = round(sum(_LEVEL_SCORE[s] for s in statuses) / (2 * len(statuses)) * 100) if statuses else 0
    level = "위험" if score >= 70 else "경고" if score >= 45 else "주의" if score >= 20 else "낮음"
    return {
        "score": score, "level": level, "signs": signs, "swaps": _KR_SWAPS,
        "as_of": max((d[-1][0] for d in (fx, res, debt) if d), default=None),
        "frame": "김대종 세종대 교수 『제2 IMF 외환위기 다시 오는가?』(2025) 프레임",
        "note": "한 학자의 특정·논쟁적 시각을 점검표로 옮긴 것입니다. 임계값도 교수 주장 기준이며, 한국은행·기재부 공식 설명과 다른 견해도 함께 보세요. 위기 시점을 예측하지 않습니다.",
    }


# --------------------------------------------------------------------------- #
# 국가별 거시지표 비교표 (Trading Economics 스타일) — FRED 국가별 시리즈.
#   GDP·성장률·금리·물가·실업률·부채/GDP·경상수지·인구 (정부예산은 무료 일관 소스 없음).
# --------------------------------------------------------------------------- #
_COUNTRIES = [
    {"name": "한국", "iso2": "KR", "iso3": "KOR"},
    {"name": "미국", "iso2": "US", "iso3": "USA"},
    {"name": "일본", "iso2": "JP", "iso3": "JPN"},
    {"name": "중국", "iso2": "CN", "iso3": "CHN"},
    {"name": "독일", "iso2": "DE", "iso3": "DEU"},
    {"name": "영국", "iso2": "GB", "iso3": "GBR"},
]


def _country_series(c: dict) -> dict[str, str]:
    """국가별 지표 → FRED series id (코드 체계가 지표마다 2/3글자로 다름)."""
    i2, i3 = c["iso2"], c["iso3"]
    return {
        "gdp": f"MKTGDP{i2}A646NWDB",          # 명목 GDP(달러, 연)
        "growth": f"{i3}GDPRQPSMEI",           # 실질 GDP 성장률(전년동기%, OECD)
        "rate": f"IR3TIB01{i2}M156N",          # 3개월 단기금리(%)
        "cpi": f"FPCPITOTLZG{i3}",             # 물가상승률(연%)
        "unemp": f"LRHUTTTT{i2}M156S",         # 실업률(월%)
        "debt": f"GGGDTP{i2}A188N",            # 일반정부부채/GDP(%)
        "ca": f"{i3}B6BLTT02STSAQ",            # 경상수지/GDP(%)
        "pop": f"POPTOT{i2}A647NWDB",          # 인구(명, 연)
    }


def _country_series_ids() -> list[str]:
    ids: list[str] = []
    for c in _COUNTRIES:
        ids.extend(_country_series(c).values())
    return ids


def _last(series: str) -> tuple[float | None, str | None]:
    r = fred_cached(series)
    return (r[-1][1], r[-1][0]) if r else (None, None)


def country_macros() -> dict:
    """주요국 핵심 거시지표 최신값 비교표. 캐시만 읽으므로(워밍 의존) 비면 None."""
    rows: list[dict] = []
    for c in _COUNTRIES:
        s = _country_series(c)
        gdp, gdp_d = _last(s["gdp"])
        growth, _ = _last(s["growth"])
        rate, _ = _last(s["rate"])
        cpi, _ = _last(s["cpi"])
        unemp, _ = _last(s["unemp"])
        debt, _ = _last(s["debt"])
        ca, _ = _last(s["ca"])
        pop, _ = _last(s["pop"])

        def rnd(v, n=2):
            return round(v, n) if v is not None else None

        rows.append({
            "country": c["name"], "iso": c["iso2"],
            "gdp_usd": gdp,                      # 명목 GDP(달러)
            "gdp_year": gdp_d[:4] if gdp_d else None,
            "gdp_growth": rnd(growth, 1),       # %
            "rate": rnd(rate),                  # %
            "cpi": rnd(cpi, 1),                 # %
            "unemployment": rnd(unemp, 1),      # %
            "debt_gdp": rnd(debt, 1),           # %
            "current_account": rnd(ca, 1),      # % of GDP
            "population": pop,                  # 명
        })
    return {
        "countries": rows,
        "as_of": max((d for d in (_last(s)[1] for s in _country_series_ids()) if d), default=None),
        "note": "주요국 핵심 거시지표(FRED). GDP·인구는 연간, 성장률·경상수지는 분기, 금리·실업률은 월간 최신값. 정부예산수지는 국가별 무료 일관 소스가 없어 제외. 빈칸은 해당국 미제공/적재중.",
    }


# --------------------------------------------------------------------------- #
# 공개 API
# --------------------------------------------------------------------------- #
def meta() -> dict:
    metrics = []
    for k, m in METRICS.items():
        metrics.append({"key": k, "label": m["label"], "direction": m["direction"], "desc": m["desc"]})
    crises = [{
        "key": c["key"], "label": c["label"], "day0": c["day0"],
        "trigger": c["trigger"], "desc": c["desc"], "color": c["color"],
    } for c in CRISES]
    return {
        "metrics": metrics,
        "crises": crises,
        "source": "FRED (환율·주가·국채금리·VIX·신용스프레드·유가·고용)",
        "note": "Day0=위기 방아쇠 사건. 모든 지표는 Day0=100으로 정규화. 현재선은 같은 지수의 과거 위기와 비교. (한국 코스피·실업률 등 일부는 월별)",
    }


def simulate(metric: str, crisis_keys: list[str] | None = None) -> dict:
    if metric not in METRICS:
        metric = "fx"
    keys = crisis_keys or [c["key"] for c in CRISES]
    keys = [k for k in keys if k in CRISIS_BY_KEY]

    series: list[dict] = []
    for k in keys:
        series.extend(_build_series(metric, k))

    currents = _build_currents(metric, series)

    # 그래프 표시 범위 (현재 정렬 위치·투영 포함)
    max_day = 0
    min_day = 0
    for s in series:
        for p in s["points"]:
            max_day = max(max_day, p["day"])
            min_day = min(min_day, p["day"])
    for c in currents:
        for p in c["points"] + c.get("projection", []):
            max_day = max(max_day, p["day"])
            min_day = min(min_day, p["day"])

    return {
        "metric": {"key": metric, **METRICS[metric]},
        "crises": [{
            "key": k, "label": CRISIS_BY_KEY[k]["label"],
            "color": CRISIS_BY_KEY[k]["color"], "trigger": CRISIS_BY_KEY[k]["trigger"],
            "day0": CRISIS_BY_KEY[k]["day0"], "desc": CRISIS_BY_KEY[k]["desc"],
        } for k in keys],
        "series": series,
        "currents": currents,
        "axis": {"min_day": min_day, "max_day": max_day},
    }
