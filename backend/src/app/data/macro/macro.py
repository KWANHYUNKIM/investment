"""Global finance macro layer — the "돈과 관련된 모든 것" big-data feed.

This is the market-wide ("전체 영향") context, widened from Korea to the whole
world: it sweeps finance/money news across regions (한국·미국·유럽·중국·일본) and
topics (금리·환율·유가·채권·증시·무역·경기·암호화폐·은행·지정학) from Google News,
tags each headline with its region, and buckets everything into macro drivers with
a rough up/down lean. The classifier is bilingual (Korean + English) so domestic
and global headlines fall into the same drivers. Cached 30 min.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from app.data.news import news

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 1800.0  # 30 min

# (query, hl, gl, ceid, region). English (en-US) feeds give global coverage that
# the bilingual classifier can read; Korea uses Korean feeds.
_QUERIES: tuple[tuple[str, str, str, str, str], ...] = (
    # 한국
    ("코스피 코스닥 증시", "ko", "KR", "KR:ko", "한국"),
    ("원달러 환율 외환", "ko", "KR", "KR:ko", "한국"),
    ("한국은행 기준금리 통화정책", "ko", "KR", "KR:ko", "한국"),
    ("외국인 수급 코스피", "ko", "KR", "KR:ko", "한국"),
    ("한국 경제 물가 수출", "ko", "KR", "KR:ko", "한국"),
    # 미국
    ("Federal Reserve interest rate FOMC", "en-US", "US", "US:en", "미국"),
    ("Wall Street stocks Nasdaq Dow S&P 500", "en-US", "US", "US:en", "미국"),
    ("US inflation CPI economy", "en-US", "US", "US:en", "미국"),
    ("US Treasury bond yields", "en-US", "US", "US:en", "미국"),
    # 유럽
    ("European Central Bank ECB rates", "en-US", "US", "US:en", "유럽"),
    ("European stocks Euro Stoxx FTSE DAX", "en-US", "US", "US:en", "유럽"),
    ("Europe economy inflation", "en-US", "US", "US:en", "유럽"),
    # 중국
    ("China economy PBOC yuan", "en-US", "US", "US:en", "중국"),
    ("China stocks Shanghai Hang Seng", "en-US", "US", "US:en", "중국"),
    # 일본
    ("Bank of Japan yen monetary policy", "en-US", "US", "US:en", "일본"),
    ("Japan Nikkei stocks", "en-US", "US", "US:en", "일본"),
    # 글로벌 · 원자재 · 자금
    ("global stock markets", "en-US", "US", "US:en", "글로벌"),
    ("crude oil price OPEC", "en-US", "US", "US:en", "글로벌"),
    ("gold price commodities", "en-US", "US", "US:en", "글로벌"),
    ("US dollar forex currency", "en-US", "US", "US:en", "글로벌"),
    ("global recession economy outlook", "en-US", "US", "US:en", "글로벌"),
    ("IMF world economy growth", "en-US", "US", "US:en", "글로벌"),
    ("global bond yields debt", "en-US", "US", "US:en", "글로벌"),
    ("bitcoin cryptocurrency market", "en-US", "US", "US:en", "글로벌"),
    ("global trade tariffs", "en-US", "US", "US:en", "글로벌"),
    ("emerging markets stocks currency", "en-US", "US", "US:en", "글로벌"),
    ("bank banking credit liquidity", "en-US", "US", "US:en", "글로벌"),
)

# (label, keywords) — bilingual; a headline may hit several drivers.
_MACRO_THEMES: list[tuple[str, tuple[str, ...]]] = [
    ("금리·통화정책", (
        "금리", "기준금리", "연준", "FOMC", "한국은행", "통화정책", "긴축", "인하", "동결",
        "Fed", "Federal Reserve", "ECB", "BOJ", "central bank", "interest rate", "rate cut",
        "rate hike", "monetary", "tightening", "hawkish", "dovish",
    )),
    ("물가·인플레이션", (
        "물가", "인플레", "소비자물가", "디플레",
        "inflation", "CPI", "consumer price", "deflation", "price index", "PPI",
    )),
    ("환율·외환", (
        "환율", "원달러", "달러", "원화", "엔화", "위안", "유로", "외환",
        "currency", "forex", "dollar", "euro", "yen", "yuan", "exchange rate", "FX", "peso",
    )),
    ("국제유가·원자재", (
        "유가", "국제유가", "WTI", "브렌트", "두바이유", "OPEC", "금값", "구리", "원자재",
        "oil", "crude", "Brent", "OPEC", "gold", "copper", "commodity", "commodities", "natural gas",
    )),
    ("채권·금리시장", (
        "국채", "채권", "수익률", "장단기",
        "bond", "treasury", "yield", "yields", "sovereign", "debt",
    )),
    ("글로벌 증시", (
        "코스피", "코스닥", "나스닥", "다우", "뉴욕증시", "유럽증시", "상하이", "항셍", "닛케이",
        "stocks", "equities", "Nasdaq", "Dow", "S&P", "FTSE", "DAX", "Nikkei", "Hang Seng",
        "Shanghai", "rally", "selloff", "sell-off", "shares", "index",
    )),
    ("무역·관세", (
        "관세", "무역", "통상", "미중", "수출규제", "트럼프",
        "tariff", "trade", "trade war", "sanction", "export", "customs",
    )),
    ("경기·고용", (
        "경기", "침체", "성장률", "GDP", "고용", "실업",
        "economy", "recession", "growth", "GDP", "jobs", "unemployment", "payrolls", "labor",
    )),
    ("암호화폐", (
        "비트코인", "암호화폐", "가상자산", "이더리움",
        "bitcoin", "crypto", "cryptocurrency", "ethereum", "BTC", "stablecoin",
    )),
    ("은행·신용", (
        "은행", "신용", "유동성", "부도", "디폴트",
        "bank", "banking", "credit", "liquidity", "default", "lending",
    )),
    ("지정학 리스크", (
        "전쟁", "북한", "중동", "지정학", "이스라엘", "러시아", "이란", "우크라이나",
        "war", "geopolitical", "conflict", "sanctions", "Israel", "Russia", "Iran", "Ukraine",
    )),
    ("반도체·기술", (
        "반도체", "HBM", "엔비디아", "메모리",
        "semiconductor", "chip", "Nvidia", "AI chip", "memory",
    )),
]

_POS_HINT = (
    "강세", "급등", "상승", "완화", "기대", "호조", "반등", "랠리", "사상 최고", "신고가", "인하", "회복",
    "rally", "surge", "gain", "gains", "rise", "rises", "rebound", "record high", "optimism",
    "ease", "eases", "recovery", "jump", "jumps", "soar", "climb", "boost", "higher",
)
_NEG_HINT = (
    "약세", "급락", "하락", "긴축", "우려", "부진", "쇼크", "충격", "패닉", "경계", "리스크", "위축", "둔화",
    "fall", "falls", "drop", "drops", "plunge", "slump", "fear", "fears", "concern", "concerns",
    "selloff", "sell-off", "crash", "recession", "tighten", "worry", "slowdown", "sink", "tumble", "lower", "weak",
)


def _lean(text: str) -> str:
    p = sum(1 for w in _POS_HINT if w in text)
    n = sum(1 for w in _NEG_HINT if w in text)
    if p > n:
        return "긍정"
    if n > p:
        return "부정"
    return "중립"


def _classify(pool: list[dict]) -> list[dict]:
    drivers: list[dict] = []
    for label, kws in _MACRO_THEMES:
        hits = [a for a in pool if any(k in a["title"] for k in kws)]
        if not hits:
            continue
        pos = sum(1 for a in hits if _lean(a["title"]) == "긍정")
        neg = sum(1 for a in hits if _lean(a["title"]) == "부정")
        direction = "긍정" if pos > neg else "부정" if neg > pos else "중립"
        regions: dict[str, int] = {}
        for a in hits:
            regions[a["region"]] = regions.get(a["region"], 0) + 1
        # 대표 내용: aggregate the related-coverage clusters of the top headlines —
        # the gist of what's reported across outlets, deduped, not just one title.
        digest: list[str] = []
        seen_d: set[str] = set()
        for a in hits[:6]:
            for line in a.get("cluster", []):
                key = line.strip()
                if key and key not in seen_d:
                    seen_d.add(key)
                    digest.append(line)
                if len(digest) >= 6:
                    break
            if len(digest) >= 6:
                break
        drivers.append(
            {
                "theme": label,
                "direction": direction,
                "count": len(hits),
                "regions": regions,
                "headlines": [
                    {"title": a["title"], "link": a["link"], "source": a["source"], "region": a["region"]}
                    for a in hits[:4]
                ],
                "digest": digest,
            }
        )
    drivers.sort(key=lambda d: d["count"], reverse=True)
    return drivers


def _fetch_one(q: tuple[str, str, str, str, str]) -> list[dict]:
    query, hl, gl, ceid, region = q
    try:
        arts = news._fetch(query, hl, gl, ceid, 10)
    except Exception:
        return []
    for a in arts:
        a["region"] = region
    return arts


def market_macro() -> dict:
    """Return the global finance macro feed (drivers + region breakdown + news)."""
    with _lock:
        if _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]

    # Parallel sweep across every region/topic query.
    pool: list[dict] = []
    seen: set[str] = set()
    with ThreadPoolExecutor(max_workers=10) as ex:
        for arts in ex.map(_fetch_one, _QUERIES):
            for a in arts:
                t = a.get("title", "")
                if t and t not in seen:
                    seen.add(t)
                    pool.append(a)
    pool.sort(key=lambda a: a.get("ts") or 0, reverse=True)

    drivers = _classify(pool)

    # Region breakdown (글로벌 금융 뉴스 — 지역별).
    region_order = ["한국", "미국", "유럽", "중국", "일본", "글로벌"]
    by_region: list[dict] = []
    for reg in region_order:
        items = [a for a in pool if a["region"] == reg][:6]
        if items:
            by_region.append(
                {
                    "region": reg,
                    "count": sum(1 for a in pool if a["region"] == reg),
                    "news": [{"title": a["title"], "link": a["link"], "source": a["source"]} for a in items],
                }
            )

    domestic = [a for a in pool if a["region"] == "한국"]
    glob = [a for a in pool if a["region"] != "한국"]

    parts: list[str] = []
    if drivers:
        top = [d for d in drivers[:4] if d["direction"] != "중립"][:3] or drivers[:3]
        worded = ", ".join(f"{d['theme']}({d['direction']})" for d in top)
        parts.append(f"전 세계 금융 뉴스 {len(pool)}건 취합 — 주요 매크로 이슈: {worded}.")

    data = {
        "drivers": drivers,
        "news": domestic[:10],
        "global_news": glob[:12],
        "by_region": by_region,
        "pool_size": len(pool),
        "summary": " ".join(parts),
    }
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = data
    return data
