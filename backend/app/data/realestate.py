"""부동산 실거래 — 국토부 아파트 매매 실거래가(RTMS, data.go.kr 무료 키).

전국 250개 시군구 × 최근 N개월의 아파트 매매 거래를 받아 **월별 거래량(건수)·
거래대금(억원)** 과 **완성 최신월의 시도별 분포 + 상위 시군구**로 집계한다.
"최근 부동산 거래액이 어떻게 움직이는지" = 부동산으로 돈이 들어오나 빠지나의 직접 신호.

시군구 코드는 lawd_codes.SIGUNGU(행정표준 법정동코드에서 리프 시군구만 추출).
당월은 신고기한(계약 후 30일) 탓에 미완성 → '잠정' 처리. 호출이 많아(시군구×개월)
12h 캐시 + 스케줄러 워밍으로 첫 진입 대기를 없앤다. 키 없거나 403이면 available=False.
"""
from __future__ import annotations

import datetime
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from xml.etree import ElementTree as ET

import requests

from app.core.config import get_settings
from app.data.lawd_codes import SIGUNGU

_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
_HEADERS = {"User-Agent": "Mozilla/5.0"}

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 12 * 3600.0  # 12시간 (전국 1,500여 콜이라 자주 받지 않음, 스케줄러가 워밍)
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


def _fetch_one(lawd: str, ymd: str) -> tuple[int, float, bool]:
    """(거래건수, 거래대금_만원합, ok). ok=False면 키 미반영/에러."""
    key = get_settings().data_go_kr_key
    if not key:
        return 0, 0.0, False
    count = 0
    amount_manwon = 0.0
    page = 1
    while True:
        params = {
            "serviceKey": key, "LAWD_CD": lawd, "DEAL_YMD": ymd,
            "pageNo": str(page), "numOfRows": "1000",
        }
        try:
            r = requests.get(_URL, params=params, headers=_HEADERS, timeout=12)
        except Exception:
            return count, amount_manwon, False
        if r.status_code != 200:
            return count, amount_manwon, False
        try:
            root = ET.fromstring(r.text)
        except ET.ParseError:
            return count, amount_manwon, False
        rc = _txt(root, ".//resultCode") or _txt(root, ".//returnReasonCode")
        if rc not in (None, "000", "00", "0"):
            return count, amount_manwon, False
        items = root.findall(".//item")
        for it in items:
            amt = _txt(it, "dealAmount", "거래금액")
            if amt:
                try:
                    amount_manwon += float(amt.replace(",", "").strip())
                    count += 1
                except ValueError:
                    pass
        total = _txt(root, ".//totalCount")
        try:
            total_n = int(total) if total else count
        except ValueError:
            total_n = count
        if count >= total_n or not items:
            break
        page += 1
        if page > 30:
            break
    return count, amount_manwon, True


def snapshot(months: int = MONTHS, force: bool = False) -> dict:
    with _lock:
        if not force and _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]

    if not get_settings().data_go_kr_key:
        return {"available": False,
                "reason": "DATA_GO_KR_KEY 미설정 — backend/.env에 키를 넣으면 활성화됩니다.",
                "monthly": [], "by_sido": [], "top_sigungu": [], "scope": "전국"}

    yms = _recent_months(months)
    jobs = [(lawd, sido, name, ym) for ym in yms for (lawd, sido, name) in SIGUNGU]

    def run(job):
        lawd, sido, name, ym = job
        c, a, ok = _fetch_one(lawd, ym)
        return {"ym": ym, "lawd": lawd, "sido": sido, "region": name,
                "count": c, "manwon": a, "ok": ok}

    with ThreadPoolExecutor(max_workers=20) as ex:
        results = list(ex.map(run, jobs))

    ok_n = sum(1 for r in results if r["ok"])
    if ok_n == 0:
        return {"available": False,
                "reason": "data.go.kr API가 403(키 미반영)으로 응답 — 활용신청 직후 게이트웨이 "
                          "반영까지 시간이 걸릴 수 있습니다. 활성화되면 자동 표시됩니다.",
                "monthly": [], "by_sido": [], "top_sigungu": [], "scope": "전국"}

    cur_ym = _recent_months(1)[0]

    # 월별 전국 집계
    by_month: dict[str, dict] = {}
    for r in results:
        m = by_month.setdefault(r["ym"], {"count": 0, "manwon": 0.0})
        m["count"] += r["count"]
        m["manwon"] += r["manwon"]
    monthly = [
        {"ym": ym, "label": f"{ym[:4]}.{ym[4:]}",
         "count": by_month[ym]["count"],
         "amount_eok": round(by_month[ym]["manwon"] / 10000.0, 0),
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

    # 시도별 분포(완성 최신월)
    by_sido_acc: dict[str, dict] = {}
    for r in region_rows:
        s = by_sido_acc.setdefault(r["sido"], {"count": 0, "manwon": 0.0})
        s["count"] += r["count"]
        s["manwon"] += r["manwon"]
    by_sido = sorted(
        [{"sido": k, "count": v["count"], "amount_eok": round(v["manwon"] / 10000.0, 0)}
         for k, v in by_sido_acc.items()],
        key=lambda x: x["amount_eok"], reverse=True,
    )

    # 상위 시군구(완성 최신월)
    top_sigungu = sorted(
        [{"region": r["region"], "sido": r["sido"], "count": r["count"],
          "amount_eok": round(r["manwon"] / 10000.0, 0)}
         for r in region_rows if r["count"] > 0],
        key=lambda x: x["amount_eok"], reverse=True,
    )[:15]

    data = {
        "available": True,
        "scope": "전국 250개 시군구",
        "source": "국토교통부 실거래가(RTMS) · data.go.kr",
        "latest_ym": head["ym"], "latest_label": head["label"],
        "latest_count": head["count"], "latest_amount_eok": head["amount_eok"],
        "mom_count_pct": mom, "region_ym": region_ym,
        "monthly": monthly, "by_sido": by_sido, "top_sigungu": top_sigungu,
        "partial": ok_n < len(results),
    }
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = data
    return data
