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


# --- 부동산 투자(자기자본+대출→임대) 시뮬레이터 ---------------------------
def realty_sim(price: float, own: float, loan_rate: float, years: int,
               appreciation: float, mode: str, deposit: float, rent_monthly: float) -> dict:
    """자기자본+대출로 매입해 세(전세/월세) 놓는 부동산 투자 수익 시뮬.

    전세(갭투자): 전세보증금이 매매가 대부분 커버 → 자기자본은 '갭'만, 월수입 없음.
    월세: 대출 끼고 매입 → 월세 − 대출이자 = 월 현금흐름 + 집값 상승 차익.
    핵심: 이자(interest-only 가정)만 내다가 매도 시 대출·보증금 상환. 레버리지로 자기자본
    대비 수익률(ROE)이 커지지만, 집값 하락 시 손실도 자기자본 대비 크게 확대된다.
    """
    price = _n(price); own = _n(own); r = _n(loan_rate) / 100.0
    Y = max(1, int(_n(years, 1))); deposit = _n(deposit); rent = _n(rent_monthly)
    wolse = (mode == "wolse")

    loan = max(0.0, price - own - deposit)      # 자기자본+보증금으로 부족한 만큼 대출
    mo_interest = loan * r / 12.0
    total_interest = loan * r * Y               # 이자만 상환(원금은 매도 시)
    mo_cashflow = (rent - mo_interest) if wolse else (-mo_interest)
    rent_yield = round(rent * 12 / own * 100, 1) if (wolse and own > 0) else None

    def outcome(a_pct: float) -> dict:
        fp = price * (1 + a_pct / 100.0) ** Y
        gain = fp - price
        total_rent = rent * 12 * Y if wolse else 0.0
        net = gain + total_rent - total_interest
        roe = round(net / own * 100, 1) if own > 0 else None
        return {"appreciation": a_pct, "future_price": round(fp), "sale_gain": round(gain),
                "net_profit": round(net), "roe": roe}

    base = outcome(appreciation)
    # 하락/보합/입력값 시나리오 — 레버리지 양방향 효과
    scen = [
        {"name": "하락", **outcome(-3.0)},
        {"name": "보합", **outcome(0.0)},
        {"name": f"상승", **outcome(appreciation)},
    ]
    # 무대출(전액 자기자본) 대비 레버리지 효과
    roe_noleverage = round((price * (1 + appreciation / 100.0) ** Y - price) / price * 100, 1)

    return {
        "mode": "월세 수익형" if wolse else "전세 갭투자",
        "price": round(price), "own_capital": round(own), "loan": round(loan),
        "loan_rate": _n(loan_rate), "years": Y, "appreciation": appreciation,
        "deposit": round(deposit), "rent_monthly": round(rent) if wolse else 0,
        "monthly_interest": round(mo_interest), "monthly_cashflow": round(mo_cashflow),
        "rent_yield_on_capital": rent_yield,
        "total_interest": round(total_interest),
        "future_price": base["future_price"], "sale_gain": base["sale_gain"],
        "net_profit": base["net_profit"], "roe": base["roe"],
        "roe_no_leverage": roe_noleverage,
        "scenarios": scen,
        "note": ("월세 − 대출이자 = 월 현금흐름. 자기자본 대비 수익률(ROE)이 집값 자체 상승률보다 큰 것이 레버리지 효과."
                 if wolse else
                 "전세보증금이 매매가 대부분을 충당해 소액(갭)으로 투자. 월수입은 없고 집값 상승분이 수익."),
        "warning": "⚠ 부동산 레버리지 위험: ① 금리 상승 시 이자 급증 ② 집값 하락 시 손실이 자기자본 대비 크게 확대 "
                   "③ 전세는 역전세(전세가 하락 시 차액 반환)·세입자 미확보 위험 ④ 월세는 공실 위험 ⑤ 취득세·중개비·양도세 등 세금 별도. "
                   "실제 투자 전 반드시 전문가 상담과 지역·물건 분석이 필요합니다.",
    }


# --- 부동산 대출 종류·한도 (구입자금·전세자금·정책) -------------------------
def _dsr_limit(annual_income: float, rate_pct: float, years: int = 30, dsr: float = 0.40) -> float:
    """DSR 40% 기준 최대 대출원금(원리금균등, years년). 소득 없으면 0."""
    if annual_income <= 0:
        return 0.0
    monthly_cap = annual_income * dsr / 12.0
    r = rate_pct / 100.0 / 12.0
    n = years * 12
    if r > 0:
        return monthly_cap * ((1 + r) ** n - 1) / (r * (1 + r) ** n)
    return monthly_cap * n


def realty_loans(price: float, annual_income: float, age: float, married: bool,
                 homeless: bool, has_child: bool, deposit: float, mode: str) -> dict:
    """매매가·소득·자격으로 받을 수 있는 부동산 대출 종류와 한도(LTV·DSR·정책 상한)를 정리."""
    price = _n(price); inc = _n(annual_income); age = _n(age); deposit = _n(deposit)
    married = bool(married); homeless = bool(homeless); has_child = bool(has_child)
    jeonse = (mode == "jeonse")

    loans = []

    def add(name, kind, rate, cap, eligible, cond, note, limit=None):
        # limit 미지정 시 cap과 DSR 중 작은 값(정책 저리는 DSR 완화되나 보수적으로 표기)
        lim = cap if limit is None else limit
        loans.append({
            "name": name, "kind": kind, "rate": rate,
            "limit": round(max(0, lim)) if lim is not None else None,
            "eligible": bool(eligible), "cond": cond, "note": note,
        })

    # --- 구입자금(주택담보) : 매입/월세임대 시 ---
    ltv = 0.70  # 무주택 서민 기준(비규제 가정). 규제지역·다주택은 축소
    dsr_gen = _dsr_limit(inc, 4.5)
    ltv_amt = price * ltv
    gen_limit = min(ltv_amt, dsr_gen) if inc > 0 else ltv_amt
    add("주택담보대출(일반)", "구입", 4.5, ltv_amt,
        not jeonse and price > 0,
        f"무주택 LTV {int(ltv*100)}% 가정(규제지역·다주택 축소) · DSR 40%",
        f"LTV 한도 {round(ltv_amt):,}원" + (f", DSR 한도 {round(dsr_gen):,}원 중 작은 값" if inc > 0 else " (소득 입력 시 DSR 반영)"),
        limit=gen_limit)

    # 디딤돌(내집마련) — 저리 정책
    ddd_cap = 400_000_000 if married else 250_000_000
    ddd_inc_ok = inc <= (85_000_000 if married else 60_000_000)
    add("디딤돌 대출(구입)", "정책·구입", 3.3, ddd_cap,
        not jeonse and homeless and ddd_inc_ok and price <= 500_000_000,
        f"무주택 · 부부합산소득 {'8,500' if married else '6,000'}만↓ · 주택 5억↓",
        f"최대 {'4억(신혼)' if married else '2.5억'} · 연 2~3%대 저리")

    # 보금자리론
    add("보금자리론", "정책·구입", 4.0, 360_000_000,
        not jeonse and inc <= (85_000_000 if married else 70_000_000) and price <= 600_000_000,
        f"소득 {'8,500' if married else '7,000'}만↓ · 주택 6억↓",
        "최대 3.6억 · 고정금리")

    # 신생아 특례 디딤돌
    add("신생아 특례 디딤돌", "정책·구입", 2.5, 500_000_000,
        not jeonse and has_child and inc <= 200_000_000 and price <= 900_000_000,
        "2년내 출산·입양 · 부부합산 2억↓ · 주택 9억↓",
        "최대 5억 · 최저 연 1.6~3.3% 특례")

    # --- 전세자금 : 전세/갭투자 맥락 ---
    jeonse_amt = deposit * 0.8 if deposit > 0 else 0
    add("전세자금대출(일반)", "전세", 4.0, 400_000_000,
        deposit > 0,
        "전세보증금의 최대 80% (HUG/서울보증 보증)",
        f"보증금 {round(deposit):,}원의 80% ≈ {round(jeonse_amt):,}원" if deposit > 0 else "보증금 입력 시 한도 계산",
        limit=min(400_000_000, jeonse_amt) if deposit > 0 else 400_000_000)

    add("청년 버팀목 전세대출", "정책·전세", 2.2, 200_000_000,
        19 <= age <= 34 and homeless,
        "만19~34 · 무주택 · 보증금 3억↓ · 소득요건",
        "최대 2억 · 초저금리")

    add("신혼부부 버팀목 전세", "정책·전세", 2.4, 300_000_000,
        married and homeless,
        "신혼 · 무주택 · 보증금 수도권 4억↓ · 소득요건",
        "최대 3억(수도권) · 저금리")

    eligible = [x for x in loans if x["eligible"]]
    best = max((x["limit"] or 0 for x in eligible), default=0)
    return {
        "price": round(price), "annual_income": round(inc), "mode": "전세 갭투자" if jeonse else "월세/매입",
        "ltv_pct": int(ltv * 100),
        "loans": loans,
        "eligible_count": len(eligible),
        "max_limit": best,
        "dsr_note": (f"연소득 {round(inc):,}원 기준 DSR 40%면 연 원리금 {round(inc*0.4):,}원까지 "
                     f"(30년·4.5% 가정 시 약 {round(_dsr_limit(inc,4.5)):,}원 대출 여력)." if inc > 0
                     else "연소득을 입력하면 DSR 40% 기준 대출 여력을 계산합니다."),
        "note": "한도·금리·소득요건은 2026 참고 가정치입니다. LTV는 무주택 서민·비규제지역 70% 가정이며 규제지역·다주택·주택가격대별로 달라집니다. "
                "DSR(총부채원리금상환비율)은 모든 대출 합산 40%가 규제 상한입니다. 갭투자(전세 낀 매입)는 세입자 보증금이 선순위라 담보대출 한도가 크게 제한됩니다. "
                "정확한 한도는 은행·주택도시기금에서 확인하세요.",
    }


# --- 배당주·공모주로 소득 만들기 (가이드 + 계산기) -------------------------
_DIV_TAX = 0.154  # 배당소득세 15.4% (2천만 초과분은 금융소득종합과세 별도)


def dividend_plan(invest: float, yield_pct: float, years: int,
                  growth_pct: float, reinvest: bool) -> dict:
    """배당주 소득: 투자금 → 연/월 배당(세후), 배당성장·재투자 시 N년 경로 + 목표 월소득에 필요한 투자금."""
    invest = max(0.0, _n(invest)); y0 = _n(yield_pct); years = max(1, min(40, int(_n(years, 10)) or 10))
    g = _n(growth_pct) / 100.0
    gross = invest * y0 / 100.0
    net = gross * (1 - _DIV_TAX)

    bal = invest
    cum_net = 0.0
    rows = []
    for yr in range(1, years + 1):
        eff_yield = (y0 / 100.0) * ((1 + g) ** (yr - 1))   # 배당 성장 반영(원가 대비 수익률↑)
        div = bal * eff_yield
        ndiv = div * (1 - _DIV_TAX)
        cum_net += ndiv
        if reinvest:
            bal += ndiv                                     # 세후 배당 재투자(주가는 보합 가정, 보수적)
        rows.append({"year": yr, "dividend_net": round(ndiv), "cum_net": round(cum_net), "value": round(bal)})

    # 목표 월소득에 필요한 투자금 (세후 기준)
    def need_for(mon: float) -> float:
        denom = (y0 / 100.0) * (1 - _DIV_TAX)
        return round(mon * 12 / denom) if denom > 0 else 0
    targets = [{"monthly": m, "invest": need_for(m)} for m in (300_000, 500_000, 1_000_000, 2_000_000)]

    return {
        "invest": round(invest), "yield_pct": y0, "years": years,
        "growth_pct": _n(growth_pct), "reinvest": bool(reinvest), "tax_pct": round(_DIV_TAX * 100, 1),
        "annual_gross": round(gross), "annual_net": round(net), "monthly_net": round(net / 12),
        "final_value": round(bal), "total_dividends_net": round(cum_net),
        "yearly": rows, "targets": targets,
        "examples": [
            {"name": "고배당 리츠·인프라", "yield": "5~7%", "note": "맥쿼리인프라·리츠 등, 분배금 정기 지급"},
            {"name": "은행·통신·정유 등 전통 배당주", "yield": "4~6%", "note": "KB·신한·SK텔레콤·기아 등(참고)"},
            {"name": "월배당 ETF", "yield": "3~7%", "note": "커버드콜·미국배당 ETF, 매월 분배"},
            {"name": "배당성장주", "yield": "1~3% + 성장", "note": "배당이 매년 늘어 원가 대비 수익률 상승"},
        ],
        "guide": [
            "① 배당주는 '주가 차익'이 아니라 보유만 해도 나오는 '현금흐름'으로 소득을 만듭니다.",
            "② 배당수익률 = 연 배당금 ÷ 주가. 4~6%가 흔하고, 리츠·커버드콜 ETF는 더 높지만 주가 변동·분배 삭감 위험이 있습니다.",
            "③ 배당소득세 15.4%가 원천징수됩니다. 연 금융소득 2,000만원 초과 시 종합과세되니 ISA·연금계좌 활용이 유리합니다.",
            "④ '배당락' 기준일(보통 분기·연말) 전에 보유해야 그 회차 배당을 받습니다.",
            "⑤ 초기엔 세후 배당을 재투자하면 복리로 배당이 늘어납니다(위 계산의 재투자 옵션).",
            "⑥ 배당은 실적에 따라 줄 수도 있으니, 배당성향·이익 안정성·연속 배당 이력을 확인하세요(앱의 배당·실적 탭 활용).",
        ],
        "note": "배당수익률·성장률은 가정치입니다. 재투자 계산은 주가 보합을 가정한 보수적 값이며 실제 주가 등락에 따라 달라집니다. 세금은 15.4% 단순 적용.",
    }


def ipo_plan(offer_price: float, alloc_shares: float, subscribe_amount: float) -> dict:
    """공모주(IPO) 소득: 배정 주수·공모가 → 상장일 상승률별 수익 시나리오 + 청약 방법 가이드."""
    op = max(0.0, _n(offer_price)); shares = max(0.0, _n(alloc_shares)); sub = max(0.0, _n(subscribe_amount))
    cost = op * shares

    def at(gain_pct: float) -> dict:
        sell = op * (1 + gain_pct / 100.0)
        profit = (sell - op) * shares
        return {"gain_pct": gain_pct, "sell_price": round(sell), "profit": round(profit),
                "roi_on_cost": round(profit / cost * 100, 1) if cost > 0 else None}

    scen = [at(0), at(30), at(60), at(100), at(160)]  # 공모가·+30·+60·따블·따상 근접
    margin = round(sub * 0.5)  # 청약 증거금 통상 50%

    return {
        "offer_price": round(op), "alloc_shares": round(shares), "cost": round(cost),
        "subscribe_amount": round(sub), "margin_estimate": margin,
        "scenarios": scen,
        "guide": [
            "① 공모주는 상장 전 '공모가'로 주식을 배정받아, 상장 첫날 오른 가격에 팔아 차익을 노리는 방법입니다.",
            "② 증권사 계좌에서 '청약'합니다. 청약 증거금은 보통 청약금액의 50%가 필요하고, 배정 후 나머지는 환불됩니다.",
            "③ 배정 방식: 균등배정(최소 청약하면 누구나 비슷하게 나눠 받음) + 비례배정(많이 청약할수록 더 받음). 소액이면 여러 증권사에 균등 청약이 유리.",
            "④ 인기 공모주는 경쟁률이 높아 배정 주수가 매우 적습니다(수 주~수십 주). '따상'(시초가 2배+상한가)은 드무니 기대 수익을 보수적으로 잡으세요.",
            "⑤ 상장일 시초가·초반 변동성이 큽니다. 목표 수익률을 정해 분할 매도하는 전략이 안전합니다.",
            "⑥ 기관 수요예측 경쟁률·의무보유확약 비율·공모가 밴드 상·하단 여부를 확인하면 흥행 여부를 가늠할 수 있습니다.",
            "⑦ 상장 차익은 소액주주는 양도세가 없지만(증권거래세만), 손실 위험도 있으니 여유자금으로 접근하세요.",
        ],
        "note": "배정 주수는 경쟁률에 따라 결정되어 예측이 어렵습니다. 위 계산은 '배정받았다고 가정한' 주수 기준 시나리오입니다. 따상은 보장되지 않습니다.",
    }


# --- 내 저축·상품(보유) → 혜택 + N년 뒤 예상 -------------------------------
# 상품별 예상 연수익률(rate) + 정부매칭/세제혜택(bonus). bonus_rate = 연 납입액 대비
# 지원 비율, bonus_cap = 연 지원 상한(원, 0이면 상한 없음). 참고값(2026 기준).
_HOLDING_META: dict[str, dict] = {
    "청년미래적금":              {"rate": 0.035, "bonus_rate": 0.09,  "bonus_cap": 1_080_000, "note": "정부매칭 6~12% + 이자 비과세"},
    "청년내일저축계좌":          {"rate": 0.030, "bonus_rate": 2.00,  "bonus_cap": 3_600_000, "note": "저소득 청년 정부매칭 최대 3배"},
    "청년 주택드림 청약통장":    {"rate": 0.040, "bonus_rate": 0.0,   "bonus_cap": 0,          "note": "우대금리 + 비과세 + 청약가점"},
    "주택청약종합저축":          {"rate": 0.025, "bonus_rate": 0.0,   "bonus_cap": 0,          "note": "청약 자격 + 소득공제"},
    "연금저축":                  {"rate": 0.050, "bonus_rate": 0.165, "bonus_cap": 990_000,    "note": "연 최대 99만원 세액공제 환급"},
    "IRP(개인형퇴직연금)":       {"rate": 0.050, "bonus_rate": 0.165, "bonus_cap": 1_485_000,  "note": "연금 합산 최대 148.5만 환급"},
    "ISA(개인종합자산관리계좌)": {"rate": 0.050, "bonus_rate": 0.0,   "bonus_cap": 0,          "note": "수익 200/400만 비과세"},
    "정기적금·예금":             {"rate": 0.035, "bonus_rate": 0.0,   "bonus_cap": 0,          "note": "원금 보장 안전 저축"},
    "주식·ETF 투자":             {"rate": 0.080, "bonus_rate": 0.0,   "bonus_cap": 0,          "note": "장기 복리(원금 손실 위험)"},
    "리츠(REITs)·부동산펀드":    {"rate": 0.050, "bonus_rate": 0.0,   "bonus_cap": 0,          "note": "배당 연 4~7%"},
    "배당주·채권·금/달러 ETF":   {"rate": 0.060, "bonus_rate": 0.0,   "bonus_cap": 0,          "note": "분산 투자·현금흐름"},
}
_DEFAULT_META = {"rate": 0.035, "bonus_rate": 0.0, "bonus_cap": 0, "note": "일반 저축"}


def holdings_catalog() -> list[dict]:
    """가입해서 저축 중이라고 고를 수 있는 상품 목록(혜택·예상수익률 포함)."""
    info = {it["name"]: it for it in _products({})}
    out = []
    for name, meta in _HOLDING_META.items():
        it = info.get(name, {})
        out.append({
            "name": name,
            "category": it.get("category", "저축"),
            "benefit": it.get("benefit", ""),
            "example": it.get("example", ""),
            "rate": round(meta["rate"] * 100, 1),
            "bonus_note": meta["note"],
            "has_bonus": meta["bonus_rate"] > 0,
        })
    return out


def _project_one(h: dict, horizon: int) -> dict:
    name = h.get("name", "저축")
    meta = _HOLDING_META.get(name, _DEFAULT_META)
    monthly = max(0.0, _n(h.get("monthly")))
    current = max(0.0, _n(h.get("current")))
    rate = meta["rate"]
    rm = rate / 12.0
    annual_contrib = monthly * 12.0
    annual_bonus = annual_contrib * meta["bonus_rate"]
    if meta["bonus_cap"] > 0:
        annual_bonus = min(annual_bonus, meta["bonus_cap"])

    bal = current
    bonus_total = 0.0
    yearly = []
    for y in range(1, horizon + 1):
        for _ in range(12):
            bal = bal * (1 + rm) + monthly
        bonus_total += annual_bonus
        yearly.append({"year": y, "total": round(bal + bonus_total)})

    principal = current + annual_contrib * horizon        # 낸 돈(원금)
    invest_only = round(bal)                               # 투자성장분 포함(혜택 제외)
    total = round(bal + bonus_total)
    return {
        "name": name,
        "category": meta.get("category", h.get("category", "저축")),
        "monthly": round(monthly),
        "current": round(current),
        "rate": round(rate * 100, 1),
        "bonus_note": meta["note"],
        "principal": round(principal),
        "invest_value": invest_only,
        "bonus_total": round(bonus_total),
        "total": total,
        "gain": round(total - principal),
        "yearly": yearly,
    }


def project_holdings(holdings: list[dict], horizon: int) -> dict:
    horizon = max(1, min(40, int(_n(horizon, 10)) or 10))
    items = [_project_one(h, horizon) for h in (holdings or []) if _n(h.get("monthly")) > 0 or _n(h.get("current")) > 0]

    # 연도별 합계 경로
    totals_by_year = []
    for y in range(1, horizon + 1):
        s = sum(next((r["total"] for r in it["yearly"] if r["year"] == y), 0) for it in items)
        totals_by_year.append({"year": y, "total": round(s)})

    principal = sum(it["principal"] for it in items)
    bonus_total = sum(it["bonus_total"] for it in items)
    grand_total = sum(it["total"] for it in items)
    monthly_sum = sum(it["monthly"] for it in items)
    return {
        "horizon": horizon,
        "items": items,
        "totals_by_year": totals_by_year,
        "summary": {
            "monthly_sum": round(monthly_sum),
            "principal": round(principal),          # 낸 돈
            "bonus_total": round(bonus_total),      # 정부지원·세제혜택 합
            "gain": round(grand_total - principal), # 불어난 돈(혜택+수익)
            "total": round(grand_total),            # N년 뒤 총액
        },
        "note": "예상수익률·정부지원은 2026 기준 참고 가정치입니다. 세제혜택(연금/IRP)은 환급액을 매년 현금으로 더한 보수적 계산이며, "
                "실제 수령액은 상품·소득·시장에 따라 달라집니다.",
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


def get_holdings(user: str) -> dict:
    d = _load(user)
    holdings = d.get("holdings", [])
    horizon = int(_n(d.get("holdings_horizon"), 10)) or 10
    return {
        "holdings": holdings,
        "horizon": horizon,
        "catalog": holdings_catalog(),
        "projection": project_holdings(holdings, horizon),
    }


def save_holdings(user: str, holdings: list[dict], horizon: int) -> dict:
    with _lock:
        d = _load(user)
        clean = []
        for h in (holdings or []):
            nm = str(h.get("name", "")).strip()
            if not nm:
                continue
            clean.append({"name": nm, "monthly": _n(h.get("monthly")), "current": _n(h.get("current"))})
        d["holdings"] = clean
        d["holdings_horizon"] = max(1, min(40, int(_n(horizon, 10)) or 10))
        _save(user, d)
    return get_holdings(user)
