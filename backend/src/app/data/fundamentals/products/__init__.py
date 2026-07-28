"""제품 단위 원가분해의 **지식베이스** — 업종별 모듈을 하나로 조립한다.

예전에는 이 230품목이 ``unit_economics.py`` 안에 3,458줄 리터럴로 들어가 있었다.
계산 로직은 227줄뿐이었으니 그 파일의 88%가 데이터였다. 품목 하나 고치려고 4천 줄
파일을 열어야 했고, 업종 분류는 ``SECTOR_GROUPS`` 리터럴과 그 뒤의
``_SECTOR_BY_ID.update({...})`` 두 곳에 나뉘어 있어 새 품목마다 두 군데를 손대야
했다. 이제 **품목은 자기 업종 모듈에만** 적으면 되고, 업종은 모듈이 곧 정의다.

각 업종 모듈은 ``SECTOR``(업종 라벨)와 ``PRODUCTS``(그 업종 품목) 두 개만 내보낸다.
품목을 추가할 때 건드릴 파일은 그 하나뿐이고, 새 업종을 만들 때만 아래 ``_MODULES``
에 한 줄 넣는다.

품목 필드
    distribution_margin       소비자가 중 유통(도소매)이 가져가는 몫
    material_ratio_of_cogs    매출원가 중 원재료비 비중(나머지 = 가공비: 노무·감가·에너지)
    material_mix[].weight     원재료비 내 상대 비중(합=1.0)
    material_mix[].commodity  commodities 시세 키. None 이면 민감도 계산에서 빠진다
    default_ratios            DART 실측 실패 시 폴백 {cogs, op}

``_MODULES`` 의 순서가 곧 화면 순서다. 프론트(UnitEconomics.tsx)는 products 배열을
훑어 **업종이 처음 나온 순서**로 드롭다운을 만들기 때문에, 이 튜플 순서를 바꾸면
화면의 업종 순서도 같이 바뀐다. 지금 순서는 쪼개기 전 PRODUCTS 의 업종 첫 등장
순서를 그대로 옮긴 것이다(= 이전 화면과 동일).
"""
from __future__ import annotations

from app.data.fundamentals.products import (
    apparel,
    auto,
    battery,
    chemical,
    construction,
    cosmetics,
    finance,
    food,
    it_media_telecom,
    logistics_rental,
    pharma,
    retail,
    semiconductor,
    shipbuilding_defense,
    steel,
    trading_services,
)

# 업종 순서의 유일한 정의 지점 (위 import 는 알파벳순 — 순서와 무관하다).
_MODULES = (
    food,
    cosmetics,
    pharma,
    retail,
    semiconductor,
    auto,
    steel,
    chemical,
    battery,
    logistics_rental,
    it_media_telecom,
    construction,
    shipbuilding_defense,
    apparel,
    trading_services,
    finance,
)

PRODUCTS: dict[str, dict] = {}
SECTOR_BY_ID: dict[str, str] = {}
for _m in _MODULES:
    for _pid, _p in _m.PRODUCTS.items():
        if _pid in PRODUCTS:
            raise ValueError(f"제품 id 중복: {_pid} ({_m.SECTOR})")
        PRODUCTS[_pid] = _p
        SECTOR_BY_ID[_pid] = _m.SECTOR

SECTOR_ORDER: list[str] = [_m.SECTOR for _m in _MODULES]
