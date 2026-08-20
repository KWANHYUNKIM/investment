"""지역 상권 — 업종 구성으로 **그 동네가 무엇을 하는 곳인지** 읽는다.

무엇을 재는가
-------------
점포 총수만으로는 "사람이 많은 곳" 밖에 모른다. 업종 구성을 보면 성격이 나온다 —
사무실 밀집지는 과학기술·시설관리가 두껍고, 주거지는 학원·병원·미용실이 두껍다.

실측으로 확인했다. (과학기술+시설관리) / (교육+보건의료+수리개인) 이

    종로 1.74 · 강남 1.69 · 마포 1.27 · 강서 0.83 · 분당 0.61 · 노원 0.36

업무지역부터 순수 주거지역까지 한 줄로 늘어선다. 지어낸 지표가 아니라 아는 동네에
대 보고 맞는 것을 확인한 뒤에 쓴다.

왜 부동산에 쓰나
----------------
같은 값이라도 성격이 다르면 가격이 다르게 움직인다. 업무지역은 일자리에, 주거지역은
학군·교통에 반응한다. 상권이 커지는 중인지(음식·소매 증가) 비는 중인지도 가격보다
먼저 움직인다.

어떻게 세는가
-------------
소상공인시장진흥공단 상가(상권)정보 API 를 쓴다. 전량을 받으면 감당이 안 되므로
(역삼1동 하나가 14,077개) **``totalCount`` 만 읽는다** — ``numOfRows=1`` 로 부르면
개수만 돌아온다. 시군구 × 업종 10개 = 2,500콜이고, 원본이 분기 갱신이라 한 번 받으면
한동안 유효하다.

호출 형태를 찾는 데 시행착오가 있었다. 기록해 둔다.

    storeListInArea  divId=signguCd   → NODATA (여긴 상권코드 전용이다)
    storeListInUpjong 지역 파라미터    → **무시된다**(강남·노원이 같은 전국값을 준다)
    storeListInDong  divId=signguCd   → **된다**. indsLclsCd 필터도 먹는다
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from app.core.config import get_settings
from app.data.infra.lawd_codes import SIGUNGU

_API = "https://apis.data.go.kr/B553077/api/open/sdsc2/storeListInDong"

# 업종 대분류. 코드는 실제 응답에서 뽑았다(2023 개편 체계).
CATEGORIES: tuple[tuple[str, str], ...] = (
    ("G2", "소매"), ("I1", "숙박"), ("I2", "음식"), ("L1", "부동산"),
    ("M1", "과학·기술"), ("N1", "시설관리·임대"), ("P1", "교육"),
    ("Q1", "보건의료"), ("R1", "예술·스포츠"), ("S2", "수리·개인"),
)
_NAMES = dict(CATEGORIES)

# 성격 판별에 쓰는 두 묶음.
#   업무: 사무실이 있어야 존재하는 업종 — 법무·회계·컨설팅(과학기술), 임대·시설관리
#   생활: 사람이 살아야 존재하는 업종 — 학원·병원·미용실·세탁
_WORK = ("M1", "N1")
_LIVE = ("P1", "Q1", "S2")

_lock = threading.Lock()
_state = {"running": False, "filled": 0, "last_run": None, "msg": ""}


class CommerceError(Exception):
    pass


def configured() -> bool:
    return bool(get_settings().data_go_kr_key)


# --- 수집 -------------------------------------------------------------------
def count_stores(sigungu_cd: str, category: str | None = None) -> int | None:
    """시군구(+업종)의 점포 수. 실패하면 ``None`` — 0 과 구분해야 한다.

    0 은 '그 업종이 없다', None 은 '못 받았다' 이다. 섞으면 수집이 덜 된 지역이
    '상권이 없는 지역' 으로 보인다.
    """
    key = get_settings().data_go_kr_key
    if not key:
        return None
    params = {"divId": "signguCd", "key": sigungu_cd, "numOfRows": "1",
              "pageNo": "1", "type": "json", "serviceKey": key}
    if category:
        params["indsLclsCd"] = category
    url = f"{_API}?{urllib.parse.urlencode(params, safe='%')}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            d = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise CommerceError("data.go.kr 호출 한도 초과") from e
        return None
    except Exception:  # noqa: BLE001
        return None

    code = (d.get("header") or {}).get("resultCode")
    if code == "03":            # NODATA — 그 업종이 정말 없는 경우
        return 0
    if code != "00":
        return None
    return (d.get("body") or {}).get("totalCount")


# --- 판정 -------------------------------------------------------------------
def classify(counts: dict[str, int]) -> dict:
    """업종 구성 → 성격. 비율과 지수를 함께 돌려준다.

    경계값(1.2 / 0.7)은 실측 여섯 지역이 늘어선 자리에서 잡았다. 종로 1.74·강남 1.69 와
    노원 0.36 사이에 마포 1.27·강서 0.83·분당 0.61 이 있어, 그 사이를 가른다.
    임의로 0.5·1.0 같은 둥근 수를 쓰지 않은 이유다.
    """
    total = sum(counts.values())
    if not total:
        return {"total": 0, "shares": {}, "work_index": None,
                "character": "자료 없음", "note": "점포 자료가 없습니다."}

    work = sum(counts.get(c, 0) for c in _WORK)
    live = sum(counts.get(c, 0) for c in _LIVE)
    idx = round(work / live, 2) if live else None

    if idx is None:
        character = "판단 보류"
    elif idx >= 1.2:
        character = "업무·상업"
    elif idx >= 0.7:
        character = "혼합"
    else:
        character = "주거"

    return {
        "total": total,
        "shares": {c: round(counts.get(c, 0) * 100 / total, 1) for c, _ in CATEGORIES},
        "work_index": idx,
        "character": character,
        "note": ("업무지수 = (과학·기술 + 시설관리·임대) ÷ (교육 + 보건의료 + 수리·개인). "
                 "사무실이 있어야 존재하는 업종과 사람이 살아야 존재하는 업종의 비다."),
    }


# --- 저장 -------------------------------------------------------------------
def load() -> dict:
    """``{lawd: {category_code: count}}`` — 저장된 것만 읽는다."""
    from app.db import stores
    return stores.commerce_load()


def save(cells: dict) -> None:
    from app.db import stores
    stores.commerce_save(cells)


def missing() -> list[tuple[str, str]]:
    """아직 못 받은 (시군구, 업종) 칸."""
    have = load()
    out = []
    for lawd, _sido, _name in SIGUNGU:
        got = have.get(lawd, {})
        for code, _ in CATEGORIES:
            if code not in got:
                out.append((lawd, code))
    return out


def refresh(budget: int | None = None) -> dict:
    """예산만큼만 채운다 — 실거래 집계와 같은 한도를 나눠 쓴다.

    상권 자료는 분기 갱신이라 한 번 받으면 한동안 유효하다. 그래서 실거래처럼
    되받는 주기를 따로 두지 않고, 빈 칸만 채운다.
    """
    s = get_settings()
    budget = int(budget or s.commerce_budget)
    # 지난 회차 메시지를 지운다 — 안 지우면 아래 `if not msg` 가 매번 막혀서
    # 화면에 몇 시간 전 진행률이 계속 걸린다.
    _state["msg"] = ""
    todo = missing()[:budget]
    if not todo:
        _state["msg"] = "채울 칸 없음"
        return {"filled": 0, "gaps": 0, "note": _state["msg"]}

    have = load()
    filled = failed = 0
    now = int(time.time())
    hit_limit = False
    for lawd, code in todo:
        try:
            n = count_stores(lawd, code)
        except CommerceError:
            # 일 한도 초과. 여기서 예외를 그대로 올리면 **이번 회차에 받아 둔 칸이
            # 통째로 버려진다**(save 가 루프 뒤에 있다). 받은 것까지는 남긴다.
            hit_limit = True
            break
        if n is None:
            failed += 1
            if failed >= 20:        # 연속 실패는 대개 한도 초과다
                _state["msg"] = "연속 실패 — 이번 회차 중단"
                break
            continue
        failed = 0
        have.setdefault(lawd, {})[code] = {"count": int(n), "at": now}
        filled += 1

    with _lock:
        save(have)
    remaining = max(0, len(missing()))
    _state.update({"filled": _state["filled"] + filled,
                   "last_run": time.strftime("%Y-%m-%d %H:%M:%S")})
    if hit_limit:
        _state["msg"] = f"{filled}칸 채움 · 일 한도 초과로 중단 · {remaining}칸 남음"
    if not _state["msg"]:
        _state["msg"] = f"{filled}칸 채움 · {remaining}칸 남음"
    return {"filled": filled, "gaps": remaining, "note": _state["msg"]}


# --- 조회 -------------------------------------------------------------------
def region(lawd: str) -> dict:
    """한 시군구의 상권 구성 + 성격."""
    got = {k: v["count"] for k, v in (load().get(lawd) or {}).items()}
    out = classify(got)
    return {
        "lawd": lawd,
        "available": bool(got),
        "counts": [{"code": c, "name": n, "count": got.get(c, 0),
                    "share": out["shares"].get(c, 0.0)}
                   for c, n in CATEGORIES if c in got],
        **out,
    }


def ranking(character: str | None = None, limit: int = 30) -> dict:
    """업무지수 순위. 성격이 같은 지역끼리 비교하려는 화면을 위해 필터를 둔다."""
    have = load()
    names = {lawd: (sido, name) for lawd, sido, name in SIGUNGU}
    rows = []
    for lawd, cells in have.items():
        counts = {k: v["count"] for k, v in cells.items()}
        if len(counts) < len(CATEGORIES):
            continue            # 덜 받은 지역을 섞으면 순위가 거짓이 된다
        c = classify(counts)
        if character and c["character"] != character:
            continue
        sido, name = names.get(lawd, ("", lawd))
        rows.append({"lawd": lawd, "sido": sido, "region": name,
                     "total": c["total"], "work_index": c["work_index"],
                     "character": c["character"]})
    rows.sort(key=lambda r: -(r["work_index"] or 0))
    return {"count": len(rows), "items": rows[:limit]}


def coverage() -> dict:
    total = len(SIGUNGU) * len(CATEGORIES)
    have = sum(len(v) for v in load().values())
    return {"have": have, "total": total,
            "pct": round(have / total * 100, 1) if total else 0.0,
            "configured": configured(), **_state}


__all__ = ["CATEGORIES", "CommerceError", "classify", "count_stores", "coverage",
           "load", "missing", "ranking", "refresh", "region", "save"]
