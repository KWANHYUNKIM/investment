"""인구이동 API 가 실제로 어떻게 대답하는지 확인한다.

활용신청이 승인되는 순간 이걸 먼저 돌린다. 명세만으로는 알 수 없는 두 가지 —

1. 전출지를 비우면 '전체' 로 받아 주는가? 안 되면 지역 쌍(250×250)을 다 불러야 해서
   수집 전략이 완전히 달라진다.
2. 행정기관코드가 법정동코드 10자리(1168000000)인가, 행정표준코드(3220000)인가?

둘 다 답이 나오기 전에는 수집기를 쓰지 않는다. 추측으로 짜면 승인 직후에 다시 짜야 한다.

    python -m scripts.probe_migration
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

from app.core.config import get_settings
from app.data.macro import migration as M

# 강남구를 후보 코드 체계별로. 하나만 답하면 그게 이 API 의 코드 체계다.
CANDIDATES = {
    "법정동 10자리": "1168000000",
    "법정동 5자리": "11680",
    "행정표준코드": "3220000",
}
FR, TO = "202603", "202605"      # 3개월 — API 상한


def _call(**kw) -> str:
    p = {"serviceKey": get_settings().data_go_kr_key, "type": "JSON",
         "numOfRows": "3", "pageNo": "1", "srchFrYm": FR, "srchToYm": TO, "lv": "2"}
    p.update(kw)
    url = f"{M._API}?{urllib.parse.urlencode(p, safe='%')}"
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            return r.read().decode("utf-8")
    except Exception as e:  # noqa: BLE001
        return f"ERR {e}"


def _verdict(raw: str) -> str:
    if raw.startswith("ERR"):
        if "403" in raw:
            return "403 - 활용신청 미승인 (https://www.data.go.kr/data/15108093/openapi.do)"
        return raw[:100]
    try:
        rows = M.parse(raw)
    except M.MigrationError as e:
        return f"거절: {e}"
    if not rows:
        return "0건"
    r = rows[0]
    return f"{len(rows)}건 · 예: {r['from_name']} → {r['to_name']} {r['total']}명"


def main() -> None:
    if not M.configured():
        print("DATA_GO_KR_KEY 가 없습니다.")
        return

    print("[1] 코드 체계 - 어떤 형식을 받아 주는가")
    for label, cd in CANDIDATES.items():
        print(f"  {label:<12} {_verdict(_call(mvinAdmmCd=cd, mvtAdmmCd=''))}")

    print("\n[2] 전출지 '전체' 가 되는가 (되면 250콜, 안 되면 62,500콜)")
    for label, mvt in (("빈 문자열", ""), ("전국", "0000000000"), ("생략", None)):
        kw = {"mvinAdmmCd": "1168000000"}
        if mvt is not None:
            kw["mvtAdmmCd"] = mvt
        print(f"  {label:<12} {_verdict(_call(**kw))}")

    print("\n[3] lv 별 응답 단위")
    for lv in ("1", "2", "3"):
        raw = _call(mvinAdmmCd="1168000000", mvtAdmmCd="", lv=lv)
        print(f"  lv={lv} {_verdict(raw)}")

    print("\n[4] 원본 한 줄 (필드 확인용)")
    raw = _call(mvinAdmmCd="1168000000", mvtAdmmCd="", numOfRows="1")
    if not raw.startswith("ERR"):
        print(json.dumps(json.loads(raw), ensure_ascii=False)[:1200])


if __name__ == "__main__":
    main()
