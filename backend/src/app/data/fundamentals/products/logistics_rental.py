"""제품 원가 지식베이스 — 운송·물류·렌탈.

필드의 의미는 패키지 문서(``products/__init__.py``) 참고. 이 파일은 **데이터만**
담는다 — 계산 로직은 ``app/data/fundamentals/unit_economics.py``.
"""
from __future__ import annotations

SECTOR = "운송·물류·렌탈"

PRODUCTS: dict[str, dict] = {
    "003490:passenger": {
        "ticker": "003490", "company": "대한항공", "product": "여객운송(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "직판·대리점",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 0.45,
        "material_mix": [
            {"item": "항공유(연료비)", "weight": 0.33, "commodity": "jet_fuel"},
            {"item": "인건비", "weight": 0.20, "commodity": None},
            {"item": "감가상각·항공기 리스료", "weight": 0.18, "commodity": None},
            {"item": "공항·조업·화객비", "weight": 0.14, "commodity": None},
            {"item": "정비·부품", "weight": 0.08, "commodity": None},
            {"item": "판매수수료·기타", "weight": 0.07, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.78, "op": 0.121},
        "note": "영업비용의 1/3이 항공유 — 유가·환율에 손익 직결. 유가↓+여객 회복으로 '24년 영업이익률 12%대.",
    },
    "011200:container": {
        "ticker": "011200", "company": "HMM", "product": "컨테이너 해운(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "직계약·포워더",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 0.30,
        "material_mix": [
            {"item": "연료비(벙커유)", "weight": 0.18, "commodity": "crude_oil"},
            {"item": "항비·터미널·하역비", "weight": 0.30, "commodity": None},
            {"item": "용선료", "weight": 0.18, "commodity": None},
            {"item": "컨테이너·장비 임차", "weight": 0.12, "commodity": None},
            {"item": "인건비", "weight": 0.10, "commodity": None},
            {"item": "내륙운송·기타", "weight": 0.12, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.65, "op": 0.30},
        "note": "운임(SCFI)·유가 사이클. '24 운임 급등(홍해사태)으로 영업이익률 30%. 운임 급락 시 얇은 마진.",
    },
    # ===== 여행·교육 (원자재 없음) =====
    "039130:hanatour": {
        "ticker": "039130", "company": "하나투어", "product": "여행(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "여행중개",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "여행상품 원가(항공·지상비)", "weight": 0.55, "commodity": None},
            {"item": "인건비", "weight": 0.20, "commodity": None},
            {"item": "마케팅", "weight": 0.15, "commodity": None},
            {"item": "기타", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.80, "op": 0.08},
        "note": "원자재 무관. 여행상품 원가(항공권·지상비)가 대부분. 해외여행 수요·환율·유가(항공권)가 실적 좌우.",
    },
    "000120:cjlogistics": {
        "ticker": "000120", "company": "CJ대한통운", "product": "물류·택배(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "물류",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "운송·외주(간선·택배기사)", "weight": 0.55, "commodity": None},
            {"item": "인건비", "weight": 0.20, "commodity": None},
            {"item": "연료(경유)", "weight": 0.08, "commodity": "crude_oil"},
            {"item": "시설·감가상각", "weight": 0.10, "commodity": None},
            {"item": "기타", "weight": 0.07, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.93, "op": 0.05},
        "note": "택배 단가·물동량·인건비가 원가. 자동화(풀필먼트)로 효율화. 이커머스 물동량·글로벌 포워딩이 성장축.",
    },
    "089860:lotterental": {
        "ticker": "089860", "company": "롯데렌탈", "product": "렌터카(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "렌탈",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "차량 감가상각", "weight": 0.45, "commodity": None},
            {"item": "이자비용(차량금융)", "weight": 0.20, "commodity": None},
            {"item": "정비·보험", "weight": 0.15, "commodity": None},
            {"item": "인건비", "weight": 0.10, "commodity": None},
            {"item": "기타", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.88, "op": 0.12},
        "note": "차량 감가상각+금리가 원가. 중고차 잔가(처분이익)가 손익 변수. 장기렌터카·중고차 사업.",
    },
    "089590:jejuair": {
        "ticker": "089590", "company": "제주항공", "product": "LCC 여객(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "직판",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "항공유(연료비)", "weight": 0.30, "commodity": "jet_fuel"},
            {"item": "항공기 리스료", "weight": 0.20, "commodity": None},
            {"item": "공항·조업비", "weight": 0.20, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "정비·기타", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.88, "op": 0.05},
        "note": "LCC. 유가·환율에 민감(리스료·연료 달러). 일본·동남아 단거리 수요, 좌석 효율(L/F)이 마진.",
    },
    # ===== 물류·자동차부품·발전정비 =====
    "086280:glovis": {
        "ticker": "086280", "company": "현대글로비스", "product": "물류·완성차운송",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "물류",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "운송·용선·외주", "weight": 0.55, "commodity": None},
            {"item": "인건비", "weight": 0.12, "commodity": None},
            {"item": "연료", "weight": 0.10, "commodity": "crude_oil"},
            {"item": "시설·감가상각", "weight": 0.10, "commodity": None},
            {"item": "기타", "weight": 0.13, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.94, "op": 0.06},
        "note": "완성차 해상운송(PCTC)+종합물류. 현대차그룹 물량 기반. 운임·유가·환율에 노출.",
    },
    "028670:panocean": {
        "ticker": "028670", "company": "팬오션", "product": "벌크 해운",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "해운",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "용선료", "weight": 0.30, "commodity": None},
            {"item": "연료(벙커유)", "weight": 0.25, "commodity": "crude_oil"},
            {"item": "항비·운영", "weight": 0.20, "commodity": None},
            {"item": "인건비", "weight": 0.10, "commodity": None},
            {"item": "감가·기타", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.88, "op": 0.12},
        "note": "벌크선(BDI)·곡물운송. 운임·유가 사이클. 하림그룹, 곡물 트레이딩과 시너지.",
    },
}
