"""회사 규모 프로필 — 인원수·인건비·매출·고정비(DART 구조화 API).

제품 원가분해(unit_economics)에 "회사 규모 & 숨만 쉬어도 나가는 고정비"를 붙이기
위한 데이터. OpenDART 구조화 API 사용(문서 파싱 불필요):
  - empSttus.json           → 직원수·연간급여총액 → 총 인건비·1인평균급여
  - fnlttSinglAcntAll.json   → 매출액·매출원가·영업이익(절대금액)

결과: {headcount, annual_labor, avg_salary, revenue, cogs, op, sga, year}. 원(KRW).
디스크 캐시(분기 갱신). 실패 항목은 None.
"""
from __future__ import annotations

import json
import time

import requests

from app.data.fundamentals.dart_cache import ReportCache
from app.core.config import get_settings
from app.data.fundamentals.dart import _load_corp_map, _float, enabled

_BASE = "https://opendart.fss.or.kr/api"
# version 은 파서를 고칠 때 올린다 — 예전엔 이 모듈에 버전 검사가 없어서
# 파서를 고쳐도 한 달간 옛 결과가 나왔다.
_CACHE = ReportCache("profile", version=1)



def _latest_fy() -> int:
    y, m = int(time.strftime("%Y")), int(time.strftime("%m"))
    return y - 1 if m >= 4 else y - 2


def _int(s) -> int:
    try:
        return int(str(s).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0


def _employees(corp: str, year: int) -> tuple[int, int]:
    """(총 직원수, 연간급여총액 합). 실패 시 (0,0)."""
    try:
        r = requests.get(f"{_BASE}/empSttus.json", params={
            "crtfc_key": get_settings().dart_api_key, "corp_code": corp,
            "bsns_year": str(year), "reprt_code": "11011"}, timeout=30)
        rows = r.json().get("list") or []
    except Exception:
        return 0, 0
    head = sum(_int(it.get("sm")) for it in rows)
    labor = sum(_int(it.get("fyer_salary_totamt")) for it in rows)
    return head, labor


_SALES = ("매출액", "수익(매출액)", "영업수익", "매출")


def _financials(corp: str, year: int) -> dict | None:
    """{revenue, cogs, op} 절대금액(원). CFS 우선."""
    for fs in ("CFS", "OFS"):
        try:
            r = requests.get(f"{_BASE}/fnlttSinglAcntAll.json", params={
                "crtfc_key": get_settings().dart_api_key, "corp_code": corp,
                "bsns_year": str(year), "reprt_code": "11011", "fs_div": fs}, timeout=30)
            items = r.json().get("list") or []
        except Exception:
            items = []
        if not items:
            continue
        acc = {}
        for it in items:
            if it.get("sj_div") not in ("IS", "CIS"):
                continue
            nm = (it.get("account_nm") or "").strip()
            amt = _float(it.get("thstrm_amount"))
            if amt is not None and nm not in acc:
                acc[nm] = amt
        rev = next((acc[k] for k in _SALES if k in acc), None)
        if rev:
            return {"revenue": rev, "cogs": acc.get("매출원가"),
                    "op": acc.get("영업이익", acc.get("영업이익(손실)"))}
    return None


def profile(ticker: str) -> dict:
    """회사 규모 프로필. 캐시. 실패해도 빈 dict 반환(항목 None)."""
    empty = {"headcount": None, "annual_labor": None, "avg_salary": None,
             "revenue": None, "cogs": None, "op": None, "sga": None, "year": None}
    if not enabled():
        return empty
    hit = _CACHE.get(ticker)
    if hit is not None:
        return {k: hit.get(k) for k in empty}
    corp = _load_corp_map().get(ticker)
    if not corp:
        return empty
    year = _latest_fy()
    fin = _financials(corp, year)
    if not fin:
        year -= 1
        fin = _financials(corp, year)
    head, labor = _employees(corp, year)
    if (not head) and year:
        head, labor = _employees(corp, year - 1)
    out = dict(empty)
    if fin:
        rev, cogs, op = fin["revenue"], fin["cogs"], fin["op"]
        out.update(revenue=rev, cogs=cogs, op=op,
                   sga=(rev - (cogs or 0) - (op or 0)) if rev else None, year=year)
    out.update(headcount=head or None, annual_labor=labor or None,
               avg_salary=(labor // head) if (head and labor) else None)
    return _CACHE.put(ticker, out)
