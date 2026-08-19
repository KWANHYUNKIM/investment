"""부동산 전월세 실거래 — 국토부 아파트 전월세 실거래가(RTMS, data.go.kr).

전국 250개 시군구 × 최근 N개월의 아파트 전월세 계약을 받아 **월별 거래량·전세/월세
비중·평균 전세보증금**을 집계한다. 월세 비중↑ = 전세의 월세화(전세 매물 감소·금리
부담 신호), 평균 전세보증금 = 전세가 방향.

API: GET .../1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent
각 item: deposit(보증금, 만원) · monthlyRent(월세, 만원; 0이면 전세) · sggCd 등.
매매 모듈과 동일하게 250 시군구·당월 잠정·12h 캐시·스케줄러 워밍.
"""
from __future__ import annotations

import datetime
import time
from concurrent.futures import ThreadPoolExecutor
from xml.etree import ElementTree as ET

import requests

from app.core.cache import TTLCache
from app.core.config import get_settings
from app.data.infra.lawd_codes import SIGUNGU

_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"
_HEADERS = {"User-Agent": "Mozilla/5.0"}

_cache = TTLCache(ttl=12 * 3600.0)
MONTHS = 6


def _txt(item, *names) -> str | None:
    for n in names:
        el = item.find(n)
        if el is not None and el.text is not None:
            return el.text.strip()
    return None


def _recent_months(n: int) -> list[str]:
    today = datetime.date.today()
    out: list[str] = []
    y, m = today.year, today.month
    for _ in range(n):
        out.append(f"{y:04d}{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(out))


def _num(s: str | None) -> float | None:
    if not s:
        return None
    s = s.replace(",", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _fetch_one(lawd: str, ymd: str) -> tuple[int, int, int, float, bool]:
    """(전체건수, 전세건수, 월세건수, 전세보증금합_만원, ok)."""
    key = get_settings().data_go_kr_key
    if not key:
        return 0, 0, 0, 0.0, False
    total = jeonse = wolse = 0
    dep_sum = 0.0
    page = 1
    while True:
        params = {"serviceKey": key, "LAWD_CD": lawd, "DEAL_YMD": ymd,
                  "pageNo": str(page), "numOfRows": "1000"}
        try:
            r = requests.get(_URL, params=params, headers=_HEADERS, timeout=12)
        except Exception:
            return total, jeonse, wolse, dep_sum, False
        if r.status_code != 200:
            return total, jeonse, wolse, dep_sum, False
        try:
            root = ET.fromstring(r.text)
        except ET.ParseError:
            return total, jeonse, wolse, dep_sum, False
        rc = _txt(root, ".//resultCode") or _txt(root, ".//returnReasonCode")
        if rc not in (None, "000", "00", "0"):
            return total, jeonse, wolse, dep_sum, False
        items = root.findall(".//item")
        for it in items:
            dep = _num(_txt(it, "deposit", "보증금액", "보증금"))
            rent = _num(_txt(it, "monthlyRent", "월세금액", "월세"))
            if dep is None and rent is None:
                continue
            total += 1
            if (rent or 0) > 0:
                wolse += 1
            else:
                jeonse += 1
                if dep:
                    dep_sum += dep
        tc = _txt(root, ".//totalCount")
        try:
            total_n = int(tc) if tc else total
        except ValueError:
            total_n = total
        if total >= total_n or not items:
            break
        page += 1
        if page > 30:
            break
    return total, jeonse, wolse, dep_sum, True


def snapshot(months: int = MONTHS, force: bool = False) -> dict:
    hit = None if force else _cache.get()
    if hit:
        return hit

    if not get_settings().data_go_kr_key:
        return {"available": False,
                "reason": "DATA_GO_KR_KEY 미설정 — backend/.env에 키를 넣으면 활성화됩니다.",
                "monthly": [], "by_sido": [], "scope": "전국"}

    yms = _recent_months(months)
    jobs = [(lawd, sido, name, ym) for ym in yms for (lawd, sido, name) in SIGUNGU]

    def run(job):
        lawd, sido, name, ym = job
        t, j, w, dep, ok = _fetch_one(lawd, ym)
        return {"ym": ym, "sido": sido, "total": t, "jeonse": j,
                "wolse": w, "dep_sum": dep, "ok": ok}

    with ThreadPoolExecutor(max_workers=20) as ex:
        results = list(ex.map(run, jobs))

    if sum(1 for r in results if r["ok"]) == 0:
        return {"available": False,
                "reason": "data.go.kr 전월세 API가 403/오류로 응답 — 키 권한·반영 상태를 확인하세요.",
                "monthly": [], "by_sido": [], "scope": "전국"}

    cur_ym = _recent_months(1)[0]

    def ratio(w, j):
        tot = w + j
        return round(w / tot * 100.0, 1) if tot else None

    def avg_eok(dep_sum, j):
        return round(dep_sum / j / 10000.0, 2) if j else None

    by_month: dict[str, dict] = {}
    for r in results:
        m = by_month.setdefault(r["ym"], {"total": 0, "jeonse": 0, "wolse": 0, "dep": 0.0})
        m["total"] += r["total"]
        m["jeonse"] += r["jeonse"]
        m["wolse"] += r["wolse"]
        m["dep"] += r["dep_sum"]
    monthly = [
        {"ym": ym, "label": f"{ym[:4]}.{ym[4:]}",
         "count": by_month[ym]["total"], "jeonse": by_month[ym]["jeonse"],
         "wolse": by_month[ym]["wolse"],
         "wolse_ratio": ratio(by_month[ym]["wolse"], by_month[ym]["jeonse"]),
         "avg_jeonse_eok": avg_eok(by_month[ym]["dep"], by_month[ym]["jeonse"]),
         "provisional": ym == cur_ym}
        for ym in yms
    ]

    complete = [m for m in monthly if not m["provisional"]]
    head = complete[-1] if complete else monthly[-1]
    mom = None
    if len(complete) >= 2 and complete[-2]["count"]:
        mom = round((complete[-1]["count"] / complete[-2]["count"] - 1.0) * 100.0, 1)

    region_ym = head["ym"]
    region_rows = [r for r in results if r["ym"] == region_ym]
    by_sido_acc: dict[str, dict] = {}
    for r in region_rows:
        s = by_sido_acc.setdefault(r["sido"], {"total": 0, "jeonse": 0, "wolse": 0, "dep": 0.0})
        s["total"] += r["total"]
        s["jeonse"] += r["jeonse"]
        s["wolse"] += r["wolse"]
        s["dep"] += r["dep_sum"]
    by_sido = sorted(
        [{"sido": k, "count": v["total"], "wolse_ratio": ratio(v["wolse"], v["jeonse"]),
          "avg_jeonse_eok": avg_eok(v["dep"], v["jeonse"])}
         for k, v in by_sido_acc.items()],
        key=lambda x: x["count"], reverse=True,
    )

    data = {
        "available": True,
        "scope": "전국 250개 시군구",
        "source": "국토교통부 전월세 실거래가(RTMS) · data.go.kr",
        "latest_ym": head["ym"], "latest_label": head["label"],
        "latest_count": head["count"], "latest_jeonse": head["jeonse"],
        "latest_wolse": head["wolse"], "latest_wolse_ratio": head["wolse_ratio"],
        "latest_avg_jeonse_eok": head["avg_jeonse_eok"],
        "mom_count_pct": mom, "region_ym": region_ym,
        "monthly": monthly, "by_sido": by_sido,
        "partial": sum(1 for r in results if r["ok"]) < len(results),
    }
    _cache.set(None, data)
    return data


# --- 단지별 전월세 실거래(지도용) --------------------------------------------
# 매매(realestate.month_deals)와 같은 모양의 계약 단위 목록. 지도에서 매매/전세/월세를
# 같은 코드로 다루려고 금액 필드를 통일한다: 전세는 deposit_eok, 월세는 보증금+월세.
_deal_cache = TTLCache(ttl=12 * 3600.0)


def month_deals(lawd: str, ymd: str) -> tuple[list[dict], bool]:
    """한 시군구·한 달의 아파트 전월세 계약 **전체** 목록과 성공여부(ok)."""
    key = get_settings().data_go_kr_key
    if not key:
        return [], False
    out: list[dict] = []
    page = 1
    while True:
        params = {"serviceKey": key, "LAWD_CD": lawd, "DEAL_YMD": ymd,
                  "pageNo": str(page), "numOfRows": "1000"}
        try:
            r = requests.get(_URL, params=params, headers=_HEADERS, timeout=12)
        except Exception:
            return out, False
        if r.status_code != 200:
            return out, False
        try:
            root = ET.fromstring(r.text)
        except ET.ParseError:
            return out, False
        rc = _txt(root, ".//resultCode") or _txt(root, ".//returnReasonCode")
        if rc not in (None, "000", "00", "0"):
            return out, False
        items = root.findall(".//item")
        for it in items:
            dep = _num(_txt(it, "deposit", "보증금액", "보증금"))
            rent_m = _num(_txt(it, "monthlyRent", "월세금액", "월세")) or 0.0
            if dep is None and not rent_m:
                continue
            y = _txt(it, "dealYear", "년") or ymd[:4]
            m = _txt(it, "dealMonth", "월") or ymd[4:]
            d = _txt(it, "dealDay", "일") or ""
            area = _txt(it, "excluUseAr", "전용면적")
            out.append({
                "apt": _txt(it, "aptNm", "아파트") or "-",
                "dong": _txt(it, "umdNm", "법정동") or "",
                "area": round(float(area), 1) if area else None,
                "deposit_eok": round((dep or 0.0) / 10000.0, 2),
                "monthly_manwon": int(rent_m),
                "rent_type": "월세" if rent_m > 0 else "전세",
                "floor": _txt(it, "floor", "층"),
                "build_year": _txt(it, "buildYear", "건축년도"),
                "date": f"{int(y):04d}-{int(m):02d}-{int(d):02d}" if d else f"{y}-{m}",
            })
        tc = _txt(root, ".//totalCount")
        try:
            total_n = int(tc) if tc else len(out)
        except ValueError:
            total_n = len(out)
        if len(out) >= total_n or not items or page > 30:
            break
        page += 1
    return out, True


# 실패(429/키오류)도 잠깐 기억한다 — 안 그러면 매매 조회마다 전월세 API 를 헛되이
# 다시 때려 남은 일일 쿼터를 더 태운다.
_deal_fail = TTLCache(ttl=10 * 60.0)


def deals_ok(lawd: str, ymd: str | None = None, limit: int = 600) -> tuple[list[dict], bool]:
    """(계약목록, 성공여부). ok=False 면 쿼터 초과/키 오류 — '거래 없음'과 구분해야 한다."""
    if not ymd:
        ymd = _recent_months(2)[0]
    ck = f"{lawd}:{ymd}"
    hit = _deal_cache.get(ck)
    if hit is not None:
        return hit[:limit], True
    if _deal_fail.get(ck) is not None:
        return [], False
    out, ok = month_deals(lawd, ymd)
    out.sort(key=lambda x: (x["date"], x["deposit_eok"]), reverse=True)
    if ok:
        _deal_cache.set(ck, out)
    else:
        _deal_fail.set(ck, True)
    return out[:limit], ok


def deals(lawd: str, ymd: str | None = None, limit: int = 600) -> list[dict]:
    """한 시군구의 아파트 전월세 계약 목록. 매매와 달리 건수가 많아 캐시를 둔다."""
    return deals_ok(lawd, ymd, limit)[0]
