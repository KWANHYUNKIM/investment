"""인구이동 — **사람이 어디에서 어디로 옮겨 가는가**.

왜 부동산에 쓰나
----------------
가격은 결과고 이동은 원인에 가깝다. 사람이 계속 들어오는 동네와 계속 빠지는 동네는
같은 호가라도 다른 자산이다. 특히 **20~34세 순이동**이 중요하다. 이 나이대가 들어오는
곳은 임대 수요·상권·신축 수요가 같이 붙는다. (인스타그램으로 '젊은 사람이 어디로
가는지' 를 보려던 것을 이 자료가 대체한다 — 표본이 아니라 전수인 주민등록 자료다.)

자료
----
행정안전부 지역별 인구이동 현황 (주민등록 전입신고 기준, 2022.10~, 매월 2일 공표).

    https://apis.data.go.kr/1741000/ppltnDataStus/selectPpltnDataStus

전입지 × 전출지 쌍으로 조회하며, 성별 × 만 나이 한 살 단위까지 나온다. 표본조사가
아니라 전입신고 전수라서 "몇 명이 옮겼다" 를 그대로 쓸 수 있다.

    lv=1 시도 · lv=2 시군구 · lv=3 읍면동(기본) · lv=4 전국 시도
    srchFrYm~srchToYm 는 **최대 3개월**

한계
----
- 2022년 10월 이전은 없다. 장기 추세는 이 API 로 못 만든다.
- 전입신고 기준이라 실거주 이동과 완전히 같지는 않다(위장전입·미신고).
- 이 서비스는 **별도 활용신청**이 필요하다. 승인 전에는 403 이 돌아온다.
  https://www.data.go.kr/data/15108093/openapi.do (개발계정 자동승인, 일 10,000회)
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from app.core.config import get_settings

_API = "https://apis.data.go.kr/1741000/ppltnDataStus/selectPpltnDataStus"

# 청년 구간. 취업·독립·결혼으로 실제로 집을 옮기는 나이대다. 이 구간의 순이동이
# 전체 순이동보다 임대 수요·상권 변화를 먼저 설명한다.
YOUNG = range(20, 35)


class MigrationError(Exception):
    """호출 자체가 실패했을 때. '이동이 0' 과 구분하려고 예외로 둔다."""


class NotApprovedError(MigrationError):
    """활용신청이 안 된 상태(403). 키를 바꿔도 소용없고 신청 한 번이면 풀린다."""


def configured() -> bool:
    return bool(get_settings().data_go_kr_key)


# --- 호출 -------------------------------------------------------------------
def fetch(mvin: str, mvt: str, fr_ym: str, to_ym: str,
          lv: str = "2", rows: int = 100, page: int = 1) -> list[dict]:
    """전입지 ``mvin`` ← 전출지 ``mvt`` 의 이동 건들.

    기간은 API 가 3개월까지만 받는다 — 더 넓게 부르면 빈 응답이 오므로 호출부에서
    잘라 넣어야 한다.
    """
    key = get_settings().data_go_kr_key
    if not key:
        raise MigrationError("DATA_GO_KR_KEY 미설정")

    params = {"serviceKey": key, "mvinAdmmCd": mvin, "mvtAdmmCd": mvt,
              "srchFrYm": fr_ym, "srchToYm": to_ym, "lv": lv,
              "type": "JSON", "numOfRows": str(rows), "pageNo": str(page)}
    url = f"{_API}?{urllib.parse.urlencode(params, safe='%')}"
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            raw = r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise NotApprovedError(
                "인구이동 API 활용신청이 필요합니다 — "
                "https://www.data.go.kr/data/15108093/openapi.do") from e
        raise MigrationError(f"HTTP {e.code}") from e
    except Exception as e:  # noqa: BLE001
        raise MigrationError(str(e)) from e

    return parse(raw)


def parse(raw: str) -> list[dict]:
    """응답 → 항목 목록. 항목이 하나면 dict, 여럿이면 list 로 오는 형태를 고른다.

    공공데이터포털 응답의 고질적인 함정이다. 하나짜리를 그냥 순회하면 dict 의 키를
    돌게 되어 조용히 빈 결과가 된다.
    """
    try:
        d = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        raise MigrationError(f"응답 파싱 실패: {raw[:120]}") from e

    head = d.get("head") or {}
    code = str(head.get("resultCode", "")).strip()
    if code and code not in ("00", "0", "INFO-000"):
        if "03" == code:
            return []
        raise MigrationError(f"{code} {head.get('resultMsg', '')}")

    items = (d.get("items") or {}).get("item")
    if items is None:
        return []
    if isinstance(items, dict):
        items = [items]
    return [_row(x) for x in items]


def _int(v) -> int:
    """숫자 칸이 ''·None·'1,234' 로 오는 경우가 있다."""
    if v in (None, ""):
        return 0
    try:
        return int(str(v).replace(",", "").strip())
    except ValueError:
        return 0


def _row(x: dict) -> dict:
    """원본 한 줄 → 쓰기 좋은 모양. 나이별 남녀를 청년 구간으로 합쳐 둔다."""
    young = sum(_int(x.get(f"{sex}{age}AgeNmprCnt"))
                for sex in ("male", "feml") for age in YOUNG)
    return {
        "ym": str(x.get("statsYm") or ""),
        "to_cd": str(x.get("mvinAdmmCd") or ""),      # 전입(도착)
        "from_cd": str(x.get("mvtAdmmCd") or ""),     # 전출(출발)
        "to_name": " ".join(p for p in (x.get("mvinCtpvNm"), x.get("mvinSggNm"),
                                        x.get("mvinDongNm")) if p),
        "from_name": " ".join(p for p in (x.get("mvtCtpvNm"), x.get("mvtSggNm"),
                                          x.get("mvtDongNm")) if p),
        "total": _int(x.get("totNmprCnt")),
        "male": _int(x.get("maleNmprCnt")),
        "female": _int(x.get("femlNmprCnt")),
        "young": young,
    }


# --- 집계 -------------------------------------------------------------------
def summarize(rows: list[dict], lawd_admm: str) -> dict:
    """한 지역의 전입·전출·순이동. ``lawd_admm`` 은 그 지역의 행정기관코드다.

    순이동만 보면 규모를 알 수 없고, 총량만 보면 방향을 알 수 없다. 둘 다 준다.
    청년 순이동을 따로 두는 이유는 전체가 늘어도 청년이 빠지는 동네가 실제로 있고,
    그 둘이 가격에 다르게 작용하기 때문이다.
    """
    in_tot = sum(r["total"] for r in rows if r["to_cd"] == lawd_admm)
    out_tot = sum(r["total"] for r in rows if r["from_cd"] == lawd_admm)
    in_y = sum(r["young"] for r in rows if r["to_cd"] == lawd_admm)
    out_y = sum(r["young"] for r in rows if r["from_cd"] == lawd_admm)

    net = in_tot - out_tot
    net_y = in_y - out_y
    return {
        "in_total": in_tot, "out_total": out_tot, "net": net,
        "in_young": in_y, "out_young": out_y, "net_young": net_y,
        # 규모 대비 순이동. 큰 도시와 작은 군을 같은 자리에 놓고 보려면 필요하다.
        "churn": in_tot + out_tot,
        "net_rate": round(net / (in_tot + out_tot) * 100, 1) if (in_tot + out_tot) else 0.0,
        "direction": "유입" if net > 0 else ("유출" if net < 0 else "균형"),
        "young_direction": "청년 유입" if net_y > 0 else ("청년 유출" if net_y < 0 else "균형"),
    }


def flows(rows: list[dict], lawd_admm: str, limit: int = 10) -> dict:
    """어디에서 왔고 어디로 갔는가 — 상대 지역별 상위 흐름.

    '순이동 +300' 은 어디서 온 300명인지 말해 주지 않는다. 짝을 봐야 그 동네가
    어느 생활권과 묶여 있는지 보인다(직주근접 이동인지, 원거리 이동인지).
    """
    inbound: dict[str, dict] = {}
    outbound: dict[str, dict] = {}
    for r in rows:
        if r["to_cd"] == lawd_admm and r["from_cd"] != lawd_admm:
            b = inbound.setdefault(r["from_cd"],
                                   {"cd": r["from_cd"], "name": r["from_name"],
                                    "total": 0, "young": 0})
        elif r["from_cd"] == lawd_admm and r["to_cd"] != lawd_admm:
            b = outbound.setdefault(r["to_cd"],
                                    {"cd": r["to_cd"], "name": r["to_name"],
                                     "total": 0, "young": 0})
        else:
            continue        # 같은 지역 내부 이동 — 흐름이 아니다
        b["total"] += r["total"]
        b["young"] += r["young"]

    top = lambda d: sorted(d.values(), key=lambda x: -x["total"])[:limit]  # noqa: E731
    return {"inbound": top(inbound), "outbound": top(outbound)}


__all__ = ["MigrationError", "NotApprovedError", "YOUNG", "configured",
           "fetch", "flows", "parse", "summarize"]
