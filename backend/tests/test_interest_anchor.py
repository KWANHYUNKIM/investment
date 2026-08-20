"""지역 관심도 — 앵커 정규화가 맞는가.

데이터랩은 **요청마다** 최대값을 100 으로 잡는 상대값만 준다. 그래서 시군구를
5개씩 나눠 부르면 요청이 다른 지역끼리는 축이 달라 비교가 성립하지 않는다.
여기서 틀리면 화면의 지역 순위가 통째로 거짓이 되므로, 그 한 가지를 고정한다.
"""
from __future__ import annotations

import pytest

from app.data.macro import interest as I


REGIONS = [
    {"lawd": "11680", "sido": "서울", "region": "강남구"},
    {"lawd": "11650", "sido": "서울", "region": "서초구"},
    {"lawd": "41135", "sido": "경기", "region": "성남분당구"},
    {"lawd": "41111", "sido": "경기", "region": "수원장안구"},
    {"lawd": "26350", "sido": "부산", "region": "해운대구"},
]


def _series(*vals: float) -> list[dict]:
    return [{"period": f"2026-0{i + 1}-01", "ratio": v} for i, v in enumerate(vals)]


@pytest.fixture
def creds(monkeypatch):
    """설정만 채운다 — 네트워크는 _query 를 갈아끼워 막는다."""
    from app.core.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "naver_client_id", "id", raising=False)
    monkeypatch.setattr(s, "naver_client_secret", "secret", raising=False)
    monkeypatch.setattr(s, "naver_interest_anchor", "성남시 아파트", raising=False)
    return s


def test_two_calls_are_put_on_one_axis(creds, monkeypatch, tmp_path):
    """핵심. 요청이 달라도 '앵커 대비 배수' 로 바꾸면 서로 비교할 수 있어야 한다.

    1차 요청에서는 강남이 최대(100)라 앵커가 50 으로 찍히고,
    2차 요청에서는 해운대가 최대(100)라 앵커가 25 로 찍힌다 —
    **같은 앵커인데 숫자가 다르다.** 그대로 이으면 해운대가 강남보다 커 보인다.
    앵커로 나누면 강남 2.0 배 / 해운대 4.0 배로 제자리를 찾는다.
    """
    calls = []

    def fake_query(groups, start, end, unit):
        calls.append([g["groupName"] for g in groups])
        if len(calls) == 1:      # 앵커 50, 강남 100, 서초 75, 분당 25
            return {"__anchor__": _series(50, 50), "11680": _series(100, 100),
                    "11650": _series(75, 75), "41135": _series(25, 25),
                    "41111": _series(10, 10)}
        return {"__anchor__": _series(25, 25), "26350": _series(100, 100)}

    monkeypatch.setattr(I, "_query", fake_query)
    monkeypatch.setattr(I, "_path", lambda: str(tmp_path / "interest.json"))

    data = I.collect(REGIONS, months=2, pause=0)
    idx = {it["lawd"]: it["index"] for it in data["items"]}

    assert idx["11680"] == 2.0      # 강남 100/50
    assert idx["26350"] == 4.0      # 해운대 100/25 — 요청이 달라도 축이 같다
    assert idx["26350"] > idx["11680"]


def test_anchor_rides_in_every_request(creds, monkeypatch, tmp_path):
    """앵커를 한 요청이라도 빠뜨리면 그 요청은 이어붙일 축이 없다."""
    seen = []

    def fake_query(groups, start, end, unit):
        seen.append([g["groupName"] for g in groups])
        return {g["groupName"]: _series(10, 10) for g in groups}

    monkeypatch.setattr(I, "_query", fake_query)
    monkeypatch.setattr(I, "_path", lambda: str(tmp_path / "interest.json"))
    I.collect(REGIONS, months=2, pause=0)

    assert len(seen) == 2                       # 5곳 → 4+1 씩 두 번
    assert all(names[0] == "__anchor__" for names in seen)
    assert all(len(names) <= 5 for names in seen)   # 데이터랩 그룹 상한


def test_zero_anchor_is_dropped_not_divided(creds, monkeypatch, tmp_path):
    """앵커가 0 인 요청을 나누면 값이 폭발한다. 지어내지 말고 버려야 한다."""
    def fake_query(groups, start, end, unit):
        return {g["groupName"]: (_series(0, 0) if g["groupName"] == "__anchor__"
                                 else _series(80, 80)) for g in groups}

    monkeypatch.setattr(I, "_query", fake_query)
    monkeypatch.setattr(I, "_path", lambda: str(tmp_path / "interest.json"))
    data = I.collect(REGIONS, months=2, pause=0)

    assert data["items"] == []
    assert set(data["dropped"]) == {r["lawd"] for r in REGIONS}


def test_missing_group_means_zero_not_crash(creds, monkeypatch, tmp_path):
    """검색량이 0 인 지역은 응답에서 통째로 빠진다 — 그 지역을 잃어버리면 안 된다."""
    def fake_query(groups, start, end, unit):
        out = {"__anchor__": _series(40, 40)}
        for g in groups[1:]:
            if g["groupName"] != "11650":       # 서초만 응답에서 누락
                out[g["groupName"]] = _series(20, 20)
        return {**{g["groupName"]: [] for g in groups}, **out}

    monkeypatch.setattr(I, "_query", fake_query)
    monkeypatch.setattr(I, "_path", lambda: str(tmp_path / "interest.json"))
    data = I.collect(REGIONS, months=2, pause=0)

    idx = {it["lawd"]: it["index"] for it in data["items"]}
    assert idx["11650"] == 0.0                  # 빠진 지역은 0, 사라지지 않는다
    assert len(data["items"]) == len(REGIONS)


def test_trend_compares_recent_three_to_previous_three(creds, monkeypatch, tmp_path):
    """한 달만 보면 계절성·튐에 흔들린다. 3구간씩 묶어서 본다."""
    def fake_query(groups, start, end, unit):
        out = {"__anchor__": _series(10, 10, 10, 10, 10, 10)}
        for g in groups[1:]:
            out[g["groupName"]] = _series(10, 10, 10, 20, 20, 20)   # 뒤 3구간이 2배
        return out

    monkeypatch.setattr(I, "_query", fake_query)
    monkeypatch.setattr(I, "_path", lambda: str(tmp_path / "interest.json"))
    data = I.collect(REGIONS, months=6, pause=0)

    assert data["items"][0]["trend_pct"] == 100.0


def test_keyword_pins_the_topic(creds):
    """'강남구' 만 쓰면 맛집·날씨 검색이 섞인다 — 부동산으로 못박는다."""
    assert I._keyword("강남구") == "강남구 아파트"


def test_duplicate_region_names_are_split_by_sido(creds):
    """실측에서 터진 버그 — 서울 강서구와 부산 강서구가 같은 6.75배를 받았다.

    키워드가 '강서구 아파트' 하나라 두 지역이 **같은 검색량**을 나눠 가진 것이다.
    이름이 겹치는 시군구는 시도를 붙여 갈라야 한다.
    """
    seoul = I._keyword("강서구", "서울특별시")
    busan = I._keyword("강서구", "부산광역시")
    assert seoul != busan
    assert seoul == "서울 강서구 아파트"
    assert busan == "부산 강서구 아파트"


def test_unambiguous_region_keeps_the_bare_name(creds):
    """안 겹치는 지역까지 시도를 붙이면 아무도 안 치는 말이 되어 검색량이 깎인다."""
    assert I._keyword("노원구", "서울특별시") == "노원구 아파트"
    assert I._keyword("하남시", "경기도") == "하남시 아파트"


def test_incomplete_current_month_is_dropped(creds):
    """오늘이 20일이면 이번 달 값은 20일치다. 완성된 달과 나란히 두면 전 지역이
    일제히 마이너스로 나온다 — 시장이 식은 게 아니라 달이 안 끝난 것이다."""
    import time
    current = time.strftime("%Y-%m-01")
    ser = [{"period": "2026-01-01", "ratio": 50}, {"period": current, "ratio": 9}]
    assert I._drop_partial(ser, "month") == [{"period": "2026-01-01", "ratio": 50}]


def test_seasonality_cancels_out(creds):
    """봄 이사철처럼 **전국이 함께 겪는** 오르내림은 추세에서 빠져야 한다.

    지역과 앵커가 똑같은 계절 곡선을 그리면 그 지역은 '변화 없음'이어야 한다.
    전체 평균으로 한 번만 나누면 여기서 -50% 가 찍혔다.
    """
    season = [100, 100, 100, 50, 50, 50]        # 봄 성수기 → 여름 비수기
    anchor = [{"period": f"2026-0{i + 1}-01", "ratio": v} for i, v in enumerate(season)]
    region = [{"period": f"2026-0{i + 1}-01", "ratio": v * 3} for i, v in enumerate(season)]

    out = I._normalize(region, anchor)
    assert [p["ratio"] for p in out] == [3.0] * 6      # 계절 성분이 상쇄된다

    items = [{"index": I._mean(out), "series": out}]
    I._rank(items)
    assert items[0]["trend_pct"] == 0.0


def test_period_missing_from_anchor_is_skipped(creds):
    """앵커에 없는 구간은 나눌 수가 없다 — 지어내지 않고 건너뛴다."""
    anchor = [{"period": "2026-01-01", "ratio": 10}]
    region = [{"period": "2026-01-01", "ratio": 20}, {"period": "2026-02-01", "ratio": 99}]
    assert I._normalize(region, anchor) == [{"period": "2026-01-01", "ratio": 2.0}]


def test_collect_without_credentials_refuses(monkeypatch):
    monkeypatch.setattr(I, "configured", lambda: False)
    with pytest.raises(I.DatalabError):
        I.collect(REGIONS, months=2, pause=0)
