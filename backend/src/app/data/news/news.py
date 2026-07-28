"""Per-stock news via Google News RSS.

Google News RSS needs no API key and covers both Korean (hl=ko, gl=KR) and
global/English (hl=en, gl=US) coverage for any query. We query by company name
and split the result into domestic vs global, newest first.

Naver Finance news is blocked/login-walled in this environment, so Google News
is the single source.
"""
from __future__ import annotations

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from urllib.parse import quote
from xml.etree import ElementTree as ET

import requests

# Google News bundles each story's <description> as an HTML list of related
# coverage (<a>headline</a> from multiple outlets). Pulling those out gives the
# "대표 내용" — what's being reported across sources, not just one headline.
_A_RE = re.compile(r"<a[^>]*>(.*?)</a>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def _cluster(description: str | None, headline: str) -> list[str]:
    if not description:
        return []
    out: list[str] = []
    seen = {headline.strip()}
    for raw in _A_RE.findall(description):
        t = _TAG_RE.sub("", raw).strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
        if len(out) >= 6:
            break
    return out

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_lock = threading.Lock()
_cache: dict[str, tuple[float, list[dict]]] = {}
TTL = 300.0  # 5 min

# English names for the most-searched names → better global coverage.
EN_NAMES: dict[str, str] = {
    "삼성전자": "Samsung Electronics",
    "SK하이닉스": "SK Hynix",
    "LG에너지솔루션": "LG Energy Solution",
    "삼성바이오로직스": "Samsung Biologics",
    "현대차": "Hyundai Motor",
    "기아": "Kia",
    "NAVER": "Naver",
    "카카오": "Kakao",
    "LG화학": "LG Chem",
    "POSCO홀딩스": "POSCO Holdings",
    "삼성SDI": "Samsung SDI",
    "현대모비스": "Hyundai Mobis",
    "셀트리온": "Celltrion",
    "LG전자": "LG Electronics",
    "SK이노베이션": "SK Innovation",
    "한국전력": "KEPCO",
    "SK텔레콤": "SK Telecom",
    "KB금융": "KB Financial",
    "신한지주": "Shinhan Financial",
    "하나금융지주": "Hana Financial",
    "한화에어로스페이스": "Hanwha Aerospace",
    "HD현대중공업": "HD Hyundai Heavy Industries",
    "두산에너빌리티": "Doosan Enerbility",
    "삼성물산": "Samsung C&T",
    "크래프톤": "Krafton",
    "에코프로비엠": "Ecopro BM",
    "포스코퓨처엠": "POSCO Future M",
    "HMM": "HMM",
    "코스피": "Korea KOSPI stock market",
    "코스닥": "Korea KOSDAQ stock market",
}


def _parse(xml: str, limit: int) -> list[dict]:
    out: list[dict] = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return out
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = it.findtext("pubDate")
        src_el = it.find("source")
        source = (src_el.text if src_el is not None else None) or ""
        if not source and " - " in title:
            title, source = title.rsplit(" - ", 1)
        ts = None
        if pub:
            try:
                ts = parsedate_to_datetime(pub).timestamp()
            except (TypeError, ValueError):
                ts = None
        cluster = _cluster(it.findtext("description"), title)
        out.append({"title": title, "link": link, "source": source.strip(), "ts": ts, "cluster": cluster})
        if len(out) >= limit:
            break
    out.sort(key=lambda x: x["ts"] or 0, reverse=True)
    for i, a in enumerate(out):
        a["important"] = i < 3  # most-recent few flagged
    return out


def _fetch(query: str, hl: str, gl: str, ceid: str, limit: int) -> list[dict]:
    url = (
        f"https://news.google.com/rss/search?q={quote(query)}"
        f"&hl={hl}&gl={gl}&ceid={ceid}"
    )
    r = requests.get(url, headers=_UA, timeout=12)
    r.raise_for_status()
    return _parse(r.text, limit)


def news_for(name: str, limit: int = 15) -> dict:
    """Return {'domestic': [...], 'global': [...]} for a company name (cached)."""
    key = f"{name}|{limit}"
    with _lock:
        hit = _cache.get(key)
        if hit and (time.time() - hit[0] < TTL):
            return {"domestic": hit[1][0], "global": hit[1][1], "cached": True}  # type: ignore

    def _safe(*a) -> list[dict]:
        try:
            return _fetch(*a)
        except Exception:
            return []

    # Mapped majors use their real English name; unmapped names are anchored
    # with "Korea" so a Korean company name in an English feed doesn't match
    # unrelated foreign stories (e.g. 핌스→"Imran Khan/PIMS").
    en = EN_NAMES.get(name)
    glob_query = en if en else f"{name} Korea"
    # Domestic + global are independent network calls — run them concurrently so
    # a slow feed doesn't serialize behind the other (was ~2×12s worst case).
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_dom = ex.submit(_safe, name, "ko", "KR", "KR:ko", limit)
        f_glob = ex.submit(_safe, glob_query, "en-US", "US", "US:en", limit)
        domestic = f_dom.result()
        glob = f_glob.result()

    with _lock:
        _cache[key] = (time.time(), [domestic, glob])  # type: ignore
    return {"domestic": domestic, "global": glob, "cached": False}
