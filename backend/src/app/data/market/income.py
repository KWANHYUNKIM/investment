"""소득·성장 — 상세 급여 · 인상 시뮬 · 부업 소득 · 투자 수익 종합.

계정별(income_<user>.json)로 저장한다:
  - salary: 지급 항목별(기본급·수당·상여) + 공제 항목별(4대보험·세금) 상세, 월 기준.
    저장할 때 실수령액이 바뀌면 history 에 스냅샷을 남겨 '급여 인상'을 추적한다.
  - side: 부업 소득 내역([{id, date, source, amount, memo}]).
주식 수익(평가손익)은 watchlist.diagnose(user) 에서 실시간으로 끌어온다.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time

from app.core.config import get_settings

_lock = threading.Lock()


def _safe_user(user: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.\-]", "_", user or "default")


def _path(user: str) -> str:
    return str(get_settings().data_dir / f"income_{_safe_user(user)}.json")


def _empty() -> dict:
    return {"salary": None, "salary_history": [], "side": [], "seq": 0}


def _load(user: str) -> dict:
    p = _path(user)
    if not os.path.exists(p):
        return _empty()
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        for k, v in _empty().items():
            d.setdefault(k, v)
        return d
    except Exception:
        return _empty()


def _save(user: str, d: dict) -> None:
    p = _path(user)
    tmp = f"{p}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, p)


def _sum(items) -> float:
    s = 0.0
    for it in items or []:
        try:
            s += float(it.get("amount") or 0)
        except (TypeError, ValueError):
            pass
    return s


def _today() -> str:
    return time.strftime("%Y-%m-%d")


# --- 급여 상세 -------------------------------------------------------------
def _compute_salary(sal: dict | None) -> dict | None:
    if not sal:
        return None
    gross = _sum(sal.get("earnings"))
    deduct = _sum(sal.get("deductions"))
    net = gross - deduct
    return {
        "earnings": sal.get("earnings", []),
        "deductions": sal.get("deductions", []),
        "memo": sal.get("memo", ""),
        "gross": round(gross),
        "deduction": round(deduct),
        "net": round(net),
        "annual_net": round(net * 12),
        "annual_gross": round(gross * 12),
        "updated": sal.get("updated"),
    }


def set_salary(user: str, earnings: list[dict], deductions: list[dict], memo: str = "") -> dict:
    """지급/공제 항목별 급여 저장. 실수령액이 바뀌면 history 스냅샷 추가."""
    def clean(items):
        out = []
        for it in items or []:
            label = str(it.get("label", "")).strip()
            try:
                amt = float(str(it.get("amount", 0)).replace(",", ""))
            except (TypeError, ValueError):
                continue
            if label or amt:
                out.append({"label": label or "항목", "amount": amt})
        return out

    with _lock:
        d = _load(user)
        sal = {"earnings": clean(earnings), "deductions": clean(deductions),
               "memo": memo or "", "updated": _today()}
        computed = _compute_salary(sal)
        hist = d.get("salary_history", [])
        if not hist or hist[-1].get("net") != computed["net"]:
            hist.append({"date": _today(), "gross": computed["gross"],
                         "net": computed["net"], "annual_net": computed["annual_net"]})
        d["salary"] = sal
        d["salary_history"] = hist
        _save(user, d)
    return computed


def get_salary(user: str) -> dict:
    d = _load(user)
    return {"salary": _compute_salary(d.get("salary")), "history": d.get("salary_history", [])}


# --- 급여 인상 시뮬레이션 --------------------------------------------------
def raise_sim(user: str, raise_pct: float = 0, raise_amount: float = 0,
              years: int = 5, invest_ratio: float = 0.5, annual_return: float = 6.0) -> dict:
    """현재 실수령(월) 기준 인상 시나리오 + 인상분 투자 시 복리 미래가치.

    raise_pct(%) 또는 raise_amount(월 증가액) 중 주어진 것으로 새 실수령을 만든다.
    인상분의 invest_ratio 를 매월 연 annual_return% 로 years 년 적립투자한다고 가정.
    """
    d = _load(user)
    cur = _compute_salary(d.get("salary"))
    base = cur["net"] if cur else 0
    if raise_amount and raise_amount > 0:
        new_net = base + raise_amount
    else:
        new_net = round(base * (1 + (raise_pct or 0) / 100.0))
    monthly_inc = round(new_net - base)
    annual_inc = monthly_inc * 12

    # 인상분 중 투자분을 매월 적립(연 annual_return% 복리) → years년 후 미래가치
    invest_month = monthly_inc * max(0.0, min(1.0, invest_ratio))
    r = (annual_return or 0) / 100.0 / 12.0
    n = max(0, int(years)) * 12
    if r > 0 and n > 0:
        fv = invest_month * ((1 + r) ** n - 1) / r
    else:
        fv = invest_month * n
    contributed = invest_month * n

    return {
        "base_net": base,
        "new_net": new_net,
        "monthly_increase": monthly_inc,
        "annual_increase": annual_inc,
        "years": int(years),
        "invest_ratio": invest_ratio,
        "annual_return": annual_return,
        "invest_monthly": round(invest_month),
        "contributed": round(contributed),
        "future_value": round(fv),
        "investment_gain": round(fv - contributed),
        "note": "인상분의 일부를 매월 적립투자했을 때의 추정 복리 결과입니다(세전·참고용).",
    }


# --- 부업 소득 -------------------------------------------------------------
def add_side(user: str, items: list[dict]) -> dict:
    with _lock:
        d = _load(user)
        seq = d.get("seq", 0)
        for it in items or []:
            try:
                amt = float(str(it.get("amount", 0)).replace(",", ""))
            except (TypeError, ValueError):
                continue
            seq += 1
            d["side"].append({
                "id": seq,
                "date": str(it.get("date") or _today())[:10],
                "source": str(it.get("source", "")).strip() or "부업",
                "amount": amt,
                "memo": str(it.get("memo", "")).strip(),
            })
        d["seq"] = seq
        _save(user, d)
    return {"added": len(items or [])}


def delete_side(user: str, sid: int) -> dict:
    with _lock:
        d = _load(user)
        d["side"] = [s for s in d["side"] if s.get("id") != sid]
        _save(user, d)
    return {"ok": True}


def list_side(user: str, month: str | None = None) -> dict:
    d = _load(user)
    side = d["side"]
    months = sorted({str(s.get("date", ""))[:7] for s in side if s.get("date")}, reverse=True)
    rows = [s for s in side if (not month or str(s.get("date", "")).startswith(month))]
    total_all = round(_sum(side))
    by_source: dict[str, float] = {}
    for s in side:
        by_source[s["source"]] = by_source.get(s["source"], 0.0) + float(s.get("amount") or 0)
    sources = sorted(({"source": k, "amount": round(v)} for k, v in by_source.items()), key=lambda x: -x["amount"])
    return {
        "month": month,
        "months": months,
        "rows": sorted(rows, key=lambda s: str(s.get("date", "")), reverse=True),
        "month_total": round(_sum(rows)),
        "total": total_all,
        "sources": sources,
    }


# --- 종합 + 조언 -----------------------------------------------------------
def _investment(user: str) -> dict:
    try:
        from app.data.market import watchlist
        s = watchlist.diagnose(user).get("summary", {})
        return {"value": s.get("total_value", 0) or 0, "pnl": s.get("total_pnl", 0) or 0,
                "pnl_pct": s.get("total_pnl_pct")}
    except Exception:
        return {"value": 0, "pnl": 0, "pnl_pct": None}


def _tips(net: int, side_month: int, side_total: int, inv: dict) -> list[str]:
    tips: list[str] = []
    if net <= 0:
        tips.append("먼저 급여 상세를 입력하면 소득 구조에 맞는 제안을 드립니다.")
        return tips
    # 부업
    if side_total <= 0:
        tips.append("부업 소득이 아직 없습니다. 월 30만원 부업이면 연 360만원 추가 소득 — 소액이라도 시작해 기록해보세요.")
    else:
        ratio = side_month / net * 100 if net else 0
        tips.append(f"이번 달 부업 소득은 급여의 {ratio:.0f}% 입니다. 반복 가능한 부업 1~2개로 집중하면 규모가 커집니다.")
    # 투자
    if inv["value"] <= 0:
        tips.append("아직 주식 투자 자산이 없습니다. 급여 인상분·부업 소득의 일부를 꾸준히 투자하면 복리로 불어납니다.")
    elif (inv["pnl"] or 0) < 0:
        tips.append("보유 주식이 평가손실 중입니다. 매매 신호·목표주가를 점검하고 분할·손절 기준을 세우세요.")
    else:
        tips.append(f"주식 평가이익 {round(inv['pnl']):,}원. 수익 실현·재투자 원칙을 정해두면 성장을 이어갈 수 있습니다.")
    # 급여 인상 활용
    tips.append("급여가 오르면 오른 만큼 생활비를 늘리지 말고, 인상분의 절반 이상을 저축·투자로 자동이체해 보세요(‘인상 시뮬’ 참고).")
    return tips


def overview(user: str) -> dict:
    d = _load(user)
    sal = _compute_salary(d.get("salary"))
    net = sal["net"] if sal else 0
    month = time.strftime("%Y-%m")
    side_month = round(_sum([s for s in d["side"] if str(s.get("date", "")).startswith(month)]))
    side_total = round(_sum(d["side"]))
    inv = _investment(user)
    total_month = net + side_month
    return {
        "salary": sal,
        "side": {"this_month": side_month, "total": side_total, "count": len(d["side"])},
        "investment": inv,
        "total_month_income": round(total_month),
        "annual_est": round(net * 12 + side_total),  # 급여 연환산 + 부업 누적
        "tips": _tips(net, side_month, side_total, inv),
    }
