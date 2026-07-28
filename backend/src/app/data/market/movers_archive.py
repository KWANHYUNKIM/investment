"""급등락 원인 스냅샷 이력 (rolling JSON).

스케줄러가 주기적으로 남기는 급등락+원인 요약을 시간순으로 축적해, '언제 무엇이 왜
올랐다/내렸다'를 되돌아볼 수 있게 한다. 단일 파일(movers/history.json)에 최근 N개 보관.
"""
from __future__ import annotations

import json
import os
import threading

from app.core.config import get_settings

_lock = threading.Lock()
_MAX = 800


def _path() -> str:
    d = get_settings().movers_dir
    os.makedirs(d, exist_ok=True)
    return str(d / "history.json")


def _load() -> list:
    p = _path()
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return []
    return []


def _compact(snap: dict) -> dict:
    def top(items):
        return [{"name": x["name"], "change_pct": x["change_pct"]} for x in (items or [])[:3]]
    ai = snap.get("ai") or {}
    return {
        "generated_at": snap.get("generated_at"),
        "breadth": snap.get("breadth"),
        "gainers": top(snap.get("gainers")),
        "losers": top(snap.get("losers")),
        "sector_up": (snap.get("sectors_up") or [{}])[0].get("sector") if snap.get("sectors_up") else None,
        "sector_down": (snap.get("sectors_down") or [{}])[0].get("sector") if snap.get("sectors_down") else None,
        "overall": ai.get("overall"),
        "losers_cause": ai.get("losers_cause"),
        "gainers_cause": ai.get("gainers_cause"),
    }


def record(snap: dict) -> None:
    if not snap or snap.get("count", 0) <= 0:
        return
    entry = _compact(snap)
    with _lock:
        hist = _load()
        if hist and hist[-1].get("generated_at") == entry.get("generated_at"):
            return
        hist.append(entry)
        hist = hist[-_MAX:]
        p = _path()
        tmp = f"{p}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(hist, fh, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, p)


def recent(limit: int = 50) -> list:
    with _lock:
        return list(reversed(_load()[-limit:]))
