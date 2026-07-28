"""제품 원가 지식베이스 — 의류·패션.

필드의 의미는 패키지 문서(``products/__init__.py``) 참고. 이 파일은 **데이터만**
담는다 — 계산 로직은 ``app/data/fundamentals/unit_economics.py``.
"""
from __future__ import annotations

SECTOR = "의류·패션"

PRODUCTS: dict[str, dict] = {
    # ===== 의류 (브랜드 vs OEM 대비) =====
    "383220:mlb": {
        "ticker": "383220", "company": "F&F", "product": "MLB 브랜드 의류",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "브랜드",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 0.35,
        "material_mix": [
            {"item": "상품매입원가(OEM 사입)", "weight": 0.55, "commodity": None},
            {"item": "브랜드 라이선스 로열티", "weight": 0.15, "commodity": None},
            {"item": "면 원단·면화", "weight": 0.12, "commodity": "cotton"},
            {"item": "화섬(폴리에스터) 원단", "weight": 0.08, "commodity": "naphtha"},
            {"item": "봉제 인건비·부자재", "weight": 0.06, "commodity": None},
            {"item": "물류비", "weight": 0.04, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.36, "op": 0.25},
        "note": "브랜드사=고마진(영업이익률 25%). 원가보다 브랜드·라이선스가 판가 결정. 원단(면화·화섬) 노출은 간접적.",
    },
    "111770:oem": {
        "ticker": "111770", "company": "영원무역", "product": "아웃도어 의류 OEM",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "OEM 수출",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 0.75,
        "material_mix": [
            {"item": "면 원단·면화", "weight": 0.30, "commodity": "cotton"},
            {"item": "화섬(폴리에스터) 원단", "weight": 0.22, "commodity": "naphtha"},
            {"item": "봉제 인건비(방글라·베트남)", "weight": 0.28, "commodity": None},
            {"item": "부자재(지퍼·라벨)", "weight": 0.12, "commodity": None},
            {"item": "물류·기타", "weight": 0.08, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.75, "op": 0.11},
        "note": "OEM 제조=저마진·고원가율(75%). 원가 절반이 원단(면화·화섬), 나머지가 봉제 인건비. 면화·유가·환율 직결.",
    },
    "105630:hansae": {
        "ticker": "105630", "company": "한세실업", "product": "의류 OEM",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "OEM 수출",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "면 원단·면화", "weight": 0.30, "commodity": "cotton"},
            {"item": "화섬(폴리에스터)", "weight": 0.20, "commodity": "naphtha"},
            {"item": "봉제 인건비(베트남·중미)", "weight": 0.28, "commodity": None},
            {"item": "부자재", "weight": 0.12, "commodity": None},
            {"item": "물류·기타", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.82, "op": 0.07},
        "note": "갭·타겟 등 미국 바이어 OEM. 면화·유가·환율·미국 소비경기에 실적 직결. 저마진 제조.",
    },
}
