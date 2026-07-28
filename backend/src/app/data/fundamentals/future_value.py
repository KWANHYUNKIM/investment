"""미래가치 4문(門) — "지금 이익이 없는 이유"를 가른다.

"이 회사는 미래가치가 있나?"는 재무제표로 답할 수 없다(재무제표는 전부 과거다).
답이 나오는 형태는 이것 하나다:

    지금 이익이 없는 이유가 **미래에 쓰고 있어서**인가, **수요가 사라져서**인가.

그래서 단일 점수 대신 네 개의 문으로 나눠 묻는다.

| 문 | 묻는 것 | 지표 |
|---|---|---|
| 1. 미래에 돈을 쓰나 | 재투자 강도 | (유형자산 취득 + 무형자산 취득) ÷ 매출, 3년 평균 |
| 2. 그 돈이 돌아오나 | 전환 효율 | 3년 매출 증분 ÷ 3년 누적 재투자 |
| 3. 그때까지 버티나 | 재무 체력   | 순현금비율 · 이자보상배율 · 런웨이(현금 ÷ 현금소진) |
| 4. 시장이 커지나  | 외부 수요   | 메가트렌드 테마 매핑 여부 |

**배점은 30·30·30·10.** 1~3 은 회사 안에서 완결되는 공시 실측이고, 4 만 외부
뉴스가 섞인다. 뉴스는 조작·과장 여지가 커서 의도적으로 가장 낮은 비중을 준다.

## 데이터로 할 수 있는 것만 한다 (실측 커버리지, 2,591사 기준)
    유형자산 취득 91% · 무형자산 취득 91% · 영업/투자/재무 현금흐름 99%
    현금및현금성자산 100% · 차입금 87/82% · 이자지급 82% · 자산총계 100%
**연구개발비는 7%뿐이라 R&D/매출 지표는 만들지 않았다.** 회사마다 판관비·제조원가·
개발비 자산화로 흩어져 계정으로 잡히지 않는다. 대신 **무형자산 취득**(91%)을 쓴다 —
개발비 자산화·특허·소프트웨어가 들어가므로 R&D 전부는 아니어도 "미래에 쓴 돈"의 일부다.
같은 이유로 감가상각비(CF 31%)를 못 써서 'CAPEX ÷ 감가상각'도 쓰지 않는다.

## 반증(falsification) 이 점수보다 중요하다
"미래에 투자 중"이라는 서사를 **깨는** 신호가 켜지면 점수를 깎는 게 아니라 **등급 상한**을
건다. 감점으로 처리하면 다른 항목 점수로 상쇄돼 서사가 살아남기 때문이다.
"""
from __future__ import annotations

import threading
import time

from app.data.infra import store

WEIGHTS = {"reinvest": 30, "conversion": 30, "endurance": 30, "market": 10}

# 스케일은 실측 분포에 맞춰 잡는다(_calibration_stats 로 다시 뽑을 수 있음).
_CONV_FULL = 1.0        # 재투자 1원당 매출 1원 증분이면 전환 만점
# 분모가 작으면 비율이 폭발한다(매출 대비 재투자 160%, 전환 16배 같은 값이 실제로 나왔다).
# 그래서 ① 재투자율은 40%에서 자르고 ② 재투자가 매출의 3% 미만이면 전환 판단을 보류한다.
_REINVEST_CAP = 0.40
_INVEST_FLOOR = 0.03    # 3년 누적 재투자 ÷ 최근 매출
_RUNWAY_SAFE = 36.0     # 개월 — 이 이상이면 런웨이 만점
_RUNWAY_CAP = 12.0      # 개월 — 이 미만이면 등급 상한 D
_COVER_FULL = 5.0       # 이자보상배율 5배 이상이면 만점

_GRADES = [(80, "A+"), (70, "A"), (60, "B+"), (50, "B"), (40, "C"), (0, "D")]
_GRADE_ORDER = ["D", "C", "B", "B+", "A", "A+"]

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 1800.0
_UNIT = 1e8


# ── 계정 적재 ──────────────────────────────────────────────────────────────
# 계정명은 회사마다 공백이 제각각이라("유형자산의 취득") 공백을 지우고 맞춘다.
# 이걸 안 해서 처음엔 CAPEX 커버리지를 4%로 잘못 셌다.
_WANT = {
    "sales": (("IS", "CIS"), ("매출액", "수익(매출액)", "영업수익", "매출")),
    "op": (("IS", "CIS"), ("영업이익", "영업이익(손실)")),
    "assets": (("BS",), ("자산총계",)),
    "liab": (("BS",), ("부채총계",)),
    "cash": (("BS",), ("현금및현금성자산",)),
    "ppe": (("BS",), ("유형자산",)),
    "intangible": (("BS",), ("무형자산",)),
    "debt_s": (("BS",), ("단기차입금",)),
    "debt_l": (("BS",), ("장기차입금",)),
    "bond": (("BS",), ("사채",)),
    "cfo": (("CF",), ("영업활동현금흐름", "영업활동으로인한현금흐름")),
    "cfi": (("CF",), ("투자활동현금흐름", "투자활동으로인한현금흐름")),
    "cff": (("CF",), ("재무활동현금흐름", "재무활동으로인한현금흐름")),
    "capex": (("CF",), ("유형자산의취득", "유형자산취득")),
    "intan_buy": (("CF",), ("무형자산의취득", "무형자산취득")),
    "interest": (("CF",), ("이자지급", "이자의지급")),
}


def _series(conn=None) -> dict[str, dict[int, dict]]:
    """{ticker: {year: {key: amount}}} — 필요한 계정만 한 번의 벌크 쿼리로."""
    names = sorted({n for _, ns in _WANT.values() for n in ns})
    ph = ",".join("?" for _ in names)
    sql = f"""
        SELECT ticker, sj_div, year, nm, amount FROM (
            SELECT ticker, sj_div, year, amount,
                   replace(replace(account_nm, ' ', ''), ' ', '') AS nm
            FROM dart_financials WHERE amount IS NOT NULL
        ) WHERE nm IN ({ph})
    """
    if conn is not None:
        rows = conn.execute(sql, names).fetchall()
    else:
        with store.connection() as c:
            rows = c.execute(sql, names).fetchall()

    # (sj, 계정명) → 키 역인덱스
    idx: dict[tuple[str, str], str] = {}
    for key, (sjs, ns) in _WANT.items():
        for sj in sjs:
            for n in ns:
                idx[(sj, n)] = key

    out: dict[str, dict[int, dict]] = {}
    for tk, sj, yr, nm, amt in rows:
        key = idx.get((sj, nm))
        if not key:
            continue
        y = out.setdefault(tk, {}).setdefault(int(yr), {})
        # 같은 해 같은 항목이 여러 표에 있으면 먼저 잡힌 값을 쓴다(우선순위 = _WANT 순서)
        y.setdefault(key, float(amt))
    return out


def _recent(years: dict[int, dict], n: int = 3) -> list[tuple[int, dict]]:
    """매출이 있는 최근 n개 사업연도(최신 우선)."""
    ys = sorted((y for y, v in years.items() if v.get("sales")), reverse=True)[:n]
    return [(y, years[y]) for y in ys]


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _grade(score: float) -> str:
    for cut, g in _GRADES:
        if score >= cut:
            return g
    return "D"


def _cap(grade: str, ceiling: str) -> str:
    """등급 상한 적용 — 반증 신호가 켜지면 점수와 무관하게 등급을 눌러 앉힌다."""
    if _GRADE_ORDER.index(grade) <= _GRADE_ORDER.index(ceiling):
        return grade
    return ceiling


def _percentile(value: float, pool: list[float]) -> float:
    if not pool or len(pool) < 3:
        return 0.5
    below = sum(1 for v in pool if v < value)
    same = sum(1 for v in pool if v == value)
    return (below + same / 2) / len(pool)


# ── 지표 계산 ──────────────────────────────────────────────────────────────
def _metrics(rows: list[tuple[int, dict]]) -> dict:
    """회사 1개의 원지표. 계산 불가한 값은 None 으로 둔다(0으로 채우지 않는다)."""
    if not rows:
        return {}
    cur_y, cur = rows[0]
    oldest = rows[-1][1]

    def s(v, key):
        return v.get(key)

    invest = [(r.get("capex") or 0) + (r.get("intan_buy") or 0) for _, r in rows]
    has_invest = any((r.get("capex") is not None or r.get("intan_buy") is not None)
                     for _, r in rows)
    sales = [r.get("sales") for _, r in rows]

    reinvest_rate = raw_reinvest = None
    if has_invest:
        pairs = [(i, sv) for i, sv in zip(invest, sales) if sv]
        if pairs:
            raw_reinvest = sum(i / sv for i, sv in pairs) / len(pairs)
            reinvest_rate = min(raw_reinvest, _REINVEST_CAP)

    conversion = None
    cum_invest = sum(invest) if has_invest else 0
    invest_share = (cum_invest / sales[0]) if (has_invest and sales[0]) else None
    if (has_invest and cum_invest > 0 and len(rows) >= 2 and sales[0] and sales[-1]
            and invest_share is not None and invest_share >= _INVEST_FLOOR):
        conversion = (sales[0] - sales[-1]) / cum_invest

    sales_cagr = None
    if len(rows) >= 2 and sales[0] and sales[-1] and sales[-1] > 0:
        n = len(rows) - 1
        sales_cagr = (sales[0] / sales[-1]) ** (1 / n) - 1

    debt = sum(x for x in (s(cur, "debt_s"), s(cur, "debt_l"), s(cur, "bond")) if x)
    cash = s(cur, "cash")
    assets = s(cur, "assets")
    net_cash_ratio = ((cash - debt) / assets) if (cash is not None and assets) else None

    op, interest = s(cur, "op"), s(cur, "interest")
    interest_cover = None
    if op is not None and interest:
        interest_cover = op / abs(interest)

    cfo = s(cur, "cfo")
    runway_m = None
    if cfo is not None and cash is not None:
        runway_m = float("inf") if cfo >= 0 else (cash / (abs(cfo) / 12))

    # 유상증자 연명 — 영업CF 음수인데 재무CF 양수인 해가 몇 번인가
    dilution_years = sum(
        1 for _, r in rows
        if (r.get("cfo") is not None and r["cfo"] < 0
            and r.get("cff") is not None and r["cff"] > 0))

    # 설비 축소 — 유형자산 잔액이 3년 내내 줄었나
    ppe = [r.get("ppe") for _, r in rows]
    shrinking = (len(ppe) >= 3 and all(p is not None for p in ppe)
                 and ppe[0] < ppe[1] < ppe[2])

    return {
        "year": cur_y, "years": [y for y, _ in rows],
        "revenue_eok": round(sales[0] / _UNIT) if sales[0] else None,
        "op_margin": round(op / sales[0], 4) if (op is not None and sales[0]) else None,
        "reinvest_rate": reinvest_rate,
        "reinvest_raw": raw_reinvest,
        "reinvest_capped": bool(raw_reinvest is not None and raw_reinvest > _REINVEST_CAP),
        "reinvest_eok": round(invest[0] / _UNIT) if has_invest else None,
        "cum_invest_eok": round(cum_invest / _UNIT) if has_invest else None,
        "invest_share": invest_share,
        "conversion": conversion,
        "sales_cagr": sales_cagr,
        "net_cash_ratio": net_cash_ratio,
        "net_cash_eok": round((cash - debt) / _UNIT) if cash is not None else None,
        "interest_cover": interest_cover,
        "runway_months": runway_m,
        "dilution_years": dilution_years,
        "ppe_shrinking": shrinking,
        "loss_making": (op is not None and op < 0),
        "intangible_share": (
            round((cur.get("intan_buy") or 0) / (invest[0] or 1), 3) if has_invest else None),
    }


def _score(m: dict, peers: list[float]) -> dict:
    parts: dict[str, dict] = {}
    missing: list[str] = []

    def put(key: str, ratio: float | None, detail: str):
        w = WEIGHTS[key]
        if ratio is None:
            missing.append(key)
            parts[key] = {"score": round(w * 0.5, 1), "max": w, "detail": detail,
                          "estimated": True}
        else:
            parts[key] = {"score": round(w * _clamp(ratio), 1), "max": w, "detail": detail}

    # 문1 — 재투자 강도(업종 내 백분위). 자본집약도가 업종마다 달라 절대비교는 위험하다.
    r = m.get("reinvest_rate")
    if r is None:
        put("reinvest", None, "유형·무형자산 취득 미공시")
    else:
        raw = m.get("reinvest_raw") or r
        put("reinvest", _percentile(r, peers),
            f"매출의 {raw*100:.1f}% 를 설비·무형자산에 재투자 (3년 평균)"
            + (f" ※{_REINVEST_CAP*100:.0f}% 상한 적용" if m.get("reinvest_capped") else "")
            + (f" · 무형 비중 {m['intangible_share']*100:.0f}%"
               if m.get("intangible_share") else ""))

    # 문2 — 전환 효율. 쓴 돈이 매출로 돌아왔나.
    c = m.get("conversion")
    if c is None:
        share = m.get("invest_share")
        if share is not None and share < _INVEST_FLOOR:
            put("conversion", None,
                f"3년 누적 재투자가 매출의 {share*100:.1f}% — "
                f"{_INVEST_FLOOR*100:.0f}% 미만이라 전환 배수가 불안정해 판단 보류")
        else:
            put("conversion", None, "재투자 또는 3개년 매출 부족")
    else:
        put("conversion", c / _CONV_FULL,
            f"3년 누적 재투자 {m['cum_invest_eok']:,}억 → 매출 증분 "
            f"{c:.2f}배" + (f" · 매출 CAGR {m['sales_cagr']*100:+.1f}%"
                            if m.get("sales_cagr") is not None else ""))

    # 문3 — 체력. 순현금 / 이자보상 / 런웨이 셋을 합쳐 하나로.
    sub, notes = [], []
    nc = m.get("net_cash_ratio")
    if nc is not None:
        sub.append(_clamp((nc + 0.2) / 0.6))          # −20% → 0, +40% → 만점
        notes.append(f"순현금 {m['net_cash_eok']:,}억(자산 대비 {nc*100:+.0f}%)")
    ic = m.get("interest_cover")
    if ic is not None:
        sub.append(_clamp(ic / _COVER_FULL))
        notes.append(f"이자보상 {ic:.1f}배")
    rw = m.get("runway_months")
    if rw is not None:
        sub.append(1.0 if rw == float("inf") else _clamp(rw / _RUNWAY_SAFE))
        notes.append("영업현금 흑자" if rw == float("inf") else f"런웨이 {rw:.0f}개월")
    put("endurance", (sum(sub) / len(sub)) if sub else None,
        " · ".join(notes) or "현금·차입금 미공시")

    # 문4 — 시장 방향. 뉴스가 섞이므로 배점이 가장 작고, 없으면 중립이다.
    themes = m.get("themes") or []
    if not m.get("theme_ready"):
        put("market", None, "테마 매핑 미준비")
    elif themes:
        put("market", 1.0, "메가트렌드 테마: " + ", ".join(themes[:3]))
    else:
        put("market", 0.4, "메가트렌드 테마 매핑 없음")

    total = round(sum(p["score"] for p in parts.values()), 1)
    return {"score": total, "parts": parts, "estimated_parts": missing}


# ── 반증 — 서사를 깨는 신호 ────────────────────────────────────────────────
def _falsifiers(m: dict, risk_level: int | None, audit: int | None) -> list[dict]:
    """켜지면 '미래에 투자 중'이라는 설명이 성립하지 않는 신호. 등급 상한을 건다."""
    out = []

    def add(cap: str, text: str, why: str):
        out.append({"cap": cap, "text": text, "why": why})

    rw = m.get("runway_months")
    if rw is not None and rw != float("inf") and rw < _RUNWAY_CAP:
        add("D", f"런웨이 {rw:.0f}개월 — 현금이 1년을 못 버틴다",
            "미래를 논하기 전에 생존이 먼저다.")
    if (m.get("dilution_years") or 0) >= 2:
        add("C", f"영업현금 적자인데 재무현금 유입 {m['dilution_years']}년 — 증자·차입 연명",
            "자체 사업이 아니라 외부 조달로 버티는 구조.")
    conv = m.get("conversion")
    if conv is not None and conv <= 0 and (m.get("reinvest_rate") or 0) > 0.02:
        add("C", "재투자는 하는데 3년 매출이 줄었다 — 전환 실패",
            "돈을 쓰는 것과 미래가 오는 것은 다르다.")
    if m.get("ppe_shrinking"):
        add("B", "유형자산이 3년 연속 감소 — 설비를 줄이는 중",
            "사양산업·구조조정의 전형. 미래 투자와 반대 방향.")
    if risk_level is not None and risk_level >= 2:
        add("D", "관리종목·상폐 요건에 걸려 있음",
            "상장 유지가 불투명하면 미래가치 논의가 의미 없다.")
    if audit is not None and audit < 60:
        add("C", f"재무제표 감사점수 {audit}점 — 숫자 자체를 믿기 어렵다",
            "입력이 흔들리면 위 계산이 전부 흔들린다.")
    return out


def _verdict(m: dict, parts: dict, falsifiers: list) -> str:
    """적자기업을 미래투자형 / 구조조정형 / 소멸형으로 가른다 — 이 모듈의 존재 이유."""
    caps = {f["cap"] for f in falsifiers}
    if not m.get("loss_making"):
        # 흑자기업도 갈린다 — 벌어서 다시 심는 곳 / 그냥 버는 곳 / 줄이는 곳.
        if m.get("ppe_shrinking"):
            return "흑자지만 설비 축소 — 수확기(캐시카우)"
        inv = parts["reinvest"]["score"] / parts["reinvest"]["max"]
        conv = parts["conversion"]["score"] / parts["conversion"]["max"]
        if inv >= 0.6 and conv >= 0.5:
            return "성장투자형 흑자 — 벌어서 다시 심고, 그게 매출로 돌아온다"
        if inv >= 0.6:
            return "투자형 흑자 — 재투자는 크나 매출 전환은 아직"
        return "현상유지형 흑자 — 재투자가 업종 평균 이하"
    invest_ok = parts["reinvest"]["score"] / parts["reinvest"]["max"] >= 0.5
    endure_ok = parts["endurance"]["score"] / parts["endurance"]["max"] >= 0.5
    if "D" in caps or not endure_ok:
        return "소멸형 적자 — 버틸 현금이 부족하다"
    if invest_ok and parts["conversion"]["score"] / parts["conversion"]["max"] >= 0.4:
        return "미래투자형 적자 — 쓰는 돈이 매출로 돌아오고 있다"
    if invest_ok:
        return "투자 중이나 전환 미확인 — 매출 전환을 지켜봐야 한다"
    return "구조조정형 적자 — 재투자 없이 적자"


# ── 보드 ───────────────────────────────────────────────────────────────────
def _theme_map() -> tuple[dict[str, list[str]], bool]:
    """{ticker: [테마명]} — 문4 재료. 실패하면 (빈 맵, False) 로 중립 처리한다."""
    try:
        from app.data.intel import futuretheme
        out: dict[str, list[str]] = {}
        for t in futuretheme.themes():
            for mrow in t.get("members") or []:
                tk = mrow.get("ticker")
                if tk:
                    out.setdefault(tk, []).append(t.get("title") or t.get("key"))
        return out, True
    except Exception:
        return {}, False


def _build() -> dict:
    series = _series()
    try:
        profiles = {p["ticker"]: p for p in store.company_profiles().to_dict("records")}
    except Exception:
        profiles = {}
    themes, theme_ready = _theme_map()
    try:
        from app.data.market import delisting
        risk = {r["ticker"]: r["level"] for r in delisting.board().get("rows", [])}
    except Exception:
        risk = {}
    try:
        from app.data.fundamentals import company_costmodel as ccm
        audit = {tk: r.get("audit_score")
                 for tk, r in ((ccm.load_batch() or {}).get("companies") or {}).items()}
    except Exception:
        audit = {}

    metrics: dict[str, dict] = {}
    for tk, years in series.items():
        rows = _recent(years)
        if len(rows) < 2:
            continue
        m = _metrics(rows)
        if not m or m.get("revenue_eok") in (None, 0):
            continue
        p = profiles.get(tk) or {}
        m["name"] = p.get("name") or tk
        m["sector"] = p.get("wics_sector") or p.get("industry") or "미분류"
        m["themes"] = themes.get(tk, [])
        m["theme_ready"] = theme_ready
        metrics[tk] = m

    peers: dict[str, list[float]] = {}
    for m in metrics.values():
        if m.get("reinvest_rate") is not None:
            peers.setdefault(m["sector"], []).append(m["reinvest_rate"])
    all_rates = [v for lst in peers.values() for v in lst]

    rows = []
    for tk, m in metrics.items():
        pool = peers.get(m["sector"], [])
        s = _score(m, pool if len(pool) >= 3 else all_rates)
        f = _falsifiers(m, risk.get(tk), audit.get(tk))
        grade = _grade(s["score"])
        for x in f:
            grade = _cap(grade, x["cap"])
        rw = m.get("runway_months")
        rows.append({
            "ticker": tk, "name": m["name"], "sector": m["sector"],
            "score": s["score"], "grade": grade,
            "raw_grade": _grade(s["score"]),
            "parts": s["parts"], "estimated_parts": s["estimated_parts"],
            "falsifiers": f,
            "verdict": _verdict(m, s["parts"], f),
            "loss_making": m["loss_making"],
            "year": m["year"], "revenue_eok": m["revenue_eok"], "op_margin": m["op_margin"],
            "reinvest_rate": None if m["reinvest_rate"] is None else round(m["reinvest_rate"], 4),
            "conversion": None if m["conversion"] is None else round(m["conversion"], 2),
            "sales_cagr": None if m["sales_cagr"] is None else round(m["sales_cagr"], 4),
            "net_cash_eok": m["net_cash_eok"],
            "interest_cover": None if m["interest_cover"] is None else round(m["interest_cover"], 1),
            "runway_months": None if rw is None else (None if rw == float("inf") else round(rw)),
            "cash_positive": rw == float("inf"),
            "dilution_years": m["dilution_years"],
            "themes": m["themes"],
        })
    rows.sort(key=lambda x: (-x["score"], x["name"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    from collections import Counter
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M"),
        "count": len(rows),
        "weights": WEIGHTS,
        "grades": dict(Counter(r["grade"] for r in rows)),
        "verdicts": dict(Counter(r["verdict"] for r in rows)),
        "loss_verdicts": dict(Counter(r["verdict"] for r in rows if r["loss_making"])),
        "theme_ready": theme_ready,
        "sectors": sorted({r["sector"] for r in rows}),
        "rows": rows,
        "note": "미래가치 4문 = 재투자30(유형+무형 취득÷매출, 업종 내 백분위) + 전환30"
                "(3년 매출증분÷누적재투자) + 체력30(순현금·이자보상·런웨이) + 시장10"
                "(메가트렌드 테마). 뉴스가 섞이는 시장 항목만 배점을 최소로 뒀다. "
                "연구개발비는 공시 커버리지가 7%뿐이라 지표로 쓰지 않고 무형자산 취득으로 대신한다. "
                "반증 신호(런웨이 12개월 미만·증자 연명·전환 실패·설비 축소·상폐 요건·감사점수 미달)는 "
                "감점이 아니라 **등급 상한**으로 적용한다 — 감점은 다른 항목으로 상쇄돼 서사가 살아남는다.",
    }


def board(force: bool = False) -> dict:
    now = time.time()
    with _lock:
        if not force and _cache["data"] is not None and now - _cache["ts"] < TTL:
            return _cache["data"]
    data = _build()
    with _lock:
        _cache.update(ts=now, data=data)
    return data


def for_ticker(ticker: str) -> dict | None:
    for r in board().get("rows", []):
        if r["ticker"] == ticker:
            return r
    return None
