"""제품 원가 지식베이스 — 자동차·부품·타이어.

필드의 의미는 패키지 문서(``products/__init__.py``) 참고. 이 파일은 **데이터만**
담는다 — 계산 로직은 ``app/data/fundamentals/unit_economics.py``.
"""
from __future__ import annotations

SECTOR = "자동차·부품·타이어"

PRODUCTS: dict[str, dict] = {
    # ===== 완성차 (소재+부품, 환율 레버리지) =====
    "005380:grandeur": {
        "ticker": "005380", "company": "현대차", "product": "그랜저(준대형세단)",
        "unit": "1대", "retail_price": 40000000, "channel": "딜러",
        "distribution_margin": 0.10, "material_ratio_of_cogs": 0.75,
        "material_mix": [
            {"item": "강판(철강)", "weight": 0.30, "commodity": "steel_hr"},
            {"item": "알루미늄", "weight": 0.10, "commodity": "aluminum"},
            {"item": "구리(전장)", "weight": 0.05, "commodity": "copper"},
            {"item": "플라스틱·수지", "weight": 0.10, "commodity": "naphtha"},
            {"item": "부품·모듈·인건비", "weight": 0.45, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.805, "op": 0.081},
        "note": "강판·알루미늄·구리가 소재 원가. 차 1대 마진은 믹스(제네시스·고급트림)·환율(수출)이 좌우.",
    },
    "000270:sorento": {
        "ticker": "000270", "company": "기아", "product": "쏘렌토(중형SUV)",
        "unit": "1대", "retail_price": 36000000, "channel": "딜러",
        "distribution_margin": 0.10, "material_ratio_of_cogs": 0.75,
        "material_mix": [
            {"item": "강판(철강)", "weight": 0.32, "commodity": "steel_hr"},
            {"item": "알루미늄", "weight": 0.10, "commodity": "aluminum"},
            {"item": "구리(전장·HEV)", "weight": 0.05, "commodity": "copper"},
            {"item": "플라스틱·수지", "weight": 0.08, "commodity": "naphtha"},
            {"item": "부품·모듈·인건비", "weight": 0.45, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.788, "op": 0.118},
        "note": "SUV·HEV 믹스가 좋아 대당 마진 높음(영업이익률 11.8% 역대최고). 환율이 마진 레버리지.",
    },
    # ===== 타이어 (천연고무+합성고무가 원가 절반+) =====
    "161390:hankooktire": {
        "ticker": "161390", "company": "한국타이어", "product": "승용차 타이어",
        "unit": "타이어 1본", "retail_price": 130000, "channel": "타이어전문점",
        "distribution_margin": 0.35, "material_ratio_of_cogs": 0.65,
        "material_mix": [
            {"item": "천연고무", "weight": 0.22, "commodity": "natural_rubber"},
            {"item": "합성고무(부타디엔/SBR)", "weight": 0.20, "commodity": "naphtha"},
            {"item": "카본블랙·오일·화학첨가제", "weight": 0.13, "commodity": "naphtha"},
            {"item": "타이어코드·비드와이어(철강)", "weight": 0.10, "commodity": "steel_hr"},
            {"item": "인건비·에너지", "weight": 0.20, "commodity": None},
            {"item": "감가상각·간접비", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.62, "op": 0.187},
        "note": "원가 절반이 고무(천연+합성). 고인치·EV타이어 믹스로 영업이익률 18%대. 고무가·유가가 마진 좌우.",
    },
    "073240:kumhotire": {
        "ticker": "073240", "company": "금호타이어", "product": "승용차 타이어",
        "unit": "타이어 1본", "retail_price": 110000, "channel": "타이어전문점",
        "distribution_margin": 0.35, "material_ratio_of_cogs": 0.62,
        "material_mix": [
            {"item": "천연고무", "weight": 0.21, "commodity": "natural_rubber"},
            {"item": "합성고무(부타디엔/SBR)", "weight": 0.20, "commodity": "naphtha"},
            {"item": "카본블랙·오일·화학첨가제", "weight": 0.13, "commodity": "naphtha"},
            {"item": "타이어코드·비드와이어(철강)", "weight": 0.10, "commodity": "steel_hr"},
            {"item": "인건비·에너지", "weight": 0.21, "commodity": None},
            {"item": "감가상각·간접비", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.695, "op": 0.125},
        "note": "판가 대비 재료비 33~34%. 고인치 믹스로 이익 방어. 고무·유가 하락 시 마진 개선.",
    },
    # ===== 자동차부품 =====
    "012330:mobis": {
        "ticker": "012330", "company": "현대모비스", "product": "자동차부품(모듈·전장)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "전장·반도체 부품", "weight": 0.30, "commodity": None},
            {"item": "철강·강판", "weight": 0.20, "commodity": "steel_hr"},
            {"item": "알루미늄", "weight": 0.10, "commodity": "aluminum"},
            {"item": "구리·전선", "weight": 0.05, "commodity": "copper"},
            {"item": "인건비·외주", "weight": 0.35, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.87, "op": 0.06},
        "note": "현대차·기아 향 모듈·전장·A/S부품. 전동화 부품 성장. 철강·알루미늄·전장부품이 원가.",
    },
    "018880:hanon": {
        "ticker": "018880", "company": "한온시스템", "product": "자동차 공조부품",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "알루미늄", "weight": 0.25, "commodity": "aluminum"},
            {"item": "구리", "weight": 0.10, "commodity": "copper"},
            {"item": "부품·소재", "weight": 0.30, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "외주·기타", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.92, "op": 0.03},
        "note": "공조(열관리) 부품 글로벌 2위. 알루미늄·구리가 원가. EV 열관리 수요 성장, 저마진 구조.",
    },
    "011210:wia": {
        "ticker": "011210", "company": "현대위아", "product": "자동차부품·공작기계",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "부품·엔진모듈", "weight": 0.35, "commodity": None},
            {"item": "철강·소재", "weight": 0.25, "commodity": "steel_hr"},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "외주·기타", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.93, "op": 0.03},
        "note": "엔진·등속조인트·모듈+공작기계. 철강·부품이 원가. 현대차·기아 향, 열관리·전동화 부품 확대.",
    },
    # ===== 자동차부품(HL만도·에스엘) =====
    "204320:hlmando": {
        "ticker": "204320", "company": "HL만도", "product": "자동차부품(브레이크·조향)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "부품·전자소재", "weight": 0.35, "commodity": None},
            {"item": "철강·알루미늄", "weight": 0.20, "commodity": "steel_hr"},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "외주·기타", "weight": 0.30, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.90, "op": 0.05},
        "note": "브레이크·조향·ADAS. 전동화·자율주행(SbW) 부품 성장. 철강·전자부품이 원가.",
    },
    "005850:sl": {
        "ticker": "005850", "company": "에스엘", "product": "자동차 램프",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "부품·전자소재(LED)", "weight": 0.35, "commodity": None},
            {"item": "플라스틱·수지", "weight": 0.20, "commodity": "naphtha"},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "외주·기타", "weight": 0.30, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.85, "op": 0.08},
        "note": "헤드램프(LED) 국내 1위. 전동화·프리미엄 램프 믹스로 마진 개선. 현대차·GM 향.",
    },
    "010690:hwashin": {
        "ticker": "010690", "company": "화신", "product": "자동차 차체·샤시부품",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "철강·강판", "weight": 0.45, "commodity": "steel_hr"},
            {"item": "부품·소재", "weight": 0.20, "commodity": None},
            {"item": "인건비", "weight": 0.13, "commodity": None},
            {"item": "외주·기타", "weight": 0.22, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.90, "op": 0.04},
        "note": "자동차 차체·샤시 부품. 철강이 원가 절반. 현대차·기아 물량, 전기차 언더바디 부품 확대.",
    },
}
