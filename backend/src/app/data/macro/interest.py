"""지역별 부동산 **관심도** — 네이버 데이터랩 검색어 트렌드로 만든다.

왜 검색량인가
-------------
거래량은 관심의 **결과**다. 계약서를 쓰기까지 몇 주가 걸리므로, 거래량이 움직였을
때는 이미 늦었다. 검색은 그보다 먼저 튄다 — 사람들이 사기 전에 찾아보기 때문이다.
그래서 '검색은 올랐는데 거래량은 아직 안 붙은 지역' 이 이 화면이 노리는 값이다.

데이터랩의 함정 — 절대값이 없다
-------------------------------
데이터랩은 검색 **횟수**를 주지 않는다. 한 요청 안에서 가장 큰 값을 100 으로 놓은
**상대값**만 준다. 게다가 한 요청에 키워드 그룹을 5개까지만 넣을 수 있다.

여기서 사람들이 대부분 틀린다. 시군구 250곳을 50번에 나눠 부르면, 각 요청의 100 이
서로 다른 검색량을 뜻하므로 **요청이 다른 지역끼리는 비교가 성립하지 않는다.**
그냥 이어붙이면 지역 순위가 통째로 거짓이 된다.

앵커 정규화
-----------
그래서 **모든 요청에 같은 앵커 키워드를 하나 끼워 넣는다.** 요청 i 에서 앵커의
평균이 a_i 라면, 그 요청의 지역값을 a_i 로 나눈다. 남는 것은 '앵커 대비 몇 배' 라는
**요청과 무관한 축**이고, 이 축 위에서는 전국 어느 지역끼리도 비교할 수 있다.

앵커를 무엇으로 두느냐가 해상도를 정한다. 전국구 대형 키워드('아파트')를 쓰면 모든
지역값이 0.0x 로 뭉개져 소수점만 남는다. **중간 규모 지역**을 앵커로 두면 지역값이
앵커 위아래로 고르게 흩어져 차이가 보인다. 기본값을 성남시로 둔 이유다.

한 가지 더 — 앵커가 0 인 구간(검색이 아예 없던 달)은 나누면 폭발하므로 버린다.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

from app.core.config import get_settings
from app.core.jsonstore import read_json, write_json

# NAVER API HUB (네이버 클라우드 콘솔). 옛 developers.naver.com 의
# ``openapi.naver.com/v1/datalab/search`` 는 **신규 등록이 막혔다** — 앱 설정에서 고르면
# "신규로 등록할 수 없는 API" 로 거부된다. 기존 키는 2027-06-30 까지만 살아 있고,
# 새로 붙이는 쪽은 이 HUB 엔드포인트다.
#
# 인증 헤더도 다르다: Client-Id/Secret 이 아니라 NCP API 게이트웨이 키를 쓴다.
_API = "https://naverapihub.apigw.ntruss.com/search-trend/v1/search"

# 한 요청에 넣을 수 있는 키워드 그룹은 5개. 그중 하나는 앵커가 가져가므로 지역은 4개.
_GROUPS_PER_CALL = 5
_REGIONS_PER_CALL = _GROUPS_PER_CALL - 1

_lock = threading.Lock()
_warm = {"running": False, "done": 0, "total": 0, "msg": "", "started": None}


def _path() -> str:
    return str(get_settings().data_dir / "realestate_interest.json")


def configured() -> bool:
    s = get_settings()
    return bool(s.naver_client_id and s.naver_client_secret)


# --- 데이터랩 호출 ----------------------------------------------------------
class DatalabError(Exception):
    pass


def _post(body: dict) -> dict:
    s = get_settings()
    req = urllib.request.Request(
        _API,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-ncp-apigw-api-key-id": s.naver_client_id,
            "x-ncp-apigw-api-key": s.naver_client_secret,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        if e.code in (401, 403):
            # 게이트웨이가 두 가지를 구분해 준다 — 키가 틀린 건지, 상품을 안 켠 건지.
            if "subscription" in detail.lower():
                raise DatalabError(
                    "NAVER API HUB 에서 Search Trend 상품을 구독하지 않았습니다 — "
                    "ncloud 콘솔 > NAVER API HUB > 검색어 트렌드 이용 신청."
                ) from e
            raise DatalabError(
                "네이버 인증 실패 — NAVER_CLIENT_ID/SECRET 을 확인하세요. "
                "ncloud 콘솔의 API Gateway 인증키(Access Key ID / Secret)여야 합니다."
            ) from e
        if e.code == 429:
            raise DatalabError("네이버 데이터랩 호출 한도 초과 — 잠시 후 다시 시도하세요.") from e
        raise DatalabError(f"데이터랩 오류 HTTP {e.code}: {detail}") from e
    except Exception as e:  # noqa: BLE001
        raise DatalabError(f"데이터랩 접속 실패: {type(e).__name__}") from e


def _drop_partial(series: list[dict], unit: str) -> list[dict]:
    """아직 안 끝난 마지막 구간을 버린다.

    오늘이 8월 20일이면 데이터랩이 주는 8월 값은 **20일치**다. 그걸 완성된 달과
    나란히 놓으면 모든 지역의 추세가 일제히 마이너스로 나온다 — 실제로 처음 돌렸을 때
    181곳이 전부 -13~-38% 였다. 시장이 식은 게 아니라 달이 안 끝난 것이다.
    """
    if not series:
        return series
    now = time.localtime()
    cutoff = {"month": "%Y-%m-01", "week": None, "date": "%Y-%m-%d"}.get(unit)
    if not cutoff:
        return series           # 주 단위는 경계를 단정하기 어려워 손대지 않는다
    current = time.strftime(cutoff, now)
    return [p for p in series if str(p.get("period", "")) != current]


def _mean(series: list[dict]) -> float:
    vals = [float(p.get("ratio") or 0) for p in series]
    return sum(vals) / len(vals) if vals else 0.0


def _normalize(raw: list[dict], anchor_series: list[dict]) -> list[dict]:
    """구간별로 앵커와 나눈다 — 축을 맞추면서 **계절성까지 함께 걷어낸다.**

    전체 평균으로 한 번만 나누면 요청 간 비교는 되지만 계절성이 남는다. 부동산
    검색은 봄 이사철(2~4월)에 몰리고 여름에 빠지므로, 7월과 3월을 견주면 181곳이
    전부 마이너스로 나온다(처음 돌렸을 때 실제로 그랬다). 그건 시장이 식은 게 아니라
    달력이 그런 것이라 '어디가 뜨고 있나' 에 답하지 못한다.

    같은 달의 앵커로 나누면 전국이 공유하는 계절 성분이 분자·분모에서 상쇄되고,
    **그 지역만의 움직임**이 남는다. 앵커가 0 인 구간은 나눌 수 없어 건너뛴다.
    """
    amap = {str(p.get("period")): float(p.get("ratio") or 0) for p in anchor_series}
    out = []
    for p in raw:
        a = amap.get(str(p.get("period")), 0.0)
        if a <= 0:
            continue
        out.append({"period": p.get("period"),
                    "ratio": round(float(p.get("ratio") or 0) / a, 4)})
    return out


def _query(keyword_groups: list[dict], start: str, end: str, unit: str) -> dict[str, list[dict]]:
    """그룹명 → 시계열. 요청에 없던 그룹(검색량 0)은 응답에서 빠지므로 채워 넣는다."""
    res = _post({
        "startDate": start, "endDate": end, "timeUnit": unit,
        "keywordGroups": keyword_groups,
    })
    out = {g["groupName"]: [] for g in keyword_groups}
    for row in res.get("results", []):
        out[row.get("title", "")] = row.get("data", [])
    return out


# --- 수집 ------------------------------------------------------------------
# 시도를 앞에 붙일 때 쓰는 짧은 이름. 사람들이 실제로 검색하는 말이어야 해서
# '서울특별시 강서구' 가 아니라 '서울 강서구' 로 만든다.
_SIDO_SHORT = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
    "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종",
    "경기도": "경기", "강원특별자치도": "강원", "강원도": "강원",
    "충청북도": "충북", "충청남도": "충남", "전라북도": "전북",
    "전북특별자치도": "전북", "전라남도": "전남", "경상북도": "경북", "경상남도": "경남",
    "제주특별자치도": "제주",
}

# 여러 시도에 같은 이름이 있는 시군구. 이것들만 시도를 붙인다 — 안 겹치는 지역까지
# 붙이면 '서울 노원구 아파트' 처럼 아무도 안 치는 말이 되어 검색량이 깎인다.
_AMBIGUOUS = {
    "중구", "동구", "서구", "남구", "북구", "강서구", "성산구", "고성군",
    "남원시", "동면", "일산동구", "일산서구", "단원구", "상록구",
}


def _keyword(region: str, sido: str = "") -> str:
    """'강남구' → '강남구 아파트'. 지역명만 쓰면 맛집·날씨 검색까지 섞인다.

    이름이 겹치는 시군구는 시도를 붙여 가른다. 붙이지 않으면 서울 강서구와 부산
    강서구가 **같은 키워드**가 되어 두 지역에 똑같은 값이 들어간다(실제로 그랬다).
    """
    if region in _AMBIGUOUS and sido:
        return f"{_SIDO_SHORT.get(sido, sido)} {region} 아파트"
    return f"{region} 아파트"


def collect(regions: list[dict], *, months: int = 12,
            unit: str = "month", pause: float = 0.3) -> dict:
    """시군구 목록 → 앵커로 정규화한 관심도.

    ``regions``: ``[{lawd, sido, region}, …]`` (지도 스냅샷의 그 모양 그대로)
    """
    if not configured():
        raise DatalabError("NAVER_CLIENT_ID/NAVER_CLIENT_SECRET 미설정")
    if not regions:
        raise DatalabError("대상 지역이 없습니다 — 실거래 지도가 먼저 채워져야 합니다.")

    s = get_settings()
    anchor_kw = s.naver_interest_anchor
    end = time.strftime("%Y-%m-%d")
    start = time.strftime("%Y-%m-%d", time.localtime(time.time() - months * 31 * 86400))

    chunks = [regions[i:i + _REGIONS_PER_CALL]
              for i in range(0, len(regions), _REGIONS_PER_CALL)]
    _warm.update({"total": len(chunks), "done": 0})

    items: list[dict] = []
    dropped: list[str] = []
    for chunk in chunks:
        groups = [{"groupName": "__anchor__", "keywords": [anchor_kw]}]
        groups += [{"groupName": r["lawd"], "keywords": [_keyword(r["region"], r.get("sido", ""))]}
                   for r in chunk]

        series = _query(groups, start, end, unit)
        # 앵커도 같은 구간으로 잘라야 한다 — 한쪽만 미완성 달을 품으면 축이 틀어진다.
        anchor_series = _drop_partial(series.get("__anchor__", []), unit)
        anchor = _mean(anchor_series)
        if anchor <= 0:
            # 앵커가 0 이면 이 요청의 값들은 다른 요청과 이을 축이 없다. 지어내지 않고 버린다.
            dropped += [r["lawd"] for r in chunk]
            _warm["done"] += 1
            continue

        for r in chunk:
            raw = _drop_partial(series.get(r["lawd"], []), unit)
            ser = _normalize(raw, anchor_series)
            items.append({
                "lawd": r["lawd"], "sido": r["sido"], "region": r["region"],
                "keyword": _keyword(r["region"], r.get("sido", "")),
                # 앵커 대비 배수 — 요청이 달라도 같은 축 위에 놓인다.
                "index": round(_mean(ser), 4),
                "series": ser,
            })
        _warm["done"] += 1
        if pause:
            time.sleep(pause)      # 한도를 아끼려고 살살 두드린다

    _rank(items)
    data = {
        "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "anchor": anchor_kw,
        "unit": unit,
        "period": {"start": start, "end": end},
        "count": len(items),
        "dropped": dropped,
        "items": items,
    }
    with _lock:
        write_json(_path(), data)
    return data


def _rank(items: list[dict]) -> None:
    """순위와 최근 추세를 붙인다 — 화면이 '어디가 뜨고 있나' 를 바로 말할 수 있게."""
    for it in items:
        ser = it["series"]
        # 최근 3구간 대비 그 앞 3구간 — 한 달만 보면 계절성·튐에 흔들린다.
        recent = [p["ratio"] for p in ser[-3:]]
        before = [p["ratio"] for p in ser[-6:-3]]
        if recent and before and sum(before) > 0:
            it["trend_pct"] = round((sum(recent) / sum(before) - 1) * 100, 1)
        else:
            it["trend_pct"] = None
    for rank, it in enumerate(sorted(items, key=lambda x: -x["index"]), 1):
        it["rank"] = rank


# --- 조회 ------------------------------------------------------------------
def snapshot() -> dict:
    """저장된 관심도. 없으면 왜 없는지 말해 준다(빈 화면을 그냥 두지 않는다)."""
    data = read_json(_path(), None)
    if data:
        return {"ready": True, "warming": _warm["running"], **data, **_note()}
    if not configured():
        msg = ("네이버 검색 API 키가 없습니다 — developers.naver.com 에서 애플리케이션을 "
               "등록하고 NAVER_CLIENT_ID/NAVER_CLIENT_SECRET 을 backend/.env 에 넣으세요.")
    elif _warm["running"]:
        msg = f"검색 관심도 수집 중… ({_warm['done']}/{_warm['total']})"
    else:
        msg = _warm["msg"] or "아직 수집 전입니다. '관심도 수집' 을 눌러 주세요."
    return {"ready": False, "warming": _warm["running"], "message": msg,
            "items": [], "count": 0, **_note()}


def _note() -> dict:
    return {
        "source": "네이버 데이터랩 검색어 트렌드",
        "note": ("검색량은 절대 횟수가 아니라 앵커 키워드 대비 배수다. 요청마다 100 의 기준이 "
                 "달라지는 데이터랩 특성 때문에, 모든 요청에 같은 앵커를 넣고 **같은 달의 앵커"
                 "값으로** 나눈다. 그러면 요청 간 축이 맞을 뿐 아니라 봄 이사철 같은 전국 공통 "
                 "계절성도 상쇄돼, 추세가 그 지역만의 움직임을 가리킨다. 아직 안 끝난 이번 "
                 "달은 집계가 덜 돼 빼고 센다."),
    }


# --- 백그라운드 수집 --------------------------------------------------------
def start_warm(regions: list[dict], *, months: int = 12) -> dict:
    """수집을 백그라운드로 돌린다 — 250곳이면 60여 번 호출이라 요청 안에서 못 끝낸다."""
    if _warm["running"]:
        return {"started": False, "reason": "이미 수집 중입니다.", **status()}
    if not configured():
        return {"started": False, "reason": "NAVER_CLIENT_ID/NAVER_CLIENT_SECRET 미설정"}

    def _run() -> None:
        _warm.update({"running": True, "msg": "", "started": time.strftime("%Y-%m-%d %H:%M:%S")})
        try:
            data = collect(regions, months=months)
            _warm["msg"] = f'{data["count"]}곳 수집 완료'
        except DatalabError as e:
            _warm["msg"] = str(e)
        except Exception as e:  # noqa: BLE001
            _warm["msg"] = f"{type(e).__name__}: {str(e)[:120]}"
        finally:
            _warm["running"] = False

    threading.Thread(target=_run, daemon=True, name="interest-warm").start()
    return {"started": True, **status()}


def status() -> dict:
    return {"configured": configured(), **_warm}


__all__ = ["DatalabError", "collect", "configured", "snapshot", "start_warm", "status"]
