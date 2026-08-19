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
