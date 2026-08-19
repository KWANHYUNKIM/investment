"""고정지출 — 계속 결제되는 것만 따로 뽑아낸다.

구독·통신·보험·공과금은 성격이 다르다. 이번 달에 많이 썼다고 다음 달에 줄일 수
있는 돈이 아니라서, 변동비와 같은 자리에 섞어 놓으면 '얼마를 줄일 수 있는가' 라는
질문에 답할 수 없다.

**무엇으로 찾는가.** 세 신호를 함께 쓴다. 하나만으로는 다 놓친다.

1. 반복 + 금액 유사 — 같은 가맹점이 여러 달에 걸쳐 **비슷한 금액**으로 찍힌다.
   가장 확실한 신호지만 최소 두 달치가 쌓여야 한다.
2. 카테고리·키워드 — 통신/공과금/구독, '자동납부'·'멤버십' 같은 말. 한 달치만
   있어도 잡히지만 놓치는 게 있다.
3. 사용자 지정 — 위 둘이 틀렸을 때 못박는다. 항상 우선한다.

**금액 유사를 왜 따지나.** 반복만 보면 자주 가는 마트가 고정비가 된다(선비할인마트
6,796 ~ 20,000 원). 매달 가지만 금액이 제각각이면 그건 변동비다. 반대로 통신비처럼
달마다 조금씩 달라도 배수로 튀지는 않는다. 그래서 '최대/최소 비율' 로 본다.
"""
from __future__ import annotations

import statistics
from datetime import date, timedelta

from . import categories as C

# 최대/최소 비율이 이 이내면 '금액이 비슷하다'. 통신요금처럼 소폭 변동은 통과시키고,
# 마트·식비처럼 배수로 튀는 건 걸러낸다.
STEADY_RATIO = 1.35
MIN_HITS = 2                # 반복으로 인정할 최소 결제 횟수(서로 다른 달)


def _month(t: dict) -> str:
    return str(t.get("date") or t.get("billing_month", ""))[:7]


def _parse(d: str) -> date | None:
    try:
        y, m, dd = (int(x) for x in str(d)[:10].split("-"))
        return date(y, m, dd)
    except (ValueError, TypeError):
        return None


def _group(txs: list[dict]) -> dict[str, list[dict]]:
    """가맹점 키로 묶는다 — 지점·단말기 번호가 달라도 같은 곳으로."""
    out: dict[str, list[dict]] = {}
    for t in txs:
        if (t.get("amount") or 0) <= 0 or t.get("projected"):
            continue
        key = C.merchant_key(t.get("merchant", ""))
        if key:
            out.setdefault(key, []).append(t)
    return out


def _profile(rows: list[dict]) -> dict:
    """한 가맹점의 결제 이력을 요약한다."""
    rows = sorted(rows, key=lambda t: str(t.get("date", "")))
    amounts = [float(t["amount"]) for t in rows]
    months = sorted({_month(t) for t in rows if _month(t)})
    lo, hi = min(amounts), max(amounts)
    ratio = (hi / lo) if lo > 0 else float("inf")

    dates = [d for d in (_parse(t.get("date", "")) for t in rows) if d]
    gaps = [(b - a).days for a, b in zip(dates, dates[1:]) if (b - a).days > 0]
    interval = int(statistics.median(gaps)) if gaps else 0

    if not interval:
        cadence = "월 1회 추정" if len(months) <= 1 else "불규칙"
    elif interval <= 10:
        cadence = f"{interval}일마다"
    elif interval <= 45:
        cadence = "매월"
    elif interval <= 100:
        cadence = "분기"
    else:
        cadence = "연간"

    last = dates[-1] if dates else None
    return {
        "merchant": rows[-1].get("merchant", ""),
        "key": C.merchant_key(rows[-1].get("merchant", "")),
        "category": rows[-1].get("category", "기타"),
        "cards": sorted({f'{t.get("issuer", "")} {t.get("card", "")}'.strip()
                         for t in rows if t.get("card") or t.get("issuer")}),
        "count": len(rows),
        "months": months,
        "min": round(lo),
        "max": round(hi),
        "avg": round(statistics.fmean(amounts)),
        "last_amount": round(amounts[-1]),
        "total": round(sum(amounts)),
        "steady": ratio <= STEADY_RATIO,
        "spread_pct": round((ratio - 1) * 100, 1) if lo > 0 else None,
        "interval_days": interval,
        "cadence": cadence,
        "last_date": last.isoformat() if last else "",
        "next_expected": (last + timedelta(days=interval)).isoformat()
                         if (last and interval) else "",
    }


def _keyword_fixed(prof: dict) -> bool:
    if prof["category"] in C.FIXED_CATEGORIES:
        return True
    low = prof["merchant"].lower()
    return any(k in low for k in C.FIXED_KEYWORDS)


def analyze(txs: list[dict], fixed_rules: dict | None = None) -> dict:
    """고정지출 목록 + 월/연 환산, 그리고 '반복은 되는데 금액이 들쭉날쭉한' 후보.

    후보를 따로 주는 이유: 자동 판정이 애매한 걸 숨기면 사용자가 직접 넣을 방법이
    없다. 화면에서 한 번 눌러 고정비로 승격시킬 수 있게 보여준다.
    """
    rules = fixed_rules or {}
    items, candidates = [], []

    for rows in _group(txs).values():
        prof = _profile(rows)
        repeated = len(prof["months"]) >= MIN_HITS

        override = rules.get(prof["merchant"])
        if override is False:
            continue
        if override is True:
            prof["source"] = "직접 지정"
        elif repeated and prof["steady"]:
            prof["source"] = "반복 결제"
        elif _keyword_fixed(prof):
            prof["source"] = "구독·공과금 분류"
        else:
            if repeated:        # 매달 가지만 금액이 제각각 — 변동비다
                candidates.append({**prof, "reason": "금액이 달마다 크게 달라 변동비로 봤습니다"})
            continue

        # 월 환산: 주기를 알면 30일 기준으로, 모르면 평균 결제액 그대로.
        per_month = (prof["avg"] * 30 / prof["interval_days"]) if prof["interval_days"] else prof["avg"]
        prof["monthly"] = round(per_month)
        prof["annual"] = round(per_month * 12)
        items.append(prof)

    items.sort(key=lambda x: -x["monthly"])
    candidates.sort(key=lambda x: -x["total"])

    by_cat: dict[str, float] = {}
    for it in items:
        by_cat[it["category"]] = by_cat.get(it["category"], 0.0) + it["monthly"]

    monthly = sum(it["monthly"] for it in items)
    return {
        "items": items,
        "candidates": candidates[:12],
        "count": len(items),
        "monthly_total": round(monthly),
        "annual_total": round(monthly * 12),
        "by_category": sorted(({"category": k, "monthly": round(v)} for k, v in by_cat.items()),
                              key=lambda x: -x["monthly"]),
        "note": ("반복 결제는 서로 다른 달에 2회 이상 비슷한 금액으로 찍힌 것만 잡습니다. "
                 "한 달치만 있으면 구독·통신·공과금 분류로만 판단하니, 빠진 게 있으면 "
                 "거래 목록에서 '고정' 을 눌러 지정하세요."),
    }


def steady_keys(txs: list[dict], fixed_rules: dict | None = None) -> set[str]:
    """집계에서 쓸 '고정비 가맹점 키' 집합 — ``analyze`` 와 같은 규칙을 쓴다.

    두 곳이 서로 다른 규칙으로 고정비를 정하면 요약의 고정비 합계와 고정지출 화면의
    합계가 어긋난다. 그래서 판정은 여기 한 곳에서만 한다.
    """
    return {it["key"] for it in analyze(txs, fixed_rules)["items"] if it["key"]}
