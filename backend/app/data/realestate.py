"""부동산 실거래 — 국토부 아파트 매매 실거래가(RTMS, data.go.kr 무료 키).

서울 25개 구 × 최근 N개월의 아파트 매매 거래를 받아 **월별 거래량(건수)·거래대금
(억원)** 과 **최신월 지역(구)별 분포**로 집계한다. "최근 부동산 거래액이 어떻게
움직이는지" = 부동산으로 돈이 들어오나 빠지나의 직접 신호.

API: GET https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade
파라미터: serviceKey, LAWD_CD(법정동 앞5자리=시군구), DEAL_YMD(계약년월 6자리),
          pageNo, numOfRows. 응답 XML, 각 item의 dealAmount(만원, 콤마 포함).
키가 없거나 아직 게이트웨이 미반영(403)이면 available=False로 우아하게 빠진다.
"""
from __future__ import annotations

import datetime
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from xml.etree import ElementTree as ET

import requests

from app.core.config import get_settings

_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
_HEADERS = {"User-Agent": "Mozilla/5.0"}

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 6 * 3600.0  # 6시간 (거래 데이터는 일 단위 갱신 → 자주 받을 이유 없음)

# 서울 25개 구 (LAWD_CD 시군구 5자리, 라벨). 가장 대표성 큰 시장부터.
_SEOUL: tuple[tuple[str, str], ...] = (
    ("11110", "종로구"), ("11140", "중구"), ("11170", "용산구"), ("11200", "성동구"),
    ("11215", "광진구"), ("11230", "동대문구"), ("11260", "중랑구"), ("11290", "성북구"),
    ("11305", "강북구"), ("11320", "도봉구"), ("11350", "노원구"), ("11380", "은평구"),
    ("11410", "서대문구"), ("11440", "마포구"), ("11470", "양천구"), ("11500", "강서구"),
    ("11530", "구로구"), ("11545", "금천구"), ("11560", "영등포구"), ("11590", "동작구"),
    ("11620", "관악구"), ("11650", "서초구"), ("11680", "강남구"), ("11710", "송파구"),
    ("11740", "강동구"),
)


def _txt(item, *names) -> str | None:
    """English/Korean 태그명 모두 대응해 첫 매치 텍스트 반환."""
    for n in names:
        el = item.find(n)
        if el is not None and el.text is not None:
            return el.text.strip()
    return None


def _recent_months(n: int) -> list[str]:
    """최근 n개 계약년월(YYYYMM), 과거→현재."""
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
            "serviceKey": key,
            "LAWD_CD": lawd,
            "DEAL_YMD": ymd,
            "pageNo": str(page),
            "numOfRows": "1000",
        }
        try:
            r = requests.get(_URL, params=params, headers=_HEADERS, timeout=12)
        except Exception:
            return count, amount_manwon, False
        if r.status_code != 200:
            # 403 등 게이트웨이 거부(키 미활성화) → 신호용으로 ok=False
            return count, amount_manwon, False
        try:
            root = ET.fromstring(r.text)
        except ET.ParseError:
            return count, amount_manwon, False
        # 명시적 에러코드(예: SERVICE_KEY_IS_NOT_REGISTERED) 처리
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
        if page > 20:  # 안전장치
            break
    return count, amount_manwon, True


def snapshot(months: int = 6, force: bool = False) -> dict:
    with _lock:
        if not force and _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]

    if not get_settings().data_go_kr_key:
        return {
            "available": False,
            "reason": "DATA_GO_KR_KEY 미설정 — backend/.env에 키를 넣으면 활성화됩니다.",
            "monthly": [], "by_region": [], "scope": "서울 25개구",
        }

    yms = _recent_months(months)
    jobs = [(lawd, name, ym) for ym in yms for (lawd, name) in _SEOUL]

    def run(job):
        lawd, name, ym = job
        c, a, ok = _fetch_one(lawd, ym)
        return {"ym": ym, "lawd": lawd, "region": name, "count": c, "manwon": a, "ok": ok}

    with ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(run, jobs))

    ok_n = sum(1 for r in results if r["ok"])
    if ok_n == 0:
        return {
            "available": False,
            "reason": "data.go.kr API가 403(키 미반영)으로 응답 — 활용신청 직후 게이트웨이 "
                      "반영까지 수십 분~최대 하루 걸릴 수 있습니다. 활성화되면 자동 표시됩니다.",
            "monthly": [], "by_region": [], "scope": "서울 25개구",
        }

    # 당월은 실거래 신고기한(계약 후 30일) 때문에 아직 미완성 → '잠정'으로 표시하고
    # 헤드라인·전월대비는 '완성된 달' 기준으로 잡는다.
    cur_ym = _recent_months(1)[0]

    # 월별 집계
    by_month: dict[str, dict] = {}
    for r in results:
        m = by_month.setdefault(r["ym"], {"count": 0, "manwon": 0.0})
        m["count"] += r["count"]
        m["manwon"] += r["manwon"]
    monthly = [
        {
            "ym": ym,
            "label": f"{ym[:4]}.{ym[4:]}",
            "count": by_month[ym]["count"],
            "amount_eok": round(by_month[ym]["manwon"] / 10000.0, 0),  # 만원→억
            "provisional": ym == cur_ym,  # 신고 진행중(잠정)
        }
        for ym in yms
    ]

    # 헤드라인·MoM은 완성월 기준
    complete = [m for m in monthly if not m["provisional"]]
    head = complete[-1] if complete else monthly[-1]
    mom = None
    if len(complete) >= 2 and complete[-2]["count"]:
        mom = round((complete[-1]["count"] / complete[-2]["count"] - 1.0) * 100.0, 1)

    # 지역(구)별 분포 — 완성된 최신월 기준
    region_ym = head["ym"]
    region_rows = [r for r in results if r["ym"] == region_ym]
    by_region = sorted(
        [
            {"region": r["region"], "count": r["count"],
             "amount_eok": round(r["manwon"] / 10000.0, 0)}
            for r in region_rows
        ],
        key=lambda x: x["amount_eok"], reverse=True,
    )

    data = {
        "available": True,
        "scope": "서울 25개구",
        "source": "국토교통부 실거래가(RTMS) · data.go.kr",
        "latest_ym": head["ym"],
        "latest_label": head["label"],
        "latest_count": head["count"],
        "latest_amount_eok": head["amount_eok"],
        "mom_count_pct": mom,
        "region_ym": region_ym,
        "monthly": monthly,
        "by_region": by_region,
        "partial": ok_n < len(results),  # 일부 구/월 누락 여부
    }
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = data
    return data
