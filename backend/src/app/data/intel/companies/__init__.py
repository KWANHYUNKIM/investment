"""글로벌 경쟁지도의 **정성 큐레이션 데이터** — 클러스터별 모듈을 조립한다.

예전엔 이 1,050줄이 ``global_intel.py`` 안에 리터럴로 들어가 있었다. 조회 로직은
28줄뿐이었으니 그 파일의 96%가 데이터였다. 게다가 같은 클러스터의 **경쟁 구도**
(BATTLEGROUNDS)와 **기업 프로파일**(PROFILES)이 서로 다른 덩어리에 떨어져 있어,
한 업종을 손보려면 900줄을 오르내려야 했다. 이제 클러스터 하나가 파일 하나다.

각 클러스터 모듈이 내보내는 것
    KEY            클러스터 슬러그 (global_map 의 클러스터 키와 같아야 한다)
    LABEL          한글 라벨
    TECH           기술 설명을 전면에 둘 클러스터인가
    BATTLEGROUNDS  세부 전장 목록 — arena(전장) · desc(설명) · players(주요 선수)
    PROFILES       기업별 tech(핵심기술) · biz(이익구조) · moat(해자) · invest(투자성격)

``extra_kr`` 은 전장에는 안 들어가지만 프로파일이 필요한 한국 종목, ``aliases`` 는
표시 이름이 여러 가지인 회사의 별칭이다.
"""
from __future__ import annotations

from app.data.intel.companies import (
    auto,
    auto_parts,
    bank_fin,
    battery,
    bigtech_sw,
    chemical,
    consumer,
    defense,
    display,
    ecommerce,
    media_game,
    pharma_bio,
    semiconductor,
    shipbuilding,
    steel,
    extra_kr,
)
from app.data.intel.companies.aliases import ALIASES  # noqa: F401

# 클러스터 순서 = 원본 리터럴 순서(반도체부터). 표시 순서에 영향은 없다.
_CLUSTERS = (
    semiconductor,
    battery,
    auto,
    auto_parts,
    bigtech_sw,
    pharma_bio,
    display,
    steel,
    chemical,
    shipbuilding,
    defense,
    bank_fin,
    media_game,
    consumer,
    ecommerce,
)

TECH_CLUSTERS: set[str] = {c.KEY for c in _CLUSTERS if c.TECH}
BATTLEGROUNDS: dict[str, list[dict]] = {c.KEY: c.BATTLEGROUNDS for c in _CLUSTERS}

PROFILES: dict[str, dict] = {}
for _c in (*_CLUSTERS, extra_kr):
    for _name, _p in _c.PROFILES.items():
        if _name in PROFILES:
            raise ValueError(f"기업 프로파일 중복: {_name}")
        PROFILES[_name] = _p
