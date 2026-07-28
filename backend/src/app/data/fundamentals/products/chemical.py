"""제품 원가 지식베이스 — 화학·정유·에너지.

필드의 의미는 패키지 문서(``products/__init__.py``) 참고. 이 파일은 **데이터만**
담는다 — 계산 로직은 ``app/data/fundamentals/unit_economics.py``.
"""
from __future__ import annotations

SECTOR = "화학·정유·에너지"

PRODUCTS: dict[str, dict] = {
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
}
