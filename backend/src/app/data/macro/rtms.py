"""국토교통부 실거래가(RTMS) 전 유형 클라이언트 — 네이버 부동산의 '매물 종류' 탭 대응.

아파트만 받던 것을 오피스텔·연립다세대·단독다가구·상업업무용·토지·분양권까지 넓힌다.
서비스마다 XML 필드명이 다르지만(aptNm/offiNm/mhouseNm…) 뜻은 같아, 후보 이름을 여러 개
주고 먼저 잡히는 것을 쓰는 방식으로 **한 개의 정규화된 계약 dict** 로 통일한다:

    {name, dong, area, amount_eok, deposit_eok, monthly_manwon, rent_type,
     floor, build_year, date}

이렇게 해 두면 지도·목록·필터가 유형을 몰라도 그대로 돈다.
키는 아파트 실거래와 같은 data_go_kr_key 를 쓰지만 **서비스마다 활용신청이 따로** 필요하다.
승인 안 된 서비스는 403 이 오고, 그 유형만 unavailable 로 표시된다.
"""
from __future__ import annotations

import datetime
from xml.etree import ElementTree as ET

import requests

from app.core.cache import TTLCache
from app.core.config import get_settings

_BASE = "https://apis.data.go.kr/1613000"
_HEADERS = {"User-Agent": "Mozilla/5.0"}

# kind -> {label, sale: 서비스경로, rent: 서비스경로 or None, has_name: 단지명이 있는 유형인가}
KINDS: dict[str, dict] = {
    "apt": {
        "label": "아파트",
        "sale": "RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade",
        "rent": "RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
        "has_name": True,
    },
    "offi": {
        "label": "오피스텔",
        "sale": "RTMSDataSvcOffiTrade/getRTMSDataSvcOffiTrade",
        "rent": "RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent",
        "has_name": True,
    },
    "rh": {
        "label": "연립·다세대",
        "sale": "RTMSDataSvcRHTrade/getRTMSDataSvcRHTrade",
        "rent": "RTMSDataSvcRHRent/getRTMSDataSvcRHRent",
        "has_name": True,
    },
    "sh": {
        "label": "단독·다가구",
        "sale": "RTMSDataSvcSHTrade/getRTMSDataSvcSHTrade",
        "rent": "RTMSDataSvcSHRent/getRTMSDataSvcSHRent",
        "has_name": False,   # 단지명이 없다 — 동+주택유형으로 묶는다
    },
    "nrg": {
        "label": "상업·업무",
        "sale": "RTMSDataSvcNrgTrade/getRTMSDataSvcNrgTrade",
        "rent": None,
        "has_name": False,
    },
    "land": {
        "label": "토지",
        "sale": "RTMSDataSvcLandTrade/getRTMSDataSvcLandTrade",
        "rent": None,
        "has_name": False,
    },
    "silv": {
        "label": "분양권",
        "sale": "RTMSDataSvcSilvTrade/getRTMSDataSvcSilvTrade",
        "rent": None,
        "has_name": True,
    },
}

# 유형별로 이름이 다른 필드들 — 앞에서부터 먼저 잡히는 것을 쓴다.
_F_NAME = ("aptNm", "offiNm", "mhouseNm", "bldgNm", "buildingNm", "아파트",
           "houseType", "buildingType", "jimok", "주택유형", "건물주용도", "지목")
_F_DONG = ("umdNm", "법정동")
_F_AREA = ("excluUseAr", "totalFloorAr", "buildingAr", "dealArea", "plottageAr",
           "전용면적", "연면적", "건물면적", "거래면적", "대지면적")
_F_AMOUNT = ("dealAmount", "거래금액")
_F_DEPOSIT = ("deposit", "보증금액", "보증금")
_F_MONTHLY = ("monthlyRent", "월세금액", "월세")
_F_FLOOR = ("floor", "층")
_F_BUILD = ("buildYear", "건축년도")

_cache = TTLCache(ttl=12 * 3600.0)
_fail = TTLCache(ttl=10 * 60.0)   # 429/403 을 잠깐 기억해 남은 쿼터를 아낀다


def _txt(item, *names) -> str | None:
    for n in names:
        el = item.find(n)
        if el is not None and el.text is not None:
            t = el.text.strip()
            if t:
                return t
    return None


def _num(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return float(s.replace(",", "").strip())
    except ValueError:
        return None


def recent_months(n: int) -> list[str]:
    today = datetime.date.today()
    out: list[str] = []
    y, m = today.year, today.month
    for _ in range(n):
        out.append(f"{y:04d}{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(out))


def _parse(item, kind: str, mode: str) -> dict | None:
    """XML item 하나 → 정규화 계약 dict. 금액이 아예 없으면 None."""
    y = _txt(item, "dealYear", "년") or ""
    m = _txt(item, "dealMonth", "월") or ""
    d = _txt(item, "dealDay", "일") or ""
    try:
        date = f"{int(y):04d}-{int(m):02d}-{int(d):02d}" if d else f"{y}-{m}"
    except ValueError:
        date = f"{y}-{m}"

    name = _txt(item, *_F_NAME) or KINDS[kind]["label"]
    dong = _txt(item, *_F_DONG) or ""
    area = _num(_txt(item, *_F_AREA))

    row = {
        "apt": name, "dong": dong,
        "area": round(area, 1) if area is not None else None,
        "floor": _txt(item, *_F_FLOOR),
        "build_year": _txt(item, *_F_BUILD),
        "date": date,
    }

    if mode == "sale":
        amt = _num(_txt(item, *_F_AMOUNT))
        if amt is None:
            return None
        row["amount_eok"] = round(amt / 10000.0, 2)
        return row

    dep = _num(_txt(item, *_F_DEPOSIT))
    rent_m = _num(_txt(item, *_F_MONTHLY)) or 0.0
    if dep is None and not rent_m:
        return None
    row["deposit_eok"] = round((dep or 0.0) / 10000.0, 2)
    row["monthly_manwon"] = int(rent_m)
    row["rent_type"] = "월세" if rent_m > 0 else "전세"
    return row


def _fetch(kind: str, mode: str, lawd: str, ym: str) -> tuple[list[dict], bool, str]:
    """(계약목록, ok, 실패사유). ok=False 면 키/권한/한도 문제로 '거래 없음'과 다르다."""
    spec = KINDS.get(kind)
    if not spec:
        return [], False, "알 수 없는 매물 유형"
    path = spec.get(mode)
    if not path:
        return [], False, f"{spec['label']}은(는) {'전월세' if mode == 'rent' else '매매'} 실거래가 공공데이터에 없습니다."
    key = get_settings().data_go_kr_key
    if not key:
        return [], False, "DATA_GO_KR_KEY 미설정"

    out: list[dict] = []
    page = 1
    while True:
        params = {"serviceKey": key, "LAWD_CD": lawd, "DEAL_YMD": ym,
                  "pageNo": str(page), "numOfRows": "1000"}
        try:
            r = requests.get(f"{_BASE}/{path}", params=params, headers=_HEADERS, timeout=15)
        except Exception:
            return out, False, "네트워크 오류"
        if r.status_code == 429:
            return out, False, "일일 호출한도 초과(429)"
        if r.status_code != 200:
            return out, False, f"HTTP {r.status_code}"
        try:
            root = ET.fromstring(r.text)
        except ET.ParseError:
            return out, False, "응답 파싱 실패"
        rc = _txt(root, ".//resultCode") or _txt(root, ".//returnReasonCode")
        if rc not in (None, "000", "00", "0"):
            msg = _txt(root, ".//resultMsg") or _txt(root, ".//returnAuthMsg") or f"코드 {rc}"
            # 22=한도초과, 30/31=키 미승인·만료
            return out, False, msg
        items = root.findall(".//item")
        for it in items:
            row = _parse(it, kind, mode)
            if row:
                out.append(row)
        tc = _txt(root, ".//totalCount")
        try:
            total_n = int(tc) if tc else len(out)
        except ValueError:
            total_n = len(out)
        if len(out) >= total_n or not items or page > 30:
            break
        page += 1
    return out, True, ""


def deals(kind: str, mode: str, lawd: str, ym: str | None = None) -> tuple[list[dict], bool, str]:
    """한 시군구·한 달의 정규화된 실거래 계약 목록. 12h 캐시 + 10분 실패 캐시."""
    if not ym:
        ym = recent_months(2)[0]      # 완성 최신월(전월)
    ck = f"{kind}:{mode}:{lawd}:{ym}"
    hit = _cache.get(ck)
    if hit is not None:
        return hit, True, ""
    bad = _fail.get(ck)
    if bad is not None:
        return [], False, str(bad)
    out, ok, why = _fetch(kind, mode, lawd, ym)
    if ok:
        key_amount = "amount_eok" if mode == "sale" else "deposit_eok"
        out.sort(key=lambda x: (x["date"], x.get(key_amount, 0)), reverse=True)
        _cache.set(ck, out)
    else:
        _fail.set(ck, why)
    return out, ok, why
