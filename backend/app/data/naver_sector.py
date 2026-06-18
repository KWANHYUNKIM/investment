"""WICS 업종 분류 (네이버 금융) — the grouping axis real 주식사이트 actually use.

KRX-DESC's ``Industry`` is KSIC (사업자등록 표준산업분류): an administrative
classification that buckets 22% of names into "기타" and files holding companies
under 금융/기타 regardless of what they actually do. 네이버·다음·증권사 리포트 all
group by **WICS** (FnGuide) instead — built from each company's revenue mix, so
peers land together (e.g. SK하이닉스 → 반도체와반도체장비).

WICS is a paid feed, but 네이버 금융 publishes the exact same 79-업종 grouping at
``/sise/sise_group.naver?type=upjong`` with the member list per 업종. We scrape
that once and map ticker → WICS 업종, caching it so the per-day scheduler refresh
is the only thing that pays the ~80-request cost.
"""
from __future__ import annotations

import re
import threading
import time

import httpx

_BASE = "https://finance.naver.com/sise"
_LIST = f"{_BASE}/sise_group.naver?type=upjong"
_DETAIL = f"{_BASE}/sise_group_detail.naver?type=upjong&no={{no}}"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

_GROUP_RE = re.compile(r"sise_group_detail\.naver\?type=upjong&no=(\d+)\">([^<]+)</a>")
_CODE_RE = re.compile(r"code=(\d{6})\">")

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "map": None}
TTL = 6 * 3600.0  # WICS membership barely moves intraday; refresh a few times a day.


def _groups(client: httpx.Client) -> list[tuple[str, str]]:
    """[(no, 업종명)] for the 79 WICS sectors."""
    r = client.get(_LIST, timeout=20)
    r.encoding = "euc-kr"
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for no, name in _GROUP_RE.findall(r.text):
        if no in seen:
            continue
        seen.add(no)
        out.append((no, name.strip()))
    return out


def _members(client: httpx.Client, no: str) -> list[str]:
    """Ticker codes belonging to one WICS 업종 (deduped, order preserved)."""
    r = client.get(_DETAIL.format(no=no), timeout=20)
    r.encoding = "euc-kr"
    out: list[str] = []
    seen: set[str] = set()
    for code in _CODE_RE.findall(r.text):
        if code not in seen:
            seen.add(code)
            out.append(code)
    return out


def _build() -> dict[str, str]:
    """Scrape the full WICS grouping → {ticker: 업종명}. Best-effort per group."""
    mapping: dict[str, str] = {}
    with httpx.Client(headers=_HEADERS) as client:
        groups = _groups(client)
        for no, name in groups:
            try:
                for code in _members(client, no):
                    # First sector wins; Naver rarely lists a name in two 업종.
                    mapping.setdefault(code, name)
            except Exception:
                continue
    return mapping


def sector_map(force: bool = False) -> dict[str, str]:
    """ticker → WICS 업종명, cached for ``TTL``. Returns {} if the scrape fails."""
    with _lock:
        if not force and _cache["map"] is not None and time.time() - _cache["ts"] < TTL:
            return _cache["map"]
    try:
        mapping = _build()
    except Exception:
        mapping = {}
    if mapping:  # never overwrite a good cache with an empty failed scrape
        with _lock:
            _cache["ts"] = time.time()
            _cache["map"] = mapping
        return mapping
    with _lock:
        return _cache["map"] or {}
