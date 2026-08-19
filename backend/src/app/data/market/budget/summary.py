"""집계 — 한 달치 지출을 네 축으로 쪼개고, 할부의 미래 부담까지 내다본다.

네 축(카테고리 · 카드 · 거래구분 · 고정비/변동비)은 같은 거래를 다르게 자른
것이라 합계가 모두 같아야 한다. 그래서 분모를 한 곳(``net_spent``)에서만 만든다.

**기준 달.** 기본은 청구월(``billing_month``)이다 — 7월에 긁어도 9월에 빠지는 돈이면
9월 가계부다. 거래 시점으로 보고 싶으면 ``basis="date"`` 로 바꾼다. 예전에 넣어둔
거래는 청구월을 알 수 없어 거래월이 그대로 들어가 있다.

**할부.** 이번 달 청구분만 지출로 잡으므로, 남은 회차는 '아직 안 나갔지만 이미
확정된 지출'이다. 이걸 안 보여주면 저축 가능액이 실제보다 낙관적으로 보인다.
"""
from __future__ import annotations

from . import categories as C
from .cards import model as M
from .store import load


def _month_of(t: dict, basis: str) -> str:
    if basis == "date":
        return str(t.get("date", ""))[:7]
    return str(t.get("billing_month") or t.get("date", ""))[:7]


def _add_months(month: str, n: int) -> str:
    try:
        y, m = (int(x) for x in month.split("-")[:2])
    except (ValueError, IndexError):
        return ""
    total = y * 12 + (m - 1) + n
    return f"{total // 12}-{total % 12 + 1:02d}"


def months_of(txs: list[dict], basis: str = "billing_month") -> list[str]:
    return sorted({_month_of(t, basis) for t in txs if _month_of(t, basis)}, reverse=True)


def _bucket(rows: list[tuple[str, float]], denom: float) -> list[dict]:
    agg: dict[str, list] = {}
    for key, amt in rows:
        cur = agg.setdefault(key, [0.0, 0])
        cur[0] += amt
        cur[1] += 1
    out = [{"key": k, "amount": round(v[0]), "count": v[1],
            "pct": round(v[0] / denom * 100, 1) if denom else 0.0}
           for k, v in agg.items()]
    return sorted(out, key=lambda x: -x["amount"])


ALL = "all"     # 월 선택에서 '전체 기간'


def summary(user: str, month: str | None = None, basis: str = "billing_month") -> dict:
    d = load(user)
    txs = d["transactions"]
    basis = "date" if basis == "date" else "billing_month"
    months = months_of(txs, basis)
    if not month:
        month = months[0] if months else ""

    recurring = C.recurring_keys(txs)
    fixed_rules = d.get("fixed_rules", {})
    # 카드사마다 결제일이 달라 청구월이 갈린다(신한 9월 · 삼성 8월). 최신 달만 보면
    # 다른 달에 있는 카드가 '안 들어간 것처럼' 보이므로 전체 기간을 볼 수 있어야 한다.
    mtx = list(txs) if month == ALL else [t for t in txs if _month_of(t, basis) == month]
    for t in mtx:
        t["fixed"] = C.is_fixed(t, recurring, fixed_rules)

    spent = sum(t["amount"] for t in mtx if t["amount"] > 0)
    refund = sum(-t["amount"] for t in mtx if t["amount"] < 0)
    net_spent = spent - refund
    pos = [t for t in mtx if t["amount"] > 0]

    by_category = [{"category": b["key"], **b}
                   for b in _bucket([(t["category"], t["amount"]) for t in pos], spent)]
    by_card = [{"card": b["key"] or "미상", **b}
               for b in _bucket([(f'{t["issuer"]} {t["card"]}'.strip() or "미상", t["amount"])
                                 for t in pos], spent)]
    by_tx_type = [{"tx_type": b["key"], **b}
                  for b in _bucket([(t["tx_type"] or M.ETC, t["amount"]) for t in mtx], spent)]

    fixed_amt = sum(t["amount"] for t in pos if t["fixed"])
    var_amt = spent - fixed_amt
    fixed_items = _bucket([(t["merchant"], t["amount"]) for t in pos if t["fixed"]], spent)

    inst = installments(user)
    upcoming = inst["schedule"]

    inc = d["income"]
    income_total = (inc.get("monthly_net") or 0) + (inc.get("extra") or 0)
    savings_possible = income_total - net_spent

    return {
        "month": month,
        "months": months,
        "basis": basis,
        "income": inc,
        "income_total": round(income_total),
        "spent": round(net_spent),
        "refund": round(refund),
        "savings_possible": round(savings_possible),
        "savings_rate": round(savings_possible / income_total * 100, 1) if income_total else None,
        # --- 분리 축 4개 (합계는 모두 spent 와 같다) ---
        "by_category": by_category,
        "by_card": by_card,
        "by_tx_type": by_tx_type,
        "by_fixed": {
            "fixed": round(fixed_amt),
            "variable": round(var_amt),
            "fixed_pct": round(fixed_amt / spent * 100, 1) if spent else 0.0,
            "items": fixed_items[:20],
        },
        # --- 참고 목록 ---
        "categories": C.CATEGORIES,
        "tx_types": M.TX_TYPES,
        "cards": sorted({f'{t["issuer"]} {t["card"]}'.strip() for t in txs
                         if (t.get("card") or t.get("issuer"))}),
        "issuers": sorted({t["issuer"] for t in txs if t.get("issuer")}),
        "installments": {k: v for k, v in inst.items() if k != "schedule"},
        "upcoming": upcoming[:6],
        "count": len(mtx),
        "transactions": sorted(mtx, key=lambda t: (str(t.get("date", "")), t.get("id", 0)),
                               reverse=True),
        "imports": d.get("imports", [])[:5],
    }


# --- 할부 -------------------------------------------------------------------
def installments(user: str) -> dict:
    """남아 있는 할부와, 그게 앞으로 몇 달 얼마씩 빠지는지.

    같은 할부가 달마다 한 줄씩 들어오므로 (카드·가맹점·총액) 으로 묶어 **가장 최근
    회차**만 남긴다. 남은 회차는 ``이용개월 − 청구회차``, 월 원금은 ``잔액 ÷ 남은 회차``.

    수수료는 잔액에 붙어 회차마다 줄어든다. 정확한 값은 카드사만 알기 때문에
    원금만 확정으로 잡고 마지막 회차 수수료를 상한으로 함께 준다(화면에서 '+수수료'로 표시).
    """
    d = load(user)
    active: dict[tuple, dict] = {}
    for t in d["transactions"]:
        inst = t.get("installment")
        if not inst or t.get("tx_type") != M.INSTALLMENT:
            continue
        months, seq = int(inst.get("months") or 0), int(inst.get("seq") or 0)
        if months <= 1:
            continue
        key = (t.get("card", ""), t.get("merchant", ""), round(float(t.get("total") or 0)))
        cur = active.get(key)
        if cur is None or seq > cur["seq"]:
            active[key] = {
                "card": f'{t.get("issuer", "")} {t.get("card", "")}'.strip(),
                "merchant": t.get("merchant", ""),
                "category": t.get("category", "기타"),
                "total": round(float(t.get("total") or 0)),
                "months": months,
                "seq": seq,
                "remaining": round(float(inst.get("remaining") or 0)),
                "last_fee": round(float(t.get("fee") or 0)),
                "billing_month": t.get("billing_month", ""),
            }

    items, schedule_map = [], {}
    for it in active.values():
        left = max(0, it["months"] - it["seq"])
        it["months_left"] = left
        it["monthly_principal"] = round(it["remaining"] / left) if left else 0
        if left <= 0 or it["remaining"] <= 0:
            continue
        items.append(it)
        for k in range(1, left + 1):
            m = _add_months(it["billing_month"], k)
            if not m:
                continue
            row = schedule_map.setdefault(m, {"month": m, "principal": 0, "items": []})
            row["principal"] += it["monthly_principal"]
            row["items"].append({"merchant": it["merchant"], "card": it["card"],
                                 "amount": it["monthly_principal"],
                                 "seq": it["seq"] + k, "months": it["months"]})

    items.sort(key=lambda x: -x["remaining"])
    schedule = [{**v, "principal": round(v["principal"])}
                for v in sorted(schedule_map.values(), key=lambda x: x["month"])]
    return {
        "items": items,
        "count": len(items),
        "remaining_total": round(sum(i["remaining"] for i in items)),
        "next_month": schedule[0]["principal"] if schedule else 0,
        "fee_note": "월 금액은 원금 기준입니다. 수수료는 잔액에 붙어 회차마다 줄어듭니다.",
        "schedule": schedule,
    }


# --- 저축·투자 계획 ---------------------------------------------------------
def plan(user: str, emergency_months: int = 3, invest_ratio: float = 0.5) -> dict:
    """최근 월평균 지출과 수입 여유로 비상금·저축·투자를 배분한다.

    고정비는 줄이기 어렵고 할부 잔액은 이미 확정된 지출이라, 둘을 따로 떼어
    '실제로 손댈 수 있는 여유'가 얼마인지 보여준다.
    """
    d = load(user)
    txs = d["transactions"]
    months = months_of(txs)
    recent = months[:3]

    recurring = C.recurring_keys(txs)
    fixed_rules = d.get("fixed_rules", {})
    per_month, fixed_per_month = [], []
    for m in recent:
        rows = [t for t in txs if _month_of(t, "billing_month") == m and t["amount"] > 0]
        per_month.append(sum(t["amount"] for t in rows))
        fixed_per_month.append(sum(t["amount"] for t in rows
                                   if C.is_fixed(t, recurring, fixed_rules)))
    avg_spend = round(sum(per_month) / len(per_month)) if per_month else 0
    avg_fixed = round(sum(fixed_per_month) / len(fixed_per_month)) if fixed_per_month else 0
    avg_var = avg_spend - avg_fixed

    inc = d["income"]
    income_total = round((inc.get("monthly_net") or 0) + (inc.get("extra") or 0))
    surplus = income_total - avg_spend

    inst = installments(user)
    inst_next = inst["next_month"]

    stock_value = 0
    try:
        from app.data.market import watchlist
        stock_value = watchlist.diagnose(user).get("summary", {}).get("total_value", 0) or 0
    except Exception:
        stock_value = 0

    emergency_target = avg_spend * emergency_months
    monthly_invest = round(max(0, surplus) * invest_ratio)
    monthly_save = round(max(0, surplus) - monthly_invest)

    steps: list[str] = []
    if income_total <= 0:
        steps.append("먼저 월 급여(실수령액)를 입력하면 저축·투자 계획을 계산합니다.")
    elif surplus <= 0:
        steps.append(f"현재 월 지출(평균 {avg_spend:,}원)이 수입({income_total:,}원)과 비슷하거나 많습니다. "
                     f"고정비 {avg_fixed:,}원은 손대기 어려우니 변동비 {avg_var:,}원부터 줄이세요.")
    else:
        steps.append(f"매월 여유자금은 약 {surplus:,}원입니다(수입 {income_total:,} − 평균지출 {avg_spend:,}).")
        steps.append(f"이 중 고정비가 {avg_fixed:,}원(지출의 "
                     f"{round(avg_fixed / avg_spend * 100) if avg_spend else 0}%)이라 "
                     f"실제로 조절 가능한 건 변동비 {avg_var:,}원입니다.")
        steps.append(f"1순위 비상금: 생활비 {emergency_months}개월치({emergency_target:,}원)를 예적금으로 먼저 확보하세요.")
        steps.append(f"이후 매월 여유자금을 저축 {monthly_save:,}원 / 투자(주식 등) {monthly_invest:,}원으로 배분하는 것을 제안합니다.")
        if stock_value:
            steps.append(f"이미 주식 포트폴리오 {round(stock_value):,}원을 투자 자산으로 보유 중입니다(투자 배분의 일부).")
    if inst["remaining_total"] > 0:
        steps.append(f"할부 잔액 {inst['remaining_total']:,}원이 남아 다음 달 {inst_next:,}원(+수수료)이 "
                     "이미 확정 지출입니다. 여유자금에서 먼저 빼고 계획하세요.")

    return {
        "income_total": income_total,
        "avg_spend": avg_spend,
        "avg_fixed": avg_fixed,
        "avg_variable": avg_var,
        "surplus": surplus,
        "surplus_after_installment": surplus - inst_next,
        "savings_rate": round(surplus / income_total * 100, 1) if income_total else None,
        "emergency_months": emergency_months,
        "emergency_target": round(emergency_target),
        "invest_ratio": invest_ratio,
        "monthly_save": monthly_save,
        "monthly_invest": monthly_invest,
        "stock_value": round(stock_value),
        "installment_remaining": inst["remaining_total"],
        "installment_next_month": inst_next,
        "allocation": [
            {"name": "안전저축(예적금)", "monthly": monthly_save},
            {"name": "투자(주식 등)", "monthly": monthly_invest},
        ],
        "steps": steps,
        "note": "월평균 지출·수입 기반 참고 계획입니다. 비상금 개월수·투자비중은 조절할 수 있습니다.",
    }


def state(user: str) -> dict:
    d = load(user)
    return {"income": d["income"], "months": months_of(d["transactions"]),
            "count": len(d["transactions"])}
