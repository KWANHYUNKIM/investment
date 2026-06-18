"""외국인이 바라보는 한국 증시 (the foreign view of KR equities).

국내 뉴스가 아니라 *영문(외신)* 뉴스를 한국 증시·외국인 수급·원화·MSCI 한국 등
주제로 쓸어담아, 외국인·해외 매체가 우리 증시를 어떤 시각(긍정/부정)으로 보는지
한 단으로 요약한다. 헤드라인뿐 아니라 여러 매체의 관련 보도(대표 내용)도 취합한다.
Cached ~30분.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from app.data import macro, news

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 1800.0  # 30 min

# 외신이 한국 증시를 다루는 각도들 (전부 영문 피드).
_QUERIES = (
    ("South Korea KOSPI stock market foreign investors", "en-US", "US", "US:en"),
    ("Korea equities outlook foreign investment", "en-US", "US", "US:en"),
    ("MSCI Korea index foreign funds", "en-US", "US", "US:en"),
    ("South Korea won foreign capital flows", "en-US", "US", "US:en"),
    ("Korea stock market rally selloff foreigners", "en-US", "US", "US:en"),
    ("Korea discount corporate governance valuation", "en-US", "US", "US:en"),
)


def _fetch_one(q):
    query, hl, gl, ceid = q
    try:
        return news._fetch(query, hl, gl, ceid, 10)
    except Exception:
        return []


def foreign_view() -> dict:
    """외신이 보는 한국 증시: 시각(lean) + 요약 + 헤드라인 + 대표 내용."""
    with _lock:
        if _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]

    pool: list[dict] = []
    seen: set[str] = set()
    with ThreadPoolExecutor(max_workers=6) as ex:
        for arts in ex.map(_fetch_one, _QUERIES):
            for a in arts:
                t = a.get("title", "")
                if t and t not in seen:
                    seen.add(t)
                    pool.append(a)
    pool.sort(key=lambda a: a.get("ts") or 0, reverse=True)

    pos = sum(1 for a in pool if macro._lean(a["title"]) == "긍정")
    neg = sum(1 for a in pool if macro._lean(a["title"]) == "부정")
    lean = "긍정" if pos > neg else "부정" if neg > pos else "중립"

    headlines = [
        {"title": a["title"], "link": a["link"], "source": a["source"]}
        for a in pool[:8]
    ]
    digest: list[str] = []
    seen_d: set[str] = set()
    for a in pool[:8]:
        for line in a.get("cluster", []):
            if line and line not in seen_d:
                seen_d.add(line)
                digest.append(line)
            if len(digest) >= 6:
                break
        if len(digest) >= 6:
            break

    tone = {"긍정": "우호적", "부정": "신중·부정적", "중립": "중립적"}[lean]
    summary = (
        f"외신·해외 매체는 한국 증시를 대체로 {tone}({lean}) 시각으로 보고 있습니다 "
        f"— 관련 영문 보도 {len(pool)}건 취합 (긍정 {pos} · 부정 {neg})."
        if pool else ""
    )

    data = {
        "lean": lean,
        "pos": pos,
        "neg": neg,
        "pool_size": len(pool),
        "summary": summary,
        "headlines": headlines,
        "digest": digest,
    }
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = data
    return data
