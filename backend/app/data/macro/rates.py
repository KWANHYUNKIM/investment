"""금리 결정 일정 + 인상/인하 시기 전망 (rate-decision calendar & outlook).

"언제 금리를 발표하는지" — 미 연준(FOMC)과 한국은행 금융통화위원회의 공식 2026
통화정책 결정일을 담아 *다음 발표일*과 D-day를 계산한다. 여기에 '금리 인상 시기'
를 다루는 뉴스(국문+영문)를 취합해 시장이 보는 향후 금리 방향을 함께 보여준다.

결정일 출처(미리 공표되는 일정):
  - FOMC: federalreserve.gov 2026 calendar (결정·기자회견은 회의 둘째 날)
  - 한국은행: 2026년 금통위 통화정책방향 결정회의 일정 (bok.or.kr)
"""
from __future__ import annotations

import datetime
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from app.data.news import news

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 3600.0  # 1h (schedule is static; outlook news refreshes hourly)

# 공식 결정일(발표일). FOMC는 회의 2일차 = 성명 발표일.
_FOMC_2026 = ["2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
              "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09"]
# 한국은행 금통위 통화정책방향 결정회의 2026.
_BOK_2026 = ["2026-01-15", "2026-02-26", "2026-04-10", "2026-05-28",
             "2026-07-16", "2026-08-27", "2026-10-22", "2026-11-26"]

_BANKS = (
    {"key": "fomc", "name": "미국 연준 (FOMC)", "flag": "🇺🇸", "dates": _FOMC_2026},
    {"key": "bok", "name": "한국은행 금통위", "flag": "🇰🇷", "dates": _BOK_2026},
)

# 금리 '시기'를 읽기 위한 뉴스 질의 (언제 올리/내릴지에 대한 전망).
_OUTLOOK_QUERIES = (
    ("기준금리 인상 인하 시기 전망", "ko", "KR", "KR:ko"),
    ("한국은행 금통위 기준금리 전망", "ko", "KR", "KR:ko"),
    ("Fed interest rate cut hike timing 2026 outlook", "en-US", "US", "US:en"),
    ("FOMC rate decision expectations next meeting", "en-US", "US", "US:en"),
)


def _today() -> datetime.date:
    return datetime.date.today()


def _next(dates: list[str], today: str) -> str | None:
    fut = [d for d in dates if d >= today]
    return fut[0] if fut else None


def _prev(dates: list[str], today: str) -> str | None:
    past = [d for d in dates if d < today]
    return past[-1] if past else None


def _dday(d: str, today: datetime.date) -> int:
    return (datetime.date.fromisoformat(d) - today).days


def _fmt(d: str) -> str:
    y, m, dd = d.split("-")
    return f"{int(m)}/{int(dd)}"


def rate_calendar() -> dict:
    """다음 금리 발표일 + D-day + 금리 시기 전망 뉴스 (cached ~1h)."""
    with _lock:
        if _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]

    today = _today()
    tstr = today.isoformat()
    schedule: list[dict] = []
    for b in _BANKS:
        nxt = _next(b["dates"], tstr)
        prv = _prev(b["dates"], tstr)
        schedule.append(
            {
                "key": b["key"],
                "name": b["name"],
                "flag": b["flag"],
                "next_date": nxt,
                "next_label": _fmt(nxt) if nxt else None,
                "d_day": _dday(nxt, today) if nxt else None,
                "prev_date": prv,
                "remaining_2026": sum(1 for d in b["dates"] if d >= tstr),
            }
        )

    # 금리 '시기' 전망 뉴스 취합 → 대표 내용 digest. 쿼리들은 서로 독립적인
    # 네트워크 호출이라 병렬로 가져온다(순차 4×12s → 최대 1×12s).
    def _safe(args) -> list[dict]:
        q, hl, gl, ceid = args
        try:
            return news._fetch(q, hl, gl, ceid, 8)
        except Exception:
            return []

    pool: list[dict] = []
    seen: set[str] = set()
    with ThreadPoolExecutor(max_workers=len(_OUTLOOK_QUERIES)) as ex:
        for arts in ex.map(_safe, _OUTLOOK_QUERIES):
            for a in arts:
                t = a.get("title", "")
                if t and t not in seen:
                    seen.add(t)
                    pool.append(a)
    pool.sort(key=lambda a: a.get("ts") or 0, reverse=True)

    outlook = [
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

    bits = []
    for s in schedule:
        if s["next_label"]:
            bits.append(f"{s['flag']} {s['name'].split(' ')[0]} {s['next_label']}(D-{s['d_day']})")
    summary = "다음 금리 발표 — " + ", ".join(bits) + "." if bits else ""

    data = {"schedule": schedule, "outlook": outlook, "digest": digest, "summary": summary}
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = data
    return data
