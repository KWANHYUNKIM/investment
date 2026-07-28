"""제품 원가 지식베이스 — 유통·리테일.

필드의 의미는 패키지 문서(``products/__init__.py``) 참고. 이 파일은 **데이터만**
담는다 — 계산 로직은 ``app/data/fundamentals/unit_economics.py``.
"""
from __future__ import annotations

SECTOR = "유통·리테일"

PRODUCTS: dict[str, dict] = {
    # ===== 유통 (매출 1,000원 기준, 박리다매) =====
    "139480:emart": {
        "ticker": "139480", "company": "이마트", "product": "대형마트(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "유통",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "상품매입원가", "weight": 1.0, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.72, "op": 0.007},
        "note": "원자재가 아니라 상품매입원가+인건비+임차료가 원가. 영업이익률 0.7% — 매출 1,000원에 7원 남는 박리다매.",
    },
    "282330:cu": {
        "ticker": "282330", "company": "BGF리테일", "product": "CU 편의점(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "유통",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "상품매입원가(담배 38%·가공식품 43%)", "weight": 1.0, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.818, "op": 0.033},
        "note": "매출원가율 82%(담배 비중 큼). 영업이익률 3.3%로 편의점 3사 중 최고지만 여전히 얇음.",
    },
    "007070:gs25": {
        "ticker": "007070", "company": "GS리테일", "product": "GS25 편의점(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "유통",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "상품매입원가", "weight": 1.0, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.79, "op": 0.0225},
        "note": "매출원가율 79%, 영업이익률 2%대. 매출은 커도 남기는 게 22원뿐인 박리다매.",
    },
    "008770:hotelshilla": {
        "ticker": "008770", "company": "호텔신라", "product": "면세점(TR)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "면세",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "상품매입원가", "weight": 0.70, "commodity": None},
            {"item": "송객수수료", "weight": 0.12, "commodity": None},
            {"item": "임차료", "weight": 0.08, "commodity": None},
            {"item": "인건비", "weight": 0.06, "commodity": None},
            {"item": "기타", "weight": 0.04, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.85, "op": 0.02},
        "note": "원자재 무관. 상품매입+송객수수료(따이궁)가 원가. 저마진(2%대), 중국인 관광·따이궁 회복이 변수.",
    },
    # ===== 유통(백화점·홈쇼핑)·물류·건설기계 =====
    "004170:shinsegae": {
        "ticker": "004170", "company": "신세계", "product": "백화점(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "백화점",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "상품매입·특약매입 원가", "weight": 0.60, "commodity": None},
            {"item": "임차·감가상각", "weight": 0.13, "commodity": None},
            {"item": "판촉·관리비", "weight": 0.15, "commodity": None},
            {"item": "인건비", "weight": 0.12, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.80, "op": 0.08},
        "note": "원자재 무관. 특약매입(수수료) 구조라 마진 상대적 양호. 명품·VIP 매출·소비경기가 실적 좌우.",
    },
    "057050:hyundaihs": {
        "ticker": "057050", "company": "현대홈쇼핑", "product": "홈쇼핑(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "홈쇼핑",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "상품매입원가", "weight": 0.55, "commodity": None},
            {"item": "송출수수료", "weight": 0.20, "commodity": None},
            {"item": "인건비", "weight": 0.10, "commodity": None},
            {"item": "물류·CS", "weight": 0.10, "commodity": None},
            {"item": "마케팅", "weight": 0.05, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.90, "op": 0.04},
        "note": "원자재 무관. 송출수수료(SO·IPTV)가 최대 비용이자 규제이슈. TV시청 감소로 수익성 압박, 이커머스 전환.",
    },
    "069960:hyundaidept": {
        "ticker": "069960", "company": "현대백화점", "product": "백화점(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "백화점",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "상품매입·특약매입 원가", "weight": 0.62, "commodity": None},
            {"item": "임차·감가상각", "weight": 0.13, "commodity": None},
            {"item": "판촉·관리비", "weight": 0.13, "commodity": None},
            {"item": "인건비", "weight": 0.12, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.82, "op": 0.06},
        "note": "원자재 무관. 특약매입 구조. 명품·프리미엄 매출·소비경기가 실적 좌우. 면세·아울렛도.",
    },
    "023530:lotteshopping": {
        "ticker": "023530", "company": "롯데쇼핑", "product": "종합유통(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "유통",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "상품매입원가", "weight": 0.65, "commodity": None},
            {"item": "임차·감가상각", "weight": 0.13, "commodity": None},
            {"item": "인건비", "weight": 0.12, "commodity": None},
            {"item": "판촉·관리", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.72, "op": 0.03},
        "note": "원자재 무관. 백화점+마트+이커머스+하이마트 종합유통. 저마진(3%), 오프라인 구조조정·이커머스 전환.",
    },
    "051500:cjfreshway": {
        "ticker": "051500", "company": "CJ프레시웨이", "product": "식자재유통·급식",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "유통",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "상품매입원가(식자재)", "weight": 0.80, "commodity": None},
            {"item": "물류", "weight": 0.08, "commodity": None},
            {"item": "인건비", "weight": 0.06, "commodity": None},
            {"item": "기타", "weight": 0.06, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.90, "op": 0.03},
        "note": "원자재 무관(중간유통). 식자재유통+단체급식. 저마진, 외식경기·급식 물량·식자재 물가가 변수.",
    },
}
