"""글로벌 경쟁지도 — 정성(定性) 큐레이션 조회.

핀허브/DART의 '숫자'만으로는 안 보이는 것들을 사람이 미리 정리해 둔 것을 찾아 준다.

1) BATTLEGROUNDS — 클러스터 안에서 **실제로 같은 시장을 두고 맞붙는 세부 전장**.
   (반도체라도 메모리·파운드리·AI가속기·장비는 싸우는 선수가 전혀 다르다.)
2) PROFILES — 기업별로 ① 핵심 기술/제품(tech) ② 영업이익을 어떻게 내는지(biz)
   ③ 경쟁 우위·해자(moat) ④ 투자(R&D·CAPEX)와 그 회수 성격(invest).
3) TECH_CLUSTERS — '기술주' 성격이 강해 기술 설명을 전면에 내세울 클러스터.

큐레이션 **데이터 자체는 ``companies`` 패키지**에 클러스터별 모듈로 들어 있다(클러스터
하나가 파일 하나 — 경쟁 구도와 그 안의 기업 프로파일이 같은 파일에). 이 파일은 찾아
주는 일만 한다.

키 매칭: 한국은 회사명(WICS 멤버 name), 해외는 global_universe 라벨(표시이름)로 찾는다.
별칭(alias)이 흔한 곳은 ALIASES로 흡수한다. 프로파일이 없으면 그냥 비워 둔다.
"""
from __future__ import annotations

from app.data.intel.companies import ALIASES, BATTLEGROUNDS, PROFILES, TECH_CLUSTERS

__all__ = ["BATTLEGROUNDS", "PROFILES", "TECH_CLUSTERS",
           "profile_for", "battlegrounds", "is_tech"]


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def profile_for(name: str | None) -> dict | None:
    """회사명/라벨 → 프로파일(tech·biz·moat·invest). 없으면 None."""
    if not name:
        return None
    if name in PROFILES:
        return PROFILES[name]
    key = ALIASES.get(_norm(name))
    if key and key in PROFILES:
        return PROFILES[key]
    # 부분일치(해외 회사명이 'NVIDIA Corp'처럼 접미사가 붙는 경우)
    n = _norm(name)
    for k in PROFILES:
        kn = _norm(k)
        if kn and (kn in n or n in kn):
            return PROFILES[k]
    return None


def battlegrounds(cluster_key: str) -> list[dict]:
    return BATTLEGROUNDS.get(cluster_key, [])


def is_tech(cluster_key: str) -> bool:
    return cluster_key in TECH_CLUSTERS
