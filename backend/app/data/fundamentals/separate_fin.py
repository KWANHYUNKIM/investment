"""별도재무제표(OFS) 영업이익·순이익·매출 수집 — 연결(CFS) 대비 괴리 탐지용.

dart_financials 테이블은 (ticker, sj_div, year, account_nm) PK라 같은 해 연결/별도를 동시에
담지 못한다. 내부거래 이전가격으로 '별도재무제표상 이익'을 부풀리는 착시(연결은 손실인데
별도는 흑자)를 잡으려면 별도(OFS)를 따로 받아야 한다. 최근 몇 개 사업연도만 수집해 JSON 캐시.
"""
from __future__ import annotations

import json

import requests

from app.core.config import get_settings
from app.data.fundamentals.dart import _float, _load_corp_map, enabled

_BASE = "https://opendart.fss.or.kr/api"
_SALES = ("매출액", "수익(매출액)", "영업수익", "매출")


def _path():
    return get_settings().data_dir / "separate_fin.json"


def load() -> dict:
    p = _path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("map", {})
    except Exception:
        return {}


def _latest_fy() -> int:
    import time
    y, m = int(time.strftime("%Y")), int(time.strftime("%m"))
    return y - 1 if m >= 4 else y - 2


def fetch_ofs(corp: str, years: list[int]) -> dict:
    """{year: {op, ni, rev}} — 별도(OFS) 손익. 값 없으면 생략."""
    out: dict[str, dict] = {}
    key = get_settings().dart_api_key
    for yr in years:
        try:
            r = requests.get(f"{_BASE}/fnlttSinglAcntAll.json", params={
                "crtfc_key": key, "corp_code": corp, "bsns_year": str(yr),
                "reprt_code": "11011", "fs_div": "OFS"}, timeout=30)
            items = r.json().get("list") or []
        except Exception:
            continue
        if not items:
            continue
        acc: dict[str, float] = {}
        for it in items:
            if it.get("sj_div") not in ("IS", "CIS"):
                continue
            nm = (it.get("account_nm") or "").strip()
            amt = _float(it.get("thstrm_amount"))
            if amt is not None and nm not in acc:
                acc[nm] = amt
        op = acc.get("영업이익", acc.get("영업이익(손실)"))
        ni = acc.get("당기순이익", acc.get("당기순이익(손실)"))
        rev = next((acc[k] for k in _SALES if k in acc), None)
        if op is None and ni is None and rev is None:
            continue
        out[str(yr)] = {"op": op, "ni": ni, "rev": rev}
    return out


def refresh(tickers: list[str], back: int = 3) -> dict:
    """주어진 종목의 별도(OFS) 손익 최근 back개 연도 수집 → JSON 캐시."""
    if not enabled():
        return {}
    import time
    cmap = _load_corp_map()
    fy = _latest_fy()
    years = [fy - i for i in range(back)]
    out: dict[str, dict] = {}
    for i, tk in enumerate(tickers, 1):
        corp = cmap.get(tk)
        if not corp:
            continue
        d = fetch_ofs(corp, years)
        if d:
            out[tk] = d
    _path().write_text(json.dumps(
        {"generated_at": time.strftime("%Y-%m-%d %H:%M"), "map": out},
        ensure_ascii=False), encoding="utf-8")
    return out
