"""원자재 시세 스냅샷 — 제품 단위 원가분해(unit_economics)의 가격 소스.

제품별 마진 민감도를 계산하려면 각 원재료의 "현재 시세 + 최근 추세"가 필요하다.
지금은 리서치로 확정한 **스냅샷**(as_of 명시)을 담고, 나중에 이 모듈만 실거래
피드(CBOT/LME/석유공사·통계청 PPI 등)로 교체하면 엔진 전체가 자동 갱신된다.

각 항목:
  key       : 코드(제품 KB의 material_mix.commodity 와 매칭)
  name_ko   : 한글명
  unit      : 시세 단위
  price     : 최근 시세(스냅샷)
  chg_1y    : 전년比 변동률(소수, 예 +0.16 = +16%)  → 마진 모멘텀 계산에 사용
  source    : 대표 가격 소스(실시간 연동 시 참고)
"""
from __future__ import annotations

# as_of: 이 스냅샷의 기준 시점(수동 갱신). 실시간 피드 연동 전까지 유효.
AS_OF = "2026-07"

_TABLE: dict[str, dict] = {
    "wheat": {
        "name_ko": "소맥(밀)", "unit": "USc/bu", "price": 598.0, "chg_1y": -0.08,
        "source": "CBOT 소맥선물 · 통계청 PPI",
    },
    "palm_oil": {
        "name_ko": "팜유", "unit": "USD/톤", "price": 1020.0, "chg_1y": +0.098,
        "source": "말레이시아 팜유(MDEX)",
    },
    "soybean_oil": {
        "name_ko": "대두유", "unit": "USD/톤", "price": 974.0, "chg_1y": -0.216,
        "source": "CBOT 대두유선물",
    },
    "sugar": {
        "name_ko": "원당·설탕", "unit": "USc/lb", "price": 18.5, "chg_1y": -0.12,
        "source": "ICE 뉴욕 원당선물",
    },
    "cocoa": {
        "name_ko": "코코아", "unit": "USD/톤", "price": 3300.0, "chg_1y": -0.60,
        "source": "ICE 코코아선물",
    },
    "corn": {
        "name_ko": "옥수수", "unit": "USc/bu", "price": 452.0, "chg_1y": -0.10,
        "source": "CBOT 옥수수선물",
    },
    "rice": {
        "name_ko": "쌀(국내산)", "unit": "원/20kg", "price": 46000.0, "chg_1y": +0.03,
        "source": "통계청 산지쌀값",
    },
    "aluminum": {
        "name_ko": "알루미늄(캔)", "unit": "USD/톤", "price": 3518.0, "chg_1y": +0.164,
        "source": "LME 알루미늄",
    },
    "naphtha": {
        "name_ko": "나프타(석화·PET원료)", "unit": "USD/톤", "price": 700.0, "chg_1y": -0.03,
        "source": "석유공사 페트로넷",
    },
    "bopp_film": {
        "name_ko": "포장재(BOPP필름)", "unit": "지수", "price": 100.0, "chg_1y": +0.15,
        "source": "한국물가정보(KPI) · 업계",
    },
    "lysine": {
        "name_ko": "라이신(바이오)", "unit": "EUR/톤", "price": 1461.0, "chg_1y": -0.40,
        "source": "유럽·중국 스팟(증권사 리포트)",
    },
    "raw_milk": {
        "name_ko": "원유(우유)", "unit": "원/L", "price": 1084.0, "chg_1y": +0.04,
        "source": "낙농진흥회 원유가격연동제",
    },
    "ethanol_alcohol": {
        "name_ko": "주정(소주 원료)", "unit": "지수", "price": 100.0, "chg_1y": +0.05,
        "source": "대한주정판매 고시가",
    },
    "malt": {
        "name_ko": "맥아(맥주 원료)", "unit": "USD/톤", "price": 430.0, "chg_1y": -0.05,
        "source": "국제 보리·맥아가",
    },
    "tuna": {
        "name_ko": "가다랑어(참치 어가)", "unit": "USD/톤", "price": 1450.0, "chg_1y": -0.10,
        "source": "방콕 가다랑어 어가",
    },
    "tobacco_leaf": {
        "name_ko": "잎담배(연초)", "unit": "지수", "price": 100.0, "chg_1y": +0.02,
        "source": "국제 엽연초 시세",
    },
    "tomato": {
        "name_ko": "토마토페이스트", "unit": "USD/톤", "price": 950.0, "chg_1y": -0.05,
        "source": "국제 가공용 토마토가",
    },
    "potato": {
        "name_ko": "감자(가공용)", "unit": "원/kg", "price": 1600.0, "chg_1y": +0.05,
        "source": "aT 도매·통계청",
    },
    "pork": {
        "name_ko": "돈육", "unit": "원/kg", "price": 5300.0, "chg_1y": +0.03,
        "source": "축산물품질평가원",
    },
    "usdkrw": {
        "name_ko": "원/달러 환율", "unit": "원", "price": 1390.0, "chg_1y": +0.05,
        "source": "한국은행 ECOS",
    },
    # --- 식품·농축산 확장 ---
    "coffee_bean": {
        "name_ko": "커피 원두(아라비카)", "unit": "USc/lb", "price": 320.0, "chg_1y": +0.30,
        "source": "ICE 아라비카 선물",
    },
    "chicken": {
        "name_ko": "육계(생계)", "unit": "원/kg", "price": 2100.0, "chg_1y": +0.05,
        "source": "한국육계협회 시세",
    },
    "soybean": {
        "name_ko": "대두·대두박", "unit": "USc/bu", "price": 1050.0, "chg_1y": -0.08,
        "source": "CBOT 대두선물",
    },
    "api_pharma": {
        "name_ko": "원료의약품(API)", "unit": "지수", "price": 100.0, "chg_1y": +0.02,
        "source": "수입 원료의약품가",
    },
    # --- 산업재·소재 ---
    "silicon_wafer": {
        "name_ko": "실리콘 웨이퍼", "unit": "지수", "price": 100.0, "chg_1y": +0.02,
        "source": "웨이퍼 공급가",
    },
    "steel_hr": {
        "name_ko": "철강(열연·고철)", "unit": "원/톤", "price": 850000.0, "chg_1y": -0.03,
        "source": "철강금속신문 유통가",
    },
    "iron_ore": {
        "name_ko": "철광석", "unit": "USD/톤", "price": 105.0, "chg_1y": -0.05,
        "source": "중국 CFR 62% 분광",
    },
    "coking_coal": {
        "name_ko": "석탄(원료탄·발전탄)", "unit": "USD/톤", "price": 200.0, "chg_1y": +0.05,
        "source": "호주 원료탄·연료탄",
    },
    "copper": {
        "name_ko": "구리", "unit": "USD/톤", "price": 9800.0, "chg_1y": +0.15,
        "source": "LME 구리",
    },
    "crude_oil": {
        "name_ko": "원유(WTI/두바이)", "unit": "USD/bbl", "price": 68.0, "chg_1y": -0.05,
        "source": "두바이유·WTI",
    },
    "lng": {
        "name_ko": "LNG(천연가스)", "unit": "USD/MMBtu", "price": 12.0, "chg_1y": -0.05,
        "source": "동북아 JKM",
    },
    "jet_fuel": {
        "name_ko": "항공유(제트유)", "unit": "USD/bbl", "price": 88.0, "chg_1y": -0.08,
        "source": "싱가포르 항공유",
    },
    # --- 2차전지 메탈 ---
    "lithium": {
        "name_ko": "리튬(탄산·수산화)", "unit": "USD/톤", "price": 12000.0, "chg_1y": -0.20,
        "source": "탄산리튬 스팟",
    },
    "nickel": {
        "name_ko": "니켈", "unit": "USD/톤", "price": 15500.0, "chg_1y": -0.15,
        "source": "LME 니켈",
    },
    "cobalt": {
        "name_ko": "코발트", "unit": "USD/톤", "price": 33000.0, "chg_1y": -0.10,
        "source": "LME 코발트",
    },
    # --- 건설·화학·경공업 ---
    "cement": {
        "name_ko": "시멘트·레미콘", "unit": "원/톤", "price": 112000.0, "chg_1y": +0.05,
        "source": "한국물가정보(KPI)",
    },
    "natural_rubber": {
        "name_ko": "천연고무", "unit": "USc/kg", "price": 190.0, "chg_1y": +0.08,
        "source": "SICOM 천연고무 선물",
    },
    "cotton": {
        "name_ko": "면화", "unit": "USc/lb", "price": 68.0, "chg_1y": -0.05,
        "source": "ICE 면화 선물",
    },
    "wood": {
        "name_ko": "목재(MDF·PB)", "unit": "지수", "price": 100.0, "chg_1y": -0.02,
        "source": "수입 원목·보드 시세",
    },
    "titanium_dioxide": {
        "name_ko": "이산화티타늄(도료 안료)", "unit": "USD/톤", "price": 3000.0, "chg_1y": -0.05,
        "source": "국제 TiO2 시세",
    },
    "pulp": {
        "name_ko": "펄프(제지 원료)", "unit": "USD/톤", "price": 720.0, "chg_1y": -0.08,
        "source": "BHKP 활엽수 펄프",
    },
    "zinc": {
        "name_ko": "아연", "unit": "USD/톤", "price": 2800.0, "chg_1y": -0.03,
        "source": "LME 아연",
    },
    "polysilicon": {
        "name_ko": "폴리실리콘(태양광)", "unit": "USD/kg", "price": 5.0, "chg_1y": -0.30,
        "source": "중국 폴리실리콘 스팟",
    },
    "urea": {
        "name_ko": "요소(비료·암모니아)", "unit": "USD/톤", "price": 360.0, "chg_1y": -0.05,
        "source": "국제 요소 시세",
    },
}


def get(key: str) -> dict | None:
    """단일 원자재 시세. {key, name_ko, unit, price, chg_1y, direction, source}."""
    row = _TABLE.get(key)
    if not row:
        return None
    return {"key": key, "direction": _dir(row["chg_1y"]), **row}


def all() -> list[dict]:
    return [get(k) for k in _TABLE]


def _dir(chg: float) -> str:
    if chg >= 0.03:
        return "up"      # ▲ 원가 악재
    if chg <= -0.03:
        return "down"    # ▼ 원가 호재
    return "flat"
