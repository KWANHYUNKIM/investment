"""제품 원가 지식베이스 — 화장품.

필드의 의미는 패키지 문서(``products/__init__.py``) 참고. 이 파일은 **데이터만**
담는다 — 계산 로직은 ``app/data/fundamentals/unit_economics.py``.
"""
from __future__ import annotations

SECTOR = "화장품"

PRODUCTS: dict[str, dict] = {
    # ===== 화장품 (원가보다 브랜드·유통이 판가의 대부분) =====
    "090430:sulwhasoo": {
        "ticker": "090430", "company": "아모레퍼시픽", "product": "설화수 자음생크림",
        "unit": "60ml", "retail_price": 270000, "channel": "백화점",
        "distribution_margin": 0.50, "material_ratio_of_cogs": 0.70,
        "material_mix": [
            {"item": "고급 유리 용기·펌프", "weight": 0.35, "commodity": None},
            {"item": "인삼·자음단 특수원료", "weight": 0.25, "commodity": None},
            {"item": "보습 베이스", "weight": 0.15, "commodity": None},
            {"item": "오일·에몰리언트", "weight": 0.10, "commodity": "palm_oil"},
            {"item": "단상자·포장재", "weight": 0.10, "commodity": "bopp_film"},
            {"item": "향료", "weight": 0.05, "commodity": "palm_oil"},
        ],
        "default_ratios": {"cogs": 0.32, "op": 0.03},
        "note": "제조원가는 소비자가의 10%대. 나머지는 브랜드·백화점 수수료·마케팅. 내용물보다 용기값이 큼.",
    },
    "051900:whoo": {
        "ticker": "051900", "company": "LG생활건강", "product": "더후 비첩 자생에센스",
        "unit": "50ml", "retail_price": 165000, "channel": "백화점",
        "distribution_margin": 0.50, "material_ratio_of_cogs": 0.70,
        "material_mix": [
            {"item": "유리 용기·펌프", "weight": 0.30, "commodity": None},
            {"item": "발효·인삼 특수원료", "weight": 0.25, "commodity": None},
            {"item": "에센스 베이스", "weight": 0.20, "commodity": None},
            {"item": "오일·에몰리언트", "weight": 0.10, "commodity": "palm_oil"},
            {"item": "단상자·포장재", "weight": 0.10, "commodity": "bopp_film"},
            {"item": "향료", "weight": 0.05, "commodity": "palm_oil"},
        ],
        "default_ratios": {"cogs": 0.46, "op": 0.07},
        "note": "상시 두 자릿수 할인이 상수 = 원가 대비 판가 여유가 크다는 방증. 브랜드·유통이 판가 결정.",
    },
    # ===== 화장품 ODM (브랜드사와 대비 — 제조 저마진) =====
    "192820:cosmax": {
        "ticker": "192820", "company": "코스맥스", "product": "화장품 ODM",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 제조",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.03, "material_ratio_of_cogs": 0.75,
        "material_mix": [
            {"item": "화장품 원료(특수)", "weight": 0.40, "commodity": None},
            {"item": "유지·오일", "weight": 0.10, "commodity": "palm_oil"},
            {"item": "용기·포장재", "weight": 0.25, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "감가상각", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.75, "op": 0.06},
        "note": "브랜드사(고마진)와 달리 원료·용기 매입이 원가. 물량(가동률)이 마진. K뷰티 인디브랜드 수출 수혜.",
    },
    "161890:kolmar": {
        "ticker": "161890", "company": "한국콜마", "product": "화장품·제약 ODM",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 제조",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.03, "material_ratio_of_cogs": 0.72,
        "material_mix": [
            {"item": "화장품·의약 원료", "weight": 0.38, "commodity": None},
            {"item": "유지·오일", "weight": 0.10, "commodity": "palm_oil"},
            {"item": "용기·포장재", "weight": 0.24, "commodity": None},
            {"item": "인건비", "weight": 0.16, "commodity": None},
            {"item": "감가상각", "weight": 0.12, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.72, "op": 0.07},
        "note": "화장품+제약 ODM. 자외선차단제 등 선케어 강점. 원료·용기가 원가, 물량이 마진.",
    },
    # ===== 화장품브랜드·벌크해운·손보·제약·반도체테스트핀 =====
    "237880:clio": {
        "ticker": "237880", "company": "클리오", "product": "색조 화장품 브랜드",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "브랜드",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "상품매입원가(ODM 사입)", "weight": 0.45, "commodity": None},
            {"item": "용기·부자재", "weight": 0.15, "commodity": None},
            {"item": "마케팅", "weight": 0.20, "commodity": None},
            {"item": "인건비", "weight": 0.12, "commodity": None},
            {"item": "물류", "weight": 0.08, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.55, "op": 0.08},
        "note": "색조 브랜드(페리페라·구달). ODM 위탁생산이라 제조원가보다 마케팅·채널(H&B·수출)이 마진 좌우.",
    },
}
