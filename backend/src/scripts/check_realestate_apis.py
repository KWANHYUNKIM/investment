"""부동산 실거래 공공데이터(data.go.kr) 활용신청·한도 점검.

지도가 유형별로 왜 비어 있는지는 **키 문제냐, 승인 문제냐, 한도 문제냐** 셋 중 하나다.
이 스크립트가 한 시군구·한 달로 각 서비스를 한 번씩 때려 보고 그 셋을 갈라 준다.
data.go.kr 에서 활용신청하거나 트래픽을 늘린 뒤 다시 돌리면 바뀐 결과가 바로 보인다.

승인은 대개 즉시(자동승인)지만 **키 반영에 1~2시간** 걸리는 경우가 있다. 403 이 남아
있으면 조금 뒤 다시 돌려 볼 것.

사용:
    python -m scripts.check_realestate_apis                 # 강남구·완성 최신월
    python -m scripts.check_realestate_apis --lawd 30170    # 대전 서구
    python -m scripts.check_realestate_apis --ym 202605
"""
from __future__ import annotations

import argparse

from app.core.config import get_settings
from app.data.macro import rtms

# 서비스별 data.go.kr 검색어 — 목록에서 이 이름으로 찾아 활용신청한다.
SEARCH_NAME = {
    ("apt", "sale"): "국토교통부_아파트 매매 실거래가 자료",
    ("apt", "rent"): "국토교통부_아파트 전월세 실거래가 자료",
    ("offi", "sale"): "국토교통부_오피스텔 매매 실거래가 자료",
    ("offi", "rent"): "국토교통부_오피스텔 전월세 실거래가 자료",
    ("rh", "sale"): "국토교통부_연립다세대 매매 실거래가 자료",
    ("rh", "rent"): "국토교통부_연립다세대 전월세 실거래가 자료",
    ("sh", "sale"): "국토교통부_단독/다가구 매매 실거래가 자료",
    ("sh", "rent"): "국토교통부_단독/다가구 전월세 실거래가 자료",
    ("nrg", "sale"): "국토교통부_상업업무용 부동산 매매 신고 자료",
    ("land", "sale"): "국토교통부_토지 매매 신고 조회 서비스",
    ("silv", "sale"): "국토교통부_분양권전매 신고 자료",
}


def _verdict(ok: bool, why: str, n: int) -> tuple[str, str]:
    """(판정, 다음에 할 일)."""
    if ok:
        return "정상", f"{n}건"
    w = (why or "").upper()
    if "429" in w or "한도" in why or "LIMITED" in w:
        return "한도초과", "트래픽 증가 신청 필요"
    if "403" in w:
        return "미승인", "data.go.kr 활용신청 필요"
    if "미설정" in why:
        return "키없음", "backend/.env 의 DATA_GO_KR_KEY 설정"
    if "없습니다" in why:
        return "해당없음", "공공데이터에 이 조합이 없음"
    return "실패", why[:40]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lawd", default="11680", help="시군구 법정동코드 5자리(기본 서울 강남구)")
    ap.add_argument("--ym", default=None, help="YYYYMM(기본: 완성 최신월)")
    args = ap.parse_args()

    if not get_settings().data_go_kr_key:
        print("DATA_GO_KR_KEY 가 없습니다 — backend/.env 를 먼저 채우세요.")
        return

    ym = args.ym or rtms.recent_months(2)[0]
    print(f"기준: 시군구 {args.lawd} · {ym[:4]}년 {ym[4:]}월\n")
    print(f"{'유형':<12}{'구분':<6}{'판정':<10}{'다음에 할 일':<26}검색어")
    print("-" * 108)

    todo_apply: list[str] = []
    todo_quota: list[str] = []

    for kind, spec in rtms.KINDS.items():
        for mode in ("sale", "rent"):
            label = spec["label"]
            mode_ko = "매매" if mode == "sale" else "전월세"
            if not spec.get(mode):
                print(f"{label:<12}{mode_ko:<6}{'해당없음':<10}{'공공데이터에 없음':<26}—")
                continue
            out, ok, why = rtms._fetch(kind, mode, args.lawd, ym)
            verdict, todo = _verdict(ok, why, len(out))
            name = SEARCH_NAME.get((kind, mode), "")
            print(f"{label:<12}{mode_ko:<6}{verdict:<10}{todo:<26}{name}")
            if verdict == "미승인":
                todo_apply.append(name)
            elif verdict == "한도초과":
                todo_quota.append(name)

    if todo_apply:
        print("\n■ data.go.kr 에서 '활용신청' 할 것 — 아래 이름으로 검색")
        for n in todo_apply:
            print(f"   · {n}")
    if todo_quota:
        print("\n■ 트래픽(호출한도) 증가 신청할 것")
        print("   마이페이지 → 오픈API → 개발계정 → 해당 API → '트래픽 증가 신청'")
        for n in todo_quota:
            print(f"   · {n}")
    if not todo_apply and not todo_quota:
        print("\n모두 정상 — 지도에서 매물 종류 탭이 전부 살아 있습니다.")


if __name__ == "__main__":
    main()
