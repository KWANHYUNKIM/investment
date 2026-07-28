"""제품 원가 지식베이스 — 철강·비철·소재.

필드의 의미는 패키지 문서(``products/__init__.py``) 참고. 이 파일은 **데이터만**
담는다 — 계산 로직은 ``app/data/fundamentals/unit_economics.py``.
"""
from __future__ import annotations

SECTOR = "철강·비철·소재"

PRODUCTS: dict[str, dict] = {
    # ===== 철강·화학 (스프레드가 마진, 사이클) =====
    "005490:hrcoil": {
        "ticker": "005490", "company": "POSCO홀딩스", "product": "열연강판",
        "unit": "톤", "retail_price": 850000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.03, "material_ratio_of_cogs": 0.78,
        "material_mix": [
            {"item": "철광석", "weight": 0.32, "commodity": "iron_ore"},
            {"item": "원료탄", "weight": 0.30, "commodity": "coking_coal"},
            {"item": "고철(스크랩)", "weight": 0.08, "commodity": "steel_hr"},
            {"item": "전력·에너지", "weight": 0.18, "commodity": None},
            {"item": "인건비·감가상각", "weight": 0.12, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.925, "op": 0.027},
        "note": "철강 마진 = 열연가 − (철광석+원료탄) 쇳물 스프레드. 원료탄 급등 전가 못해 마진 축소(OPM 2.7%).",
    },
    "213500:hansol": {
        "ticker": "213500", "company": "한솔제지", "product": "인쇄·산업용지",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "펄프", "weight": 0.45, "commodity": "pulp"},
            {"item": "폐지·고지", "weight": 0.15, "commodity": None},
            {"item": "에너지(중유·LNG)", "weight": 0.15, "commodity": "crude_oil"},
            {"item": "인건비·감가", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.88, "op": 0.04},
        "note": "펄프가+유가(에너지)가 원가 좌우. 저마진(4%). 인쇄용지 수요 감소·특수지(친환경 포장)로 전환 중.",
    },
    "010130:koreazinc": {
        "ticker": "010130", "company": "고려아연", "product": "아연·연 제련",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "아연·연 정광 매입", "weight": 0.60, "commodity": "zinc"},
            {"item": "부산물 회수·기타", "weight": 0.10, "commodity": None},
            {"item": "에너지(전력)", "weight": 0.12, "commodity": None},
            {"item": "인건비·감가", "weight": 0.18, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.85, "op": 0.09},
        "note": "마진=제련수수료(TC/RC)+은·금 부산물. 아연가·환율 노출. 세계 1위 제련사, 신사업(2차전지 소재·신재생) 투자.",
    },
    # ===== 철강·전선(금속) =====
    "004020:hyundaisteel": {
        "ticker": "004020", "company": "현대제철", "product": "철강(판재·봉형강)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "철광석", "weight": 0.25, "commodity": "iron_ore"},
            {"item": "원료탄", "weight": 0.22, "commodity": "coking_coal"},
            {"item": "고철(스크랩)", "weight": 0.15, "commodity": "steel_hr"},
            {"item": "전력·에너지", "weight": 0.15, "commodity": None},
            {"item": "인건비·감가", "weight": 0.23, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.93, "op": 0.03},
        "note": "고로(판재)+전기로(봉형강). 철광석·원료탄·고철이 원가. 건설경기·자동차강판 수요, 중국 철강가에 노출.",
    },
    "006260:ls": {
        "ticker": "006260", "company": "LS", "product": "전선·케이블",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "구리", "weight": 0.55, "commodity": "copper"},
            {"item": "알루미늄", "weight": 0.10, "commodity": "aluminum"},
            {"item": "절연·기타 소재", "weight": 0.10, "commodity": "naphtha"},
            {"item": "인건비·감가", "weight": 0.15, "commodity": None},
            {"item": "기타", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.92, "op": 0.05},
        "note": "구리가 원가 절반+(구리 연동 판가). 초고압·해저케이블·전력망 투자 수혜. 구리가·전력 인프라 사이클.",
    },
    # ===== 철강 =====
    "460860:dongkuk": {
        "ticker": "460860", "company": "동국제강", "product": "철강(봉형강·철근)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "고철(스크랩)", "weight": 0.45, "commodity": "steel_hr"},
            {"item": "전력·에너지", "weight": 0.18, "commodity": None},
            {"item": "부원료", "weight": 0.10, "commodity": None},
            {"item": "인건비·감가", "weight": 0.27, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.90, "op": 0.05},
        "note": "전기로(봉형강·철근)+컬러강판. 고철·전기료가 원가. 건설 철근 수요·전기료가 마진 좌우.",
    },
    "014620:sungkwang": {
        "ticker": "014620", "company": "성광벤드", "product": "관이음쇠(피팅)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "철강·스테인리스 소재", "weight": 0.50, "commodity": "steel_hr"},
            {"item": "인건비", "weight": 0.20, "commodity": None},
            {"item": "에너지", "weight": 0.10, "commodity": None},
            {"item": "감가·기타", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.75, "op": 0.15},
        "note": "관이음쇠(피팅) — 조선·플랜트·에너지 발주에 연동. 후판·스테인리스가 원가. 프로젝트 수주 사이클.",
    },
    # ===== 철강·비철(신동·특수강·컬러강판) =====
    "103140:poongsan": {
        "ticker": "103140", "company": "풍산", "product": "신동(구리)·방산탄약",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B·수주",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "구리·아연(신동 원료)", "weight": 0.70, "commodity": "copper"},
            {"item": "에너지", "weight": 0.08, "commodity": None},
            {"item": "인건비·감가", "weight": 0.12, "commodity": None},
            {"item": "기타", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.90, "op": 0.06},
        "note": "신동(구리 가공)+방산 탄약. 구리가 연동(신동 롤마진)+방산 수출 성장. 구리 가격이 실적 변수.",
    },
    "001430:seah": {
        "ticker": "001430", "company": "세아베스틸지주", "product": "특수강",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "고철·특수합금", "weight": 0.50, "commodity": "steel_hr"},
            {"item": "전력·에너지", "weight": 0.15, "commodity": None},
            {"item": "부원료", "weight": 0.10, "commodity": None},
            {"item": "인건비·감가", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.90, "op": 0.05},
        "note": "특수강(자동차·기계·방산·에너지용). 고철·전기료가 원가. 자동차·방산·해상풍력 수요가 변수.",
    },
    "016380:kgsteel": {
        "ticker": "016380", "company": "KG스틸", "product": "컬러강판",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "열연·냉연(철강)", "weight": 0.55, "commodity": "steel_hr"},
            {"item": "아연·도료", "weight": 0.12, "commodity": None},
            {"item": "에너지", "weight": 0.08, "commodity": None},
            {"item": "인건비·감가", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.87, "op": 0.07},
        "note": "컬러강판(가전·건재) 강자. 철강 원자재. 건설경기·수출·프리미엄 컬러강판 믹스가 마진.",
    },
}
