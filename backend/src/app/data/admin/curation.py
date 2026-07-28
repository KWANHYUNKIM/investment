"""콘텐츠 큐레이션 — 관리자가 메인에 노출할 추천을 저장/조회.

관리자가 고른 추천 종목·문구·링크를 JSON 으로 저장한다. 일반 사용자 화면은 이 값을
읽어 '오늘의 추천'으로 노출할 수 있다(프론트 연동은 단계적으로).
"""
from __future__ import annotations

import json
import os
import threading
import time

from app.core.config import get_settings

_lock = threading.Lock()
_DEFAULT = {"headline": "", "picks": [], "note": "", "updated_at": None}


def _path() -> str:
    return str(get_settings().data_dir / "curation.json")


def get() -> dict:
    p = _path()
    if not os.path.exists(p):
        return dict(_DEFAULT)
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        for k, v in _DEFAULT.items():
            d.setdefault(k, v)
        return d
    except Exception:
        return dict(_DEFAULT)


def set_(headline: str, picks: list, note: str) -> dict:
    d = {
        "headline": (headline or "").strip(),
        "picks": picks or [],
        "note": (note or "").strip(),
        "updated_at": time.strftime("%Y-%m-%d %H:%M"),
    }
    with _lock:
        p = _path()
        tmp = f"{p}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False)
        os.replace(tmp, p)
    return d
