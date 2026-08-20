"""Business logic for the macro domain.

Pure delegation: every method calls the same ``app.data.macro`` snapshot
function the legacy endpoint called, unchanged. ``korea_diagnosis`` and
``realestate_map`` are imported lazily *inside* their methods — exactly as the
legacy router did — because they are heavy modules (ECOS scans / geocoding)
that must not be paid for at import time. Never depends on FastAPI.
"""
from __future__ import annotations

from app.data.macro import korea_flow
from app.data.macro import money_analysis
from app.data.macro import money_supply
from app.data.macro import realeconomy
from app.data.macro import realestate
from app.data.macro import rent
from app.data.macro import ecos


class MacroService:
    def korea_flow(self) -> dict:
        return korea_flow.snapshot()

    def korea_diagnosis(self) -> dict:
        from . import korea_diagnosis
        return korea_diagnosis.diagnosis()

    def realestate_trades(self) -> dict:
        return realestate.snapshot()

    def realestate_map(self) -> dict:
        from app.data.macro import realestate_map
        return realestate_map.map_snapshot()

    def realestate_region_series(self, lawd: str) -> dict:
        """한 시군구의 월별 거래량·평균가 + 같은 기간 검색 관심도.

        거래(후행)와 검색(선행)을 **한 그래프 위에** 올려야 시차가 보인다. 따로 두면
        '검색이 먼저 움직였다' 를 눈으로 확인할 방법이 없다.
        """
        from app.data.macro import interest, realestate
        # 저장된 것만 읽는다 — 지역을 누를 때마다 전국 1,500콜이 돌면 화면이 멈춘다.
        snap = realestate.region_series(lawd)
        series = snap.get("months") or []

        board = interest.snapshot()
        item = next((i for i in board.get("items", []) if i["lawd"] == lawd), None)
        # 관심도는 'YYYY-MM-01', 거래는 'YYYYMM' — 거래 쪽 키에 맞춰 붙인다.
        heat = {str(p["period"])[:7].replace("-", ""): p["ratio"]
                for p in (item or {}).get("series", [])}

        return {
            "lawd": lawd,
            "available": bool(series),
            "reason": None if series else (snap.get("reason") or "이 지역의 월별 실거래가 아직 없습니다."),
            "months": [{**m, "interest": heat.get(m["ym"])} for m in series],
            "interest": {"rank": item["rank"], "index": item["index"],
                         "trend_pct": item["trend_pct"], "keyword": item["keyword"]} if item else None,
            "note": ("거래량·평균가는 국토부 실거래(RTMS), 관심도는 네이버 검색 트렌드다. "
                     "이번 달은 신고 기한이 남아 있어 잠정치(provisional)다."),
        }

    def realestate_interest(self) -> dict:
        from app.data.macro import interest
        return interest.snapshot()

    def realestate_interest_collect(self, months: int | None) -> dict:
        """지도에 이미 있는 시군구 목록을 그대로 대상으로 삼는다 — 관심도와 거래량을
        같은 지역 집합 위에서 비교해야 '검색은 떴는데 거래는 아직' 이 성립한다."""
        from app.core.config import get_settings
        from app.data.macro import interest, realestate_map
        snap = realestate_map.map_snapshot()
        regions = [{"lawd": r["lawd"], "sido": r["sido"], "region": r["region"]}
                   for r in snap.get("regions", [])]
        return interest.start_warm(
            regions, months=months or get_settings().naver_interest_months)

    def realestate_deals(self, lawd: str, ym: str | None) -> dict:
        from app.data.macro import realestate_map
        return realestate_map.region_deals(lawd, ym)

    def realestate_apartments(self, lawd: str, ym: str | None,
                              trade: str = "sale", kind: str = "apt") -> dict:
        from app.data.macro import realestate_map
        return realestate_map.region_apartments(lawd, ym, trade, kind)

    def poi_schools(self, sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float,
                    levels: str | None) -> dict:
        from app.data.macro import poi
        return poi.schools(sw_lat, sw_lng, ne_lat, ne_lng, levels)

    def poi_stations(self, sw_lat: float, sw_lng: float,
                     ne_lat: float, ne_lng: float) -> dict:
        from app.data.macro import poi
        return poi.stations(sw_lat, sw_lng, ne_lat, ne_lng)

    def realestate_kinds(self) -> dict:
        from app.data.macro import rtms
        return {"kinds": [{"key": k, "label": v["label"], "has_rent": bool(v["rent"])}
                          for k, v in rtms.KINDS.items()]}

    def realestate_apartment(self, lawd: str, apt: str, dong: str | None,
                             months: int) -> dict:
        from app.data.macro import realestate_map
        return realestate_map.apartment_detail(lawd, apt, dong, months)

    def realestate_rent(self) -> dict:
        return rent.snapshot()

    def ecos_macro(self) -> dict:
        return ecos.snapshot()

    def money_supply(self) -> dict:
        return money_supply.snapshot()

    def money_analysis(self) -> dict:
        return money_analysis.snapshot()

    def real_economy(self) -> dict:
        return realeconomy.snapshot()
