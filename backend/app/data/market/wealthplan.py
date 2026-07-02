"""재테크 로드맵 — 프로필+목표금액 → 달성 계획 + 자격조건별 상품 추천.

프로필(나이·연봉·월수입·월저축여력·현재자산·결혼·무주택)과 목표금액/기간을 받아:
  1) 목표 달성에 필요한 월 저축액 vs 현재 여력 → 달성 가능성·부족분,
  2) 복리 가정 자산 성장 경로(언제 목표 도달),
  3) 나이/소득/결혼 자격에 맞는 정부·세제·저축·투자 상품 추천 + 우선순위 배분,
  4) 실행 로드맵.
계정별 wealth_<user>.json 에 프로필/목표 저장. 소득·저축·주식자산은 다른 탭에서 기본값을 끌어온다.

상품 조건은 2026년 기준 참고값(제도는 매년 바뀌므로 가입 전 공식 확인 필요).
"""
from __future__ import annotations

import json
import os
import re
import threading

from app.core.config import get_settings

_lock = threading.Lock()
_R = 0.05  # 기본 연 기대수익률(안전+투자 혼합 가정)

# 정부/세제/저축 상품 (2026 기준 참고). elig(p)=자격여부, why=설명
_UNIT = 10_000  # 만원


def _n(v, d=0.0):
    try:
        x = float(str(v).replace(",", ""))
        return d if x != x else x
    except (TypeError, ValueError):
        return d


def _products(p: dict) -> list[dict]:
    age = _n(p.get("age"))
    inc = _n(p.get("annual_income"))          # 연소득(원)
    married = bool(p.get("married"))
    homeless = bool(p.get("homeless", True))   # 무주택 여부(기본 True)
    has_child = bool(p.get("has_child"))       # 자녀(임신/출산) 유무
    has_earn = _n(p.get("monthly_income")) > 0 or inc > 0

    items = [
        {
            "name": "청년미래적금", "category": "청년지원",
            "eligible": 19 <= age <= 34 and inc <= 75_000_000,
            "cond": "만 19~34세 · 총급여 7,500만원 이하 · 중위소득 200% 이하",
            "benefit": "월 최대 50만원 3년, 정부매칭 6~12% + 이자 비과세 (청년도약계좌 후속)",
            "cap": 500_000, "priority": 1,
            "link": "https://ylaccount.kinfa.or.kr/",
        },
        {
            "name": "청년내일저축계좌", "category": "청년지원",
            "eligible": 15 <= age <= 39 and 0 < inc <= 30_000_000,
            "cond": "만 15~39세 · 근로·사업소득 월10만+ · 가구 중위소득 50% 이하(저소득)",
            "benefit": "월 10만 저축 시 정부 10~30만 매칭(3년) — 저소득 청년 대상",
            "cap": 100_000, "priority": 1,
            "link": "https://www.bokjiro.go.kr/",
        },
        {
            "name": "청년 주택드림 청약통장", "category": "주택·청약",
            "eligible": 19 <= age <= 34 and inc <= 50_000_000 and homeless,
            "cond": "만 19~34세 · 연소득 5,000만원 이하 · 무주택",
            "benefit": "우대금리 + 총급여 3,600만 이하 이자 비과세 + 청약자격 + 연말정산 소득공제",
            "cap": 100_000, "priority": 2,
            "link": "https://nhuf.molit.go.kr/",
        },
        {
            "name": "주택청약종합저축", "category": "주택·청약",
            "eligible": homeless,
            "cond": "무주택(누구나 가입)",
            "benefit": "청약 자격 + 총급여 7천 이하 시 연 300만납입 40% 소득공제",
            "cap": 100_000, "priority": 4,
            "link": "https://www.applyhome.co.kr/",
        },
        {
            "name": "연금저축", "category": "세제혜택·노후",
            "eligible": True,
            "cond": "누구나(소득 있으면 세액공제)",
            "benefit": "연 600만 세액공제(총급여 5,500만 이하 16.5% → 최대 99만 환급)",
            "cap": 500_000, "priority": 3,
            "link": "",
        },
        {
            "name": "IRP(개인형퇴직연금)", "category": "세제혜택·노후",
            "eligible": has_earn,
            "cond": "근로·사업소득자",
            "benefit": "연금저축과 합산 연 900만까지 세액공제(최대 148.5만 환급)",
            "cap": 250_000, "priority": 3,
            "link": "",
        },
        {
            "name": "ISA(개인종합자산관리계좌)", "category": "세제혜택·투자",
            "eligible": age >= 19,
            "cond": "만 19세+ (또는 15세+ 근로소득)",
            "benefit": "비과세 200만(일반)/400만(서민형) + 만기 IRP 전환 시 10% 추가공제",
            "cap": 400_000, "priority": 3,
            "link": "",
        },
        {
            "name": "정기적금·예금", "category": "안전저축",
            "eligible": True,
            "cond": "누구나",
            "benefit": "원금 보장 안전 저축 — 비상금·단기 목표에 적합",
            "cap": 500_000, "priority": 5,
            "link": "",
        },
        {
            "name": "주식·ETF 투자", "category": "투자",
            "eligible": True,
            "cond": "누구나(원금 손실 위험)",
            "benefit": "장기 복리 성장 — 여유자금·장기 목표에 (앱의 투자점수·매매신호 활용)",
            "cap": 10_000_000, "priority": 6,
            "link": "",
        },
        {
            "name": "청년 버팀목 전세대출", "category": "주거대출",
            "eligible": 19 <= age <= 34 and homeless,
            "cond": "만 19~34세 · 무주택 · 소득요건",
            "benefit": "초저금리 전세자금 대출(전세 목표 시)",
            "cap": 0, "priority": 7,
            "link": "https://www.myhome.go.kr/",
        },
        {
            "name": "신혼부부 전세/디딤돌 대출", "category": "주거대출",
            "eligible": married and homeless,
            "cond": "신혼부부 · 무주택 · 소득요건(완화)",
            "benefit": "신혼 전세 버팀목(수도권 최대 3억)·내집마련 디딤돌 저금리",
            "cap": 0, "priority": 7, "link": "https://www.myhome.go.kr/",
        },
        {
            "name": "신혼부부·생애최초 특별공급", "category": "주택·청약",
            "eligible": married and homeless,
            "cond": "무주택 신혼(혼인 7년내)/생애최초 · 소득 150~160% 이하",
            "benefit": "아파트 특별공급 물량 우선 배정(청약 당첨 확률↑)",
            "cap": 0, "priority": 6, "link": "https://www.applyhome.co.kr/",
        },
        # 출산·육아 (자녀 있는 경우)
        {
            "name": "부모급여", "category": "출산·육아", "eligible": has_child,
            "cond": "만 0~1세 자녀 (소득무관)",
            "benefit": "0세 월 100만 · 1세 월 50만 현금 지급", "cap": 0, "priority": 8,
            "link": "https://www.bokjiro.go.kr/",
        },
        {
            "name": "아동수당", "category": "출산·육아", "eligible": has_child,
            "cond": "만 8세 미만 아동 (소득무관)",
            "benefit": "월 10만원 (부모급여와 중복 수령)", "cap": 0, "priority": 8, "link": "",
        },
        {
            "name": "첫만남이용권", "category": "출산·육아", "eligible": has_child,
            "cond": "출생 아동",
            "benefit": "첫째 200만 · 둘째+ 300만 바우처(2년 사용)", "cap": 0, "priority": 8, "link": "",
        },
        {
            "name": "육아휴직급여", "category": "출산·육아", "eligible": has_child and has_earn,
            "cond": "육아휴직 사용 근로자",
            "benefit": "육아휴직 기간 급여 지원(상한 월 250만 등)", "cap": 0, "priority": 8, "link": "",
        },
        {
            "name": "신생아 특례 디딤돌대출", "category": "부동산", "eligible": has_child and homeless,
            "cond": "2년내 출산·입양 · 무주택 · 부부합산 소득 2억 이하",
            "benefit": "최저 연 1.8%대 주택 구입자금 대출(내집마련)", "cap": 0, "priority": 7,
            "link": "https://www.myhome.go.kr/",
        },
        # 부동산·분산 투자
        {
            "name": "리츠(REITs)·부동산펀드", "category": "부동산", "eligible": True,
            "cond": "누구나(소액 가능)",
            "benefit": "적은 돈으로 부동산에 분산 투자, 배당 연 4~7% 수령(상장 리츠)", "cap": 300_000, "priority": 6,
            "link": "",
        },
        {
            "name": "배당주·채권·금/달러 ETF", "category": "투자", "eligible": True,
            "cond": "누구나(분산 투자)",
            "benefit": "배당주·국채·금·달러 ETF로 위험 분산(변동성↓·현금흐름)", "cap": 300_000, "priority": 6,
            "link": "",
        },
    ]
    _EXAMPLES = {
        "청년미래적금": "월 50만 × 3년 = 원금 1,800만 + 정부지원 최대 ~108만 + 이자 → 약 2,000만원",
        "청년내일저축계좌": "월 10만 저축 → 정부매칭, 3년 후 최대 약 1,440만원 수령",
        "청년 주택드림 청약통장": "월 최대 100만 납입 · 우대금리 + 이자 비과세 + 청약 가점",
        "주택청약종합저축": "연 300만 납입 시 40%(120만) 소득공제 (총급여 7천↓)",
        "연금저축": "연 600만 납입 → 매년 최대 99만원 세액공제 환급(16.5%)",
        "IRP(개인형퇴직연금)": "연 300만 추가 → 매년 +49.5만 환급 (연금저축 합산 최대 148.5만)",
        "ISA(개인종합자산관리계좌)": "연 최대 2천만 납입 · 수익 200만(서민형 400만)까지 비과세",
        "정기적금·예금": "월 50만 × 3년(연 3.5%) → 약 1,900만원(원금 1,800만 + 이자)",
        "주식·ETF 투자": "월 50만 장기투자(연 8% 가정) → 10년 약 9,100만원",
        "청년 버팀목 전세대출": "전세보증금 최대 약 2억, 연 1~3%대 저금리",
        "신혼부부 전세/디딤돌 대출": "신혼 전세 버팀목 수도권 최대 3억 · 내집마련 디딤돌 저금리",
        "부모급여": "0세 월 100만 · 1세 월 50만 = 2년간 최대 1,800만원(현금)",
        "아동수당": "만 8세 미만 월 10만 → 8년간 약 960만원",
        "첫만남이용권": "출생 시 첫째 200만 · 둘째+ 300만 바우처",
        "육아휴직급여": "육아휴직 시 급여 지원(상한 월 250만 등)",
        "신생아 특례 디딤돌대출": "부부 2억↓ · 최저 연 1.8%로 주택 구입자금",
        "신혼부부·생애최초 특별공급": "무주택 신혼/생애최초 아파트 특별공급(당첨 확률↑)",
        "리츠(REITs)·부동산펀드": "소액으로 부동산 분산투자 · 배당 연 4~7% 수령",
        "배당주·채권·금/달러 ETF": "배당주·국채·금·달러로 포트폴리오 위험 분산",
    }
    for it in items:
        it["example"] = _EXAMPLES.get(it["name"], "")
    return items


def _fv(current: float, pmt: float, months: int, r_month: float) -> float:
    fv = current * (1 + r_month) ** months
    if r_month > 0:
        fv += pmt * (((1 + r_month) ** months - 1) / r_month)
    else:
        fv += pmt * months
    return fv


def _reach_months(current: float, monthly: float, goal: float, r_year: float, cap_years: int = 50) -> int | None:
    """월 monthly 적립·연 r_year 복리로 goal 도달까지 개월. 미달이면 None."""
    if goal <= 0:
        return 0
    rm = r_year / 12.0
    bal = current
    for m in range(1, cap_years * 12 + 1):
        bal = bal * (1 + rm) + monthly
        if bal >= goal:
            return m
    return None


# 위험도별 시나리오 (연 수익률 낮음~중간~높음, 안전성)
_TIERS = (
    ("safe", "안전형", "예·적금·청년적금·청약 중심 (원금 보장)", 0.030, 0.035, 0.040, "원금 보장 · 안전성 매우 높음", "낮음"),
    ("balanced", "균형형", "예금+ISA+연금펀드+ETF 혼합", 0.040, 0.060, 0.080, "일부 변동 · 안전성 중간", "중간"),
    ("aggressive", "공격형", "주식·ETF 등 위험자산 비중 큼", 0.020, 0.090, 0.150, "원금 손실 가능 · 안전성 낮음", "높음"),
)


def _scenarios(current: float, monthly: float, goal: float, years: int) -> list[dict]:
    months = years * 12
    out = []
    safe_reach = None
    for key, name, desc, r_lo, r_mid, r_hi, safety, risk in _TIERS:
        bal_mid = _fv(current, monthly, months, r_mid / 12.0)
        bal_lo = _fv(current, monthly, months, r_lo / 12.0)
        bal_hi = _fv(current, monthly, months, r_hi / 12.0)
        rm_mid = _reach_months(current, monthly, goal, r_mid)
        rm_lo = _reach_months(current, monthly, goal, r_lo)
        rm_hi = _reach_months(current, monthly, goal, r_hi)
        reach_mid = round(rm_mid / 12, 1) if rm_mid else None
        if key == "safe":
            safe_reach = reach_mid
        saved = round(safe_reach - reach_mid, 1) if (safe_reach and reach_mid) else None
        out.append({
            "key": key, "name": name, "desc": desc, "safety": safety, "risk": risk,
            "return_mid": r_mid, "return_low": r_lo, "return_high": r_hi,
            "balance_at_goal_years": round(bal_mid),
            "balance_low": round(bal_lo), "balance_high": round(bal_hi),
            "reach_years": reach_mid,
            "reach_years_low": round(rm_hi / 12, 1) if rm_hi else None,   # 고수익=빠름
            "reach_years_high": round(rm_lo / 12, 1) if rm_lo else None,  # 저수익=느림
            "time_saved_vs_safe": saved,
        })
    return out


def _recommend_tier(age: float, years: int) -> str:
    if years <= 3:
        return "safe"
    if age and age <= 35 and years >= 7:
        return "aggressive"
    return "balanced"


def _required_pmt(current: float, goal: float, months: int, r_month: float) -> float:
    fv_cur = current * (1 + r_month) ** months
    need = goal - fv_cur
    if need <= 0:
        return 0.0
    if r_month > 0:
        factor = ((1 + r_month) ** months - 1) / r_month
        return need / factor if factor else need / months
    return need / months


def compute(p: dict) -> dict:
    age = _n(p.get("age"))
    goal = _n(p.get("goal_amount"))
    years = int(_n(p.get("goal_years"), 5)) or 5
    current = _n(p.get("current_assets"))
    capacity = _n(p.get("monthly_saving"))
    months = years * 12
    rm = _R / 12.0

    required = round(_required_pmt(current, goal, months, rm))
    feasible = capacity >= required if goal else None
    shortfall = max(0, required - capacity)

    # 위험도별 시나리오 (모았을 때 얼마·도달 시간·안전형 대비 단축)
    scenarios = _scenarios(current, capacity, goal, years)
    rec_tier = _recommend_tier(age, years)
    for s in scenarios:
        s["recommended"] = (s["key"] == rec_tier)

    # 현재 여력으로 굴렸을 때 목표 도달 시점
    reach_month = None
    bal = current
    proj = []
    for m in range(1, 12 * 40 + 1):
        bal = bal * (1 + rm) + capacity
        if m % 12 == 0:
            proj.append({"year": m // 12, "balance": round(bal)})
        if reach_month is None and goal and bal >= goal:
            reach_month = m
        if m >= months and reach_month is not None:
            break
    reach_years = round(reach_month / 12, 1) if reach_month else None

    # 자격 상품
    products = _products(p)
    eligible = [x for x in products if x["eligible"]]

    # 우선순위 배분(월 여력 분배)
    alloc = []
    remain = capacity
    for x in sorted(eligible, key=lambda t: t["priority"]):
        if x["cap"] <= 0 or remain <= 0:
            continue
        if x["category"] in ("주거대출", "출산·육아"):
            continue
        amt = min(remain, x["cap"])
        if x["name"] == "주식·ETF 투자":  # 마지막에 나머지 전부
            amt = remain
        if amt >= 10_000:
            alloc.append({"name": x["name"], "monthly": round(amt), "category": x["category"], "why": x["benefit"]})
            remain -= amt

    # 로드맵
    steps = []
    if goal <= 0:
        steps.append("목표금액과 기간을 입력하면 달성 계획과 맞춤 상품을 계산합니다.")
    else:
        if capacity <= 0:
            steps.append("월 저축 여력이 0입니다. 먼저 가계부에서 지출을 줄여 여유자금을 확보하세요.")
        if feasible:
            steps.append(f"현재 월 {round(capacity):,}원 저축이면 목표 {round(goal):,}원을 약 {reach_years}년에 달성할 수 있습니다(연 {int(_R*100)}% 가정).")
        else:
            steps.append(f"목표를 {years}년에 달성하려면 월 {required:,}원이 필요한데 현재 여력은 {round(capacity):,}원입니다. "
                         f"월 {shortfall:,}원 부족 → 지출 절감·부업·기간 연장·수익률 제고가 필요합니다.")
        # 상품 우선순위 조언
        yth = [x["name"] for x in eligible if x["category"] == "청년지원"]
        if yth:
            steps.append(f"1순위(정부 매칭=확정 고수익): {', '.join(yth)} 부터 채우세요.")
        steps.append("2순위(세금 환급): 연금저축 600만+IRP 300만(연 900만) 세액공제로 최대 148만원 환급받으세요.")
        if any(x["category"] == "주택·청약" for x in eligible):
            steps.append("내집마련 계획이면 청약통장은 소액이라도 유지(청약 가점·소득공제).")
        steps.append("남는 여유자금은 ISA·주식/ETF로 장기 복리 투자(앱의 투자점수·매매신호 활용).")
        agg = next((s for s in scenarios if s["key"] == "aggressive"), None)
        rec = next((s for s in scenarios if s.get("recommended")), None)
        if agg and agg.get("time_saved_vs_safe"):
            steps.append(f"위험을 감수해 공격형(연 {int(agg['return_mid']*100)}% 기대)으로 운용하면 안전형보다 약 "
                         f"{agg['time_saved_vs_safe']}년 빨리 도달할 수 있습니다(단, 원금 손실 위험).")
        if rec:
            steps.append(f"당신의 나이·기간에는 '{rec['name']}'을 추천합니다 — {rec['desc']}.")

    return {
        "profile": p,
        "goal": {"amount": round(goal), "years": years},
        "required_monthly": required,
        "capacity_monthly": round(capacity),
        "feasible": feasible,
        "shortfall": shortfall,
        "reach_years": reach_years,
        "assumed_return": _R,
        "scenarios": scenarios,
        "projection": proj[:max(years, 10)],
        "products": products,
        "eligible_count": len(eligible),
        "allocation": alloc,
        "steps": steps,
        "note": "상품 조건·혜택은 2026년 기준 참고값입니다. 정부지원은 매년 바뀌니 가입 전 공식 사이트에서 최신 조건을 확인하세요. 투자는 원금 손실 위험이 있습니다.",
    }


# --- 대출 레버리지(대출받아 투자) 시뮬레이터 -------------------------------
_LOANS = [
    ("전세자금대출", 3.5, "전세 보증금 — 실거주용(투자 아님)"),
    ("주택담보대출", 4.5, "집 담보 — 저금리·큰 한도(실거주/부동산)"),
    ("신용대출", 6.5, "직장인 신용 — 한도 연봉 내외, 신용도별 상이"),
    ("마이너스통장", 7.5, "쓴 만큼 이자 — 편리하나 금리 높음"),
    ("증권사 신용융자(빚투)", 8.5, "주식 담보 레버리지 — 반대매매 위험 매우 큼"),
    ("청년 버팀목 전세대출", 2.2, "만19~34 무주택 — 초저금리(전세)"),
    ("신생아 특례 디딤돌", 2.5, "2년내 출산·무주택 — 초저금리(주택구입)"),
]


def loan_sim(loan_amount: float, loan_rate: float, loan_years: int, invest_return: float) -> dict:
    loan_amount = max(0.0, _n(loan_amount))
    loan_years = max(1, int(_n(loan_years, 1)))
    n = loan_years * 12
    r = _n(loan_rate) / 100.0 / 12.0
    if r > 0:
        pay = loan_amount * r * (1 + r) ** n / ((1 + r) ** n - 1)
    else:
        pay = loan_amount / n
    total_repay = pay * n
    total_interest = total_repay - loan_amount

    def net_at(ret: float):
        fv = loan_amount * (1 + ret / 100.0) ** loan_years
        return round(fv), round(fv - total_repay)

    fv_mid, net_mid = net_at(invest_return)
    # 손익분기 수익률(연): 투자 원리금이 상환총액과 같아지는 수익률
    be = None
    if loan_amount > 0:
        be = round(((total_repay / loan_amount) ** (1.0 / loan_years) - 1) * 100, 2)

    scen = []
    for name, ret in (("안전형", 3.5), ("균형형", 6.0), ("공격형", 9.0)):
        fv, net = net_at(ret)
        scen.append({"name": name, "return": ret, "invest_value": fv, "net_profit": net, "worthwhile": net > 0})

    worthwhile = net_mid > 0
    return {
        "loan_amount": round(loan_amount), "loan_rate": _n(loan_rate), "loan_years": loan_years,
        "invest_return": _n(invest_return),
        "monthly_payment": round(pay), "total_repay": round(total_repay), "total_interest": round(total_interest),
        "invest_value": fv_mid, "net_profit": net_mid, "worthwhile": worthwhile,
        "breakeven_return": be,
        "scenarios": scen,
        "loans": [{"name": nm, "rate": rt, "note": nt} for nm, rt, nt in _LOANS],
        "verdict": (f"기대수익률 {_n(invest_return)}%가 손익분기({be}%)를 넘어 이론상 순이익 {net_mid:,}원이 예상됩니다. "
                    "다만 수익은 불확실하고, 손실이 나도 대출 원리금은 그대로 갚아야 합니다."
                    if worthwhile else
                    f"기대수익률 {_n(invest_return)}%가 손익분기({be}%)에 못 미쳐 {abs(net_mid):,}원 손해가 예상됩니다. 대출 투자는 권하지 않습니다."),
        "warning": "⚠ 대출 투자(레버리지)는 손실도 그대로 커집니다. 투자 실패해도 대출 원리금은 반드시 갚아야 하며, "
                   "증권사 신용융자는 반대매매로 강제 청산될 수 있습니다. 여유자금 투자를 먼저 권합니다.",
    }


# --- 저장/조회 (계정별) -----------------------------------------------------
def _safe_user(user: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.\-]", "_", user or "default")


def _path(user: str) -> str:
    return str(get_settings().data_dir / f"wealth_{_safe_user(user)}.json")


def _load(user: str) -> dict:
    p = _path(user)
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass
    return {"profile": {}}


def _save(user: str, d: dict) -> None:
    p = _path(user)
    tmp = f"{p}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, p)


def _defaults(user: str) -> dict:
    """다른 탭에서 월수입·월저축·현재자산 기본값을 끌어온다."""
    out = {}
    try:
        from app.data.market import income
        ov = income.overview(user)
        if ov.get("salary"):
            out["monthly_income"] = ov["salary"]["net"]
            out["annual_income"] = ov["salary"]["annual_net"]
    except Exception:
        pass
    try:
        from app.data.market import budget
        pl = budget.plan(user)
        out["monthly_saving"] = max(0, pl.get("surplus", 0))
    except Exception:
        pass
    try:
        from app.data.market import watchlist
        out["current_assets"] = watchlist.diagnose(user).get("summary", {}).get("total_value", 0)
    except Exception:
        pass
    return out


def get_plan(user: str) -> dict:
    d = _load(user)
    prof = dict(_defaults(user))
    prof.update(d.get("profile", {}))  # 저장된 값이 기본값을 덮어씀
    return compute(prof)


def save_profile(user: str, profile: dict) -> dict:
    with _lock:
        d = _load(user)
        d["profile"] = {**d.get("profile", {}), **(profile or {})}
        _save(user, d)
    return get_plan(user)
