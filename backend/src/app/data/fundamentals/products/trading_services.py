"""제품 원가 지식베이스 — 상사·서비스·기타.

필드의 의미는 패키지 문서(``products/__init__.py``) 참고. 이 파일은 **데이터만**
담는다 — 계산 로직은 ``app/data/fundamentals/unit_economics.py``.
"""
from __future__ import annotations

SECTOR = "상사·서비스·기타"

PRODUCTS: dict[str, dict] = {
    # ===== 렌탈·구독 (제조원가+방문판매, 계정 누적 고마진) =====
    "021240:coway": {
        "ticker": "021240", "company": "코웨이", "product": "정수기·매트리스 렌탈",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "구독",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "코디 방문판매 인건비·수수료", "weight": 0.35, "commodity": None},
            {"item": "제품 제조원가(부품·필터)", "weight": 0.30, "commodity": "naphtha"},
            {"item": "렌탈자산 감가상각", "weight": 0.15, "commodity": None},
            {"item": "관리·물류", "weight": 0.12, "commodity": None},
            {"item": "마케팅", "weight": 0.08, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.83, "op": 0.17},
        "note": "초기 제조원가+코디(방문판매) 인건비·수수료가 원가. 구독 계정 누적 레버리지로 영업이익률 17%대 안정.",
    },
    # ===== 카지노·면세 (원자재 없음 — 독점 vs 송객수수료) =====
    "035250:kangwonland": {
        "ticker": "035250", "company": "강원랜드", "product": "카지노·리조트",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "직영",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "인건비", "weight": 0.35, "commodity": None},
            {"item": "제세공과금(관광기금 등)", "weight": 0.20, "commodity": None},
            {"item": "시설·감가상각", "weight": 0.20, "commodity": None},
            {"item": "운영·관리비", "weight": 0.15, "commodity": None},
            {"item": "마케팅", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.75, "op": 0.25},
        "note": "원자재 무관. 내국인 카지노 독점으로 고마진(영업이익률 25%대). 원가는 인건비·시설·제세공과금.",
    },
    # ===== 의료기기·진단 =====
    "214150:classys": {
        "ticker": "214150", "company": "클래시스", "product": "미용 의료기기",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B·소모품",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.05, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "부품·전자소재", "weight": 0.50, "commodity": None},
            {"item": "소모품(카트리지) 원료", "weight": 0.30, "commodity": None},
            {"item": "제조노무·감가", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.25, "op": 0.48},
        "note": "에너지기반 미용기기+소모품 리커링. 원가율 25%로 낮아 영업이익률 48% 초고마진. 장비 설치 후 소모품이 캐시카우.",
    },
    "215200:megastudy": {
        "ticker": "215200", "company": "메가스터디교육", "product": "교육(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "교육",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "강사료·인세", "weight": 0.35, "commodity": None},
            {"item": "인건비", "weight": 0.20, "commodity": None},
            {"item": "마케팅", "weight": 0.15, "commodity": None},
            {"item": "콘텐츠 제작", "weight": 0.15, "commodity": None},
            {"item": "시설·기타", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.85, "op": 0.15},
        "note": "원자재 무관. 강사료·인건비가 원가. 스타강사 라인업·N수생·의대증원 등 입시정책이 실적 좌우.",
    },
    "047050:posco_intl": {
        "ticker": "047050", "company": "포스코인터내셔널", "product": "상사·에너지",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "트레이딩",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "상품매입원가(트레이딩)", "weight": 0.75, "commodity": None},
            {"item": "가스전·에너지 원가", "weight": 0.10, "commodity": None},
            {"item": "인건비", "weight": 0.05, "commodity": None},
            {"item": "기타", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.94, "op": 0.04},
        "note": "저마진 트레이딩(상사)+고마진 미얀마 가스전(에너지). 자원개발·2차전지 소재 밸류체인 확장.",
    },
    "001120:lxintl": {
        "ticker": "001120", "company": "LX인터내셔널", "product": "자원·상사",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "트레이딩·자원",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "상품매입원가(트레이딩)", "weight": 0.70, "commodity": None},
            {"item": "석탄(자원개발)", "weight": 0.10, "commodity": "coking_coal"},
            {"item": "팜유(자원개발)", "weight": 0.05, "commodity": "palm_oil"},
            {"item": "인건비·기타", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.93, "op": 0.04},
        "note": "석탄·팜 등 자원개발(고마진)+트레이딩. 석탄가·팜유가·물류(판토스)가 실적 좌우.",
    },
    "215000:golfzon": {
        "ticker": "215000", "company": "골프존", "product": "스크린골프",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "가맹·직영",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "시설·장비 감가상각", "weight": 0.25, "commodity": None},
            {"item": "인건비", "weight": 0.25, "commodity": None},
            {"item": "기타 운영비", "weight": 0.20, "commodity": None},
            {"item": "콘텐츠·개발", "weight": 0.15, "commodity": None},
            {"item": "마케팅", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.75, "op": 0.20},
        "note": "원자재 무관. 스크린골프 시뮬레이터+가맹. 골프 인구·라운드 수요, 고마진(20%) 플랫폼.",
    },
}
