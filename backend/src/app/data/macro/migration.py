"""인구이동 — **사람이 어디에서 어디로 옮겨 가는가**.

왜 부동산에 쓰나
----------------
가격은 결과고 이동은 원인에 가깝다. 사람이 계속 들어오는 동네와 계속 빠지는 동네는
같은 호가라도 다른 자산이다. 특히 **20~34세 순이동**이 중요하다. 이 나이대가 들어오는
곳은 임대 수요·상권·신축 수요가 같이 붙는다. (인스타그램으로 '젊은 사람이 어디로
가는지' 를 보려던 것을 이 자료가 대체한다 — 표본이 아니라 전입신고 전수다.)

자료
----
행정안전부 지역별 인구이동 현황 (2022.10~, 매월 2일 공표).

    https://apis.data.go.kr/1741000/ppltnDataStus/selectPpltnDataStus

호출 규칙 — 실측으로 확인한 것들이다. 명세만 보고는 알 수 없었다.

    · mvinAdmmCd(전입) · mvtAdmmCd(전출) 둘 다 **필수**. 비우면 INVALID_REQUEST_PARAMETER
    · 코드는 **법정동 10자리**(1168000000). 5자리·행정표준코드는 거절
    · 기간은 YYYYMM. "2025.12" 는 거절. 최대 3개월
    · lv=2 를 주고 **시도 코드 쌍**으로 부르면 그 안의 시군구 × 시군구가 전개된다.
      (서울←경기 한 달치 753행) 덕분에 전국이 시도쌍 17×17=289 번으로 덮인다.
      쌍마다 개별로 부르면 228×228=51,984 번이다.
    · 응답은 ``{"Response": {"head": …, "items": …}}`` 로 한 겹 싸여 있고
      성공 코드가 ``"0"``(NORMAL_SERVICE), 자료 없음이 ``"3"``, 항목 없으면 items 가 ``""``
    · 강원은 51, 전북은 52 다. 옛 코드(42·45)로 부르면 조용히 0건이 온다

한계
----
- 2022년 10월 이전은 없다. 장기 추세는 이 API 로 못 만든다.
- 전입신고 기준이라 실거주 이동과 완전히 같지는 않다(위장전입·미신고).
- 통합시는 **시 단위**로만 나온다. 수원시는 한 줄이고 장안·권선·팔달·영통이 아니다.
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from app.core.config import get_settings
from app.data.infra.lawd_codes import SIGUNGU

_API = "https://apis.data.go.kr/1741000/ppltnDataStus/selectPpltnDataStus"

# 청년 구간. 취업·독립·결혼으로 실제로 집을 옮기는 나이대다. 이 구간의 순이동이
# 전체 순이동보다 임대 수요·상권 변화를 먼저 설명한다.
YOUNG = range(20, 35)

# 나이 구간. 원본은 한 살 단위 222칸인데 실제로 보는 질문은 이 다섯이다.
AGE_BUCKETS: tuple[tuple[str, range], ...] = (
    ("age_0_19", range(0, 20)),
    ("age_20_34", range(20, 35)),
    ("age_35_49", range(35, 50)),
    ("age_50_64", range(50, 65)),
    ("age_65_plus", range(65, 111)),
)

# 원본이 쓰는 시도 코드. 우리 법정동 목록은 아직 옛 코드(강원 42·전북 45)라 바꿔 준다.
_SIDO_FIX = {"42": "51", "45": "52"}
SIDO: tuple[str, ...] = tuple(sorted({_SIDO_FIX.get(s[0][:2], s[0][:2]) for s in SIGUNGU}))

_state = {"running": False, "rows": 0, "calls": 0, "last_run": None, "msg": ""}
_lock = threading.Lock()


class MigrationError(Exception):
    """호출 자체가 실패했을 때. '이동이 0' 과 구분하려고 예외로 둔다."""


class NotApprovedError(MigrationError):
    """활용신청이 안 된 상태(403). 키를 바꿔도 소용없고 신청 한 번이면 풀린다."""


class QuotaError(MigrationError):
    """일 한도 초과. 이번 회차를 멈추되 받아 둔 것은 남긴다."""


def configured() -> bool:
    return bool(get_settings().data_go_kr_key)


# --- 코드 -------------------------------------------------------------------
def admm_of(lawd: str) -> str:
    """우리 법정동 5자리 → 원본의 행정기관코드 10자리.

    통합시의 구는 시로 올린다. 법정동코드 규칙상 시·군은 다섯째 자리가 0 이고 구는
    1~9 라, ``[:4] + '0'`` 이면 정확히 '그 구가 속한 시' 가 된다.
    (41111 수원 장안구 → 41110 수원시 · 11680 강남구 → 11680 그대로)
    """
    lawd = str(lawd).strip()[:5]
    sido = _SIDO_FIX.get(lawd[:2], lawd[:2])
    return f"{sido}{lawd[2:4]}0" + "00000"


def sido_of(code: str) -> str:
    return str(code)[:2]


# --- 호출 -------------------------------------------------------------------
def fetch(mvin: str, mvt: str, fr_ym: str, to_ym: str, lv: str = "2",
          rows: int = 100, page: int = 1) -> tuple[list[dict], int]:
    """전입지 ``mvin`` ← 전출지 ``mvt`` 의 이동 건들과 전체 건수.

    기간은 API 가 3개월까지만 받는다 — 더 넓게 부르면 거절되므로 호출부에서 자른다.
    """
    key = get_settings().data_go_kr_key
    if not key:
        raise MigrationError("DATA_GO_KR_KEY 미설정")

    params = {"serviceKey": key, "mvinAdmmCd": mvin, "mvtAdmmCd": mvt,
              "srchFrYm": fr_ym, "srchToYm": to_ym, "lv": lv,
              "type": "JSON", "numOfRows": str(rows), "pageNo": str(page)}
    url = f"{_API}?{urllib.parse.urlencode(params, safe='%')}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            raw = r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise NotApprovedError(
                "인구이동 API 활용신청이 필요합니다 — "
                "https://www.data.go.kr/data/15108093/openapi.do") from e
        if e.code == 429:
            raise QuotaError("data.go.kr 호출 한도 초과") from e
        raise MigrationError(f"HTTP {e.code}") from e
    except Exception as e:  # noqa: BLE001
        raise MigrationError(str(e)) from e

    _state["calls"] += 1
    return parse(raw)


def parse(raw: str) -> tuple[list[dict], int]:
    """응답 → (항목 목록, 전체 건수).

    함정 셋을 여기서 흡수한다.
      · 본문이 ``Response`` 로 한 겹 싸여 온다 — 안 벗기면 조용히 0건이 된다
      · 성공 코드가 ``"0"`` 이다(대부분의 포털 API 는 ``"00"``)
      · 항목이 하나면 list 가 아니라 dict 로 온다 — 그대로 순회하면 키를 돈다
    """
    try:
        d = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        raise MigrationError(f"응답 파싱 실패: {raw[:120]}") from e

    d = d.get("Response", d)
    head = d.get("head") or {}
    code = str(head.get("resultCode", "")).strip()
    if code in ("3", "03"):                 # 자료 없음 — 실패가 아니다
        return [], 0
    if code and code not in ("0", "00", "INFO-000"):
        msg = head.get("resultMsg", "")
        if "LIMIT" in str(msg).upper():
            raise QuotaError(f"{code} {msg}")
        raise MigrationError(f"{code} {msg}")

    total = _int(head.get("totalCount"))
    items = d.get("items")
    if not items:                            # 항목이 없으면 "" 로 온다
        return [], total
    item = items.get("item") if isinstance(items, dict) else items
    if item is None:
        return [], total
    if isinstance(item, dict):
        item = [item]
    return [_row(x) for x in item], total


def _int(v) -> int:
    """숫자 칸이 ''·None·'1,234' 로 오는 경우가 있다."""
    if v in (None, ""):
        return 0
    try:
        return int(str(v).replace(",", "").strip())
    except ValueError:
        return 0


def _row(x: dict) -> dict:
    """원본 한 줄 → 저장할 모양. 한 살 단위 222칸을 구간으로 접는다."""
    out = {
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
    }
    for name, ages in AGE_BUCKETS:
        out[name] = sum(_int(x.get(f"{sex}{a}AgeNmprCnt"))
                        for sex in ("male", "feml") for a in ages)
    out["young"] = out["age_20_34"]
    return out


# --- 수집 -------------------------------------------------------------------
def latest_month() -> str:
    """받을 수 있는 가장 최근 달. 매월 2일에 전달 자료가 올라온다."""
    today = dt.date.today()
    back = 1 if today.day >= 3 else 2
    y, m = today.year, today.month - back
    while m <= 0:
        y, m = y - 1, m + 12
    return f"{y}{m:02d}"


def months_back(n: int) -> list[str]:
    """최근 n 개월(최신순). 2022.10 이전은 자료가 없어 자른다."""
    out, ym = [], latest_month()
    for _ in range(n):
        if ym < "202210":
            break
        out.append(ym)
        y, m = int(ym[:4]), int(ym[4:]) - 1
        if m == 0:
            y, m = y - 1, 12
        ym = f"{y}{m:02d}"
    return out


def collect_pair(ym: str, from_sido: str, to_sido: str) -> list[dict]:
    """시도쌍 하나의 한 달치를 페이지 끝까지."""
    rows: list[dict] = []
    page = 1
    while True:
        got, total = fetch(f"{to_sido}00000000", f"{from_sido}00000000", ym, ym,
                           lv="2", rows=100, page=page)
        rows.extend(got)
        if len(rows) >= total or not got:
            break
        page += 1
        if page > 60:                # 안전장치 — 6,000행이면 시도쌍 하나로는 과하다
            break
    return rows


def refresh(budget: int | None = None, months: int | None = None) -> dict:
    """안 받은 (달 × 시도쌍) 을 예산만큼 받는다.

    한 달치가 시도쌍 289개라 한 번에 다 못 받는다. 최신 달부터 채우고, 중간에 한도에
    걸리면 **받아 둔 데까지 저장하고** 멈춘다.
    """
    from app.db import stores

    s = get_settings()
    budget = int(budget or s.migration_budget)
    months = int(months or s.migration_months)
    _state["msg"] = ""

    done = stores.migration_done()          # {(ym, from_sido, to_sido)}
    todo = [(ym, f, t) for ym in months_back(months)
            for f in SIDO for t in SIDO if (ym, f, t) not in done]
    if not todo:
        _state["msg"] = "받을 구간 없음"
        return {"pairs": 0, "rows": 0, "gaps": 0, "note": _state["msg"]}

    # 시간의 거의 전부가 응답 대기다. 12개월 전체가 3,468쌍이고 쌍마다 페이지가 붙어서
    # 한 줄로 받으면 여덟 시간이 넘는다. 받아 오는 것만 병렬로 돌리고, **저장은 한 줄로**
    # 한다 — 쓰기를 나란히 하면 얻는 게 없고 잠금만 는다.
    pairs = saved = 0
    stopped = ""
    batch = todo[:budget]
    with cf.ThreadPoolExecutor(max_workers=s.migration_workers) as pool:
        futures = {pool.submit(collect_pair, ym, f, t): (ym, f, t) for ym, f, t in batch}
        try:
            for fut in cf.as_completed(futures):
                ym, f, t = futures[fut]
                try:
                    rows = fut.result()
                except QuotaError as e:
                    stopped = str(e)
                    for other in futures:
                        other.cancel()
                    break
                except NotApprovedError as e:
                    for other in futures:
                        other.cancel()
                    _state["msg"] = str(e)
                    return {"pairs": 0, "rows": 0, "gaps": len(todo), "note": _state["msg"]}
                except MigrationError:
                    continue                # 쌍 하나 실패는 다음 회차에 다시 온다
                with _lock:
                    stores.migration_save(ym, f, t, rows)
                pairs += 1
                saved += len(rows)
        finally:
            # 취소가 안 먹은 작업(이미 시작된 것)은 끝나기를 기다린다 — 안 그러면
            # 한도 초과로 멈추기로 해 놓고 뒤에서 계속 호출이 나간다.
            pool.shutdown(wait=True, cancel_futures=True)

    _state.update({"rows": _state["rows"] + saved,
                   "last_run": time.strftime("%Y-%m-%d %H:%M:%S")})
    remaining = max(0, len(todo) - pairs)
    _state["msg"] = (f"{pairs}쌍 · {saved:,}행 저장 · {remaining}쌍 남음"
                     + (f" · {stopped}" if stopped else ""))
    return {"pairs": pairs, "rows": saved, "gaps": remaining, "note": _state["msg"]}


# --- 집계 -------------------------------------------------------------------
def summarize(rows: list[dict], code: str) -> dict:
    """한 지역의 전입·전출·순이동.

    순이동만 보면 규모를 알 수 없고, 총량만 보면 방향을 알 수 없다. 둘 다 준다.
    청년 순이동을 따로 두는 이유는 전체가 늘어도 청년이 빠지는 동네가 실제로 있고,
    그 둘이 가격에 다르게 작용하기 때문이다.
    """
    in_tot = sum(r["total"] for r in rows if r["to_cd"] == code and r["from_cd"] != code)
    out_tot = sum(r["total"] for r in rows if r["from_cd"] == code and r["to_cd"] != code)
    in_y = sum(r["young"] for r in rows if r["to_cd"] == code and r["from_cd"] != code)
    out_y = sum(r["young"] for r in rows if r["from_cd"] == code and r["to_cd"] != code)

    net, net_y = in_tot - out_tot, in_y - out_y
    churn = in_tot + out_tot
    return {
        "in_total": in_tot, "out_total": out_tot, "net": net,
        "in_young": in_y, "out_young": out_y, "net_young": net_y,
        # 규모 대비 순이동. 큰 도시와 작은 군을 같은 자리에 놓고 보려면 필요하다.
        "churn": churn,
        "net_rate": round(net / churn * 100, 1) if churn else 0.0,
        "direction": "유입" if net > 0 else ("유출" if net < 0 else "균형"),
        "young_direction": "청년 유입" if net_y > 0 else ("청년 유출" if net_y < 0 else "균형"),
    }


def flows(rows: list[dict], code: str, limit: int = 10) -> dict:
    """어디에서 왔고 어디로 갔는가 — 상대 지역별 상위 흐름.

    '순이동 +300' 은 어디서 온 300명인지 말해 주지 않는다. 짝을 봐야 그 동네가 어느
    생활권과 묶여 있는지 보인다(직주근접 이동인지, 원거리 이동인지).
    """
    inbound: dict[str, dict] = {}
    outbound: dict[str, dict] = {}
    for r in rows:
        if r["to_cd"] == code and r["from_cd"] != code:
            b = inbound.setdefault(r["from_cd"], {"cd": r["from_cd"], "name": r["from_name"],
                                                  "total": 0, "young": 0})
        elif r["from_cd"] == code and r["to_cd"] != code:
            b = outbound.setdefault(r["to_cd"], {"cd": r["to_cd"], "name": r["to_name"],
                                                 "total": 0, "young": 0})
        else:
            continue        # 같은 지역 내부 이동 — 흐름이 아니다
        b["total"] += r["total"]
        b["young"] += r["young"]

    def top(d: dict) -> list[dict]:
        return sorted(d.values(), key=lambda x: -x["total"])[:limit]

    return {"inbound": top(inbound), "outbound": top(outbound)}


# --- 좌표 -------------------------------------------------------------------
def _coord(code: str) -> list[float] | None:
    """이동 상대 지역의 좌표 — 지도에 흐름을 선으로 그리려면 필요하다.

    원본이 통합시를 시 단위로 주는데(4113000000 성남시) 우리가 지오코딩해 둔 것은
    구 단위(성남시 분당구…)다. 그래서 **그 시에 속한 구들의 평균**을 쓴다. 시청
    좌표가 아니라 사람이 사는 면적의 중심에 가까워서, 선이 엉뚱한 데서 시작하지 않는다.
    """
    from app.data.macro.realestate_map import _cached_coord, _sido_centroid

    prefix = code[:4]
    pts, sido = [], ""
    for lawd5, sd, name in SIGUNGU:
        if _SIDO_FIX.get(lawd5[:2], lawd5[:2]) + lawd5[2:4] != prefix:
            continue
        sido = sd
        c = _cached_coord(sd, name)
        if c:
            pts.append(c)
    if pts:
        return [round(sum(p[0] for p in pts) / len(pts), 5),
                round(sum(p[1] for p in pts) / len(pts), 5)]
    if sido:                       # 지오코딩 전이면 시도 중심이라도 준다
        lat, lng = _sido_centroid(sido)
        return [lat, lng]
    return None


def _with_coords(partners: list[dict]) -> list[dict]:
    out = []
    for b in partners:
        c = _coord(b["cd"])
        out.append({**b, "lat": c[0], "lng": c[1]} if c else b)
    return out


# --- 조회 -------------------------------------------------------------------
def region(lawd: str, months: int = 12) -> dict:
    """한 지역의 이동 요약 + 상대 지역 흐름 + 월별 추이."""
    from app.db import stores

    code = admm_of(lawd)
    yms = months_back(months)
    rows = stores.migration_rows(code, yms)
    out = {
        "lawd": lawd, "code": code,
        "months": sorted(yms),
        "available": bool(rows),
        **summarize(rows, code),
        **{k: _with_coords(v) for k, v in flows(rows, code).items()},
        "series": _series(rows, code, sorted(yms)),
        "note": ("전입신고 기준(행정안전부). 통합시는 시 단위로 집계되어 "
                 "구별 이동은 나오지 않습니다."),
    }
    return out


def _series(rows: list[dict], code: str, yms: list[str]) -> list[dict]:
    by: dict[str, dict] = {ym: {"ym": ym, "in": 0, "out": 0, "in_young": 0, "out_young": 0}
                           for ym in yms}
    for r in rows:
        b = by.get(r["ym"])
        if b is None or r["to_cd"] == r["from_cd"]:
            continue
        if r["to_cd"] == code:
            b["in"] += r["total"]
            b["in_young"] += r["young"]
        elif r["from_cd"] == code:
            b["out"] += r["total"]
            b["out_young"] += r["young"]
    for b in by.values():
        b["net"] = b["in"] - b["out"]
        b["net_young"] = b["in_young"] - b["out_young"]
    return [by[ym] for ym in yms]


def ranking(metric: str = "net_young", months: int = 12, limit: int = 30) -> dict:
    """순이동 순위. 청년 순이동이 기본이다 — 전체 순이동은 고령 유입에 끌려간다."""
    from app.db import stores
    return stores.migration_ranking(metric, months_back(months), limit)


def coverage() -> dict:
    """수집 진척. DB 에 실제로 들어 있는 수가 기준이다.

    ``_state`` 를 통째로 펼쳐 넣지 않는다 — 거기에도 ``rows`` 가 있어서, 저장된 전체
    행수를 **이번 프로세스가 이번에 받은 수**로 덮어썼다(40,684행이 6,451행으로 보였다).
    회차 상태는 ``run`` 아래로 따로 둔다.
    """
    from app.db import stores

    cov = stores.migration_coverage()
    target = len(SIDO) ** 2 * len(months_back(get_settings().migration_months))
    cov["target"] = target
    cov["pct"] = round(cov["pairs"] / target * 100, 1) if target else 0.0
    cov["configured"] = configured()
    cov["run"] = dict(_state)
    return cov


__all__ = ["AGE_BUCKETS", "MigrationError", "NotApprovedError", "QuotaError", "SIDO",
           "YOUNG", "admm_of", "collect_pair", "configured", "coverage", "fetch",
           "flows", "latest_month", "months_back", "parse", "ranking", "refresh",
           "region", "summarize"]
