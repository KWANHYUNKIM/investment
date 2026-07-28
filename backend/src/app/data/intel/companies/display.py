"""글로벌 경쟁지도 — 디스플레이.

이 파일은 **데이터만** 담는다(필드 의미는 패키지 문서 참고). 조회 로직은
``app/data/intel/global_intel.py``.
"""
from __future__ import annotations

KEY = "display"
LABEL = "디스플레이"
TECH = True          # 기술 설명을 전면에 둘 클러스터인가

# 세부 전장(arena) — 같은 시장을 두고 실제로 맞붙는 지점.
BATTLEGROUNDS: list[dict] = [
    {"arena": "중소형 OLED (스마트폰·IT)",
     "desc": "삼성디스플레이 선두, LG디스플레이 추격, BOE(중국) 애플 침투 시도.",
     "players": ["삼성전자", "LG디스플레이", "BOE"]},
    {"arena": "대형 패널 (TV·LCD)",
     "desc": "LCD는 BOE·AUO 등 중화권이 장악, 한국은 OLED TV·차량용으로 차별화.",
     "players": ["BOE", "AUO", "LG디스플레이"]},
]

PROFILES: dict[str, dict] = {
    "LG디스플레이": {
        "tech": "대형·차량용 OLED 강자(WOLED). 중소형 OLED 애플 공급 확대.",
        "biz": "패널 판매 — LCD 적자에서 OLED·차량용 고부가로 체질 전환 중.",
        "moat": "대형 OLED 기술·차량용 점유.",
        "invest": "구조조정·OLED 전환 투자로 흑자 회복이 과제(낮은 ROIC 회복기).",
    },
    "AUO": {
        "tech": "대만 LCD/패널. 차량용·상업용으로 다각화.",
        "biz": "패널 대량생산 — 가격 사이클에 민감.",
        "moat": "원가·대만 생태계.",
        "invest": "범용 LCD 의존으로 수익 변동 큼.",
    },
    "JDI": {
        "tech": "일본 중소형 디스플레이. 차량용·특수 패널.",
        "biz": "구조적 부진 — 특수·차량용으로 생존 모색.",
        "moat": "일부 특수 기술.",
        "invest": "저수익 구조조정 국면.",
    },
}
