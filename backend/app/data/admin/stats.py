"""방문자 통계 — 탭/화면 조회수 집계 (경량, JSON 파일).

프론트가 화면을 열 때 POST /api/track 로 view 를 보내면 여기서 (전체·오늘·화면별)
카운트를 누적한다. 외부 애널리틱스 없이 '무엇을 많이 보는지'만 가볍게 파악하는 용도.
"""
from __future__ import annotations

import json
import os
import threading
import time

from app.core.config import get_settings

_lock = threading.Lock()


def _path() -> str:
    return str(get_settings().data_dir / "page_views.json")


def _load() -> dict:
    p = _path()
    if not os.path.exists(p):
        return {"total": 0, "by_view": {}, "by_day": {}, "by_view_day": {}}
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        return {"total": 0, "by_view": {}, "by_day": {}, "by_view_day": {}}
    d.setdefault("total", 0)
    d.setdefault("by_view", {})
    d.setdefault("by_day", {})
    d.setdefault("by_view_day", {})
    return d


def _save(d: dict) -> None:
    p = _path()
    tmp = f"{p}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False)
    os.replace(tmp, p)


def track(view: str, user: str | None = None) -> None:
    view = (view or "unknown").strip()[:40]
    day = time.strftime("%Y-%m-%d")
    with _lock:
        d = _load()
        d["total"] += 1
        d["by_view"][view] = d["by_view"].get(view, 0) + 1
        d["by_day"][day] = d["by_day"].get(day, 0) + 1
        vd = d["by_view_day"].setdefault(view, {})
        vd[day] = vd.get(day, 0) + 1
        # by_day 는 최근 60일만 유지
        if len(d["by_day"]) > 90:
            for k in sorted(d["by_day"])[:-60]:
                d["by_day"].pop(k, None)
        _save(d)


def summary() -> dict:
    d = _load()
    by_view = sorted(d["by_view"].items(), key=lambda kv: -kv[1])
    days = sorted(d["by_day"].items())[-30:]
    today = time.strftime("%Y-%m-%d")
    return {
        "total": d["total"],
        "today": d["by_day"].get(today, 0),
        "top_views": [{"view": k, "count": v} for k, v in by_view[:20]],
        "daily": [{"date": k, "count": v} for k, v in days],
    }
