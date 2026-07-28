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

제품 지식베이스(230품목·업종 분류)는 ``products`` 패키지에 업종별 모듈로 들어 있다.
이 파일은 **계산만** 한다.
"""
from __future__ import annotations

from app.data.fundamentals import commodities
from app.data.fundamentals import dart_profile
from app.data.fundamentals.products import PRODUCTS, SECTOR_BY_ID, SECTOR_ORDER
from app.data.infra import store

__all__ = ["PRODUCTS", "SECTOR_BY_ID", "SECTOR_ORDER", "AUTO_SECTOR",
           "list_products", "teardown"]

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
         "sector": SECTOR_BY_ID.get(pid, "기타")}
        for pid, p in PRODUCTS.items()
    ]
    curated_tickers = {p["ticker"] for p in PRODUCTS.values()}
    for pid, p in _auto_products().items():
        if pid in PRODUCTS or p.get("ticker") in curated_tickers:
            continue  # 수작업이 있으면 자동본은 숨김
        # 원재료 매핑이 하나도 없는 자동본(껍데기·비영업 법인·파싱실패)은 숨김
        if not any(m.get("commodity") for m in p.get("material_mix", [])):
            continue
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
        "company": _company_block(p["ticker"]),
    }


def _company_block(ticker: str) -> dict | None:
    """회사 규모 · 인건비 · 숨만 쉬어도 나가는 고정비 (DART 실측, 억원 단위)."""
    try:
        pf = dart_profile.profile(ticker)
    except Exception:
        return None
    rev = pf.get("revenue")
    if not rev:
        return None
    eok = lambda v: round(v / 1e8) if v else None  # noqa: E731
    labor = pf.get("annual_labor")
    return {
        "year": pf.get("year"),
        "headcount": pf.get("headcount"),
        "avg_salary_manwon": round(pf["avg_salary"] / 1e4) if pf.get("avg_salary") else None,
        "revenue_eok": eok(rev),
        "labor_eok": eok(labor),
        "labor_pct": round(labor / rev * 100, 1) if labor else None,
        "sga_eok": eok(pf.get("sga")),       # 판관비 ≈ '숨만 쉬어도 나가는' 고정비
        "op_eok": eok(pf.get("op")),
        # 하루 단위 '숨만 쉬어도' 비용(판관비/365)
        "sga_per_day_eok": round(pf["sga"] / 1e8 / 365, 2) if pf.get("sga") else None,
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
