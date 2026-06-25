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
from app.data.infra import store

# --------------------------------------------------------------------------- #
# 위기 에피소드 — Day 0 = 방아쇠 사건
# --------------------------------------------------------------------------- #
CRISES: list[dict] = [
    {
        "key": "1997_asia", "label": "1997 아시아 외환위기", "day0": "1997-07-02",
        "pre": 30, "post": 320, "color": "#c92a2a",
        "trigger": "태국 바트 변동환율 전환",
        "desc": "태국이 달러 페그를 포기하자 바트·원·링깃이 연쇄 폭락 — 외환위기의 교과서.",
    },
    {
        "key": "2008_gfc", "label": "2008 글로벌 금융위기", "day0": "2008-09-15",
        "pre": 30, "post": 300, "color": "#e8590c",
        "trigger": "리먼 브러더스 파산",
        "desc": "신용경색이 전 세계로 번지며 신흥국 통화·증시가 동반 급락.",
    },
    {
        "key": "2010_euro", "label": "2010 유럽 재정위기", "day0": "2010-04-23",
        "pre": 30, "post": 520, "color": "#1971c2",
        "trigger": "그리스 구제금융 요청",
        "desc": "남유럽 국가신용 불안으로 그리스·스페인·이탈리아 국채금리가 급등.",
    },
    {
        "key": "2020_covid", "label": "2020 코로나 쇼크", "day0": "2020-02-19",
        "pre": 30, "post": 200, "color": "#7048e8",
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

# 주가 (FRED 일별). 한국 현재선은 DuckDB 프록시로 별도 처리.
STOCK = {
    "US": {"name": "미국 나스닥", "fred": "NASDAQCOM", "color": "#e8590c"},
    "JP": {"name": "일본 닛케이225", "fred": "NIKKEI225", "color": "#9c36b5"},
}
CRISIS_STOCK = {
    "1997_asia": ["US", "JP"],
    "2008_gfc": ["US", "JP"],
    "2010_euro": ["US", "JP"],
    "2020_covid": ["US", "JP"],
}

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

METRICS = {
    "fx": {"label": "환율 (통화가치)", "direction": "down",
           "desc": "USD 대비 통화가치. 아래로 내려갈수록 통화 붕괴(외환위기형)."},
    "stock": {"label": "주가지수", "direction": "down",
              "desc": "대표 주가지수. 아래로 내려갈수록 증시 폭락."},
    "bond": {"label": "국채금리 (신용)", "direction": "up",
             "desc": "10년물 국채금리. 위로 올라갈수록 국가신용 불안(금리 급등)."},
}

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
    """Day0(>= 기준일 첫 거래일)을 0으로 한 거래일 오프셋 시계열.
    pre 거래일 전 ~ post 거래일 후 구간을 (day_offset, value)로."""
    if not rows:
        return []
    d0 = _to_date(day0)
    # Day0 위치: 기준일 이상인 첫 점
    i0 = None
    for i, (d, _v) in enumerate(rows):
        if _to_date(d) >= d0:
            i0 = i
            break
    if i0 is None:
        return []
    lo = max(0, i0 - pre)
    hi = min(len(rows), i0 + post + 1)
    return [(i - i0, rows[i][1]) for i in range(lo, hi)]


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
# 한국 '현재' 시계열
# --------------------------------------------------------------------------- #
def _kr_fx_now(lookback: int = 220) -> list[tuple[str, float]]:
    rows = fred_cached("DEXKOUS")
    return rows[-lookback:] if rows else []


def _kr_stock_now(lookback: int = 220) -> list[tuple[str, float]]:
    """로컬 DuckDB로 만든 시가총액 가중 한국 주가 프록시 (최근 lookback 거래일).
    최신 시가총액을 정적 가중치로, 구간 전체에 존재하는 종목만 사용."""
    try:
        with store.connection() as conn:
            dates = [r[0] for r in conn.execute(
                "SELECT DISTINCT date FROM prices WHERE market='KR' ORDER BY date DESC LIMIT ?",
                [lookback],
            ).fetchall()]
            if not dates:
                return []
            start = min(dates)
            df = conn.execute(
                """
                WITH w AS (
                    SELECT ticker, market_cap,
                           ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) rn
                    FROM fundamentals WHERE market='KR' AND market_cap IS NOT NULL
                )
                SELECT p.date AS date,
                       SUM(p.close / b.base * w.market_cap) AS idx,
                       SUM(w.market_cap) AS wsum
                FROM prices p
                JOIN w ON w.ticker = p.ticker AND w.rn = 1
                JOIN (
                    SELECT ticker, close AS base FROM prices
                    WHERE market='KR' AND date = ?
                ) b ON b.ticker = p.ticker
                WHERE p.market='KR' AND p.date >= ? AND p.close IS NOT NULL
                GROUP BY p.date
                ORDER BY p.date
                """,
                [start, start],
            ).fetchall()
        out = []
        for d, idx, wsum in df:
            if wsum:
                out.append((str(d), float(idx) / float(wsum) * 100.0))
        return out
    except Exception:
        return []


def _kr_bond_now(lookback: int = 36) -> list[tuple[str, float]]:
    rows = fred_cached("IRLTLT01KRM156N")
    return rows[-lookback:] if rows else []


def _now_series(metric: str) -> tuple[list[tuple[str, float]], bool]:
    """(원시 (날짜,값) 시계열, per_usd) — 한국 '현재' 신호."""
    if metric == "fx":
        return _kr_fx_now(), True
    if metric == "stock":
        return _kr_stock_now(), False  # 이미 지수(레벨)
    return _kr_bond_now(), False


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
    c = CRISIS_BY_KEY[crisis_key]
    out: list[dict] = []
    if metric == "fx":
        members, reg = CRISIS_FX.get(crisis_key, []), FX
    elif metric == "stock":
        members, reg = CRISIS_STOCK.get(crisis_key, []), STOCK
    else:
        members, reg = CRISIS_BOND.get(crisis_key, []), BOND

    for code in members:
        meta = reg[code]
        rows = fred_cached(meta["fred"])
        win = _window(rows, c["day0"], c["pre"], c["post"])
        if len(win) < 10:
            continue
        if metric == "fx":
            norm = _strength(win, meta["per_usd"])
        else:
            norm = _index100(win)
        if len(norm) < 10:
            continue
        st = _stats(norm, METRICS[metric]["direction"])
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


def _build_current(metric: str) -> dict | None:
    raw, per_usd = _now_series(metric)
    if len(raw) < 20:
        return None
    direction = METRICS[metric]["direction"]
    if metric == "fx":
        # 환율은 '통화 강도'(USD 대비)로 변환 — anchor에서 다시 100 기준을 잡는다.
        strength = []
        for d, v in raw:
            if not v:
                continue
            strength.append((d, (raw[0][1] / v) if per_usd else (v / raw[0][1])))
        dates = [d for d, _ in strength]
        vals = [v for _, v in strength]
    else:
        dates = [d for d, _ in raw]
        vals = [v for _, v in raw]

    anchor = _anchor(vals, direction)
    base = vals[anchor]
    if not base:
        return None
    seg_vals = vals[anchor:]
    seg_dates = dates[anchor:]
    norm = [round(v / base * 100.0, 3) for v in seg_vals]
    points = [{"day": i, "v": norm[i]} for i in range(len(norm))]
    st = _stats([(i, norm[i]) for i in range(len(norm))], direction)
    label_map = {"fx": "한국 원화 (현재)", "stock": "한국 증시 (현재)", "bond": "한국 10년물 (현재)"}
    return {
        "label": label_map[metric],
        "anchor_date": str(seg_dates[0]),
        "as_of": str(seg_dates[-1]),
        "days_elapsed": len(norm) - 1,
        "norm": norm,                       # 유사도 계산용 (내부)
        "points": points,
        **st,
    }


def _similarity(metric: str, current: dict, all_series: list[dict]) -> list[dict]:
    if not current:
        return []
    cur = current["norm"]
    n = len(cur)
    out = []
    for s in all_series:
        seg = [p["v"] for p in s["points"] if p["day"] >= 0][:n]
        if len(seg) < max(5, n // 2):
            continue
        cor = _corr(cur, seg)
        rmse = _rmse(cur, seg)
        if cor is None or rmse is None:
            continue
        # 점수: 모양(상관) 70% + 수준근접(오차) 30%
        shape = max(0.0, cor) * 100.0
        prox = max(0.0, 100.0 - rmse * 4.0)
        score = round(shape * 0.7 + prox * 0.3, 1)
        crisis = CRISIS_BY_KEY[s["crisis"]]
        out.append({
            "crisis": s["crisis"],
            "crisis_label": crisis["label"],
            "code": s["code"],
            "name": s["name"],
            "label": s["label"],
            "color": s["color"],
            "score": score,
            "corr": round(cor, 3),
            "verdict": _verdict(score),
            # 그 위기가 같은 일수 시점에 도달했던 낙폭 (참고)
            "their_v_at_now": round(seg[-1], 1) if seg else None,
        })
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


# --------------------------------------------------------------------------- #
# 캐시 워밍 — 필요한 FRED 시계열을 백그라운드에서 한 번 천천히 받아 디스크에 저장.
# 요청 때마다 FRED를 두드리지 않게 해 throttle(읽기 타임아웃)을 피한다.
# --------------------------------------------------------------------------- #
def _all_series() -> list[str]:
    ids: list[str] = []
    for reg in (FX, STOCK, BOND):
        for meta in reg.values():
            if meta["fred"] not in ids:
                ids.append(meta["fred"])
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
        "source": "FRED (환율·미/일 지수·국채금리) + 로컬 DuckDB (한국 현재 주가 프록시)",
        "note": "Day0=위기 방아쇠 사건. 모든 지표는 Day0=100으로 정규화. 환율·주가는 ↓=붕괴, 금리는 ↑=붕괴.",
    }


def simulate(metric: str, crisis_keys: list[str] | None = None) -> dict:
    if metric not in METRICS:
        metric = "fx"
    keys = crisis_keys or [c["key"] for c in CRISES]
    keys = [k for k in keys if k in CRISIS_BY_KEY]

    series: list[dict] = []
    for k in keys:
        series.extend(_build_series(metric, k))

    current = _build_current(metric)
    similarity = _similarity(metric, current, series) if current else []

    # 그래프 표시 범위
    max_day = 0
    min_day = 0
    for s in series:
        for p in s["points"]:
            max_day = max(max_day, p["day"])
            min_day = min(min_day, p["day"])
    if current:
        max_day = max(max_day, current["days_elapsed"])

    # 응답에서 내부용 norm 제거
    cur_out = None
    if current:
        cur_out = {k: v for k, v in current.items() if k != "norm"}

    return {
        "metric": {"key": metric, **METRICS[metric]},
        "crises": [{
            "key": k, "label": CRISIS_BY_KEY[k]["label"],
            "color": CRISIS_BY_KEY[k]["color"], "trigger": CRISIS_BY_KEY[k]["trigger"],
            "day0": CRISIS_BY_KEY[k]["day0"], "desc": CRISIS_BY_KEY[k]["desc"],
        } for k in keys],
        "series": series,
        "current": cur_out,
        "similarity": similarity,
        "axis": {"min_day": min_day, "max_day": max_day},
    }
