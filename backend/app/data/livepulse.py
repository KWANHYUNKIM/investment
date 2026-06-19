"""실시간 시황 펄스 — 시황·전망·분석 글을 취합해 '지금 어떻게 흘러가는지' 보여준다.

데일리 리포트(하루 마감 스냅샷)와 달리, 이 피드는 **실시간**으로 시장이 어느 쪽으로
흐르는지를 시황/전망/전략/수급 류 기사(국내+해외)를 모아 읽어낸다:
  - pulse  : 전반 분위기(강세/약세/혼조) + 점수 + 한 줄 내러티브,
  - drivers: 무엇이 시장을 끌고 있나(테마별 방향), macro 분류기 재사용,
  - flow   : 가장 최근 분석/시황 헤드라인을 시간순으로(대표 내용 cluster 포함).

소스는 키 없는 Google News RSS(news._fetch). 짧은 TTL(60초)로 프론트가 폴링하면
실시간처럼 갱신된다. (커뮤니티/증권사 리포트는 이 환경에서 막혀 있어 뉴스 RSS 기반.)
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from app.data import macro, news

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 60.0  # 60초 — 실시간 폴링용

# (query, hl, gl, ceid, region) — 시황/전망/분석/전략/수급에 가중. 국내+해외.
_QUERIES: tuple[tuple[str, str, str, str, str], ...] = (
    # 국내 시황·분석·전략
    ("증시 시황 마감 분석", "ko", "KR", "KR:ko", "국내"),
    ("코스피 전망 증시 전략", "ko", "KR", "KR:ko", "국내"),
    ("코스닥 시황 분석", "ko", "KR", "KR:ko", "국내"),
    ("외국인 기관 수급 코스피", "ko", "KR", "KR:ko", "국내"),
    ("주식 시장 전망 투자 전략", "ko", "KR", "KR:ko", "국내"),
    ("증시 마감 특징주", "ko", "KR", "KR:ko", "국내"),
    ("환율 금리 증시 영향", "ko", "KR", "KR:ko", "국내"),
    # 해외 시황·분석
    ("stock market today analysis", "en-US", "US", "US:en", "해외"),
    ("market outlook stocks strategy", "en-US", "US", "US:en", "해외"),
    ("wall street today market wrap", "en-US", "US", "US:en", "해외"),
    ("global markets analysis", "en-US", "US", "US:en", "해외"),
    ("Nasdaq S&P 500 today", "en-US", "US", "US:en", "해외"),
)


def _fetch_one(q: tuple[str, str, str, str, str]) -> list[dict]:
    query, hl, gl, ceid, region = q
    try:
        arts = news._fetch(query, hl, gl, ceid, 12)
    except Exception:
        return []
    for a in arts:
        a["region"] = region
    return arts


def _rel_time(ts: float | None, now: float) -> str | None:
    """epoch → '방금'/'12분 전'/'3시간 전'/'2일 전'."""
    if not ts:
        return None
    diff = now - ts
    if diff < 0:
        diff = 0
    if diff < 60:
        return "방금"
    if diff < 3600:
        return f"{int(diff // 60)}분 전"
    if diff < 86400:
        return f"{int(diff // 3600)}시간 전"
    return f"{int(diff // 86400)}일 전"


def pulse(force: bool = False) -> dict:
    """실시간 시황 펄스 — 분위기 + 드라이버 + 시간순 흐름. cached 60s."""
    with _lock:
        if not force and _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]

    pool: list[dict] = []
    seen: set[str] = set()
    with ThreadPoolExecutor(max_workers=8) as ex:
        for arts in ex.map(_fetch_one, _QUERIES):
            for a in arts:
                t = a.get("title", "")
                if t and t not in seen:
                    seen.add(t)
                    pool.append(a)
    now = time.time()
    pool.sort(key=lambda a: a.get("ts") or 0, reverse=True)

    # 전반 분위기 — pos/neg 헤드라인 집계.
    pos = sum(1 for a in pool if macro._lean(a["title"]) == "긍정")
    neg = sum(1 for a in pool if macro._lean(a["title"]) == "부정")
    total = max(1, len(pool))
    score = round((pos - neg) / total * 100)
    if pos > neg * 1.25:
        verdict, tone = "강세 분위기", "긍정"
    elif neg > pos * 1.25:
        verdict, tone = "약세 분위기", "부정"
    else:
        verdict, tone = "혼조", "중립"

    # 무엇이 끌고 있나 — macro 테마 분류기 재사용(지역 라벨도 채워줌).
    drivers = macro._classify(pool)

    # 시간순 흐름 피드(가장 최근 헤드라인부터).
    flow: list[dict] = []
    for a in pool[:40]:
        flow.append(
            {
                "title": a["title"],
                "link": a["link"],
                "source": a["source"],
                "region": a.get("region"),
                "lean": macro._lean(a["title"]),
                "ts": a.get("ts"),
                "ago": _rel_time(a.get("ts"), now),
                "cluster": a.get("cluster", [])[:2],
            }
        )

    top_themes = [d for d in drivers[:5] if d["direction"] != "중립"][:3] or drivers[:3]
    worded = ", ".join(f"{d['theme']}({d['direction']})" for d in top_themes)
    narrative = (
        f"시황·분석 {len(pool)}건 실시간 취합 — 전반 {verdict}"
        f"(긍정 {pos} · 부정 {neg})."
        + (f" 시장을 끌고 있는 이슈: {worded}." if worded else "")
    )

    data = {
        "as_of": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
        "pulse": {
            "verdict": verdict,
            "tone": tone,
            "score": score,
            "pos": pos,
            "neg": neg,
            "neutral": total - pos - neg,
            "narrative": narrative,
        },
        "drivers": drivers,
        "flow": flow,
        "pool_size": len(pool),
    }
    with _lock:
        _cache["ts"] = now
        _cache["data"] = data
    return data
