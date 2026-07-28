"""제품 원가 지식베이스 — 금융.

필드의 의미는 패키지 문서(``products/__init__.py``) 참고. 이 파일은 **데이터만**
담는다 — 계산 로직은 ``app/data/fundamentals/unit_economics.py``.
"""
from __future__ import annotations

SECTOR = "금융"

PRODUCTS: dict[str, dict] = {
    # ===== 금융 (원자재 없음 — '원가'=이자비용·대손) =====
    "105560:kbfg": {
        "ticker": "105560", "company": "KB금융", "product": "은행지주(총수익 1,000원)",
        "unit": "총수익 1,000원", "retail_price": 1000, "channel": "금융",
        "channel_label": "조달·비용(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "이자비용(자금조달)", "weight": 0.45, "commodity": None},
            {"item": "인건비·판관비", "weight": 0.20, "commodity": None},
            {"item": "대손충당금(신용손실)", "weight": 0.15, "commodity": None},
            {"item": "전산·일반관리비", "weight": 0.12, "commodity": None},
            {"item": "기타", "weight": 0.08, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.75, "op": 0.25},
        "note": "원자재 무관. '원가'=조달 이자비용+대손충당금+인건비. 금리·연체율(대손)이 손익 좌우. 순이익률 25% 안팎.",
    },
    "055550:shinhan": {
        "ticker": "055550", "company": "신한지주", "product": "은행지주(총수익 1,000원)",
        "unit": "총수익 1,000원", "retail_price": 1000, "channel": "금융",
        "channel_label": "조달·비용(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "이자비용(자금조달)", "weight": 0.46, "commodity": None},
            {"item": "인건비·판관비", "weight": 0.20, "commodity": None},
            {"item": "대손충당금(신용손실)", "weight": 0.14, "commodity": None},
            {"item": "전산·일반관리비", "weight": 0.12, "commodity": None},
            {"item": "기타", "weight": 0.08, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.76, "op": 0.24},
        "note": "원자재 무관. 이자비용·대손충당금이 '원가'. 금리 사이클·연체율이 마진. 카드·증권 등 비은행 포트폴리오도.",
    },
    # ===== 증권·보험·리츠 (원자재 없음 — 금융비용·보험금·이자) =====
    "006800:miraeasset": {
        "ticker": "006800", "company": "미래에셋증권", "product": "증권(총수익 1,000원)",
        "unit": "총수익 1,000원", "retail_price": 1000, "channel": "금융",
        "channel_label": "조달·비용(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "이자비용·금융비용(조달)", "weight": 0.50, "commodity": None},
            {"item": "인건비·판관비", "weight": 0.30, "commodity": None},
            {"item": "전산·기타", "weight": 0.12, "commodity": None},
            {"item": "대손·기타", "weight": 0.08, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.85, "op": 0.15},
        "note": "원자재 무관. '원가'=조달 금융비용+인건비. 거래대금·금리·증시 방향이 손익 좌우.",
    },
    "032830:samsunglife": {
        "ticker": "032830", "company": "삼성생명", "product": "생명보험(수익 1,000원)",
        "unit": "수익 1,000원", "retail_price": 1000, "channel": "보험",
        "channel_label": "보험금·사업비(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "보험금·준비금 적립", "weight": 0.60, "commodity": None},
            {"item": "사업비(모집수수료)", "weight": 0.20, "commodity": None},
            {"item": "인건비·관리비", "weight": 0.10, "commodity": None},
            {"item": "기타", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.92, "op": 0.08},
        "note": "원자재 무관. '원가'=보험금·준비금+사업비. IFRS17 하 CSM·손해율·금리·운용수익이 손익 좌우.",
    },
    "000810:samsungfire": {
        "ticker": "000810", "company": "삼성화재", "product": "손해보험(수익 1,000원)",
        "unit": "수익 1,000원", "retail_price": 1000, "channel": "보험",
        "channel_label": "보험금·사업비(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "보험금·손해액", "weight": 0.65, "commodity": None},
            {"item": "사업비(모집)", "weight": 0.20, "commodity": None},
            {"item": "인건비·관리", "weight": 0.10, "commodity": None},
            {"item": "기타", "weight": 0.05, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.90, "op": 0.10},
        "note": "원자재 무관. 손해율+사업비율(합산비율)이 손익 좌우. 자동차·장기보험 손해율·운용수익이 관건.",
    },
    "330590:lottereit": {
        "ticker": "330590", "company": "롯데리츠", "product": "리츠(임대수익 1,000원)",
        "unit": "임대수익 1,000원", "retail_price": 1000, "channel": "부동산임대",
        "channel_label": "비용(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "이자비용(차입)", "weight": 0.40, "commodity": None},
            {"item": "감가상각", "weight": 0.25, "commodity": None},
            {"item": "재산세·관리비", "weight": 0.20, "commodity": None},
            {"item": "운영비", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.80, "op": 0.20},
        "note": "원자재 무관. 최대 비용이 차입 이자 → 금리 상승이 리츠 최대 악재. 임대료·공실률·배당수익률이 핵심.",
    },
    # ===== 카드·렌터카 =====
    "029780:samsungcard": {
        "ticker": "029780", "company": "삼성카드", "product": "카드(총수익 1,000원)",
        "unit": "총수익 1,000원", "retail_price": 1000, "channel": "금융",
        "channel_label": "조달·비용(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "조달 이자비용", "weight": 0.35, "commodity": None},
            {"item": "대손충당금(연체)", "weight": 0.25, "commodity": None},
            {"item": "인건비·판관비", "weight": 0.20, "commodity": None},
            {"item": "마케팅·포인트", "weight": 0.12, "commodity": None},
            {"item": "기타", "weight": 0.08, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.80, "op": 0.20},
        "note": "원자재 무관. 조달금리+대손(연체율)이 '원가'. 가맹점 수수료 규제·소비경기·연체율이 손익 좌우.",
    },
    "001450:hyundaimarine": {
        "ticker": "001450", "company": "현대해상", "product": "손해보험(수익 1,000원)",
        "unit": "수익 1,000원", "retail_price": 1000, "channel": "보험",
        "channel_label": "보험금·사업비(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "보험금·손해액", "weight": 0.65, "commodity": None},
            {"item": "사업비(모집)", "weight": 0.20, "commodity": None},
            {"item": "인건비·관리", "weight": 0.10, "commodity": None},
            {"item": "기타", "weight": 0.05, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.92, "op": 0.08},
        "note": "원자재 무관. 손해율+사업비율(합산비율)이 손익. 자동차·장기·실손보험 손해율·IFRS17 CSM이 관건.",
    },
    # ===== 증권 =====
    "039490:kiwoom": {
        "ticker": "039490", "company": "키움증권", "product": "증권(총수익 1,000원)",
        "unit": "총수익 1,000원", "retail_price": 1000, "channel": "금융",
        "channel_label": "조달·비용(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "이자비용·금융비용", "weight": 0.45, "commodity": None},
            {"item": "인건비·판관비", "weight": 0.25, "commodity": None},
            {"item": "전산·기타", "weight": 0.15, "commodity": None},
            {"item": "대손·기타", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.75, "op": 0.25},
        "note": "원자재 무관. 리테일 브로커리지 1위 — 거래대금·증시 방향이 손익 직결. 낮은 비용구조로 고ROE.",
    },
    "005940:nhis": {
        "ticker": "005940", "company": "NH투자증권", "product": "증권(총수익 1,000원)",
        "unit": "총수익 1,000원", "retail_price": 1000, "channel": "금융",
        "channel_label": "조달·비용(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "이자비용·금융비용", "weight": 0.48, "commodity": None},
            {"item": "인건비·판관비", "weight": 0.27, "commodity": None},
            {"item": "전산·기타", "weight": 0.13, "commodity": None},
            {"item": "대손·기타", "weight": 0.12, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.80, "op": 0.20},
        "note": "원자재 무관. IB·WM 균형. 거래대금·금리·부동산PF가 손익 변수. 농협 계열 대형 증권사.",
    },
}
