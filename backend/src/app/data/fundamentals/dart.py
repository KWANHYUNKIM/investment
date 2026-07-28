"""DART (전자공시) — 5% major-holder names by ticker.

Daily trading is only disclosed by investor *type* (개인/외국인/기관). Actual
firm/person NAMES come from DART's 대량보유 상황보고 (5% rule). This module:
  1. downloads DART's corpCode.xml once (ticker → DART corp_code), cached to disk
  2. queries majorstock.json per corp_code for 5%+ holders (name, ratio, shares)

Needs a free API key (settings.dart_api_key / DART_API_KEY in .env).
"""
from __future__ import annotations

import io
import json
import threading
import time
import zipfile
from xml.etree import ElementTree as ET

import requests

from app.core.config import get_settings

_BASE = "https://opendart.fss.or.kr/api"
_lock = threading.Lock()
_corp_map: dict[str, str] | None = None
_holders_cache: dict[str, tuple[float, list[dict]]] = {}
TTL = 6 * 3600.0


def enabled() -> bool:
    return bool(get_settings().dart_api_key)


def _map_path():
    return get_settings().data_dir / "dart_corpmap.json"


def _load_corp_map() -> dict[str, str]:
    global _corp_map
    if _corp_map is not None:
        return _corp_map
    path = _map_path()
    if path.exists():
        try:
            _corp_map = json.loads(path.read_text(encoding="utf-8"))
            return _corp_map
        except Exception:
            pass
    # Download + parse corpCode.xml (a zip).
    key = get_settings().dart_api_key
    r = requests.get(f"{_BASE}/corpCode.xml", params={"crtfc_key": key}, timeout=60)
    r.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    xml = zf.read(zf.namelist()[0])
    root = ET.fromstring(xml)
    m: dict[str, str] = {}
    for el in root.iter("list"):
        stock = (el.findtext("stock_code") or "").strip()
        corp = (el.findtext("corp_code") or "").strip()
        if stock and corp:
            m[stock] = corp
    _corp_map = m
    try:
        path.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return m


def _int(s) -> int | None:
    try:
        return int(str(s).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _float(s) -> float | None:
    try:
        return float(str(s).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def major_holders(ticker: str) -> dict:
    """5%+ holders for a ticker: [{name, ratio, shares, date, report_tp}] (cached)."""
    if not enabled():
        return {"available": False, "reason": "DART_API_KEY 미설정", "holders": []}

    with _lock:
        hit = _holders_cache.get(ticker)
        if hit and (time.time() - hit[0] < TTL):
            return {"available": True, "holders": hit[1]}

    try:
        corp = _load_corp_map().get(ticker)
        if not corp:
            return {"available": True, "holders": [], "reason": "DART corp_code 없음(비상장/매핑 없음)"}
        r = requests.get(
            f"{_BASE}/majorstock.json",
            params={"crtfc_key": get_settings().dart_api_key, "corp_code": corp},
            timeout=20,
        )
        r.raise_for_status()
        j = r.json()
        if j.get("status") != "000":
            return {"available": True, "holders": [], "reason": j.get("message", j.get("status"))}

        # Keep the most recent report per holder, sort by current ratio desc.
        latest: dict[str, dict] = {}
        for it in j.get("list", []):
            name = (it.get("repror") or "").strip()
            if not name:
                continue
            row = {
                "name": name,
                "ratio": _float(it.get("stkrt")),
                "shares": _int(it.get("stkqy")),
                "date": it.get("rcept_dt"),
                "report_tp": it.get("report_tp"),
            }
            prev = latest.get(name)
            if prev is None or (row["date"] or "") >= (prev["date"] or ""):
                latest[name] = row
        holders = sorted(latest.values(), key=lambda x: x["ratio"] or 0, reverse=True)
    except Exception as e:
        return {"available": True, "holders": [], "reason": f"조회 오류: {e}"}

    with _lock:
        _holders_cache[ticker] = (time.time(), holders)
    return {"available": True, "holders": holders}
