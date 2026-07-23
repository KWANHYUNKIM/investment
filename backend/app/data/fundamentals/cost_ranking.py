"""원가 경쟁력 랭킹 — "원가 구조가 괜찮은 순"으로 회사를 세운다.

레벨1 목록은 지금까지 업종·회사명 순이라 "어디가 괜찮은가"를 알 수 없었다.
야간 배치(``company_costmodels.json``)가 이미 회사별 3개년 손익·원가차이·정합성·
감사점수를 갖고 있으므로, 그걸 **투명한 5개 항목**으로 점수화해 정렬한다.

점수(0~100)는 블랙박스가 아니라 **항목별 배점과 근거 수치를 그대로 돌려준다**.
합성점수만 믿고 사지 말라는 뜻에서, 화면에도 항목 점수를 같이 띄운다.

| 항목 | 배점 | 무엇을 보나 |
|---|---|---|
| 수익성   | 25 | 영업이익률 — **업종 내 백분위**(업종마다 정상 마진이 다르므로 절대비교 X) |
| 원가추세 | 25 | 3년 매출원가율 변화(FY-2→FY). 내려갔으면 원가 압박을 이겨낸 것 |
| 전가력   | 25 | 능률·기타차이(잔차). 원자재가 올랐는데 원가율을 방어했으면 판가전가력 |
| 안정성   | 10 | 3년 원가율 표준편차. 출렁임이 작을수록 예측 가능 |
| 신뢰도   | 15 | 재무제표 감사점수 + 마진 정합성 — 숫자를 믿을 수 있는가 |

DART 실측이 없는 회사(수작업 KB 추정)는 **순위에서 제외**한다. 추정 비율로 만든
점수를 실측 회사와 같은 표에 세우면 비교가 성립하지 않는다.
"""
from __future__ import annotations

from statistics import pstdev

from app.data.fundamentals import company_costmodel as ccm

WEIGHTS = {"profitability": 25, "cost_trend": 25, "pass_through": 20,
           "stability": 15, "reliability": 15}

# 배점 스케일은 **전 종목 실측 분포**에 맞춰 잡았다(162사 기준).
#   3년 원가율 변화(%p)  p25 −2.8 · 중앙 −0.3 · p75 +1.8  → ±2.5%p 를 만점/0점 끝으로
#   3년 원가율 편차(%p)  중앙 1.27 · p75 2.65 · p90 5.38  → 4%p 를 0점 끝으로
# 처음엔 편차 2%p 를 0점으로 뒀더니 30% 넘는 회사가 안정성 0점이라, 상위권 설명이
# 전부 "안정성 약점"으로 똑같아졌다.
_TREND_SPAN = 2.5       # %p — 이만큼 개선이면 만점, 이만큼 악화면 0
_STABILITY_SPAN = 4.0   # %p — 편차가 이 이상이면 0
_PRESSURE_FLOOR = 0.5   # %p — 원자재 압력이 이보다 작으면 전가력을 묻지 않는다

# 등급 경계 — 상대평가가 아니라 고정 컷(배치마다 등급이 출렁이지 않게).
_GRADES = [(80, "A+"), (70, "A"), (60, "B+"), (50, "B"), (40, "C"), (0, "D")]


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _grade(score: float) -> str:
    for cut, g in _GRADES:
        if score >= cut:
            return g
    return "D"


def _percentile(value: float, pool: list[float]) -> float:
    """pool 안에서 value 의 백분위(0~1). pool 이 빈약하면 0.5(중립)."""
    if not pool or len(pool) < 3:
        return 0.5
    below = sum(1 for v in pool if v < value)
    same = sum(1 for v in pool if v == value)
    return (below + same / 2) / len(pool)


def _score_one(row: dict, peer_margins: list[float]) -> dict:
    """회사 1개의 항목별 점수. 자료가 없는 항목은 중립(배점의 절반)으로 두고 표시한다."""
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

    # ① 수익성 — 업종 내 백분위
    op = row.get("op_margin")
    if op is None:
        put("profitability", None, "영업이익률 없음")
    else:
        pct = _percentile(op, peer_margins)
        put("profitability", pct,
            f"영업이익률 {op*100:.1f}% · 업종 상위 {(1-pct)*100:.0f}%")

    # ② 원가추세 — 3년 매출원가율 변화(%p). 음수(개선)일수록 좋다.
    cogs3 = [c for c in (row.get("cogs_3y") or []) if c is not None]
    if len(cogs3) >= 2:
        delta_pp = (cogs3[0] - cogs3[-1]) * 100          # 최신 − 최고(과거) : +면 악화
        put("cost_trend", (_TREND_SPAN - delta_pp) / (2 * _TREND_SPAN),
            f"3년 원가율 {cogs3[-1]*100:.1f}% → {cogs3[0]*100:.1f}% "
            f"({delta_pp:+.1f}%p)")
    else:
        delta_pp = None
        put("cost_trend", None, "3개년 손익 부족")

    # ③ 전가력 — **원자재 압력 대비** 방어율. 능률·기타차이(잔차)를 그대로 쓰면
    #    원가추세와 같은 신호를 두 번 세게 된다(실측 상관 0.46). 그래서 "원자재가
    #    밀어올린 만큼을 판가·믹스로 얼마나 되받았나"로 정규화한다.
    #      방어율 = −능률차이 ÷ 가격차이   (1.0 = 압력을 정확히 상쇄)
    #    원자재 압력이 없거나 오히려 내렸으면 전가력을 물을 수 없으므로 중립 처리.
    eff = row.get("efficiency_pp")
    price = row.get("price_variance_pp")
    defense = None
    if eff is None or price is None:
        put("pass_through", None, "원가차이 분해 불가(시세 연동 원재료 없음)")
    elif price < _PRESSURE_FLOOR:
        # 압력이 0에 가까우면 나눗셈이 값을 뻥튀기한다(압력 0.1%p·잔차 −1.5%p → 방어율 15배).
        put("pass_through", None,
            f"원자재 압력 {price:+.1f}%p — {_PRESSURE_FLOOR}%p 미만이라 전가력 판단 보류")
    else:
        defense = -eff / price
        put("pass_through", (defense + 0.5) / 1.5,
            f"원자재 압력 {price:+.1f}%p 중 {defense*100:.0f}% 방어"
            f" (능률·기타차이 {eff:+.1f}%p)")

    # ④ 안정성 — 3년 원가율 표준편차(%p)
    if len(cogs3) >= 3:
        sd = pstdev([c * 100 for c in cogs3])
        put("stability", (_STABILITY_SPAN - sd) / _STABILITY_SPAN,
            f"3년 원가율 편차 {sd:.1f}%p")
    else:
        sd = None
        put("stability", None, "3개년 손익 부족")

    # ⑤ 신뢰도 — 재무제표 감사점수 + 마진 정합성
    audit = row.get("audit_score")
    recon = row.get("recon_status")
    recon_w = {"ok": 1.0, "warn": 0.6, "loss": 0.4, "mismatch": 0.2}.get(recon, 0.5)
    if audit is None:
        put("reliability", recon_w, f"정합성 {recon or '미상'} (감사점수 없음)")
    else:
        put("reliability", (audit / 100) * 0.6 + recon_w * 0.4,
            f"감사점수 {audit} · 정합성 {recon or '미상'}")

    total = round(sum(p["score"] for p in parts.values()), 1)
    return {"score": total, "grade": _grade(total), "parts": parts,
            "estimated_parts": missing,
            "delta_pp": None if delta_pp is None else round(delta_pp, 1),
            "defense": None if defense is None else round(defense, 2),
            "cogs_sd_pp": None if sd is None else round(sd, 1)}


_NAMED = {"profitability": "수익성", "cost_trend": "원가추세",
          "pass_through": "전가력", "stability": "안정성", "reliability": "신뢰도"}
_STRONG_AT = 0.70
_WEAK_AT = 0.40


def _headline(s: dict) -> str:
    """왜 이 점수인지 한 줄.

    "가장 높은 항목 = 강점"으로 뽑으면 거의 모두 만점인 항목(신뢰도)이 계속
    강점으로 나와 설명이 똑같아진다. 그래서 **분명히 높을 때(0.7↑)만 강점**,
    **분명히 낮을 때(0.4↓)만 약점**이라 부르고, 자료 없어 중립 처리된 항목은 뺀다.
    """
    scored = {k: v["score"] / v["max"] for k, v in s["parts"].items()
              if not v.get("estimated") and v["max"]}
    if not scored:
        return "판단 근거 부족 — 자료가 대부분 없음"
    # 신뢰도는 대부분 만점이라 '강점'으로 뽑으면 설명이 전부 똑같아진다. 이건 원가
    # 구조를 보는 탭이므로 신뢰도는 **게이트**로만 쓴다(낮을 때 약점으로는 나온다).
    strong_pool = {k: v for k, v in scored.items() if k != "reliability"} or scored
    best = max(strong_pool, key=strong_pool.get)
    worst = min(scored, key=scored.get)
    strong = scored[best] >= _STRONG_AT
    weak = scored[worst] <= _WEAK_AT
    if strong and weak and best != worst:
        return f"{_NAMED[best]} 강점 · {_NAMED[worst]} 약점"
    if strong:
        return f"{_NAMED[best]} 강점 · 뚜렷한 약점 없음"
    if weak:
        return f"{_NAMED[worst]} 약점 · 뚜렷한 강점 없음"
    return "항목별로 고르게 중간"


def ranking(sector: str | None = None, limit: int = 0,
            include_estimated: bool = False) -> dict:
    """원가 경쟁력 순 회사 랭킹. 배치 파일을 읽어 계산하므로 즉시 응답한다."""
    batch = ccm.load_batch()
    if not batch:
        return {"available": False, "rows": [], "excluded": 0,
                "note": "야간 배치(company_costmodels.json)가 아직 없습니다. "
                        "배치가 돌면 원가 경쟁력 순으로 정렬됩니다."}

    companies: dict[str, dict] = batch.get("companies") or {}
    # 업종 백분위는 **DART 실측 회사끼리만** 낸다(추정치가 섞이면 기준이 흔들린다).
    real = {tk: r for tk, r in companies.items() if r.get("basis") == "DART 실측"}
    peers: dict[str, list[float]] = {}
    for r in real.values():
        if r.get("op_margin") is not None:
            peers.setdefault(r["sector"], []).append(r["op_margin"])
    all_margins = [m for lst in peers.values() for m in lst]

    pool = real if not include_estimated else companies
    rows = []
    for tk, r in pool.items():
        if sector and r.get("sector") != sector:
            continue
        peer = peers.get(r.get("sector"), [])
        s = _score_one(r, peer if len(peer) >= 3 else all_margins)
        rows.append({
            "ticker": tk,
            "company": r.get("company"),
            "sector": r.get("sector"),
            "score": s["score"],
            "grade": s["grade"],
            "parts": s["parts"],
            "estimated_parts": s["estimated_parts"],
            "headline": _headline(s),
            "op_margin": r.get("op_margin"),
            "cogs_ratio": r.get("cogs_ratio"),
            "revenue_eok": r.get("revenue_eok"),
            "cogs_delta_3y_pp": s["delta_pp"],
            "cogs_sd_pp": s["cogs_sd_pp"],
            "defense_ratio": s["defense"],
            "efficiency_pp": r.get("efficiency_pp"),
            "price_variance_pp": r.get("price_variance_pp"),
            "verdict": r.get("verdict"),
            "audit_score": r.get("audit_score"),
            "recon_status": r.get("recon_status"),
            "production_type": r.get("production_type"),
            "basis": r.get("basis"),
            "year": r.get("year"),
        })
    rows.sort(key=lambda x: (-x["score"], x["company"] or ""))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    if limit:
        rows = rows[:limit]

    return {
        "available": True,
        "built_at": batch.get("built_at"),
        "as_of": batch.get("as_of"),
        "count": len(rows),
        "excluded": len(companies) - len(real),
        "weights": WEIGHTS,
        "sectors": sorted({r["sector"] for r in real.values() if r.get("sector")}),
        "rows": rows,
        "note": "원가 경쟁력 = 수익성25(업종 내 백분위)+원가추세25(3년 원가율 ±2.5%p)"
                "+전가력20(원자재 압력 대비 방어율)+안정성15(3년 원가율 편차)"
                "+신뢰도15(감사점수·정합성). "
                "DART 실측 회사만 순위에 넣고, 수작업 KB 추정치만 있는 회사는 제외한다"
                f"(제외 {len(companies) - len(real)}사). 자료가 없는 항목은 중립(배점 절반) "
                "처리하고 estimated 로 표시하므로, 합성점수보다 항목 점수를 함께 보라.",
    }
