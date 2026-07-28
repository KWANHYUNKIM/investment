"""제품 원가 지식베이스 — 건설·건자재.

필드의 의미는 패키지 문서(``products/__init__.py``) 참고. 이 파일은 **데이터만**
담는다 — 계산 로직은 ``app/data/fundamentals/unit_economics.py``.
"""
from __future__ import annotations

SECTOR = "건설·건자재"

PRODUCTS: dict[str, dict] = {
    # ===== 건설 (시멘트·철근·인건비, 원가율 90%+) =====
    "000720:hyundaieng": {
        "ticker": "000720", "company": "현대건설", "product": "아파트(분양, 매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "분양",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 0.32,
        "material_mix": [
            {"item": "토지비(택지비)", "weight": 0.25, "commodity": None},
            {"item": "철근(골조)", "weight": 0.06, "commodity": "steel_hr"},
            {"item": "시멘트·레미콘(골조)", "weight": 0.06, "commodity": "cement"},
            {"item": "골재·마감 등 기타자재", "weight": 0.20, "commodity": None},
            {"item": "노무비(인건비)", "weight": 0.18, "commodity": None},
            {"item": "외주비·간접비", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.96, "op": -0.039},
        "note": "시멘트·철근·인건비 급등으로 원가율 96%. '24년 해외·주택 원가조정으로 일시 적자(정상화 시 2~3%). PF·미분양 별개.",
    },
    "006360:gseng": {
        "ticker": "006360", "company": "GS건설", "product": "자이 아파트(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "분양",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 0.31,
        "material_mix": [
            {"item": "토지비(택지비)", "weight": 0.26, "commodity": None},
            {"item": "철근(골조)", "weight": 0.06, "commodity": "steel_hr"},
            {"item": "시멘트·레미콘(골조)", "weight": 0.05, "commodity": "cement"},
            {"item": "골재·마감 등 기타자재", "weight": 0.20, "commodity": None},
            {"item": "노무비(인건비)", "weight": 0.18, "commodity": None},
            {"item": "외주비·간접비", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.92, "op": 0.022},
        "note": "매출원가율 92%, 영업이익률 2%대. 검단사고 딛고 흑자전환. 시멘트·철근이 원가 악화 주범.",
    },
    # ===== 건자재·가구 (목재·도료, 주택경기 노출) =====
    "009240:hanssem": {
        "ticker": "009240", "company": "한샘", "product": "가구·인테리어",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "유통·시공",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 0.45,
        "material_mix": [
            {"item": "목재·MDF/PB", "weight": 0.60, "commodity": "wood"},
            {"item": "철물·판재", "weight": 0.20, "commodity": "steel_hr"},
            {"item": "기타 자재", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.78, "op": 0.02},
        "note": "목재(MDF)+시공 인건비가 원가. 주택 거래량·리모델링 경기에 실적 직결. 영업이익률 1~3%로 얇음.",
    },
    # ===== 시멘트·상사·자원 =====
    "003410:ssangyongc": {
        "ticker": "003410", "company": "쌍용C&E", "product": "시멘트",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "유연탄(연료)", "weight": 0.30, "commodity": "coking_coal"},
            {"item": "전력", "weight": 0.15, "commodity": None},
            {"item": "석회석·부원료", "weight": 0.15, "commodity": None},
            {"item": "인건비·감가", "weight": 0.25, "commodity": None},
            {"item": "물류", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.82, "op": 0.13},
        "note": "유연탄가·전기료가 원가 핵심(에너지 다소비). 순환자원(폐열·폐기물 연료)로 원가 절감. 시멘트 가격 인상이 마진.",
    },
    "300720:hanil": {
        "ticker": "300720", "company": "한일시멘트", "product": "시멘트·레미콘",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "유연탄(연료)", "weight": 0.30, "commodity": "coking_coal"},
            {"item": "전력", "weight": 0.15, "commodity": None},
            {"item": "석회석·부원료", "weight": 0.15, "commodity": None},
            {"item": "인건비·감가", "weight": 0.25, "commodity": None},
            {"item": "물류", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.83, "op": 0.11},
        "note": "유연탄·전기료가 원가 핵심. 레미콘 수직계열. 시멘트 가격 인상·건설경기가 마진 좌우.",
    },
    # ===== 건설(DL이앤씨·대우건설·삼성E&A) =====
    "375500:dlenc": {
        "ticker": "375500", "company": "DL이앤씨", "product": "아파트·플랜트(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "분양·수주",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "토지비", "weight": 0.20, "commodity": None},
            {"item": "철근", "weight": 0.06, "commodity": "steel_hr"},
            {"item": "시멘트·레미콘", "weight": 0.05, "commodity": "cement"},
            {"item": "골재·마감 등 기타자재", "weight": 0.24, "commodity": None},
            {"item": "노무비", "weight": 0.18, "commodity": None},
            {"item": "외주비", "weight": 0.27, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.90, "op": 0.05},
        "note": "주택(e편한세상)+플랜트. 시멘트·철근·인건비가 원가. 원가율·미분양·해외 플랜트 수익성이 변수.",
    },
    "047040:daewooeng": {
        "ticker": "047040", "company": "대우건설", "product": "아파트·플랜트(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "분양·수주",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "토지비", "weight": 0.20, "commodity": None},
            {"item": "철근", "weight": 0.06, "commodity": "steel_hr"},
            {"item": "시멘트·레미콘", "weight": 0.05, "commodity": "cement"},
            {"item": "골재·마감 등 기타자재", "weight": 0.24, "commodity": None},
            {"item": "노무비", "weight": 0.18, "commodity": None},
            {"item": "외주비", "weight": 0.27, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.91, "op": 0.04},
        "note": "푸르지오+해외 플랜트. 시멘트·철근이 원가 악화 요인. PF·해외 프로젝트 리스크가 변수.",
    },
    "028050:samsungena": {
        "ticker": "028050", "company": "삼성E&A", "product": "화공 플랜트 EPC(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "수주",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "기자재·자재", "weight": 0.40, "commodity": None},
            {"item": "외주·시공", "weight": 0.30, "commodity": None},
            {"item": "인건비(설계)", "weight": 0.18, "commodity": None},
            {"item": "기타", "weight": 0.12, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.90, "op": 0.07},
        "note": "화공 플랜트 EPC(중동 정유·가스). 설계역량·프로젝트 수익성이 마진. 원자재보다 수주 믹스·리스크 관리.",
    },
    "009450:kdnavien": {
        "ticker": "009450", "company": "경동나비엔", "product": "보일러·온수기",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "유통·B2B",
        "channel_label": "직판·유통",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "부품·소재", "weight": 0.40, "commodity": None},
            {"item": "철강·스테인리스", "weight": 0.20, "commodity": "steel_hr"},
            {"item": "인건비", "weight": 0.13, "commodity": None},
            {"item": "외주·기타", "weight": 0.27, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.75, "op": 0.09},
        "note": "콘덴싱 보일러·온수기 북미 1위. 철강·부품이 원가. 북미 탱크리스 온수기 수요가 성장축.",
    },
}
