"""제품 단위 원가분해 (unit economics) — "이 물건 하나 팔면 얼마 남는지".

회사 전체 원가율(예: 71%)이 아니라 **제품 1개**를 팔면 소비자가 낸 돈이 누구에게
얼마씩 가는지를 분해한다. 6단계 재구성:

  ① 소비자가            (retail_price, 조사값)
  ② − 유통마진 → 출고가  (회사가 실제 인식하는 매출)
  ③ 출고가를 회사 재무비율로 3분할: 매출원가 · 판관비 · 영업이익
        → 비율은 DART 손익계산서(store.dart_financials)에서 실측, 없으면 KB 기본값
  ④ 매출원가를 원재료비 vs 가공비(노무·감가·에너지)로 분할
  ⑤ 원재료비를 제품별 구성(material_mix)으로 배분 (밀가루·팜유·포장재·스프…)
  ⑥ 마진 민감도: 각 원자재 ±10% / 현재 추세(chg_1y) → 봉지당 영업이익 변화

③④가 **회사 실측 재무**라 자동 갱신되고, ⑤는 제품 지식베이스(추정), ⑥은
commodities 시세를 물린다. SKU별 원가는 어디에도 공시되지 않으므로 이 값은
'투명하게 재구성한 추정'이며 각 가정을 함께 반환한다.
"""
from __future__ import annotations

from app.data.fundamentals import commodities
from app.data.infra import store

# --- 제품 지식베이스 -------------------------------------------------------
# distribution_margin : 소비자가 중 유통(도소매)이 가져가는 몫
# material_ratio_of_cogs: 매출원가 중 원재료비 비중(나머지 = 가공비: 노무·감가·에너지)
# material_mix.weight : 원재료비 내 상대 비중(합=1.0)
# default_ratios      : DART 실측 실패 시 폴백 {cogs, op}
PRODUCTS: dict[str, dict] = {
    "004370:sinramyeon": {
        "ticker": "004370", "company": "농심", "product": "신라면",
        "unit": "120g 1봉지", "retail_price": 1000, "channel": "대형마트",
        "distribution_margin": 0.20, "material_ratio_of_cogs": 0.80,
        "material_mix": [
            {"item": "밀가루(소맥분)", "weight": 0.24, "commodity": "wheat"},
            {"item": "팜유(면 튀김)", "weight": 0.24, "commodity": "palm_oil"},
            {"item": "포장재(봉지)", "weight": 0.27, "commodity": "bopp_film"},
            {"item": "스프·건더기", "weight": 0.16, "commodity": None},
            {"item": "기타 원료", "weight": 0.09, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.71, "op": 0.052},
        "note": "라면은 봉지(포장재)가 밀가루·팜유만큼 큰 원가. 물량 사업.",
    },
    "007310:jinramyeon": {
        "ticker": "007310", "company": "오뚜기", "product": "진라면",
        "unit": "120g 1봉지", "retail_price": 720, "channel": "대형마트",
        "distribution_margin": 0.20, "material_ratio_of_cogs": 0.80,
        "material_mix": [
            {"item": "밀가루(소맥분)", "weight": 0.24, "commodity": "wheat"},
            {"item": "팜유(면 튀김)", "weight": 0.24, "commodity": "palm_oil"},
            {"item": "포장재(봉지)", "weight": 0.27, "commodity": "bopp_film"},
            {"item": "스프·건더기", "weight": 0.16, "commodity": None},
            {"item": "기타 원료", "weight": 0.09, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.83, "op": 0.063},
        "note": "신라면보다 저가 포지셔닝 → 봉지당 마진이 더 얇음. 가성비 물량 전략.",
    },
    "271560:chocopie": {
        "ticker": "271560", "company": "오리온", "product": "초코파이 情",
        "unit": "1개(약 35g)", "retail_price": 400, "channel": "박스 환산",
        "distribution_margin": 0.20, "material_ratio_of_cogs": 0.75,
        "material_mix": [
            {"item": "소맥분", "weight": 0.22, "commodity": "wheat"},
            {"item": "유지(팜유·쇼트닝)", "weight": 0.24, "commodity": "palm_oil"},
            {"item": "코코아", "weight": 0.14, "commodity": "cocoa"},
            {"item": "당류(원당·물엿)", "weight": 0.12, "commodity": "sugar"},
            {"item": "포장재", "weight": 0.18, "commodity": "bopp_film"},
            {"item": "기타 원료", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.60, "op": 0.167},
        "note": "코코아 -60% 급락 수혜. 브랜드 전가력 강해 5사 중 최고 마진.",
    },
    "097950:hetbahn": {
        "ticker": "097950", "company": "CJ제일제당", "product": "햇반",
        "unit": "210g 1개", "retail_price": 1600, "channel": "대형마트",
        "distribution_margin": 0.18, "material_ratio_of_cogs": 0.70,
        "material_mix": [
            {"item": "쌀(국내산)", "weight": 0.55, "commodity": "rice"},
            {"item": "포장용기(PP)", "weight": 0.18, "commodity": None},
            {"item": "살균·에너지", "weight": 0.12, "commodity": None},
            {"item": "기타 원료", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.69, "op": 0.058},
        "note": "원가의 절반이 쌀 → 산지쌀값(정부 수매)이 마진 좌우. 즉석밥 압도적 1위.",
    },
    "005300:chilsung": {
        "ticker": "005300", "company": "롯데칠성", "product": "칠성사이다",
        "unit": "355ml 캔", "retail_price": 900, "channel": "대형마트",
        "distribution_margin": 0.22, "material_ratio_of_cogs": 0.55,
        "material_mix": [
            {"item": "알루미늄 캔", "weight": 0.50, "commodity": "aluminum"},
            {"item": "감미료(원당·과당)", "weight": 0.25, "commodity": "sugar"},
            {"item": "향료·원액", "weight": 0.15, "commodity": None},
            {"item": "기타 원료", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.64, "op": 0.042},
        "note": "원가의 절반이 포장재(알루미늄캔). 곡물이 아니라 알루미늄·나프타·환율을 봐야 함.",
    },

    # --- 라면·스낵 확장 ---
    "003230:buldak": {
        "ticker": "003230", "company": "삼양식품", "product": "불닭볶음면",
        "unit": "140g 1봉지", "retail_price": 1500, "channel": "대형마트",
        "distribution_margin": 0.20, "material_ratio_of_cogs": 0.80,
        "material_mix": [
            {"item": "밀가루(면·글루텐)", "weight": 0.42, "commodity": "wheat"},
            {"item": "정제 팜유(튀김유)", "weight": 0.24, "commodity": "palm_oil"},
            {"item": "포장재", "weight": 0.15, "commodity": "bopp_film"},
            {"item": "당류·전분(스프)", "weight": 0.10, "commodity": "sugar"},
            {"item": "향신료·유지·기타", "weight": 0.09, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.63, "op": 0.20},
        "note": "수출 비중 77%(불닭). 매출·원가 모두 원/달러 환율에 노출 — 라면인데 환율주. 영업이익률 20%대.",
    },
    "004370:saewookkang": {
        "ticker": "004370", "company": "농심", "product": "새우깡",
        "unit": "90g 1봉지", "retail_price": 1300, "channel": "대형마트",
        "distribution_margin": 0.22, "material_ratio_of_cogs": 0.78,
        "material_mix": [
            {"item": "밀가루", "weight": 0.34, "commodity": "wheat"},
            {"item": "정제 팜유(튀김유)", "weight": 0.24, "commodity": "palm_oil"},
            {"item": "감자전분", "weight": 0.14, "commodity": "potato"},
            {"item": "생새우·새우분말", "weight": 0.13, "commodity": None},
            {"item": "포장재", "weight": 0.10, "commodity": "bopp_film"},
            {"item": "당류·조미", "weight": 0.05, "commodity": "sugar"},
        ],
        "default_ratios": {"cogs": 0.69, "op": 0.047},
        "note": "튀김 스낵이라 팜유 민감. 내수 중심 저마진(영업이익률 ~5%).",
    },
    "271560:pocachip": {
        "ticker": "271560", "company": "오리온", "product": "포카칩",
        "unit": "66g 1봉지", "retail_price": 1700, "channel": "대형마트",
        "distribution_margin": 0.23, "material_ratio_of_cogs": 0.77,
        "material_mix": [
            {"item": "생감자", "weight": 0.44, "commodity": "potato"},
            {"item": "정제 팜유(튀김유)", "weight": 0.28, "commodity": "palm_oil"},
            {"item": "포장재", "weight": 0.16, "commodity": "bopp_film"},
            {"item": "당류·조미(소금·향미)", "weight": 0.12, "commodity": "sugar"},
        ],
        "default_ratios": {"cogs": 0.57, "op": 0.175},
        "note": "생감자 91% — 감자 작황·팜유가 핵심. 제과 최강 수익성(영업이익률 17%대).",
    },

    # --- 제과·빙과 ---
    "280360:pepero": {
        "ticker": "280360", "company": "롯데웰푸드", "product": "빼빼로 오리지널",
        "unit": "54g 1갑", "retail_price": 1600, "channel": "대형마트",
        "distribution_margin": 0.40, "material_ratio_of_cogs": 0.58,
        "material_mix": [
            {"item": "코코아·초콜릿", "weight": 0.35, "commodity": "cocoa"},
            {"item": "식물성유지(팜유)", "weight": 0.20, "commodity": "palm_oil"},
            {"item": "소맥(스틱)", "weight": 0.18, "commodity": "wheat"},
            {"item": "당류", "weight": 0.15, "commodity": "sugar"},
            {"item": "포장재", "weight": 0.12, "commodity": "bopp_film"},
        ],
        "default_ratios": {"cogs": 0.72, "op": 0.039},
        "note": "초콜릿 코팅 비중 커 코코아 급등(2배)에 직격. 오리온과 정반대로 코코아 민감도 최상.",
    },
    "005180:bananamilk": {
        "ticker": "005180", "company": "빙그레", "product": "바나나맛우유",
        "unit": "240ml 단지", "retail_price": 1700, "channel": "편의점",
        "distribution_margin": 0.38, "material_ratio_of_cogs": 0.60,
        "material_mix": [
            {"item": "원유(우유)", "weight": 0.55, "commodity": "raw_milk"},
            {"item": "당류", "weight": 0.15, "commodity": "sugar"},
            {"item": "단지 용기·포장재", "weight": 0.20, "commodity": "bopp_film"},
            {"item": "바나나향·안정제", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.737, "op": 0.09},
        "note": "원유가격 연동제에 원가 직결. 원유 상승 시 판가 인상으로 방어. 독특한 단지라 포장재 비중도 큼.",
    },
    "005180:melona": {
        "ticker": "005180", "company": "빙그레", "product": "메로나",
        "unit": "아이스크림 1개", "retail_price": 1200, "channel": "일반소매",
        "distribution_margin": 0.50, "material_ratio_of_cogs": 0.55,
        "material_mix": [
            {"item": "원유·유크림", "weight": 0.35, "commodity": "raw_milk"},
            {"item": "당류", "weight": 0.20, "commodity": "sugar"},
            {"item": "포장재", "weight": 0.20, "commodity": "bopp_film"},
            {"item": "메론과즙·향료", "weight": 0.13, "commodity": None},
            {"item": "식물성유지", "weight": 0.12, "commodity": "palm_oil"},
        ],
        "default_ratios": {"cogs": 0.737, "op": 0.09},
        "note": "유가공품이라 원유가 핵심. 채널별 가격 편차 극심(할인점 600 vs 편의점 1,500)→유통마진 변동성 큼.",
    },

    # --- 주류 (세금이 소비자가의 큰 축) ---
    "000080:chamisul": {
        "ticker": "000080", "company": "하이트진로", "product": "참이슬 후레쉬",
        "unit": "360ml 병", "retail_price": 1350, "channel": "대형마트",
        "channel_label": "세금(주세 등)+유통",
        "distribution_margin": 0.50, "material_ratio_of_cogs": 0.40,
        "material_mix": [
            {"item": "주정", "weight": 0.45, "commodity": "ethanol_alcohol"},
            {"item": "공병(유리병)", "weight": 0.25, "commodity": None},
            {"item": "당류·감미료", "weight": 0.12, "commodity": "sugar"},
            {"item": "라벨·박스 포장재", "weight": 0.13, "commodity": "bopp_film"},
            {"item": "정제수·첨가물", "weight": 0.05, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.56, "op": 0.085},
        "note": "출고가의 절반이 주세(종가세 72%). 원가 핵심은 주정+공병. 소주는 세금이 최대 단일 항목.",
    },
    "000080:terra": {
        "ticker": "000080", "company": "하이트진로", "product": "테라",
        "unit": "500ml 캔", "retail_price": 2170, "channel": "대형마트",
        "channel_label": "세금(주세 등)+유통",
        "distribution_margin": 0.45, "material_ratio_of_cogs": 0.50,
        "material_mix": [
            {"item": "맥아(호주산)", "weight": 0.40, "commodity": "malt"},
            {"item": "캔·병 용기", "weight": 0.30, "commodity": None},
            {"item": "전분(부원료)", "weight": 0.10, "commodity": "sugar"},
            {"item": "호프", "weight": 0.08, "commodity": None},
            {"item": "포장재", "weight": 0.08, "commodity": "bopp_film"},
            {"item": "정제수·첨가물", "weight": 0.04, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.56, "op": 0.085},
        "note": "맥주는 맥아+용기(캔)가 원가 핵심. 종량세(885.7원/L)로 500ml당 주세 442.85원.",
    },
    "005300:chumchurum": {
        "ticker": "005300", "company": "롯데칠성", "product": "처음처럼",
        "unit": "360ml 병", "retail_price": 1320, "channel": "대형마트",
        "channel_label": "세금(주세 등)+유통",
        "distribution_margin": 0.50, "material_ratio_of_cogs": 0.40,
        "material_mix": [
            {"item": "주정", "weight": 0.45, "commodity": "ethanol_alcohol"},
            {"item": "공병(유리병)", "weight": 0.25, "commodity": None},
            {"item": "당류·감미료", "weight": 0.12, "commodity": "sugar"},
            {"item": "라벨·박스 포장재", "weight": 0.13, "commodity": "bopp_film"},
            {"item": "정제수·첨가물", "weight": 0.05, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.62, "op": 0.043},
        "note": "참이슬과 원가 구조 동일(주정+주세+공병). 주류부문 영업이익률(~4%)이 하이트진로보다 낮음.",
    },

    # --- 가공식품 ---
    "007310:ketchup": {
        "ticker": "007310", "company": "오뚜기", "product": "토마토케챂",
        "unit": "300g", "retail_price": 1500, "channel": "대형마트",
        "distribution_margin": 0.25, "material_ratio_of_cogs": 0.55,
        "material_mix": [
            {"item": "토마토페이스트", "weight": 0.55, "commodity": "tomato"},
            {"item": "물엿·백설탕(당류)", "weight": 0.30, "commodity": "sugar"},
            {"item": "식초·향신료·기타", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.829, "op": 0.063},
        "note": "사실상 토마토+설탕 가공품. 수입 토마토페이스트 가격에 마진 직결.",
    },
    "097950:wangkyoja": {
        "ticker": "097950", "company": "CJ제일제당", "product": "비비고 왕교자",
        "unit": "350g 냉동 1봉", "retail_price": 3300, "channel": "대형마트",
        "distribution_margin": 0.30, "material_ratio_of_cogs": 0.60,
        "material_mix": [
            {"item": "돈육", "weight": 0.40, "commodity": "pork"},
            {"item": "만두피(소맥분)", "weight": 0.25, "commodity": "wheat"},
            {"item": "채소·두부·당면 등", "weight": 0.35, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.74, "op": 0.055},
        "note": "돈육+만두피가 원가 축. CJ 글로벌전략제품(해외 만두 +18%) — 돈육·소맥 국제가가 변동성 핵심.",
    },
    "049770:tunacan": {
        "ticker": "049770", "company": "동원F&B", "product": "동원참치 살코기",
        "unit": "85g 캔", "retail_price": 1690, "channel": "대형마트",
        "distribution_margin": 0.25, "material_ratio_of_cogs": 0.65,
        "material_mix": [
            {"item": "가다랑어(원양)", "weight": 0.55, "commodity": "tuna"},
            {"item": "캔(주석/알루미늄)", "weight": 0.28, "commodity": "aluminum"},
            {"item": "카놀라유·야채즙·기타", "weight": 0.17, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.79, "op": 0.041},
        "note": "'생선+깡통' 마진 구조. 국제 가다랑어 어가·주석캔 가격에 원가 직결. 어가 하락 시 마진 개선.",
    },

    # --- 고마진·조미·기호 ---
    "033780:esse": {
        "ticker": "033780", "company": "KT&G", "product": "에쎄(ESSE)",
        "unit": "1갑(20개비)", "retail_price": 4500, "channel": "편의점",
        "channel_label": "세금(담배세 74%)+유통",
        "distribution_margin": 0.84, "material_ratio_of_cogs": 0.55,
        "material_mix": [
            {"item": "잎담배(연초)", "weight": 0.70, "commodity": "tobacco_leaf"},
            {"item": "포장재(BOPP·판지)", "weight": 0.12, "commodity": "bopp_film"},
            {"item": "필터(초산셀룰로오스)", "weight": 0.10, "commodity": None},
            {"item": "향료·첨가물", "weight": 0.08, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.51, "op": 0.20},
        "note": "소비자가 4,500원 중 세금 3,323원(74%). KT&G 실수취는 ~16%. 담뱃세 올라도 회사 몫은 고정.",
    },
    "001680:miwon": {
        "ticker": "001680", "company": "대상", "product": "미원",
        "unit": "100g", "retail_price": 1980, "channel": "대형마트",
        "distribution_margin": 0.35, "material_ratio_of_cogs": 0.55,
        "material_mix": [
            {"item": "사탕수수 원당·당밀", "weight": 0.60, "commodity": "sugar"},
            {"item": "발효 영양원", "weight": 0.10, "commodity": "corn"},
            {"item": "정제·중화 부재료", "weight": 0.10, "commodity": None},
            {"item": "포장재", "weight": 0.12, "commodity": "bopp_film"},
            {"item": "리보뉴클레오타이드 등", "weight": 0.08, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.76, "op": 0.043},
        "note": "원당을 미생물 발효→MSG. 원가 핵심은 국제 원당·당밀 시세. 회사 영업이익률 ~4%로 얇음.",
    },
    "007310:mayo": {
        "ticker": "007310", "company": "오뚜기", "product": "마요네스",
        "unit": "300g", "retail_price": 2230, "channel": "대형마트",
        "distribution_margin": 0.35, "material_ratio_of_cogs": 0.60,
        "material_mix": [
            {"item": "대두유(식용유)", "weight": 0.55, "commodity": "soybean_oil"},
            {"item": "난황·계란", "weight": 0.20, "commodity": None},
            {"item": "양조식초", "weight": 0.08, "commodity": None},
            {"item": "당류", "weight": 0.07, "commodity": "sugar"},
            {"item": "포장 용기·필름", "weight": 0.10, "commodity": "bopp_film"},
        ],
        "default_ratios": {"cogs": 0.829, "op": 0.063},
        "note": "원가 절반이 대두유. 국제 대두유(-22%) 하락 시 수혜. 매출원가율 83%로 유지류 민감.",
    },

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

    # ===== 제약·건기식 =====
    "000100:bcomc": {
        "ticker": "000100", "company": "유한양행", "product": "삐콤씨",
        "unit": "100정 병", "retail_price": 20000, "channel": "약국",
        "distribution_margin": 0.50, "material_ratio_of_cogs": 0.55,
        "material_mix": [
            {"item": "비타민C 원료(API)", "weight": 0.35, "commodity": "api_pharma"},
            {"item": "비타민B군 원료(API)", "weight": 0.20, "commodity": "api_pharma"},
            {"item": "셀레늄·미네랄 등", "weight": 0.15, "commodity": None},
            {"item": "부형제·당의코팅", "weight": 0.15, "commodity": "sugar"},
            {"item": "포장재(병·PTP)", "weight": 0.15, "commodity": "bopp_film"},
        ],
        "default_ratios": {"cogs": 0.68, "op": 0.023},
        "note": "OTC는 원가보다 '국민영양제' 브랜드+약국 유통마진이 가격 좌우. 유한은 도입상품·R&D로 영업이익률 낮음.",
    },
    "000640:bacchus": {
        "ticker": "000640", "company": "동아쏘시오", "product": "박카스",
        "unit": "100ml 병", "retail_price": 700, "channel": "약국·편의점",
        "distribution_margin": 0.40, "material_ratio_of_cogs": 0.45,
        "material_mix": [
            {"item": "유리병·뚜껑", "weight": 0.30, "commodity": None},
            {"item": "설탕(당류)", "weight": 0.28, "commodity": "sugar"},
            {"item": "타우린", "weight": 0.15, "commodity": None},
            {"item": "카페인·비타민B군", "weight": 0.12, "commodity": None},
            {"item": "라벨·박스 포장재", "weight": 0.15, "commodity": "bopp_film"},
        ],
        "default_ratios": {"cogs": 0.52, "op": 0.126},
        "note": "원료보다 60년 브랜드+약국/편의점 유통망이 마진 핵심. 자체제조라 제약사 중 원가율 낮음.",
    },
    "128940:amosartan": {
        "ticker": "128940", "company": "한미약품", "product": "아모잘탄(고혈압약)",
        "unit": "1정(급여 약가)", "retail_price": 767, "channel": "처방(약가제도)",
        "channel_label": "약가·유통(건강보험)",
        "distribution_margin": 0.15, "material_ratio_of_cogs": 0.45,
        "material_mix": [
            {"item": "암로디핀 원료(API)", "weight": 0.35, "commodity": "api_pharma"},
            {"item": "로사르탄 원료(API)", "weight": 0.35, "commodity": "api_pharma"},
            {"item": "부형제·코팅제", "weight": 0.10, "commodity": "sugar"},
            {"item": "PTP·병·포장재", "weight": 0.20, "commodity": "bopp_film"},
        ],
        "default_ratios": {"cogs": 0.50, "op": 0.145},
        "note": "전문약은 브랜드보다 건강보험 약가제도(상한가 인하)+API 수입가가 마진 좌우. 복합신약이라 원가율 낮고 수익성 최고.",
    },

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

    # ===== 유가공·육계·제빵 =====
    "267980:maeilmilk": {
        "ticker": "267980", "company": "매일유업", "product": "매일우유",
        "unit": "900ml", "retail_price": 2860, "channel": "대형마트",
        "distribution_margin": 0.30, "material_ratio_of_cogs": 0.70,
        "material_mix": [
            {"item": "원유(우유)", "weight": 0.90, "commodity": "raw_milk"},
            {"item": "당류", "weight": 0.02, "commodity": "sugar"},
            {"item": "종이팩·포장재", "weight": 0.08, "commodity": "bopp_film"},
        ],
        "default_ratios": {"cogs": 0.732, "op": 0.033},
        "note": "원가의 90%가 원유. 낙농진흥회 원유 기본가(연동제)에 실적 직결. 영업이익률 3%대로 얇음.",
    },
    "136480:harim": {
        "ticker": "136480", "company": "하림", "product": "생닭(도계육)",
        "unit": "1kg", "retail_price": 6500, "channel": "대형마트",
        "distribution_margin": 0.25, "material_ratio_of_cogs": 0.80,
        "material_mix": [
            {"item": "생계(육계 시세)", "weight": 0.55, "commodity": "chicken"},
            {"item": "사료 옥수수", "weight": 0.28, "commodity": "corn"},
            {"item": "대두박", "weight": 0.12, "commodity": "soybean"},
            {"item": "포장재", "weight": 0.05, "commodity": "bopp_film"},
        ],
        "default_ratios": {"cogs": 0.859, "op": 0.006},
        "note": "사료(옥수수·대두)+생계 시세에 이중 노출. 닭값 사이클상 공급과잉 국면엔 분기 적자. 영업이익률 0.6%.",
    },
    "005610:samlip": {
        "ticker": "005610", "company": "SPC삼립", "product": "삼립호빵(단팥)",
        "unit": "1개(약 100g)", "retail_price": 1200, "channel": "편의점",
        "distribution_margin": 0.35, "material_ratio_of_cogs": 0.55,
        "material_mix": [
            {"item": "소맥분(호빵 피)", "weight": 0.45, "commodity": "wheat"},
            {"item": "팥·설탕(팥소)", "weight": 0.28, "commodity": "sugar"},
            {"item": "유지(쇼트닝)", "weight": 0.12, "commodity": "palm_oil"},
            {"item": "유제품·버터", "weight": 0.05, "commodity": "raw_milk"},
            {"item": "개별 포장재", "weight": 0.10, "commodity": "bopp_film"},
        ],
        "default_ratios": {"cogs": 0.82, "op": 0.028},
        "note": "소맥·팥·당류가 원가 좌우. 2022 포켓몬빵 흥행 후 매출 정체. 영업이익률 2.8%.",
    },

    # ===== 반도체 (판가 사이클이 마진의 전부, B2B) =====
    "005930:dram": {
        "ticker": "005930", "company": "삼성전자", "product": "DRAM(DDR5, DS부문)",
        "unit": "8Gb 환산(1GB)", "retail_price": 36000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.05, "material_ratio_of_cogs": 0.32,
        "material_mix": [
            {"item": "장비 감가상각(EUV 등)", "weight": 0.45, "commodity": None},
            {"item": "소재·가스", "weight": 0.18, "commodity": None},
            {"item": "전력(팹 가동)", "weight": 0.12, "commodity": None},
            {"item": "실리콘 웨이퍼", "weight": 0.10, "commodity": "silicon_wafer"},
            {"item": "인건비·포장·기타", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.62, "op": 0.19},
        "note": "메모리는 DRAM 판가(ASP) 사이클이 마진의 전부. 원가는 감가상각·전력 중심 고정비. '25 판가 급등이 이익 견인.",
    },
    "000660:hbm": {
        "ticker": "000660", "company": "SK하이닉스", "product": "HBM3E(AI가속기용)",
        "unit": "36GB 스택", "retail_price": 405000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.05, "material_ratio_of_cogs": 0.35,
        "material_mix": [
            {"item": "장비 감가상각(팹+패키징)", "weight": 0.42, "commodity": None},
            {"item": "소재·가스(TSV·본딩)", "weight": 0.20, "commodity": None},
            {"item": "패키징·테스트(수율손실)", "weight": 0.13, "commodity": None},
            {"item": "전력", "weight": 0.10, "commodity": None},
            {"item": "실리콘 웨이퍼", "weight": 0.10, "commodity": "silicon_wafer"},
            {"item": "인건비·기타", "weight": 0.05, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.40, "op": 0.49},
        "note": "HBM 판가 사이클이 마진 결정. AI 수요로 '26 20% 추가 인상 — 판가 강세가 사상 최대 이익(OPM 49%) 원동력.",
    },

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
    "051910:ethylene": {
        "ticker": "051910", "company": "LG화학", "product": "에틸렌(NCC)",
        "unit": "톤", "retail_price": 1100000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.03, "material_ratio_of_cogs": 0.80,
        "material_mix": [
            {"item": "나프타(원료)", "weight": 0.75, "commodity": "naphtha"},
            {"item": "전력·스팀·연료", "weight": 0.13, "commodity": None},
            {"item": "인건비·감가상각", "weight": 0.12, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.98, "op": -0.02},
        "note": "화학 마진 = 에틸렌가 − 나프타 = 스프레드가 전부. 중국 증설로 스프레드 붕괴 → 석화부문 적자(-2%).",
    },
    "011170:lottechem": {
        "ticker": "011170", "company": "롯데케미칼", "product": "기초 석유화학(올레핀)",
        "unit": "톤", "retail_price": 1050000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.03, "material_ratio_of_cogs": 0.82,
        "material_mix": [
            {"item": "나프타(원료)", "weight": 0.76, "commodity": "naphtha"},
            {"item": "전력·유틸리티", "weight": 0.12, "commodity": None},
            {"item": "인건비·감가상각", "weight": 0.12, "commodity": None},
        ],
        "default_ratios": {"cogs": 1.0, "op": -0.051},
        "note": "범용 비중 높아 중국 공급과잉에 가장 취약, 적자 최대(-5.1%). 제품가−나프타 스프레드가 마진.",
    },

    # ===== 2차전지 (메탈가 연동·IRA 보조금) =====
    "373220:lgbattery": {
        "ticker": "373220", "company": "LG에너지솔루션", "product": "리튬이온 배터리(NMC)",
        "unit": "kWh", "retail_price": 175000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.05, "material_ratio_of_cogs": 0.70,
        "material_mix": [
            {"item": "니켈(양극재)", "weight": 0.20, "commodity": "nickel"},
            {"item": "리튬", "weight": 0.12, "commodity": "lithium"},
            {"item": "코발트", "weight": 0.06, "commodity": "cobalt"},
            {"item": "양극재 가공·전구체·분리막", "weight": 0.22, "commodity": None},
            {"item": "음극재·전해질·동박", "weight": 0.20, "commodity": None},
            {"item": "전력·감가상각·인건비", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.84, "op": 0.057},
        "note": "판가가 메탈가에 연동(연동제) → 메탈 하락이 원가·매출 동시 인하로 양면적. IRA 보조금 빼면 실질 적자.",
    },
    "006400:samsungsdi": {
        "ticker": "006400", "company": "삼성SDI", "product": "각형/원통형 배터리(NCA)",
        "unit": "kWh", "retail_price": 190000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.05, "material_ratio_of_cogs": 0.72,
        "material_mix": [
            {"item": "니켈(하이니켈)", "weight": 0.24, "commodity": "nickel"},
            {"item": "리튬", "weight": 0.12, "commodity": "lithium"},
            {"item": "코발트", "weight": 0.05, "commodity": "cobalt"},
            {"item": "양극재 가공·전구체", "weight": 0.21, "commodity": None},
            {"item": "음극재·분리막·전해질", "weight": 0.18, "commodity": None},
            {"item": "전력·감가상각·인건비", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.98, "op": -0.13},
        "note": "전기차 캐즘에 출하 급감+가동률 저하로 대규모 적자(-13%). 메탈가 하락은 판가도 낮춰 양면적.",
    },

    # ===== 에너지·운송 (연료·운임 사이클) =====
    "015760:electricity": {
        "ticker": "015760", "company": "한국전력", "product": "전기",
        "unit": "1kWh", "retail_price": 160, "channel": "규제요금",
        "channel_label": "송배전·판매(규제)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 0.67,
        "material_mix": [
            {"item": "석탄(유연탄) 발전연료", "weight": 0.22, "commodity": "coking_coal"},
            {"item": "LNG(천연가스) 발전연료", "weight": 0.18, "commodity": "lng"},
            {"item": "민간발전 전력구입비", "weight": 0.40, "commodity": None},
            {"item": "원자력·신재생 연료", "weight": 0.15, "commodity": None},
            {"item": "중유·기타 발전연료", "weight": 0.05, "commodity": "crude_oil"},
        ],
        "default_ratios": {"cogs": 0.85, "op": 0.089},
        "note": "연료비(LNG·석탄)를 규제요금에 못 넘기면 원가율 100%+ 적자. '22년 -32.7조 → '24년 요금 +6.6%로 흑자전환.",
    },
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

    # ===== 통신·인터넷 (원자재 없음 — 인건비·감가상각·마케팅) =====
    "017670:skt": {
        "ticker": "017670", "company": "SK텔레콤", "product": "이동통신(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "직판·대리점",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "망 설비 감가상각+주파수 상각", "weight": 0.30, "commodity": None},
            {"item": "마케팅(수수료·리베이트·광고)", "weight": 0.22, "commodity": None},
            {"item": "망 운영·상호접속·전력", "weight": 0.20, "commodity": None},
            {"item": "인건비", "weight": 0.12, "commodity": None},
            {"item": "단말·상품원가·기타", "weight": 0.16, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.898, "op": 0.102},
        "note": "원자재 무관. 망 설비 감가상각+마케팅(리베이트)이 원가 핵심인 대규모 고정비 사업.",
    },
    "035420:naver": {
        "ticker": "035420", "company": "NAVER", "product": "검색·커머스(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "플랫폼",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "파트너·콘텐츠정산·결제수수료", "weight": 0.42, "commodity": None},
            {"item": "개발·운영 인건비", "weight": 0.24, "commodity": None},
            {"item": "마케팅비", "weight": 0.17, "commodity": None},
            {"item": "인프라(데이터센터·서버)", "weight": 0.07, "commodity": None},
            {"item": "기타 영업비용", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.816, "op": 0.184},
        "note": "원자재 무관. 개발자 인건비+파트너 정산/결제수수료+서버 감가상각이 원가인 인건비·고정비 사업.",
    },
    "035720:kakao": {
        "ticker": "035720", "company": "카카오", "product": "플랫폼(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "플랫폼",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "매출연동비(수수료·정산·결제)", "weight": 0.40, "commodity": None},
            {"item": "개발자 인건비", "weight": 0.24, "commodity": None},
            {"item": "외주·인프라(서버·데이터센터)", "weight": 0.14, "commodity": None},
            {"item": "마케팅비", "weight": 0.12, "commodity": None},
            {"item": "콘텐츠·감가상각·기타", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.938, "op": 0.062},
        "note": "원자재 무관. 결제·정산 매출연동비+개발자 인건비+서버 감가상각이 원가. 영업이익률 6.2%.",
    },

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

    # ===== 조선 (후판이 핵심, 고선가 수주로 마진 개선) =====
    "329180:hdhi": {
        "ticker": "329180", "company": "HD현대중공업", "product": "선박(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "수주",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 0.55,
        "material_mix": [
            {"item": "후판(선박용 철강)", "weight": 0.20, "commodity": "steel_hr"},
            {"item": "엔진·기자재", "weight": 0.35, "commodity": None},
            {"item": "인건비(직영+협력)", "weight": 0.20, "commodity": None},
            {"item": "외주비", "weight": 0.15, "commodity": None},
            {"item": "도장·의장", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.897, "op": 0.049},
        "note": "후판(철강)+기자재+인건비가 원가. 후판가·환율·수주단가가 마진 좌우. 고선가 수주분 인식으로 마진 개선.",
    },
    "042660:hanwhaocean": {
        "ticker": "042660", "company": "한화오션", "product": "선박(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "수주",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 0.52,
        "material_mix": [
            {"item": "후판(선박용 철강)", "weight": 0.20, "commodity": "steel_hr"},
            {"item": "엔진·기자재", "weight": 0.33, "commodity": None},
            {"item": "인건비(직영+협력)", "weight": 0.18, "commodity": None},
            {"item": "외주비", "weight": 0.19, "commodity": None},
            {"item": "도장·의장", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.925, "op": 0.022},
        "note": "저가수주 소진 후 4년만 흑자전환(2.2%). LNG선 등 고부가 비중 확대. 후판이 핵심 소재.",
    },

    # ===== 방산 (수출 물량·믹스가 마진, 소재는 부차) =====
    "012450:hanwhaaero": {
        "ticker": "012450", "company": "한화에어로스페이스", "product": "K9자주포·엔진(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "수주",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 0.55,
        "material_mix": [
            {"item": "특수강·포신 소재", "weight": 0.28, "commodity": "steel_hr"},
            {"item": "알루미늄·경합금", "weight": 0.10, "commodity": "aluminum"},
            {"item": "전자·항전/사격통제", "weight": 0.17, "commodity": None},
            {"item": "외주·부품(엔진·포탑)", "weight": 0.27, "commodity": None},
            {"item": "인건비(고급 엔지니어)", "weight": 0.18, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.78, "op": 0.153},
        "note": "원자재보다 폴란드 등 수출 물량·계약 믹스가 마진 좌우. 지상방산 수출 호조로 영업이익률 15%대.",
    },
    "047810:kai": {
        "ticker": "047810", "company": "한국항공우주", "product": "항공기(KF-21·FA-50, 매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "수주",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 0.60,
        "material_mix": [
            {"item": "알루미늄·경합금", "weight": 0.20, "commodity": "aluminum"},
            {"item": "티타늄·특수금속", "weight": 0.12, "commodity": "steel_hr"},
            {"item": "항전·전자장비", "weight": 0.15, "commodity": None},
            {"item": "외주·부품(엔진·복합재)", "weight": 0.33, "commodity": None},
            {"item": "인건비(설계·조립)", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.88, "op": 0.066},
        "note": "엔진·항전 등 핵심부품 해외조달로 원가율 88%. 마진 개선은 완제기 수출 물량·믹스에 좌우.",
    },

    # ===== 게임 (원자재 없음 — 흥행 레버리지) =====
    "036570:ncsoft": {
        "ticker": "036570", "company": "엔씨소프트", "product": "게임(리니지, 매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "플랫폼",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "개발 인건비", "weight": 0.53, "commodity": None},
            {"item": "플랫폼 수수료(앱마켓 30%)", "weight": 0.14, "commodity": None},
            {"item": "마케팅", "weight": 0.11, "commodity": None},
            {"item": "서버·인프라", "weight": 0.05, "commodity": None},
            {"item": "외주·기타", "weight": 0.17, "commodity": None},
        ],
        "default_ratios": {"cogs": 1.07, "op": -0.07},
        "note": "원자재 무관. 인건비(영업비용 53%)+플랫폼 수수료가 원가. '24 흥행 공백+고정 인건비로 적자. 흥행 시 30%대 고마진.",
    },
    "259960:krafton": {
        "ticker": "259960", "company": "크래프톤", "product": "배틀그라운드(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "플랫폼",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "플랫폼 수수료(스팀·앱마켓 30%)", "weight": 0.35, "commodity": None},
            {"item": "개발 인건비(+주식보상)", "weight": 0.20, "commodity": None},
            {"item": "외주·기타", "weight": 0.20, "commodity": None},
            {"item": "마케팅", "weight": 0.15, "commodity": None},
            {"item": "서버·인프라", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.564, "op": 0.436},
        "note": "원자재 무관. 최대 원가는 플랫폼 수수료(30%). PUBG 단일 흥행 레버리지로 영업이익률 44%(창사 최대).",
    },

    # ===== 엔터 (원자재 없음 — 아티스트 정산·제작비) =====
    "352820:hybe": {
        "ticker": "352820", "company": "하이브", "product": "엔터(BTS 소속사, 매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "플랫폼·공연",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "아티스트 정산료", "weight": 0.35, "commodity": None},
            {"item": "앨범·MD 제작원가", "weight": 0.25, "commodity": None},
            {"item": "공연 제작비(투어·무대)", "weight": 0.15, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "마케팅·플랫폼(위버스)", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.918, "op": 0.082},
        "note": "원자재 무관. 아티스트 정산+제작비+인건비가 원가. '24 BTS 군백기로 마진 축소(8.2%). IP 라인업이 마진 좌우.",
    },
    "035900:jyp": {
        "ticker": "035900", "company": "JYP Ent.", "product": "엔터(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "플랫폼·공연",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "아티스트 정산료", "weight": 0.30, "commodity": None},
            {"item": "앨범·MD 제작원가", "weight": 0.25, "commodity": None},
            {"item": "인건비(제작·매니지먼트)", "weight": 0.20, "commodity": None},
            {"item": "공연 제작비", "weight": 0.15, "commodity": None},
            {"item": "마케팅", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.787, "op": 0.213},
        "note": "원자재 무관. 다수 IP(스키즈·트와이스·NMIXX)로 정산·제작 원가 레버리지 → 업계 최고 영업이익률 21%.",
    },

    # ===== 바이오 (설비 감가상각+배지, 가동률이 마진) =====
    "207940:samsungbio": {
        "ticker": "207940", "company": "삼성바이오로직스", "product": "CDMO(위탁생산, 매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 수주",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 0.40,
        "material_mix": [
            {"item": "배지·원부자재(세포배양)", "weight": 0.28, "commodity": "api_pharma"},
            {"item": "레진·정제 소재", "weight": 0.12, "commodity": None},
            {"item": "감가상각(대규모 설비)", "weight": 0.30, "commodity": None},
            {"item": "인건비(전문인력)", "weight": 0.20, "commodity": None},
            {"item": "유틸리티(전력·용수·스팀)", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.496, "op": 0.29},
        "note": "대규모 설비 감가상각+배지 원부자재가 원가 축. 공장 가동률·수율이 마진 좌우. 영업이익률 30% 안팎.",
    },
    "068270:celltrion": {
        "ticker": "068270", "company": "셀트리온", "product": "바이오시밀러(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B·약가",
        "channel_label": "약가·유통(글로벌)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 0.45,
        "material_mix": [
            {"item": "배지·원부자재(세포배양)", "weight": 0.32, "commodity": "api_pharma"},
            {"item": "레진·정제 소재", "weight": 0.13, "commodity": None},
            {"item": "감가상각(설비)", "weight": 0.22, "commodity": None},
            {"item": "인건비(전문인력)", "weight": 0.18, "commodity": None},
            {"item": "유틸리티", "weight": 0.08, "commodity": None},
            {"item": "품질관리·개발비 상각", "weight": 0.07, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.45, "op": 0.281},
        "note": "약가 인하·경쟁이 마진 좌우. 고원가 재고 소진·수율 개선으로 원가율 급락(52%→41%). 신제품 비중 확대가 마진 견인.",
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

    # ===== 전자부품 (MLCC 고마진 vs 카메라모듈 저마진) =====
    "009150:mlcc": {
        "ticker": "009150", "company": "삼성전기", "product": "MLCC(적층세라믹콘덴서)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.03, "material_ratio_of_cogs": 0.55,
        "material_mix": [
            {"item": "니켈 내부전극", "weight": 0.20, "commodity": "nickel"},
            {"item": "구리 외부전극", "weight": 0.10, "commodity": "nickel"},
            {"item": "세라믹 분말(티탄산바륨)", "weight": 0.25, "commodity": None},
            {"item": "설비 감가상각", "weight": 0.25, "commodity": None},
            {"item": "인건비", "weight": 0.10, "commodity": None},
            {"item": "기타(에너지·부자재)", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.72, "op": 0.147},
        "note": "니켈·구리 전극+세라믹 소재+설비 감가상각이 원가 축. 소재·공정 내재화로 사업부 영업이익률 두 자릿수(고마진).",
    },
    "011070:lginnotek": {
        "ticker": "011070", "company": "LG이노텍", "product": "카메라모듈(애플 납품)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.03, "material_ratio_of_cogs": 0.90,
        "material_mix": [
            {"item": "이미지센서(매입)", "weight": 0.55, "commodity": None},
            {"item": "렌즈", "weight": 0.15, "commodity": None},
            {"item": "액추에이터(AF/OIS)", "weight": 0.12, "commodity": None},
            {"item": "기타 부품(RF-PCB·IR필터)", "weight": 0.08, "commodity": None},
            {"item": "인건비", "weight": 0.05, "commodity": None},
            {"item": "감가상각", "weight": 0.05, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.92, "op": 0.03},
        "note": "이미지센서 매입원가가 지배(모듈원가 50~70%). 애플 95% 의존·단가압박으로 광학 영업이익률 3% 저마진.",
    },

    # ===== 정유·가스 (원료비가 원가의 90%, 유가 직결) =====
    "010950:soil": {
        "ticker": "010950", "company": "S-Oil", "product": "정유(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "정유",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 0.90,
        "material_mix": [
            {"item": "원유(Crude oil)", "weight": 0.90, "commodity": "crude_oil"},
            {"item": "정제·운영비", "weight": 0.06, "commodity": None},
            {"item": "인건비·감가상각", "weight": 0.04, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.969, "op": 0.013},
        "note": "(제품가−원유)=정제마진이 손익의 전부. 원가율 97%. '24 정제마진 약세로 이익 급감. 유가 사이클에 직결.",
    },
    "036460:kogas": {
        "ticker": "036460", "company": "한국가스공사", "product": "천연가스 도매(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "규제요금",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 0.90,
        "material_mix": [
            {"item": "LNG 도입원가", "weight": 0.90, "commodity": "lng"},
            {"item": "운영·설비비", "weight": 0.06, "commodity": None},
            {"item": "인건비·감가상각", "weight": 0.04, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.913, "op": 0.078},
        "note": "LNG 도입원가를 요금에 연동. 요금 인상 지연 시 차액이 미수금(14조 누적)으로 쌓이는 구조. 유가(JCC) 후행 연동.",
    },

    # ===== 2차전지 소재 (메탈가 연동·역래깅 리스크) =====
    "247540:ecoprobm": {
        "ticker": "247540", "company": "에코프로비엠", "product": "양극재(하이니켈)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.03, "material_ratio_of_cogs": 0.88,
        "material_mix": [
            {"item": "리튬", "weight": 0.30, "commodity": "lithium"},
            {"item": "니켈", "weight": 0.30, "commodity": "nickel"},
            {"item": "코발트", "weight": 0.08, "commodity": "cobalt"},
            {"item": "전구체·기타 소재", "weight": 0.20, "commodity": None},
            {"item": "인건비·감가·전력", "weight": 0.12, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.99, "op": -0.02},
        "note": "판가가 메탈가에 연동 → 메탈 급락 시 판가↓+재고평가손실(역래깅)로 이중 타격. '25 전기차 캐즘으로 적자.",
    },
    "003670:poscofuture": {
        "ticker": "003670", "company": "포스코퓨처엠", "product": "양극재·음극재",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.03, "material_ratio_of_cogs": 0.85,
        "material_mix": [
            {"item": "리튬", "weight": 0.28, "commodity": "lithium"},
            {"item": "니켈", "weight": 0.28, "commodity": "nickel"},
            {"item": "코발트", "weight": 0.07, "commodity": "cobalt"},
            {"item": "전구체·침상코크스 등", "weight": 0.22, "commodity": None},
            {"item": "인건비·감가·전력", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.96, "op": 0.005},
        "note": "양극재+음극재 동시. 메탈가 연동·역래깅에 노출. '25 캐즘으로 수익성 급락(BEP 수준).",
    },

    # ===== 디스플레이 (판가·가동률·감가상각) =====
    "034220:lgdisplay": {
        "ticker": "034220", "company": "LG디스플레이", "product": "OLED 패널",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.03, "material_ratio_of_cogs": 0.55,
        "material_mix": [
            {"item": "OLED 유기재료·소재", "weight": 0.25, "commodity": None},
            {"item": "구동IC·부품", "weight": 0.18, "commodity": None},
            {"item": "유리기판", "weight": 0.12, "commodity": None},
            {"item": "설비 감가상각", "weight": 0.30, "commodity": None},
            {"item": "인건비·전력", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.95, "op": -0.02},
        "note": "패널 판가·가동률·대규모 감가상각이 손익 좌우. LCD 철수·OLED 전환기 적자, 애플 OLED 물량이 흑자전환 관건.",
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
    "002380:kcc": {
        "ticker": "002380", "company": "KCC", "product": "도료·건자재",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B·유통",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 0.70,
        "material_mix": [
            {"item": "도료 수지·용제(석유계)", "weight": 0.45, "commodity": "naphtha"},
            {"item": "이산화티타늄(백색안료)", "weight": 0.20, "commodity": "titanium_dioxide"},
            {"item": "철강·판재", "weight": 0.10, "commodity": "steel_hr"},
            {"item": "기타 원료", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.78, "op": 0.06},
        "note": "도료 수지(석유계)+이산화티타늄이 원가 핵심. 유가·TiO2 시세·건설경기 노출. 실리콘(모멘티브) 사업도.",
    },

    # ===== 미디어·콘텐츠 (원자재 없음 — 제작비·판권상각) =====
    "035760:cjenm": {
        "ticker": "035760", "company": "CJ ENM", "product": "미디어·콘텐츠",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "방송·OTT",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "콘텐츠 제작비(출연료·제작)", "weight": 0.40, "commodity": None},
            {"item": "판권·방송권 상각", "weight": 0.20, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "송출·플랫폼 수수료", "weight": 0.15, "commodity": None},
            {"item": "마케팅", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.95, "op": 0.05},
        "note": "원자재 무관. 콘텐츠 제작비+판권상각이 원가. 흥행·OTT 판매가 마진 좌우(변동성 큼).",
    },
    "253450:studiodragon": {
        "ticker": "253450", "company": "스튜디오드래곤", "product": "드라마 제작",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "방송·OTT",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "드라마 제작비(출연료·제작)", "weight": 0.55, "commodity": None},
            {"item": "판권 상각", "weight": 0.18, "commodity": None},
            {"item": "인건비", "weight": 0.12, "commodity": None},
            {"item": "기타", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.88, "op": 0.12},
        "note": "원자재 무관. 제작비+판권상각이 원가. 넷플릭스 등 글로벌 OTT 판매·리쿱율이 마진 결정.",
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
    "096530:seegene": {
        "ticker": "096530", "company": "씨젠", "product": "체외진단(PCR)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.05, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "시약·효소(원료)", "weight": 0.40, "commodity": "api_pharma"},
            {"item": "플라스틱 소모품", "weight": 0.20, "commodity": "naphtha"},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.55, "op": 0.10},
        "note": "코로나 특수 후 실적 정상화. 시약·효소가 원가. 신규 검사항목(다중진단)·해외 장비 설치 확대가 관건.",
    },

    # ===== 수산·제지·비철 (원자재 직결) =====
    "006040:dongwon": {
        "ticker": "006040", "company": "동원산업", "product": "원양어업·수산가공",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "수산",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "어획·수산물 원가(가다랑어)", "weight": 0.50, "commodity": "tuna"},
            {"item": "선박 연료(벙커유)", "weight": 0.12, "commodity": "crude_oil"},
            {"item": "가공·인건비", "weight": 0.18, "commodity": None},
            {"item": "포장·기타", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.82, "op": 0.06},
        "note": "가다랑어 어가+선박유가 원가 좌우. 참치 어가 하락 시 마진 개선. STARKIST(미국)·물류 자회사도.",
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

    # ===== 태양광·반도체장비·발전설비·농기계 =====
    "009830:hanwhasol": {
        "ticker": "009830", "company": "한화솔루션", "product": "태양광 모듈·케미칼",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "웨이퍼·셀", "weight": 0.30, "commodity": None},
            {"item": "폴리실리콘", "weight": 0.25, "commodity": "polysilicon"},
            {"item": "케미칼 원료(나프타)", "weight": 0.20, "commodity": "naphtha"},
            {"item": "인건비·감가", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.95, "op": 0.01},
        "note": "태양광 모듈가·폴리실리콘·미국 IRA(AMPC)가 손익 좌우. 중국 공급과잉으로 태양광·케미칼 동반 부진.",
    },
    "042700:hanmisemi": {
        "ticker": "042700", "company": "한미반도체", "product": "반도체 장비(TC본더)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.03, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "부품·구동계", "weight": 0.45, "commodity": None},
            {"item": "정밀가공·소재", "weight": 0.20, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.55, "op": 0.42},
        "note": "HBM 붐 수혜 — SK하이닉스·마이크론 향 TC본더 사실상 독점. 영업이익률 40%대. 원가는 부품·정밀가공.",
    },
    "034020:doosanenerbility": {
        "ticker": "034020", "company": "두산에너빌리티", "product": "발전설비(원전·가스터빈)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "수주",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "특수강·단조 소재", "weight": 0.25, "commodity": "steel_hr"},
            {"item": "기자재·부품", "weight": 0.35, "commodity": None},
            {"item": "인건비(고급)", "weight": 0.20, "commodity": None},
            {"item": "외주·기타", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.86, "op": 0.07},
        "note": "원전·가스터빈·SMR. 특수강 소재+기자재+인건비가 원가. 체코 원전 등 대형 수주·SMR 성장 기대.",
    },
    "000490:daedong": {
        "ticker": "000490", "company": "대동", "product": "트랙터·농기계",
        "unit": "1대(매출 1,000원 환산)", "retail_price": 1000, "channel": "딜러",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "엔진·부품", "weight": 0.35, "commodity": None},
            {"item": "철강·강판", "weight": 0.25, "commodity": "steel_hr"},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "외주·기타", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.88, "op": 0.04},
        "note": "북미 트랙터 수출 주력. 철강·엔진이 원가. 환율·북미 농가경기·스마트농기계(자율주행) 전환이 변수.",
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
    "064350:rotem": {
        "ticker": "064350", "company": "현대로템", "product": "K2전차·철도차량",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "수주",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "특수강·철강", "weight": 0.28, "commodity": "steel_hr"},
            {"item": "기자재·부품", "weight": 0.32, "commodity": None},
            {"item": "인건비", "weight": 0.20, "commodity": None},
            {"item": "외주·기타", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.88, "op": 0.08},
        "note": "K2전차 폴란드 수출 호조가 마진 견인. 철강·기자재가 원가. 방산(전차)+철도+수소 사업.",
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
    "042670:hd_infracore": {
        "ticker": "042670", "company": "HD현대인프라코어", "product": "건설기계(굴착기)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "딜러",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.05, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "엔진·유압부품", "weight": 0.35, "commodity": None},
            {"item": "철강·강판", "weight": 0.25, "commodity": "steel_hr"},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "외주·기타", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.88, "op": 0.06},
        "note": "굴착기·엔진. 철강·엔진이 원가. 중국·신흥국 인프라 수요와 북미 시장이 실적 좌우.",
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

    # ===== 커피·우유 =====
    "026960:dongsuh": {
        "ticker": "026960", "company": "동서", "product": "커피(맥심)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "대형마트",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "커피 원두·생두", "weight": 0.30, "commodity": "coffee_bean"},
            {"item": "설탕·크리머", "weight": 0.25, "commodity": "sugar"},
            {"item": "포장재", "weight": 0.15, "commodity": "bopp_film"},
            {"item": "인건비·감가", "weight": 0.20, "commodity": None},
            {"item": "물류", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.75, "op": 0.13},
        "note": "맥심 커피믹스 독과점. 원두가 급등(+30%)이 원가 부담. 커피·설탕가가 마진 좌우.",
    },
    "003920:namyang": {
        "ticker": "003920", "company": "남양유업", "product": "우유·유가공",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "대형마트",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "원유(우유)", "weight": 0.60, "commodity": "raw_milk"},
            {"item": "당류", "weight": 0.05, "commodity": "sugar"},
            {"item": "포장재", "weight": 0.15, "commodity": "bopp_film"},
            {"item": "인건비·감가", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.90, "op": 0.01},
        "note": "원유가 연동+저출산 우유수요 감소로 적자~BEP. 원가의 60%가 원유. 경영권 분쟁 후 한앤코 인수.",
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

    # ===== 반도체 소부장·OLED소재·통신장비 =====
    "005290:dongjin": {
        "ticker": "005290", "company": "동진쎄미켐", "product": "반도체 소재(포토레지스트)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.03, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "화학 원료(용제·수지)", "weight": 0.45, "commodity": "naphtha"},
            {"item": "특수 소재", "weight": 0.20, "commodity": None},
            {"item": "인건비", "weight": 0.13, "commodity": None},
            {"item": "감가·기타", "weight": 0.22, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.78, "op": 0.10},
        "note": "포토레지스트·CMP슬러리 등 반도체 소재 국산화. 화학 원료가 원가. 반도체 가동률·소재 국산화 수혜.",
    },
    "357780:soulbrain": {
        "ticker": "357780", "company": "솔브레인", "product": "반도체 소재(식각액·전해액)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.03, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "화학 원료", "weight": 0.45, "commodity": "naphtha"},
            {"item": "특수 소재(고순도 불산 등)", "weight": 0.20, "commodity": None},
            {"item": "인건비", "weight": 0.12, "commodity": None},
            {"item": "감가·기타", "weight": 0.23, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.72, "op": 0.15},
        "note": "식각액·전해액·CMP 소재. 반도체·디스플레이·2차전지 소재. 고순도 화학 기술로 고마진(15%).",
    },
    "213420:duksan": {
        "ticker": "213420", "company": "덕산네오룩스", "product": "OLED 유기소재",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.03, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "유기소재 원료", "weight": 0.40, "commodity": None},
            {"item": "정제·합성 소재", "weight": 0.20, "commodity": None},
            {"item": "인건비", "weight": 0.13, "commodity": None},
            {"item": "감가·기타", "weight": 0.27, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.65, "op": 0.22},
        "note": "OLED 유기재료(정공수송층 등) 삼성D 향. 스마트폰·OLED TV·IT용 확대. 고마진 소재(22%).",
    },
    "032500:kmw": {
        "ticker": "032500", "company": "케이엠더블유", "product": "통신장비(필터·안테나)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.03, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "부품·소재", "weight": 0.45, "commodity": None},
            {"item": "알루미늄(필터 하우징)", "weight": 0.15, "commodity": "aluminum"},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.85, "op": 0.08},
        "note": "5G 기지국 필터·안테나. 통신사 capex 사이클에 실적 변동 극심(호황·불황 진폭 큼).",
    },

    # ===== 로봇·풍력·연료전지·방산전자 =====
    "277810:rainbow": {
        "ticker": "277810", "company": "레인보우로보틱스", "product": "협동로봇·휴머노이드",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.03, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "부품·모터·감속기", "weight": 0.50, "commodity": None},
            {"item": "전장·제어부품", "weight": 0.20, "commodity": None},
            {"item": "인건비(R&D)", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.80, "op": 0.05},
        "note": "협동로봇·휴머노이드. 삼성전자 지분투자로 주목. 감속기·모터 등 핵심부품이 원가, 성장주 프리미엄.",
    },
    "454910:doosanrobot": {
        "ticker": "454910", "company": "두산로보틱스", "product": "협동로봇",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.03, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "부품·모터·감속기", "weight": 0.50, "commodity": None},
            {"item": "전장·제어부품", "weight": 0.20, "commodity": None},
            {"item": "인건비(R&D)", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.85, "op": -0.05},
        "note": "협동로봇 글로벌 판매. 성장 투자로 아직 적자. 부품 원가+대규모 R&D·판매망 확충 부담.",
    },
    "112610:cswind": {
        "ticker": "112610", "company": "씨에스윈드", "product": "풍력 타워",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "후판(철강)", "weight": 0.50, "commodity": "steel_hr"},
            {"item": "부자재·용접", "weight": 0.15, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "물류(대형 구조물)", "weight": 0.10, "commodity": None},
            {"item": "감가·기타", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.90, "op": 0.06},
        "note": "풍력 타워 세계 1위. 후판이 원가 절반. 미국 IRA(AMPC) 수혜, 해상풍력 성장. 후판가·환율 노출.",
    },
    "336260:doosanfuel": {
        "ticker": "336260", "company": "두산퓨얼셀", "product": "발전용 연료전지",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "수주",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "스택·소재(촉매 등)", "weight": 0.40, "commodity": None},
            {"item": "부품·BOP", "weight": 0.30, "commodity": None},
            {"item": "인건비", "weight": 0.12, "commodity": None},
            {"item": "감가·기타", "weight": 0.18, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.90, "op": 0.04},
        "note": "발전용 연료전지. 수소 정책·CHPS(청정수소 의무) 물량이 실적 좌우. 정책 의존도 높음.",
    },
    "272210:hanwhasystem": {
        "ticker": "272210", "company": "한화시스템", "product": "방산전자·우주",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "수주",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "전자·부품", "weight": 0.40, "commodity": None},
            {"item": "소재(특수강·알루미늄)", "weight": 0.12, "commodity": "steel_hr"},
            {"item": "인건비(고급)", "weight": 0.23, "commodity": None},
            {"item": "외주·기타", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.88, "op": 0.06},
        "note": "레이더·전자전(방산)+ICT+우주(위성). 방산 수출·저궤도 위성통신 성장. 부품·인건비가 원가.",
    },

    # ===== 게임·항공(LCC)·비료·종합유통 =====
    "251270:netmarble": {
        "ticker": "251270", "company": "넷마블", "product": "모바일 게임(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "플랫폼",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "플랫폼 수수료(앱마켓 30%)", "weight": 0.25, "commodity": None},
            {"item": "인건비(개발)", "weight": 0.25, "commodity": None},
            {"item": "지급수수료(외부 IP 로열티)", "weight": 0.20, "commodity": None},
            {"item": "마케팅", "weight": 0.20, "commodity": None},
            {"item": "기타", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.92, "op": 0.08},
        "note": "원자재 무관. 외부 IP 로열티+플랫폼 수수료+마케팅 부담 커 마진 얇음. 흥행작·자체 IP 확대가 관건.",
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
    "025860:namhae": {
        "ticker": "025860", "company": "남해화학", "product": "비료",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B·농협",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "요소·암모니아", "weight": 0.35, "commodity": "urea"},
            {"item": "인광석·칼륨", "weight": 0.20, "commodity": None},
            {"item": "에너지", "weight": 0.12, "commodity": None},
            {"item": "인건비·감가", "weight": 0.18, "commodity": None},
            {"item": "기타", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.90, "op": 0.03},
        "note": "요소·인광석 수입가가 원가. 곡물가(비료 수요)·정부 비료값 지원·중국 요소 수출 통제가 변수.",
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
    "051600:kps": {
        "ticker": "051600", "company": "한전KPS", "product": "발전설비 정비",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 서비스",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "인건비(정비인력)", "weight": 0.50, "commodity": None},
            {"item": "자재·부품", "weight": 0.25, "commodity": None},
            {"item": "외주·기타", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.82, "op": 0.13},
        "note": "발전소 정비 서비스 — 인건비가 원가 절반. 원전·해외 정비·재생에너지 O&M 성장. 원자재 영향 작음.",
    },

    # ===== 신약·게임·스크린골프 =====
    "326030:skbp": {
        "ticker": "326030", "company": "SK바이오팜", "product": "신약(세노바메이트)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "미국 직판",
        "channel_label": "약가·유통(미국)",
        "distribution_margin": 0.05, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "API·원료", "weight": 0.20, "commodity": "api_pharma"},
            {"item": "인건비(R&D·영업)", "weight": 0.35, "commodity": None},
            {"item": "마케팅(미국 영업조직)", "weight": 0.25, "commodity": None},
            {"item": "감가·기타", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.30, "op": 0.10},
        "note": "뇌전증 신약 세노바메이트 미국 직판. 원가율 낮고 영업조직(판관비) 큼. 처방 확대로 흑자전환.",
    },
    "263750:pearlabyss": {
        "ticker": "263750", "company": "펄어비스", "product": "게임(검은사막)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "플랫폼",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "인건비(개발)", "weight": 0.40, "commodity": None},
            {"item": "플랫폼 수수료", "weight": 0.20, "commodity": None},
            {"item": "마케팅", "weight": 0.20, "commodity": None},
            {"item": "서버·인프라", "weight": 0.10, "commodity": None},
            {"item": "기타", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.90, "op": 0.10},
        "note": "원자재 무관. 검은사막·붉은사막 자체 IP·엔진. 신작 사이클에 실적 좌우, 개발 인건비가 원가.",
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

    # ===== 정유·제분·제당·시멘트 =====
    "096770:skinno": {
        "ticker": "096770", "company": "SK이노베이션", "product": "정유·배터리",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "정유",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "원유", "weight": 0.75, "commodity": "crude_oil"},
            {"item": "정제·운영비", "weight": 0.08, "commodity": None},
            {"item": "배터리 소재·기타", "weight": 0.07, "commodity": None},
            {"item": "인건비·감가", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.94, "op": 0.03},
        "note": "정유(정제마진)+배터리(SK온 적자)+석유화학. 유가·정제마진 사이클. SK온 흑자전환이 밸류 관건.",
    },
    "001130:daehanflour": {
        "ticker": "001130", "company": "대한제분", "product": "밀가루",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B·소매",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "원맥(소맥)", "weight": 0.70, "commodity": "wheat"},
            {"item": "에너지", "weight": 0.08, "commodity": None},
            {"item": "포장·부자재", "weight": 0.07, "commodity": None},
            {"item": "인건비·감가", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.90, "op": 0.04},
        "note": "곰표 밀가루. 원가의 70%가 수입 원맥. 소맥 국제가·환율이 마진 직결. 사료·펫푸드로 다각화.",
    },
    "145990:samyangsa": {
        "ticker": "145990", "company": "삼양사", "product": "설탕·식품소재",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B·소매",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "원당", "weight": 0.55, "commodity": "sugar"},
            {"item": "전분·기타 원료", "weight": 0.15, "commodity": "corn"},
            {"item": "에너지", "weight": 0.08, "commodity": None},
            {"item": "인건비·감가", "weight": 0.22, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.85, "op": 0.06},
        "note": "설탕+식품소재(전분당·알룰로스 등 프리미엄 소재)+화학. 원당가·곡물가. 스페셜티 소재로 마진 개선.",
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
    "069620:daewoong": {
        "ticker": "069620", "company": "대웅제약", "product": "의약품(나보타·펙수클루)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "처방·수출",
        "channel_label": "약가·유통",
        "distribution_margin": 0.15, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "API·원료", "weight": 0.30, "commodity": "api_pharma"},
            {"item": "인건비·R&D", "weight": 0.25, "commodity": None},
            {"item": "마케팅·영업", "weight": 0.25, "commodity": None},
            {"item": "감가·기타", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.60, "op": 0.10},
        "note": "보툴리눔톡신 나보타(미국)+위장약 펙수클루 수출 성장. R&D·영업 비중 큰 제약 구조.",
    },
    "058470:leeno": {
        "ticker": "058470", "company": "리노공업", "product": "반도체 검사부품(리노핀)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.03, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "소재(비철·특수합금)", "weight": 0.30, "commodity": None},
            {"item": "정밀가공", "weight": 0.20, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.35, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.55, "op": 0.40},
        "note": "반도체 검사용 리노핀·테스트소켓. 다품종 소량·기술 진입장벽으로 초고마진(영업이익률 40%).",
    },

    # ===== 통신(KT·LGU+) =====
    "030200:kt": {
        "ticker": "030200", "company": "KT", "product": "유무선통신·B2B(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "직판·대리점",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "망 감가상각+주파수 상각", "weight": 0.28, "commodity": None},
            {"item": "망 운영·상호접속·전력", "weight": 0.20, "commodity": None},
            {"item": "단말·상품원가·B2B(AICT·IDC)", "weight": 0.19, "commodity": None},
            {"item": "마케팅", "weight": 0.18, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.92, "op": 0.08},
        "note": "원자재 무관. 유무선+B2B(AICT·IDC·클라우드). 망 감가상각·인건비가 원가. 부동산·자회사 가치도.",
    },
    "032640:lguplus": {
        "ticker": "032640", "company": "LG유플러스", "product": "이동통신(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "직판·대리점",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "망 감가상각+주파수 상각", "weight": 0.30, "commodity": None},
            {"item": "마케팅", "weight": 0.22, "commodity": None},
            {"item": "망 운영·전력", "weight": 0.20, "commodity": None},
            {"item": "단말·기타", "weight": 0.15, "commodity": None},
            {"item": "인건비", "weight": 0.13, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.93, "op": 0.07},
        "note": "원자재 무관. 통신 3사 중 규모 작음. capex·마케팅 부담. IDC·기업인프라·AI로 성장 모색.",
    },

    # ===== 화학(합성고무·스판덱스) =====
    "011780:kumhopetro": {
        "ticker": "011780", "company": "금호석유화학", "product": "합성고무·NB라텍스",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "부타디엔·SM(나프타계)", "weight": 0.65, "commodity": "naphtha"},
            {"item": "전력·에너지", "weight": 0.12, "commodity": None},
            {"item": "인건비·감가", "weight": 0.13, "commodity": None},
            {"item": "기타", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.88, "op": 0.06},
        "note": "합성고무(NB라텍스·타이어용)·페놀·수지. 부타디엔(나프타)이 원가. 타이어·의료용 장갑 수요가 전방.",
    },
    "298020:hyosungtnc": {
        "ticker": "298020", "company": "효성티앤씨", "product": "스판덱스",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "원료(PTMEG·MDI, 석유계)", "weight": 0.60, "commodity": "naphtha"},
            {"item": "에너지", "weight": 0.12, "commodity": None},
            {"item": "인건비·감가", "weight": 0.18, "commodity": None},
            {"item": "기타", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.90, "op": 0.05},
        "note": "스판덱스 세계 1위. 석유계 원료가 원가. 중국 증설 경쟁·의류 수요가 스프레드 좌우.",
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

    # ===== 바이오(알테오젠) =====
    "196170:alteogen": {
        "ticker": "196170", "company": "알테오젠", "product": "바이오 플랫폼(제형·ADC)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "기술수출",
        "channel_label": "기술료·로열티",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "인건비(R&D)", "weight": 0.40, "commodity": None},
            {"item": "원부자재·시약", "weight": 0.15, "commodity": "api_pharma"},
            {"item": "감가·기타", "weight": 0.25, "commodity": None},
            {"item": "기타 운영비", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.45, "op": 0.20},
        "note": "피하주사(SC) 제형변경·ADC 플랫폼 기술수출. 로열티 매출은 원가율 낮은 고마진. R&D 인건비가 원가.",
    },

    # ===== 엔터(SM·YG) =====
    "041510:sm": {
        "ticker": "041510", "company": "에스엠", "product": "엔터(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "플랫폼·공연",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "아티스트 정산료", "weight": 0.30, "commodity": None},
            {"item": "앨범·MD 제작원가", "weight": 0.25, "commodity": None},
            {"item": "인건비", "weight": 0.20, "commodity": None},
            {"item": "공연 제작비", "weight": 0.15, "commodity": None},
            {"item": "마케팅", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.85, "op": 0.12},
        "note": "원자재 무관. 에스파·NCT 등 IP. 아티스트 정산·제작비가 원가. 활동 사이클·신인 데뷔가 실적 좌우.",
    },
    "122870:ygent": {
        "ticker": "122870", "company": "와이지엔터", "product": "엔터(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "플랫폼·공연",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "아티스트 정산료", "weight": 0.32, "commodity": None},
            {"item": "앨범·MD 제작원가", "weight": 0.25, "commodity": None},
            {"item": "인건비", "weight": 0.18, "commodity": None},
            {"item": "공연 제작비", "weight": 0.15, "commodity": None},
            {"item": "마케팅", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.88, "op": 0.10},
        "note": "원자재 무관. 블랙핑크·베이비몬스터 IP. 아티스트 활동 사이클(재계약·컴백)에 실적 민감.",
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

    # ===== PCB·양극재 =====
    "222800:simmtech": {
        "ticker": "222800", "company": "심텍", "product": "반도체 패키지기판(PCB)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "원판·동박(CCL)", "weight": 0.40, "commodity": "copper"},
            {"item": "화학·소재", "weight": 0.20, "commodity": "naphtha"},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.88, "op": 0.06},
        "note": "반도체 패키지기판(메모리모듈·MSAP). 동박·전방 반도체(메모리) 수요가 실적 좌우. 사이클 변동 큼.",
    },
    "005070:cosmoams": {
        "ticker": "005070", "company": "코스모신소재", "product": "양극재·기능성소재",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.03, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "리튬", "weight": 0.28, "commodity": "lithium"},
            {"item": "니켈", "weight": 0.28, "commodity": "nickel"},
            {"item": "코발트", "weight": 0.07, "commodity": "cobalt"},
            {"item": "전구체·기타 소재", "weight": 0.22, "commodity": None},
            {"item": "인건비·감가·전력", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.96, "op": 0.01},
        "note": "양극재(하이니켈)+토너·기능성필름. 메탈가 연동·역래깅에 노출. 전기차 캐즘으로 수익성 부진.",
    },

    # ===== 전자·IT서비스·SW =====
    "066570:lgelec": {
        "ticker": "066570", "company": "LG전자", "product": "가전·TV·전장",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "유통·B2B",
        "channel_label": "직판·유통",
        "distribution_margin": 0.05, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "부품·소재(패널·반도체·모터)", "weight": 0.55, "commodity": None},
            {"item": "철강·수지", "weight": 0.10, "commodity": "steel_hr"},
            {"item": "물류·마케팅", "weight": 0.15, "commodity": None},
            {"item": "인건비", "weight": 0.10, "commodity": None},
            {"item": "감가·기타", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.75, "op": 0.05},
        "note": "생활가전·TV+전장(VS)+B2B(HVAC). 패널·부품·물류비가 원가. 구독·B2B·전장으로 마진 개선.",
    },
    "018260:sds": {
        "ticker": "018260", "company": "삼성에스디에스", "product": "IT서비스·물류",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "물류(운임·외주)", "weight": 0.45, "commodity": None},
            {"item": "외주·인건비(SI·클라우드)", "weight": 0.30, "commodity": None},
            {"item": "인프라·라이선스", "weight": 0.10, "commodity": None},
            {"item": "기타", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.88, "op": 0.09},
        "note": "IT서비스(SI·클라우드)+물류(첼로). 물류 매출 비중 커 외형 크고, IT가 고마진. 생성형AI·클라우드 성장.",
    },
    "307950:autoever": {
        "ticker": "307950", "company": "현대오토에버", "product": "차량SW·IT서비스",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "외주·인건비(SW개발)", "weight": 0.55, "commodity": None},
            {"item": "라이선스·인프라", "weight": 0.15, "commodity": None},
            {"item": "감가", "weight": 0.15, "commodity": None},
            {"item": "기타", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.88, "op": 0.06},
        "note": "차량SW(모빌진)·내비·SI. 현대차그룹 SDV(소프트웨어 차량) 전환 수혜. 인건비가 원가.",
    },

    # ===== 건설기계·전력기기 =====
    "241560:bobcat": {
        "ticker": "241560", "company": "두산밥캣", "product": "소형건설기계",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "딜러",
        "channel_label": "직판·딜러",
        "distribution_margin": 0.05, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "부품·엔진", "weight": 0.35, "commodity": None},
            {"item": "철강·강판", "weight": 0.25, "commodity": "steel_hr"},
            {"item": "인건비", "weight": 0.12, "commodity": None},
            {"item": "외주·기타", "weight": 0.28, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.83, "op": 0.10},
        "note": "스키드로더 북미 1위. 북미 건설·농업 수요, 철강·엔진이 원가. 환율(달러 매출)이 마진 레버리지.",
    },
    "267260:hdelectric": {
        "ticker": "267260", "company": "HD현대일렉트릭", "product": "전력기기(변압기)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B·수주",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "전기강판", "weight": 0.20, "commodity": "steel_hr"},
            {"item": "구리", "weight": 0.15, "commodity": "copper"},
            {"item": "부품·자재", "weight": 0.30, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "외주·기타", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.82, "op": 0.13},
        "note": "변압기·차단기. 미국 전력망 교체·데이터센터 수요로 초호황(수주·판가 급등). 전기강판·구리가 원가.",
    },
    "298040:hyosungheavy": {
        "ticker": "298040", "company": "효성중공업", "product": "전력기기·건설",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B·수주",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "전기강판", "weight": 0.18, "commodity": "steel_hr"},
            {"item": "구리", "weight": 0.15, "commodity": "copper"},
            {"item": "부품·자재+건설자재", "weight": 0.32, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "외주·기타", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.88, "op": 0.07},
        "note": "변압기(미국 수출 호황)+건설(해링턴). 전력기기 성장이 실적 견인. 전기강판·구리가 원가.",
    },

    # ===== 화학(폴리실리콘·정밀화학) =====
    "010060:oci": {
        "ticker": "010060", "company": "OCI홀딩스", "product": "폴리실리콘·베이직케미칼",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "전력(폴리실리콘 제조)", "weight": 0.30, "commodity": None},
            {"item": "금속실리콘·원료", "weight": 0.25, "commodity": None},
            {"item": "베이직케미칼 원료(나프타계)", "weight": 0.20, "commodity": "naphtha"},
            {"item": "인건비·감가", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.85, "op": 0.08},
        "note": "태양광 폴리실리콘(전력 다소비)+베이직케미칼. 전기료·폴리실리콘가·미국 태양광 정책이 손익 좌우.",
    },
    "004000:lottefine": {
        "ticker": "004000", "company": "롯데정밀화학", "product": "정밀화학(가성소다·셀룰로스)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "원료(암모니아·염소·나프타계)", "weight": 0.55, "commodity": "naphtha"},
            {"item": "전력·에너지", "weight": 0.15, "commodity": None},
            {"item": "인건비·감가", "weight": 0.18, "commodity": None},
            {"item": "기타", "weight": 0.12, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.85, "op": 0.08},
        "note": "가성소다·암모니아+셀룰로스(식의약 첨가제, 고부가). 원료·전력가 노출, 그린소재로 마진 방어.",
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

    # ===== 바이오·백신·보톡스·식품 =====
    "302440:skbs": {
        "ticker": "302440", "company": "SK바이오사이언스", "product": "백신·CDMO",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B·조달",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.05, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "원부자재·배지", "weight": 0.25, "commodity": "api_pharma"},
            {"item": "인건비(R&D)", "weight": 0.30, "commodity": None},
            {"item": "감가(설비)", "weight": 0.25, "commodity": None},
            {"item": "기타", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.60, "op": 0.05},
        "note": "백신 CDMO+자체백신(폐렴구균·독감). 코로나 특수 후 실적 정상화. 설비 가동률·신규 수주가 관건.",
    },
    "145020:hugel": {
        "ticker": "145020", "company": "휴젤", "product": "보툴리눔톡신·필러",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B·수출",
        "channel_label": "직판·유통",
        "distribution_margin": 0.05, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "원부자재·배지", "weight": 0.15, "commodity": "api_pharma"},
            {"item": "인건비(R&D)", "weight": 0.25, "commodity": None},
            {"item": "마케팅·영업", "weight": 0.30, "commodity": None},
            {"item": "감가·기타", "weight": 0.30, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.35, "op": 0.30},
        "note": "보툴리눔톡신(보툴렉스)+필러. 미국·유럽·중국 수출 확대. 원가율 낮아 초고마진(영업이익률 30%).",
    },
    "017810:pulmuone": {
        "ticker": "017810", "company": "풀무원", "product": "두부·냉장식품",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "대형마트",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "대두(두부)", "weight": 0.30, "commodity": "soybean"},
            {"item": "소맥·기타 원료", "weight": 0.20, "commodity": "wheat"},
            {"item": "포장재", "weight": 0.12, "commodity": "bopp_film"},
            {"item": "인건비·감가", "weight": 0.25, "commodity": None},
            {"item": "물류", "weight": 0.13, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.82, "op": 0.03},
        "note": "두부·나물·냉장면+식물성단백(지구식단). 대두·곡물가가 원가. 저마진, 해외(미국) 두부 성장.",
    },

    # ===== 게임·미디어 =====
    "112040:wemade": {
        "ticker": "112040", "company": "위메이드", "product": "게임·블록체인(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "플랫폼",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "인건비(개발)", "weight": 0.35, "commodity": None},
            {"item": "플랫폼 수수료", "weight": 0.20, "commodity": None},
            {"item": "마케팅", "weight": 0.20, "commodity": None},
            {"item": "지급수수료·블록체인", "weight": 0.15, "commodity": None},
            {"item": "기타", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.95, "op": 0.05},
        "note": "원자재 무관. 미르·나이트크로우+위믹스(블록체인). 신작·코인(위믹스) 사이클에 실적 변동성 극심.",
    },
    "036420:contentree": {
        "ticker": "036420", "company": "콘텐트리중앙", "product": "미디어(드라마·극장)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "방송·극장",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "콘텐츠 제작비", "weight": 0.40, "commodity": None},
            {"item": "판권 상각", "weight": 0.20, "commodity": None},
            {"item": "극장 운영비(메가박스)", "weight": 0.20, "commodity": None},
            {"item": "인건비", "weight": 0.10, "commodity": None},
            {"item": "기타", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.95, "op": 0.02},
        "note": "원자재 무관. 드라마 제작(SLL)+극장(메가박스). 흥행·글로벌 OTT 판매가 관건. 적자~저마진.",
    },

    # ===== 반도체·전자 소부장(PCB·필름) =====
    "007660:isupetasys": {
        "ticker": "007660", "company": "이수페타시스", "product": "고다층 PCB(MLB)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "원판·동박(CCL)", "weight": 0.42, "commodity": "copper"},
            {"item": "화학·소재", "weight": 0.18, "commodity": "naphtha"},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.80, "op": 0.12},
        "note": "고다층 MLB(AI가속기·네트워크 장비용). 동박이 원가. AI 서버 수요로 고성장, 전방 데이터센터 투자.",
    },
    "178920:pihightech": {
        "ticker": "178920", "company": "PI첨단소재", "product": "폴리이미드 필름",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "원료(PMDA·ODA, 석유계)", "weight": 0.45, "commodity": "naphtha"},
            {"item": "에너지", "weight": 0.12, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.28, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.78, "op": 0.12},
        "note": "PI필름 세계 1위(방열시트·FPCB·전기차 절연). 석유계 원료가 원가. 전장·폴더블 수요가 성장축.",
    },
    "090460:bh": {
        "ticker": "090460", "company": "비에이치", "product": "연성인쇄회로기판(FPCB)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "원판·동박(연성 CCL)", "weight": 0.40, "commodity": "copper"},
            {"item": "화학·소재", "weight": 0.18, "commodity": "naphtha"},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.27, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.88, "op": 0.06},
        "note": "FPCB 애플 향 주력. OLED·전장(전기차)으로 확대. 애플 의존·아이폰 판매 사이클에 실적 민감.",
    },

    # ===== 2차전지 소재(전해액·첨가제·도전재) =====
    "348370:enchem": {
        "ticker": "348370", "company": "엔켐", "product": "전해액",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "리튬염(LiPF6)·용매", "weight": 0.60, "commodity": None},
            {"item": "첨가제", "weight": 0.15, "commodity": None},
            {"item": "인건비·감가", "weight": 0.15, "commodity": None},
            {"item": "기타", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.90, "op": 0.05},
        "note": "전해액 국내 1위, 미국 대규모 증설. 리튬염·용매가 원가. 전기차 캐즘·IRA 수혜가 엇갈리는 변수.",
    },
    "278280:cheonbo": {
        "ticker": "278280", "company": "천보", "product": "전해질 첨가제",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "화학 원료", "weight": 0.50, "commodity": "naphtha"},
            {"item": "리튬 관련 소재", "weight": 0.20, "commodity": "lithium"},
            {"item": "인건비·감가", "weight": 0.18, "commodity": None},
            {"item": "기타", "weight": 0.12, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.85, "op": 0.08},
        "note": "특수 전해질·첨가제(LiFSI 등) 고순도 화학. 2차전지·반도체 소재. 캐즘으로 가동률·수익성 부진.",
    },
    "121600:nanoshin": {
        "ticker": "121600", "company": "나노신소재", "product": "CNT 도전재·타겟소재",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "원료·소재", "weight": 0.45, "commodity": None},
            {"item": "화학 원료", "weight": 0.15, "commodity": "naphtha"},
            {"item": "인건비·감가", "weight": 0.20, "commodity": None},
            {"item": "기타", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.70, "op": 0.15},
        "note": "CNT 도전재(실리콘 음극용)·디스플레이 타겟소재. 4680·실리콘 음극 채택 확대가 성장 모멘텀.",
    },

    # ===== 바이오 CDMO·미용의료·건기식 =====
    "237690:stpharm": {
        "ticker": "237690", "company": "에스티팜", "product": "올리고 CDMO",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 수주",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "원부자재·시약", "weight": 0.30, "commodity": "api_pharma"},
            {"item": "인건비", "weight": 0.25, "commodity": None},
            {"item": "감가(설비)", "weight": 0.25, "commodity": None},
            {"item": "기타", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.65, "op": 0.15},
        "note": "올리고뉴클레오타이드 원료 CDMO(siRNA·mRNA 신약). 대규모 설비 증설, 신약 상업화 물량이 성장축.",
    },
    "214450:pharmaresearch": {
        "ticker": "214450", "company": "파마리서치", "product": "리쥬란·필러",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B·수출",
        "channel_label": "직판·유통",
        "distribution_margin": 0.05, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "원부자재(PN·PDRN)", "weight": 0.15, "commodity": "api_pharma"},
            {"item": "인건비·R&D", "weight": 0.25, "commodity": None},
            {"item": "마케팅·영업", "weight": 0.30, "commodity": None},
            {"item": "감가·기타", "weight": 0.30, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.35, "op": 0.30},
        "note": "리쥬란(연어 DNA 스킨부스터)·필러·톡신. 미용의료 초고마진(30%), 수출(중국·태국 등) 고성장.",
    },
    "194700:novarex": {
        "ticker": "194700", "company": "노바렉스", "product": "건강기능식품 ODM",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 제조",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.03, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "건기식 원료", "weight": 0.45, "commodity": None},
            {"item": "용기·포장재", "weight": 0.15, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.75, "op": 0.08},
        "note": "건기식 ODM(개별인정형 원료 강점). 원료·물량이 마진. 건강기능식품 수요·수출 확대.",
    },

    # ===== 전력·조선·의류OEM·보일러·LPG·피팅 =====
    "010120:lselectric": {
        "ticker": "010120", "company": "LS일렉트릭", "product": "전력·자동화기기",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "구리", "weight": 0.18, "commodity": "copper"},
            {"item": "전기강판", "weight": 0.12, "commodity": "steel_hr"},
            {"item": "부품·자재", "weight": 0.30, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "외주·기타", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.85, "op": 0.08},
        "note": "전력기기·자동화(PLC)+스마트그리드. 미국 전력망·데이터센터 수요. 구리·전기강판이 원가.",
    },
    "010620:hdmipo": {
        "ticker": "010620", "company": "HD현대미포", "product": "중형선박(PC선)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "수주",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "후판(선박용 철강)", "weight": 0.20, "commodity": "steel_hr"},
            {"item": "엔진·기자재", "weight": 0.35, "commodity": None},
            {"item": "인건비", "weight": 0.20, "commodity": None},
            {"item": "외주비", "weight": 0.15, "commodity": None},
            {"item": "도장·의장", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.90, "op": 0.05},
        "note": "중형 석유화학운반선(PC선)·컨테이너선 강자. 후판·수주단가·환율. 고선가 수주분 인식으로 흑자.",
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
    "018670:skgas": {
        "ticker": "018670", "company": "SK가스", "product": "LPG 수입·유통",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "유통",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "LPG 도입원가", "weight": 0.88, "commodity": "crude_oil"},
            {"item": "운영·설비비", "weight": 0.05, "commodity": None},
            {"item": "인건비·감가", "weight": 0.07, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.95, "op": 0.02},
        "note": "LPG 수입·유통(정유 유사 저마진). LPG가(유가 연동)에 매출·원가 직결. LNG·수소 신사업 투자.",
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

    # ===== 제약·바이오 확장 =====
    "141080:ligachem": {
        "ticker": "141080", "company": "리가켐바이오", "product": "ADC 신약 플랫폼",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "기술수출",
        "channel_label": "기술료·로열티",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "인건비(R&D)", "weight": 0.45, "commodity": None},
            {"item": "원부자재·시약", "weight": 0.15, "commodity": "api_pharma"},
            {"item": "감가·기타", "weight": 0.20, "commodity": None},
            {"item": "기타 운영비", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.40, "op": 0.10},
        "note": "ADC(항체약물접합체) 플랫폼 기술수출. 마일스톤·로열티 매출이라 실적 변동성 큼. R&D 인건비가 원가.",
    },
    "006280:gccorp": {
        "ticker": "006280", "company": "GC녹십자", "product": "혈액제제·백신",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "처방·조달",
        "channel_label": "약가·유통",
        "distribution_margin": 0.10, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "원부자재(혈장 등)", "weight": 0.35, "commodity": "api_pharma"},
            {"item": "인건비·R&D", "weight": 0.22, "commodity": None},
            {"item": "마케팅·영업", "weight": 0.18, "commodity": None},
            {"item": "감가·기타", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.70, "op": 0.05},
        "note": "혈액제제·백신·희귀질환. 혈장 원가·독감백신 계절성. 알리글로(미국 면역글로불린) 성장, 저마진 구조.",
    },
    "003850:boryung": {
        "ticker": "003850", "company": "보령", "product": "의약품(카나브)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "처방",
        "channel_label": "약가·유통",
        "distribution_margin": 0.15, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "API·원료", "weight": 0.30, "commodity": "api_pharma"},
            {"item": "인건비·R&D", "weight": 0.22, "commodity": None},
            {"item": "마케팅·영업", "weight": 0.28, "commodity": None},
            {"item": "감가·기타", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.60, "op": 0.09},
        "note": "고혈압 카나브 패밀리+항암 LBA(레거시 브랜드 인수). 처방·영업력이 마진. 우주 헬스케어 투자도.",
    },
    "086450:dkpharma": {
        "ticker": "086450", "company": "동국제약", "product": "의약품·헬스케어",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "약국·홈쇼핑",
        "channel_label": "약가·유통",
        "distribution_margin": 0.15, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "API·원료", "weight": 0.25, "commodity": "api_pharma"},
            {"item": "인건비·R&D", "weight": 0.20, "commodity": None},
            {"item": "마케팅·영업(일반약·화장품)", "weight": 0.35, "commodity": None},
            {"item": "감가·기타", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.50, "op": 0.13},
        "note": "마데카솔·인사돌·판시딜+센텔리안24(화장품). 일반약·헬스케어 마케팅이 마진. 브랜드력·채널 강점.",
    },

    # ===== 반도체 소부장(장비·부품) =====
    "403870:hpsp": {
        "ticker": "403870", "company": "HPSP", "product": "고압수소어닐링 장비",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "부품·소재", "weight": 0.40, "commodity": None},
            {"item": "정밀가공", "weight": 0.15, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.30, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.45, "op": 0.45},
        "note": "고압수소어닐링 장비 사실상 독점. 초고마진(영업이익률 45%). 파운드리·로직 미세공정 수요.",
    },
    "036930:jusung": {
        "ticker": "036930", "company": "주성엔지니어링", "product": "반도체 증착장비(ALD)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "부품·소재", "weight": 0.45, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "외주", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.60, "op": 0.20},
        "note": "ALD 증착장비(반도체·디스플레이·태양광). 자체 기술로 고마진. 전방 투자 사이클에 실적 변동.",
    },
    "064760:tck": {
        "ticker": "064760", "company": "티씨케이", "product": "반도체 SiC 부품",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "소재(흑연·SiC)", "weight": 0.40, "commodity": None},
            {"item": "정밀가공", "weight": 0.15, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.30, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.55, "op": 0.30},
        "note": "반도체 식각공정용 SiC 링·부품 독점적. 소모성 부품이라 고마진(30%)·안정 수요. 전방 가동률 연동.",
    },
    "074600:wonikqnc": {
        "ticker": "074600", "company": "원익QnC", "product": "반도체 쿼츠웨어",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "소재(석영·쿼츠)", "weight": 0.45, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "외주", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.75, "op": 0.10},
        "note": "반도체 쿼츠웨어·세정. 소모성 부품(리커링). 반도체 가동률·쿼츠 원재료(모멘티브)가 변수.",
    },
    "195870:haesungds": {
        "ticker": "195870", "company": "해성디에스", "product": "반도체 리드프레임·기판",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "구리·소재", "weight": 0.40, "commodity": "copper"},
            {"item": "화학·소재", "weight": 0.15, "commodity": "naphtha"},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.30, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.80, "op": 0.10},
        "note": "반도체 리드프레임·패키지기판. 구리가 원가. 전장(자동차)·메모리 수요, 구리가에 마진 노출.",
    },

    # ===== 2차전지 소재(전구체·불소화학) =====
    "450080:ecopromety": {
        "ticker": "450080", "company": "에코프로머티", "product": "전구체",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "니켈", "weight": 0.45, "commodity": "nickel"},
            {"item": "코발트", "weight": 0.10, "commodity": "cobalt"},
            {"item": "기타 원료", "weight": 0.20, "commodity": None},
            {"item": "인건비·감가·전력", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.92, "op": 0.03},
        "note": "전구체(양극재 중간재). 니켈가 연동. 전기차 캐즘·메탈가 하락으로 수익성 부진. 에코프로 밸류체인.",
    },
    "093370:foosung": {
        "ticker": "093370", "company": "후성", "product": "불소화학(전해질·냉매·특수가스)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "화학 원료(불소계)", "weight": 0.50, "commodity": "naphtha"},
            {"item": "리튬 관련(LiPF6)", "weight": 0.15, "commodity": "lithium"},
            {"item": "인건비·감가", "weight": 0.20, "commodity": None},
            {"item": "기타", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.82, "op": 0.08},
        "note": "반도체 특수가스(불소계)+2차전지 전해질(LiPF6)+냉매. 불소화학 국내 독점적. 전방 반도체·배터리 수요.",
    },

    # ===== 방산·조선기자재 =====
    "079550:lignex1": {
        "ticker": "079550", "company": "LIG넥스원", "product": "유도무기·감시정찰",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "수주",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "전자·부품", "weight": 0.40, "commodity": None},
            {"item": "소재(특수강·알루미늄)", "weight": 0.12, "commodity": "steel_hr"},
            {"item": "인건비(고급)", "weight": 0.23, "commodity": None},
            {"item": "외주·기타", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.85, "op": 0.09},
        "note": "유도무기(천궁·현궁)·감시정찰. 중동(UAE)·동남아 수출 성장. 전자부품·인건비가 원가.",
    },
    "082740:hanwhaengine": {
        "ticker": "082740", "company": "한화엔진", "product": "선박용 엔진",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B·수주",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "후판·소재", "weight": 0.25, "commodity": "steel_hr"},
            {"item": "부품·기자재", "weight": 0.35, "commodity": None},
            {"item": "인건비", "weight": 0.20, "commodity": None},
            {"item": "외주·기타", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.88, "op": 0.07},
        "note": "선박용 대형엔진(구 HSD엔진). 조선 호황·친환경(이중연료) 엔진 수요. 후판·기자재가 원가.",
    },

    # ===== 게임 =====
    "078340:com2us": {
        "ticker": "078340", "company": "컴투스", "product": "모바일 게임(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "플랫폼",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "인건비(개발)", "weight": 0.35, "commodity": None},
            {"item": "플랫폼 수수료", "weight": 0.20, "commodity": None},
            {"item": "마케팅", "weight": 0.20, "commodity": None},
            {"item": "지급수수료(IP·스포츠)", "weight": 0.15, "commodity": None},
            {"item": "기타", "weight": 0.10, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.92, "op": 0.03},
        "note": "원자재 무관. 서머너즈워+야구게임+미디어(콘텐츠). 신작·IP 사이클에 실적 좌우.",
    },
    "192080:doubleu": {
        "ticker": "192080", "company": "더블유게임즈", "product": "소셜카지노 게임(매출 1,000원)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "플랫폼",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "마케팅(UA)", "weight": 0.30, "commodity": None},
            {"item": "플랫폼 수수료", "weight": 0.30, "commodity": None},
            {"item": "인건비", "weight": 0.20, "commodity": None},
            {"item": "기타", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.75, "op": 0.25},
        "note": "원자재 무관. 소셜카지노(더블다운·슈퍼네이션) 북미 매출. 안정적 캐시카우로 고마진(25%).",
    },

    # ===== 2차전지 소재·장비 확장 =====
    "066970:lnf": {
        "ticker": "066970", "company": "엘앤에프", "product": "하이니켈 양극재",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "리튬", "weight": 0.30, "commodity": "lithium"},
            {"item": "니켈", "weight": 0.28, "commodity": "nickel"},
            {"item": "코발트", "weight": 0.07, "commodity": "cobalt"},
            {"item": "전구체·기타 소재", "weight": 0.20, "commodity": None},
            {"item": "인건비·감가·전력", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.98, "op": -0.02},
        "note": "하이니켈 양극재(테슬라·LG향). 메탈가 연동·역래깅으로 캐즘 국면 적자. 메탈가 반등이 관건.",
    },
    "078600:daejoo": {
        "ticker": "078600", "company": "대주전자재료", "product": "실리콘 음극재",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "원료(실리콘·금속)", "weight": 0.45, "commodity": None},
            {"item": "화학 원료", "weight": 0.15, "commodity": "naphtha"},
            {"item": "인건비·감가", "weight": 0.20, "commodity": None},
            {"item": "기타", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.75, "op": 0.10},
        "note": "실리콘 음극재·전도성페이스트(MLCC). 실리콘 음극 채택 확대(고속충전·4680)가 성장 모멘텀.",
    },
    "336370:solus": {
        "ticker": "336370", "company": "솔루스첨단소재", "product": "전지박(동박)·전자소재",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "구리", "weight": 0.55, "commodity": "copper"},
            {"item": "화학·소재", "weight": 0.12, "commodity": "naphtha"},
            {"item": "인건비·감가", "weight": 0.20, "commodity": None},
            {"item": "기타", "weight": 0.13, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.92, "op": -0.03},
        "note": "전지박(동박)+전자소재(OLED). 구리 연동. 유럽·캐나다 증설 부담·캐즘으로 적자, 가동률 회복이 관건.",
    },
    "222080:cis": {
        "ticker": "222080", "company": "씨아이에스", "product": "2차전지 전극공정 장비",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "부품·소재", "weight": 0.45, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "외주", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.80, "op": 0.08},
        "note": "전극공정 장비(코터·캘린더). 배터리 증설 투자 사이클에 실적 연동. 캐즘으로 수주 둔화가 변수.",
    },

    # ===== 화학소재(타이어코드·아라미드·탄소섬유) =====
    "120110:kolonind": {
        "ticker": "120110", "company": "코오롱인더", "product": "산업소재(타이어코드·아라미드)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "원료(석유계·PET)", "weight": 0.55, "commodity": "naphtha"},
            {"item": "에너지", "weight": 0.12, "commodity": None},
            {"item": "인건비·감가", "weight": 0.20, "commodity": None},
            {"item": "기타", "weight": 0.13, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.85, "op": 0.06},
        "note": "타이어코드·아라미드·필름+패션. 석유계 원료. 아라미드(전선·5G·방탄) 성장이 마진 견인.",
    },
    "298050:hyosungadv": {
        "ticker": "298050", "company": "효성첨단소재", "product": "타이어코드·탄소섬유",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "원료(석유계·PET)", "weight": 0.55, "commodity": "naphtha"},
            {"item": "에너지", "weight": 0.12, "commodity": None},
            {"item": "인건비·감가", "weight": 0.20, "commodity": None},
            {"item": "기타", "weight": 0.13, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.86, "op": 0.08},
        "note": "타이어코드 세계 1위+탄소섬유·아라미드. 석유계 원료. 수소(탄소섬유 압력용기)·전방 타이어 수요.",
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

    # ===== 바이오(진단·이중항체·펩타이드) =====
    "137310:sdbiosensor": {
        "ticker": "137310", "company": "에스디바이오센서", "product": "체외진단",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B·조달",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.05, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "시약·효소·원료", "weight": 0.35, "commodity": "api_pharma"},
            {"item": "플라스틱 소모품", "weight": 0.20, "commodity": "naphtha"},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.30, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.65, "op": 0.03},
        "note": "신속진단(자가검사)·POCT. 코로나 특수 후 실적 급감→정상화. 미국(메리디언) 인수로 채널 확장.",
    },
    "298380:ablbio": {
        "ticker": "298380", "company": "에이비엘바이오", "product": "이중항체 신약",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "기술수출",
        "channel_label": "기술료·로열티",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "인건비(R&D)", "weight": 0.45, "commodity": None},
            {"item": "원부자재·시약", "weight": 0.15, "commodity": "api_pharma"},
            {"item": "감가·기타", "weight": 0.20, "commodity": None},
            {"item": "기타 운영비", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.40, "op": 0.10},
        "note": "이중항체(그랩바디)·뇌혈관장벽 셔틀·ADC 기술수출. 마일스톤·로열티 매출, 파이프라인 진척이 관건.",
    },
    "087010:peptron": {
        "ticker": "087010", "company": "펩트론", "product": "지속형 펩타이드(CDMO)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B·기술수출",
        "channel_label": "기술료·유통",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "인건비(R&D)", "weight": 0.40, "commodity": None},
            {"item": "원부자재·시약", "weight": 0.20, "commodity": "api_pharma"},
            {"item": "감가(설비)", "weight": 0.20, "commodity": None},
            {"item": "기타", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.50, "op": 0.05},
        "note": "지속형 펩타이드 플랫폼(비만·당뇨 약물전달)·일라이릴리 협력. 비만약 롱액팅 수요가 성장 모멘텀.",
    },

    # ===== 원전·반도체 후공정 =====
    "052690:kepcoe": {
        "ticker": "052690", "company": "한전기술", "product": "원전 설계·엔지니어링",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "수주",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "인건비(설계)", "weight": 0.55, "commodity": None},
            {"item": "외주", "weight": 0.20, "commodity": None},
            {"item": "라이선스·기타", "weight": 0.10, "commodity": None},
            {"item": "감가·기타", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.85, "op": 0.08},
        "note": "원전 종합설계(원자로계통·종합설계). 원전 수출(체코·중동)·SMR·계속운전 수혜. 인건비 중심 서비스.",
    },
    "095340:isc": {
        "ticker": "095340", "company": "ISC", "product": "반도체 테스트소켓",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "소재(실리콘러버·소재)", "weight": 0.35, "commodity": None},
            {"item": "정밀가공", "weight": 0.20, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.30, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.65, "op": 0.20},
        "note": "반도체 테스트소켓(러버·포고). SK 계열 편입. HBM·AI 반도체 테스트 수요로 고마진(20%) 성장.",
    },
    "067310:hanamicron": {
        "ticker": "067310", "company": "하나마이크론", "product": "반도체 후공정(OSAT)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "부품·소재(리드프레임·기판)", "weight": 0.45, "commodity": None},
            {"item": "인건비", "weight": 0.18, "commodity": None},
            {"item": "감가(장비)", "weight": 0.22, "commodity": None},
            {"item": "기타", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.85, "op": 0.06},
        "note": "반도체 후공정(패키징·테스트). 메모리 업황·전공정 낙수 수혜. 브라질·베트남 등 해외 증설.",
    },

    # ===== 바이오·미용의료 확장 =====
    "028300:hlb": {
        "ticker": "028300", "company": "HLB", "product": "항암신약(리보세라닙)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "기술수출·판매",
        "channel_label": "약가·유통",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "인건비(R&D·임상)", "weight": 0.50, "commodity": None},
            {"item": "임상·CRO 비용", "weight": 0.25, "commodity": None},
            {"item": "기타", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.90, "op": -0.20},
        "note": "리보세라닙(간암) FDA 재도전. 매출 미미·대규모 R&D로 적자. 신약 승인 여부가 밸류 전부.",
    },
    "000250:samchundang": {
        "ticker": "000250", "company": "삼천당제약", "product": "안과약·바이오시밀러",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "처방·수출",
        "channel_label": "약가·유통",
        "distribution_margin": 0.10, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "API·원료", "weight": 0.30, "commodity": "api_pharma"},
            {"item": "인건비·R&D", "weight": 0.22, "commodity": None},
            {"item": "마케팅·영업", "weight": 0.28, "commodity": None},
            {"item": "감가·기타", "weight": 0.20, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.60, "op": 0.10},
        "note": "점안제(안과)+경구용 인슐린·아일리아 바이오시밀러. 시밀러 글로벌 계약·경구 인슐린이 성장 모멘텀.",
    },
    "287410:jsys": {
        "ticker": "287410", "company": "제이시스메디칼", "product": "미용 의료기기",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B·소모품",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.05, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "부품·전자소재", "weight": 0.35, "commodity": None},
            {"item": "소모품 원료", "weight": 0.25, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.40, "op": 0.25},
        "note": "미용 의료기기(포텐자·울트라셀). 소모품 리커링으로 고마진(25%). 글로벌 수출·파트너십 확대.",
    },

    # ===== 소재(환경·불소·코발트) =====
    "383310:ecoprohn": {
        "ticker": "383310", "company": "에코프로에이치엔", "product": "환경·정밀화학 소재",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "화학 원료", "weight": 0.45, "commodity": "naphtha"},
            {"item": "소재", "weight": 0.20, "commodity": None},
            {"item": "인건비·감가", "weight": 0.20, "commodity": None},
            {"item": "기타", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.75, "op": 0.15},
        "note": "환경(대기·미세먼지 저감)+정밀화학+전자소재. 에코프로 그룹 내 안정적 캐시카우(고마진).",
    },
    "089980:sangafron": {
        "ticker": "089980", "company": "상아프론테크", "product": "불소소재·2차전지 부품",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "화학 원료(불소수지 등)", "weight": 0.45, "commodity": "naphtha"},
            {"item": "소재", "weight": 0.20, "commodity": None},
            {"item": "인건비·감가", "weight": 0.20, "commodity": None},
            {"item": "기타", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.80, "op": 0.08},
        "note": "2차전지 분리막 소재·연료전지막+반도체·디스플레이 부품. 불소수지 기반. 전방 배터리·수소 수요.",
    },
    "005420:cosmochem": {
        "ticker": "005420", "company": "코스모화학", "product": "황산코발트·이산화티타늄",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "원료(코발트·티타늄광)", "weight": 0.55, "commodity": "cobalt"},
            {"item": "화학 원료", "weight": 0.15, "commodity": "naphtha"},
            {"item": "인건비·감가", "weight": 0.18, "commodity": None},
            {"item": "기타", "weight": 0.12, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.90, "op": 0.02},
        "note": "황산코발트(2차전지 리사이클)+이산화티타늄(도료 안료). 코발트·TiO2가에 마진 노출. 캐즘 영향.",
    },
    "004490:sebang": {
        "ticker": "004490", "company": "세방전지", "product": "납축전지",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B·유통",
        "channel_label": "직판·유통",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "납(연)", "weight": 0.50, "commodity": None},
            {"item": "부품·소재", "weight": 0.20, "commodity": None},
            {"item": "인건비·감가", "weight": 0.15, "commodity": None},
            {"item": "기타", "weight": 0.15, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.82, "op": 0.10},
        "note": "로케트 배터리(자동차·산업용 납축전지). 납(연) 가격이 원가 핵심. 교체 수요 안정적, ESS로 확장.",
    },

    # ===== 반도체(테스트·기판·장비) =====
    "131290:tse": {
        "ticker": "131290", "company": "티에스이", "product": "반도체 테스트(프로브카드)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "소재·부품", "weight": 0.40, "commodity": None},
            {"item": "정밀가공", "weight": 0.15, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.30, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.75, "op": 0.10},
        "note": "반도체 테스트(프로브카드·인터페이스보드). 메모리·비메모리 테스트 수요. 후공정 낙수.",
    },
    "353200:daeduk": {
        "ticker": "353200", "company": "대덕전자", "product": "반도체 패키지기판(FC-BGA)",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "원판·동박(CCL)", "weight": 0.40, "commodity": "copper"},
            {"item": "화학·소재", "weight": 0.18, "commodity": "naphtha"},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.27, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.85, "op": 0.06},
        "note": "반도체 패키지기판(FC-BGA·MLB). 동박이 원가. 서버·AI·전장 수요, 전방 반도체 사이클에 연동.",
    },
    "240810:wonikips": {
        "ticker": "240810", "company": "원익IPS", "product": "반도체·디스플레이 증착장비",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "부품·소재", "weight": 0.45, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "외주", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.75, "op": 0.10},
        "note": "반도체·디스플레이 증착장비(CVD·ALD). 삼성·SK 투자 사이클에 실적 연동. 국산 장비 대표주.",
    },
    "281820:kctech": {
        "ticker": "281820", "company": "케이씨텍", "product": "반도체 CMP장비·슬러리",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "부품·소재", "weight": 0.45, "commodity": None},
            {"item": "슬러리 원료", "weight": 0.15, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "감가·기타", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.78, "op": 0.10},
        "note": "반도체 CMP장비+세정장비+CMP슬러리(소재). 장비+소재 병행으로 리커링 매출. 전방 투자·가동률.",
    },
    "049070:intops": {
        "ticker": "049070", "company": "인탑스", "product": "사출·전장부품",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "B2B 직판",
        "channel_label": "직판(B2B)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "플라스틱·수지", "weight": 0.35, "commodity": "naphtha"},
            {"item": "부품·전자소재", "weight": 0.25, "commodity": None},
            {"item": "인건비", "weight": 0.15, "commodity": None},
            {"item": "외주·기타", "weight": 0.25, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.85, "op": 0.07},
        "note": "스마트폰 케이스·가전 사출+전장·의료기기(로봇청소기 등)로 다각화. 플라스틱(나프타)·삼성 물량.",
    },

    # ===== 수산·식자재유통 =====
    "003960:sajodaerim": {
        "ticker": "003960", "company": "사조대림", "product": "수산·식품",
        "unit": "매출 1,000원", "retail_price": 1000, "channel": "유통",
        "channel_label": "유통(해당없음)",
        "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": [
            {"item": "수산물·원료(참치 등)", "weight": 0.45, "commodity": "tuna"},
            {"item": "소맥·기타 원료", "weight": 0.15, "commodity": "wheat"},
            {"item": "포장재", "weight": 0.10, "commodity": "bopp_film"},
            {"item": "인건비·감가", "weight": 0.18, "commodity": None},
            {"item": "물류", "weight": 0.12, "commodity": None},
        ],
        "default_ratios": {"cogs": 0.85, "op": 0.05},
        "note": "수산(참치·연육·어묵)+식품+사료. 어가·곡물가가 원가. 사조그룹 식품 계열 통합.",
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


# --- 업종(sector) 분류 — 위젯 드롭다운 그룹핑용 ------------------------------
# (sector 라벨, [product_id …]) 순서대로. 여기 없는 제품은 "기타"로 표시된다.
SECTOR_GROUPS: list[tuple[str, list[str]]] = [
    ("음식료·음료", [
        "004370:sinramyeon", "007310:jinramyeon", "271560:chocopie", "097950:hetbahn",
        "005300:chilsung", "003230:buldak", "004370:saewookkang", "271560:pocachip",
        "280360:pepero", "005180:bananamilk", "005180:melona", "000080:chamisul",
        "000080:terra", "005300:chumchurum", "007310:ketchup", "097950:wangkyoja",
        "049770:tunacan", "033780:esse", "001680:miwon", "007310:mayo",
        "267980:maeilmilk", "136480:harim", "005610:samlip", "026960:dongsuh",
        "003920:namyang", "006040:dongwon",
    ]),
    ("화장품", ["090430:sulwhasoo", "051900:whoo", "192820:cosmax", "161890:kolmar"]),
    ("제약·바이오", [
        "000100:bcomc", "000640:bacchus", "128940:amosartan",
        "207940:samsungbio", "068270:celltrion", "096530:seegene",
    ]),
    ("유통·리테일", [
        "139480:emart", "282330:cu", "007070:gs25", "004170:shinsegae",
        "069960:hyundaidept", "057050:hyundaihs", "008770:hotelshilla",
    ]),
    ("반도체·전자·디스플레이", [
        "005930:dram", "000660:hbm", "009150:mlcc", "011070:lginnotek",
        "042700:hanmisemi", "034220:lgdisplay",
    ]),
    ("자동차·부품·타이어", [
        "005380:grandeur", "000270:sorento", "012330:mobis", "018880:hanon",
        "161390:hankooktire", "073240:kumhotire",
    ]),
    ("조선·방산·기계", [
        "329180:hdhi", "042660:hanwhaocean", "012450:hanwhaaero", "047810:kai",
        "064350:rotem", "034020:doosanenerbility", "000490:daedong", "042670:hd_infracore",
    ]),
    ("철강·비철·소재", ["005490:hrcoil", "010130:koreazinc", "213500:hansol"]),
    ("화학·정유·에너지", [
        "051910:ethylene", "011170:lottechem", "010950:soil", "036460:kogas",
        "015760:electricity", "009830:hanwhasol", "002380:kcc",
    ]),
    ("2차전지·소재", [
        "373220:lgbattery", "006400:samsungsdi", "247540:ecoprobm", "003670:poscofuture",
    ]),
    ("건설·건자재", ["000720:hyundaieng", "006360:gseng", "003410:ssangyongc", "009240:hanssem"]),
    ("운송·물류·렌탈", [
        "003490:passenger", "011200:container", "000120:cjlogistics",
        "089860:lotterental", "039130:hanatour",
    ]),
    ("의류·패션", ["383220:mlb", "111770:oem"]),
    ("IT·게임·엔터·미디어·통신", [
        "036570:ncsoft", "259960:krafton", "352820:hybe", "035900:jyp",
        "035760:cjenm", "253450:studiodragon", "017670:skt", "035420:naver", "035720:kakao",
    ]),
    ("금융", [
        "105560:kbfg", "055550:shinhan", "006800:miraeasset", "032830:samsunglife",
        "000810:samsungfire", "330590:lottereit", "029780:samsungcard",
    ]),
    ("상사·서비스·기타", [
        "047050:posco_intl", "001120:lxintl", "021240:coway",
        "214150:classys", "035250:kangwonland", "215200:megastudy",
    ]),
]
_SECTOR_BY_ID: dict[str, str] = {pid: sec for sec, ids in SECTOR_GROUPS for pid in ids}
# 이후 배치로 추가된 제품의 업종 매핑(위 리터럴을 건드리지 않고 확장).
_SECTOR_BY_ID.update({
    "004020:hyundaisteel": "철강·비철·소재",
    "006260:ls": "철강·비철·소재",
    "005290:dongjin": "반도체·전자·디스플레이",
    "357780:soulbrain": "반도체·전자·디스플레이",
    "213420:duksan": "반도체·전자·디스플레이",
    "032500:kmw": "반도체·전자·디스플레이",
    "277810:rainbow": "조선·방산·기계",
    "454910:doosanrobot": "조선·방산·기계",
    "272210:hanwhasystem": "조선·방산·기계",
    "112610:cswind": "화학·정유·에너지",
    "336260:doosanfuel": "화학·정유·에너지",
    "025860:namhae": "화학·정유·에너지",
    "251270:netmarble": "IT·게임·엔터·미디어·통신",
    "089590:jejuair": "운송·물류·렌탈",
    "023530:lotteshopping": "유통·리테일",
    "086280:glovis": "운송·물류·렌탈",
    "028670:panocean": "운송·물류·렌탈",
    "011210:wia": "자동차·부품·타이어",
    "051600:kps": "화학·정유·에너지",
    "096770:skinno": "화학·정유·에너지",
    "300720:hanil": "건설·건자재",
    "326030:skbp": "제약·바이오",
    "069620:daewoong": "제약·바이오",
    "263750:pearlabyss": "IT·게임·엔터·미디어·통신",
    "215000:golfzon": "상사·서비스·기타",
    "001130:daehanflour": "음식료·음료",
    "145990:samyangsa": "음식료·음료",
    "237880:clio": "화장품",
    "001450:hyundaimarine": "금융",
    "058470:leeno": "반도체·전자·디스플레이",
    "030200:kt": "IT·게임·엔터·미디어·통신",
    "032640:lguplus": "IT·게임·엔터·미디어·통신",
    "041510:sm": "IT·게임·엔터·미디어·통신",
    "122870:ygent": "IT·게임·엔터·미디어·통신",
    "011780:kumhopetro": "화학·정유·에너지",
    "298020:hyosungtnc": "화학·정유·에너지",
    "460860:dongkuk": "철강·비철·소재",
    "204320:hlmando": "자동차·부품·타이어",
    "005850:sl": "자동차·부품·타이어",
    "196170:alteogen": "제약·바이오",
    "375500:dlenc": "건설·건자재",
    "047040:daewooeng": "건설·건자재",
    "028050:samsungena": "건설·건자재",
    "222800:simmtech": "반도체·전자·디스플레이",
    "005070:cosmoams": "2차전지·소재",
    "066570:lgelec": "반도체·전자·디스플레이",
    "018260:sds": "IT·게임·엔터·미디어·통신",
    "307950:autoever": "IT·게임·엔터·미디어·통신",
    "112040:wemade": "IT·게임·엔터·미디어·통신",
    "036420:contentree": "IT·게임·엔터·미디어·통신",
    "241560:bobcat": "조선·방산·기계",
    "267260:hdelectric": "조선·방산·기계",
    "298040:hyosungheavy": "조선·방산·기계",
    "010060:oci": "화학·정유·에너지",
    "004000:lottefine": "화학·정유·에너지",
    "039490:kiwoom": "금융",
    "005940:nhis": "금융",
    "302440:skbs": "제약·바이오",
    "145020:hugel": "제약·바이오",
    "017810:pulmuone": "음식료·음료",
    "007660:isupetasys": "반도체·전자·디스플레이",
    "178920:pihightech": "반도체·전자·디스플레이",
    "090460:bh": "반도체·전자·디스플레이",
    "348370:enchem": "2차전지·소재",
    "278280:cheonbo": "2차전지·소재",
    "121600:nanoshin": "2차전지·소재",
    "237690:stpharm": "제약·바이오",
    "214450:pharmaresearch": "제약·바이오",
    "194700:novarex": "제약·바이오",
    "010120:lselectric": "조선·방산·기계",
    "010620:hdmipo": "조선·방산·기계",
    "105630:hansae": "의류·패션",
    "009450:kdnavien": "건설·건자재",
    "018670:skgas": "화학·정유·에너지",
    "014620:sungkwang": "철강·비철·소재",
    "141080:ligachem": "제약·바이오",
    "006280:gccorp": "제약·바이오",
    "003850:boryung": "제약·바이오",
    "086450:dkpharma": "제약·바이오",
    "403870:hpsp": "반도체·전자·디스플레이",
    "036930:jusung": "반도체·전자·디스플레이",
    "064760:tck": "반도체·전자·디스플레이",
    "074600:wonikqnc": "반도체·전자·디스플레이",
    "195870:haesungds": "반도체·전자·디스플레이",
    "450080:ecopromety": "2차전지·소재",
    "093370:foosung": "2차전지·소재",
    "079550:lignex1": "조선·방산·기계",
    "082740:hanwhaengine": "조선·방산·기계",
    "078340:com2us": "IT·게임·엔터·미디어·통신",
    "192080:doubleu": "IT·게임·엔터·미디어·통신",
    "066970:lnf": "2차전지·소재",
    "078600:daejoo": "2차전지·소재",
    "336370:solus": "2차전지·소재",
    "222080:cis": "2차전지·소재",
    "120110:kolonind": "화학·정유·에너지",
    "298050:hyosungadv": "화학·정유·에너지",
    "103140:poongsan": "철강·비철·소재",
    "001430:seah": "철강·비철·소재",
    "016380:kgsteel": "철강·비철·소재",
    "137310:sdbiosensor": "제약·바이오",
    "298380:ablbio": "제약·바이오",
    "087010:peptron": "제약·바이오",
    "052690:kepcoe": "조선·방산·기계",
    "095340:isc": "반도체·전자·디스플레이",
    "067310:hanamicron": "반도체·전자·디스플레이",
    "028300:hlb": "제약·바이오",
    "000250:samchundang": "제약·바이오",
    "287410:jsys": "제약·바이오",
    "383310:ecoprohn": "화학·정유·에너지",
    "089980:sangafron": "2차전지·소재",
    "005420:cosmochem": "2차전지·소재",
    "004490:sebang": "2차전지·소재",
    "131290:tse": "반도체·전자·디스플레이",
    "353200:daeduk": "반도체·전자·디스플레이",
    "240810:wonikips": "반도체·전자·디스플레이",
    "281820:kctech": "반도체·전자·디스플레이",
    "049070:intops": "반도체·전자·디스플레이",
    "010690:hwashin": "자동차·부품·타이어",
    "003960:sajodaerim": "음식료·음료",
    "051500:cjfreshway": "유통·리테일",
})
SECTOR_ORDER: list[str] = [sec for sec, _ in SECTOR_GROUPS]


# --- DART 자동생성 원가모델 병합 (수작업 PRODUCTS 정답지 + 자동 확장) --------
AUTO_SECTOR = "자동생성(DART)"
_auto_cache: dict = {"mtime": None, "data": {}}


def _auto_products() -> dict:
    """costmodels_auto.json 을 mtime 캐시로 로드. {product_id: model}."""
    from app.data.fundamentals import auto_costmodel
    p = auto_costmodel._auto_path()
    try:
        mt = p.stat().st_mtime if p.exists() else None
    except Exception:
        mt = None
    if mt != _auto_cache["mtime"]:
        _auto_cache["data"] = auto_costmodel.load_auto()
        _auto_cache["mtime"] = mt
    return _auto_cache["data"]


def _lookup(product_id: str) -> dict | None:
    return PRODUCTS.get(product_id) or _auto_products().get(product_id)


def list_products() -> list[dict]:
    """위젯 드롭다운용 제품 목록 (업종 태그 포함). 수작업 + DART 자동생성."""
    out = [
        {"id": pid, "ticker": p["ticker"], "company": p["company"],
         "product": p["product"], "unit": p["unit"],
         "sector": _SECTOR_BY_ID.get(pid, "기타")}
        for pid, p in PRODUCTS.items()
    ]
    curated_tickers = {p["ticker"] for p in PRODUCTS.values()}
    for pid, p in _auto_products().items():
        if pid in PRODUCTS or p.get("ticker") in curated_tickers:
            continue  # 수작업이 있으면 자동본은 숨김
        out.append({"id": pid, "ticker": p["ticker"], "company": p["company"],
                    "product": p["product"], "unit": p["unit"], "sector": AUTO_SECTOR})
    return out


# --- DART 손익계산서에서 원가율/영업이익률 실측 ----------------------------
_SALES = ("매출액", "수익(매출액)", "영업수익", "매출")
_COGS = ("매출원가",)
_OP = ("영업이익", "영업이익(손실)")


def _income_ratios(ticker: str) -> dict | None:
    """최신 사업연도 {cogs, op, year, sales} — 매출원가율·영업이익률(소수). 실패 시 None."""
    try:
        df = store.dart_financials(ticker)
    except Exception:
        return None
    if df is None or df.empty:
        return None
    inc = df[df["sj_div"].isin(["IS", "CIS"])]
    if inc.empty:
        return None

    def _pick(names) -> dict[int, float]:
        sub = inc[inc["account_nm"].isin(names)]
        return {int(r["year"]): float(r["amount"]) for _, r in sub.iterrows()}

    sales, cogs, op = _pick(_SALES), _pick(_COGS), _pick(_OP)
    # 매출·매출원가가 모두 있는 가장 최근 연도.
    years = sorted(set(sales) & set(cogs), reverse=True)
    for y in years:
        s = sales[y]
        if not s:
            continue
        return {
            "year": y, "sales": s,
            "cogs": round(cogs[y] / s, 4),
            "op": round(op.get(y, 0.0) / s, 4) if op.get(y) is not None else None,
        }
    return None


def teardown(product_id: str) -> dict:
    """제품 1개의 완전 원가분해 + 마진 민감도."""
    p = _lookup(product_id)
    if not p:
        raise KeyError(product_id)

    retail = float(p["retail_price"])
    dist_margin = p["distribution_margin"]
    factory = retail * (1 - dist_margin)          # 출고가 = 회사 매출

    # ③ 재무비율: DART 실측 우선, 없으면 KB 기본값.
    fin = _income_ratios(p["ticker"])
    if fin and fin["cogs"] and 0.2 < fin["cogs"] < 0.98:
        cogs_ratio = fin["cogs"]
        op_margin = fin["op"] if (fin["op"] is not None and fin["op"] > 0) else p["default_ratios"]["op"]
        basis = {"source": "DART 실측", "year": fin["year"]}
    else:
        cogs_ratio = p["default_ratios"]["cogs"]
        op_margin = p["default_ratios"]["op"]
        basis = {"source": "추정 기본값", "year": None}
    sga_ratio = max(0.0, 1 - cogs_ratio - op_margin)

    cogs_won = factory * cogs_ratio
    sga_won = factory * sga_ratio
    op_won = factory * op_margin

    # ④⑤ 매출원가 → 원재료비 → 품목 배분.
    mat_of_cogs = p["material_ratio_of_cogs"]
    material_won = cogs_won * mat_of_cogs
    process_won = cogs_won * (1 - mat_of_cogs)     # 제조 노무·감가·에너지

    materials: list[dict] = []
    for m in p["material_mix"]:
        won = material_won * m["weight"]
        c = commodities.get(m["commodity"]) if m["commodity"] else None
        materials.append({
            "item": m["item"],
            "won": round(won),
            "pct_of_retail": round(won / retail * 100, 1),
            "commodity": c["name_ko"] if c else None,
            "commodity_key": m["commodity"],
            "chg_1y": c["chg_1y"] if c else None,
            "direction": c["direction"] if c else None,
        })

    # 워터폴(소비자가 100% 기준): 유통 → 원재료 → 가공비 → 판관비 → 영업이익.
    channel_label = p.get("channel_label", "유통 마진(도소매)")
    waterfall = (
        [{"item": channel_label, "won": round(retail * dist_margin),
          "pct_of_retail": round(dist_margin * 100, 1), "kind": "channel"}]
        + [{**m, "kind": "material"} for m in materials]
        + [
            {"item": "제조 노무·감가·에너지", "won": round(process_won),
             "pct_of_retail": round(process_won / retail * 100, 1), "kind": "process"},
            {"item": "물류·마케팅·판관비", "won": round(sga_won),
             "pct_of_retail": round(sga_won / retail * 100, 1), "kind": "sga"},
            {"item": "영업이익", "won": round(op_won),
             "pct_of_retail": round(op_margin * (1 - dist_margin) * 100, 1), "kind": "profit"},
        ]
    )

    # ⑥ 마진 민감도. 원자재 X% 변동 = 해당 원재료비 X% 변동, 판가 고정 시 그대로 OP에 반영.
    sensitivity: list[dict] = []
    momentum_delta = 0.0                            # 현재 추세(chg_1y) 반영 시 원가 증감(원)
    for m in materials:
        if not m["commodity_key"]:
            continue
        d10 = m["won"] * 0.10                        # 원자재 +10% → 원가 +d10원
        sensitivity.append({
            "item": m["item"], "commodity": m["commodity"],
            "op_delta_per_10pct": -round(d10),      # 봉지당 영업이익 변화(원)
            "op_delta_pct_per_10pct": round(-d10 / op_won * 100, 1) if op_won else None,
            "chg_1y": m["chg_1y"], "direction": m["direction"],
        })
        momentum_delta += m["won"] * (m["chg_1y"] or 0.0)

    op_after_momentum = op_won - momentum_delta
    momentum = {
        "cost_delta_won": round(momentum_delta),
        "op_before": round(op_won),
        "op_after": round(op_after_momentum),
        # 이익이 양수일 때만 % 의미가 있음(적자 기업은 None).
        "op_change_pct": round(-momentum_delta / op_won * 100, 1) if op_won > 0 else None,
        "verdict": _verdict(momentum_delta, op_won),
    }

    return {
        "product": {k: p[k] for k in ("ticker", "company", "product", "unit", "channel", "note")},
        "as_of": commodities.AS_OF,
        "basis": basis,
        "summary": {
            "retail_price": round(retail),
            "distribution_take": round(retail * dist_margin),
            "channel_label": channel_label,
            "factory_price": round(factory),
            "cogs_ratio": round(cogs_ratio, 3),
            "sga_ratio": round(sga_ratio, 3),
            "op_margin": round(op_margin, 3),
            "profit_per_unit": round(op_won),
        },
        "waterfall": waterfall,
        "materials": materials,
        "sensitivity": sensitivity,
        "momentum": momentum,
    }


def _verdict(delta: float, op: float) -> str:
    if op <= 0:
        # 적자(또는 BEP) 기업: 원가 방향만으로 판단.
        if delta > 1:
            return "적자 구간 — 원자재 상승이 적자 심화"
        if delta < -1:
            return "적자 구간 — 원자재 하락이 적자 완화"
        return "적자 구간 — 원자재 영향 중립"
    r = delta / op
    if r <= -0.15:
        return "원자재 하락세 → 마진 개선 우호적"
    if r >= 0.15:
        return "원자재 상승세 → 마진 압박, 판가 인상 없이는 훼손"
    return "원자재 혼조 → 마진 중립"
