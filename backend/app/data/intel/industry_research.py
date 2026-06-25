"""Per-industry research feed — what each competitor cluster is *doing*.

For an industry group (see ``industry``), we crawl the recent news of its biggest
companies and bucket every headline into the dimensions the user asked for:

    기술개발 · 합병·인수(M&A) · 계약·수주 · 실적·성과 · 전략·방향 · 규제·리스크

so one screen tells you where a whole competitive cluster is heading — who is
developing what technology, who is merging, who signed what contract. Results are
cached per industry and snapshotted to ``data/industry_reports/{date}.json`` so
the picture accumulates over time (the "계속해서 넣어주는" feed). No LLM; rule-based
keyword classification, framed as 관련 뉴스.
"""
from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core.config import get_settings
from app.data.intel import industry
from app.data.news import news

_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}
TTL = 6 * 3600.0  # research changes slowly; refresh every 6h

# (theme key, label, keywords). A headline can land in several buckets.
_THEMES: list[tuple[str, str, tuple[str, ...]]] = [
    ("tech", "기술개발", (
        "기술", "개발", "신제품", "특허", "양산", "공정", "신기술", "R&D", "연구", "혁신",
        "AI", "인공지능", "반도체", "배터리", "전고체", "HBM", "차세대", "국산화", "상용화",
    )),
    ("ma", "합병·인수", (
        "인수", "합병", "M&A", "지분 인수", "지분인수", "매각", "분할", "출자", "자회사", "경영권",
    )),
    ("deal", "계약·수주", (
        "수주", "계약", "공급계약", "납품", "MOU", "협약", "파트너십", "수출", "공급", "양해각서",
    )),
    ("perf", "실적·성과", (
        "실적", "영업이익", "매출", "흑자", "적자", "어닝", "순이익", "사상 최대", "성장", "수익",
    )),
    ("strategy", "전략·방향", (
        "투자", "증설", "진출", "확장", "전략", "비전", "신사업", "글로벌", "공장", "설립", "전환",
    )),
    ("risk", "규제·리스크", (
        "규제", "소송", "제재", "리콜", "조사", "과징금", "벌금", "압수수색", "논란", "리스크",
    )),
]
_THEME_LABEL = {k: lbl for k, lbl, _ in _THEMES}


def classify(title: str) -> list[str]:
    return [k for k, _, kws in _THEMES if any(kw in title for kw in kws)]


def _company_news(member: dict) -> list[dict]:
    """All recent (domestic+global) headlines for one company, tagged."""
    name = member.get("name")
    if not name:
        return []
    try:
        nw = news.news_for(name, limit=8)
    except Exception:
        return []
    arts = (nw.get("domestic") or [])[:6] + (nw.get("global") or [])[:3]
    out: list[dict] = []
    for a in arts:
        title = a.get("title") or ""
        themes = classify(title)
        if not themes:
            continue
        out.append(
            {
                "company": name,
                "ticker": member.get("ticker"),
                "title": title,
                "link": a.get("link"),
                "source": a.get("source"),
                "themes": themes,
            }
        )
    return out


def research_industry(name: str, top_k: int | None = None) -> dict | None:
    """Crawl + classify news for the industry's biggest companies."""
    with _lock:
        hit = _cache.get(name)
        if hit and (time.time() - hit[0] < TTL):
            return hit[1]

    g = industry.get_industry(name)
    if not g:
        return None
    top_k = top_k or get_settings().industry_top_k
    targets = g["members"][:top_k]

    tagged: list[dict] = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(_company_news, m) for m in targets]
        for fut in as_completed(futs):
            try:
                tagged.extend(fut.result())
            except Exception:
                pass

    buckets: dict[str, list[dict]] = {k: [] for k, _, _ in _THEMES}
    for item in tagged:
        for k in item["themes"]:
            if len(buckets[k]) < 15:
                buckets[k].append(item)

    themes_out = [
        {"key": k, "label": _THEME_LABEL[k], "count": len(buckets[k]), "items": buckets[k]}
        for k, _, _ in _THEMES
    ]
    ranked = sorted([t for t in themes_out if t["count"]], key=lambda t: t["count"], reverse=True)

    competitors = [
        {"ticker": m["ticker"], "name": m["name"], "market_cap": m["market_cap"], "products": m["products"]}
        for m in g["members"][:12]
    ]

    parts = [f"'{name}' 업종은 {g['count']}개사가 경쟁하며 대표 기업은 {g['leader']}입니다."]
    if ranked:
        head = " · ".join(f"{t['label']}({t['count']})" for t in ranked[:3])
        parts.append(f"최근 뉴스 기준 두드러진 이슈: {head}.")
    else:
        parts.append("최근 분류된 주요 뉴스 이슈는 확인되지 않았습니다.")

    data = {
        "industry": name,
        "leader": g["leader"],
        "count": g["count"],
        "market_cap": g["market_cap"],
        "analyzed": [m["name"] for m in targets],
        "competitors": competitors,
        "themes": themes_out,
        "summary": " ".join(parts),
    }
    with _lock:
        _cache[name] = (time.time(), data)
    return data


# --------------------------------------------------------------------------- #
# Daily snapshot (accumulating JSON, like the daily report archive)
# --------------------------------------------------------------------------- #
def _dir():
    d = get_settings().data_dir / "industry_reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(date: str) -> str:
    return str(_dir() / f"{date}.json")


def snapshot(top_industries: int | None = None, force: bool = False) -> dict:
    """Research the top industries and persist them as one dated JSON file."""
    settings = get_settings()
    top_n = top_industries or settings.industry_snapshot_n
    date = store_max_date()
    if not force and os.path.exists(_path(date)):
        return {"status": "exists", "date": date}

    names = [g["industry"] for g in industry.industries()[:top_n]]
    reports: list[dict] = []
    for nm in names:
        r = research_industry(nm)
        if r:
            reports.append(r)

    data = {
        "date": date,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "industry_count": len(reports),
        "industries": reports,
    }
    tmp = _path(date) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, _path(date))
    return {"status": "saved", "date": date, "industries": len(reports)}


def store_max_date() -> str:
    from app.data.infra import store

    return store.max_price_date() or time.strftime("%Y-%m-%d")


def list_dates() -> list[str]:
    d = _dir()
    return sorted((p.stem for p in d.glob("*.json")), reverse=True)


def load_snapshot(date: str) -> dict | None:
    p = _path(date)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)
