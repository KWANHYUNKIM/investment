"""회사 단위 원가분석 (원가분석 탭 3단 드릴다운의 백엔드).

기존 SKU 단위 ``unit_economics.teardown`` 을 **회사(ticker)** 로 묶어,
한 회사의 품목 전체를 각각 원가분해하고 품목별 영업이익(영익)을 나열한다.

레벨 구조(``docs/원가분석_개편계획.md`` §1):
  레벨1  회사 목록(업종 필터)                     → ``list_companies``
  레벨2  회사 상세: ① 품목별 원가·영익 ② 원재료 시세 ③ 마진 정합성 → ``analyze``
  레벨3  재무제표 근거(손익계산서 원장)            → ``analyze`` 의 ``financials_detail``

데이터 출처는 값마다 표기한다(DART 실측 / 추정). DART 키가 없으면 수작업
지식베이스(``PRODUCTS``)의 추정값으로 동작하고, 키를 넣으면 자동으로 실측·전 품목으로 확장된다.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time

from app.core.config import get_settings
from app.data.fundamentals import commodities
from app.data.fundamentals import joint_costing
from app.data.fundamentals import labor_cost
from app.data.fundamentals import report_business
from app.data.fundamentals import report_notes
from app.data.fundamentals import statement_audit
from app.data.fundamentals import unit_economics as ue
from app.data.infra import store


# --- 회사 목록 (레벨 1) ----------------------------------------------------
def _all_models() -> dict[str, dict]:
    """수작업 + 자동생성 모델 전체 {product_id: model}."""
    out = dict(ue.PRODUCTS)
    for pid, m in ue._auto_products().items():
        if pid in out:
            continue
        # 원재료 매핑이 하나도 없는 자동본(껍데기·파싱실패)은 제외
        if not any(x.get("commodity") for x in m.get("material_mix", [])):
            continue
        out[pid] = m
    return out


def _company_ratios(ticker: str, models: list[dict]) -> tuple[dict, dict]:
    """회사 대표 (cogs, op, sga) 비율 + basis. DART 실측 우선, 없으면 품목 추정 평균."""
    fin = ue._income_ratios(ticker)
    if fin and fin.get("cogs") and 0.2 < fin["cogs"] < 0.98:
        cogs = fin["cogs"]
        op = fin["op"] if (fin.get("op") is not None) else _avg(models, "op")
        basis = {"source": "DART 실측", "year": fin.get("year"), "sales": fin.get("sales")}
    else:
        cogs = _avg(models, "cogs")
        op = _avg(models, "op")
        basis = {"source": "추정(수작업 KB)", "year": None, "sales": None}
    sga = max(0.0, 1 - cogs - op)
    return {"cogs": round(cogs, 4), "op": round(op, 4), "sga": round(sga, 4)}, basis


def _avg(models: list[dict], key: str) -> float:
    vals = [m["default_ratios"][key] for m in models if m.get("default_ratios")]
    return round(sum(vals) / len(vals), 4) if vals else (0.85 if key == "cogs" else 0.05)


# --- Phase A: 3개년 손익 실측 ----------------------------------------------
_SALES = ("매출액", "수익(매출액)", "영업수익", "매출")
_COGS = ("매출원가",)
_OP = ("영업이익", "영업이익(손실)")
_SGA = ("판매비와관리비", "판매비와 관리비")


def income_ratios_3y(ticker: str) -> list[dict]:
    """최근 3개 사업연도 손익비율(내림차순). 각 {year, sales, revenue_eok,
    cogs_ratio, sga_ratio, op_margin}. 실패 시 []."""
    try:
        df = store.dart_financials(ticker)
    except Exception:
        return []
    if df is None or df.empty:
        return []
    inc = df[df["sj_div"].isin(["IS", "CIS"])]
    if inc.empty:
        return []

    def pick(names) -> dict[int, float]:
        sub = inc[inc["account_nm"].isin(names)]
        return {int(r["year"]): float(r["amount"]) for _, r in sub.iterrows()}

    sales, cogs, op, sga = pick(_SALES), pick(_COGS), pick(_OP), pick(_SGA)
    years = sorted(set(sales) & set(cogs), reverse=True)[:3]
    out = []
    for y in years:
        s = sales[y]
        if not s:
            continue
        out.append({
            "year": y,
            "sales": s,
            "revenue_eok": round(s / 1e8),
            "cogs_ratio": round(cogs[y] / s, 4),
            "sga_ratio": round(sga.get(y, 0.0) / s, 4) if sga.get(y) is not None else None,
            "op_margin": round(op.get(y, 0.0) / s, 4) if op.get(y) is not None else None,
        })
    return out


# --- Phase B: 표준(기준)원가 vs 실제 원가차이 분해 -------------------------
def _variance(mods: list[dict], fin3y: list[dict], notes: dict | None = None) -> dict | None:
    """최근 1년(FY-1→FY) 원가차이를 가격차이(원자재발)/능률·기타차이(잔차)로 분해.

    - 가격차이 = Σ(원재료비ᵢ × 원자재 최근1년 등락률) : 시세가 원가에 준 압력.
    - 실제 원가율 변화 = cogs_ratio[FY] − cogs_ratio[FY-1].
    - 능률·기타차이(잔차) = 실제변화 − 가격차이(%p 환산).
    ⚪ 노무·제조간접의 표준임률/시간차이는 미공시 → 여기 잔차에 포함(주석).

    ``notes`` 가 있으면 매출원가 중 원재료비 비중을 **가정(0.8) 대신 사업보고서
    「비용의 성격별 분류」 실측**으로 대체한다 — 가격차이 금액이 실측 기반이 된다.
    """
    if len(fin3y) < 2:
        return None
    cur, prev = fin3y[0], fin3y[1]
    cogs_eok = cur["revenue_eok"] * cur["cogs_ratio"]     # 매출원가(억)

    # 원재료비 비중: 주석 실측(재료비 ÷ 매출원가) 우선, 없으면 제품 KB 가정
    cn = (notes or {}).get("cost_nature") or {}
    measured_mr = None
    if cn.get("material_eok") and cogs_eok:
        measured_mr = round(min(1.0, cn["material_eok"] / cogs_eok), 4)

    # 원재료비를 커모디티 기준으로 집계(제품 평균 material_ratio 가중)
    agg: dict[str, dict] = {}
    n = len(mods)
    for m in mods:
        mr = measured_mr if measured_mr else m.get("material_ratio_of_cogs", 0.8)
        for x in m.get("material_mix", []):
            key = x.get("commodity")
            if not key:
                continue
            agg.setdefault(key, {"item": x["item"], "w": 0.0})
            agg[key]["w"] += x["weight"] * mr
    if not agg:
        return None

    contribs, price_var = [], 0.0
    for key, v in agg.items():
        w = v["w"] / n                       # 회사 매출원가 내 이 원자재 비중(근사)
        amount = cogs_eok * w                 # 원재료비(억)
        c = commodities.get(key)
        chg = c["chg_1y"] if c else 0.0
        contrib = amount * chg                # 가격차이 기여(억)
        price_var += contrib
        contribs.append({
            "item": v["item"], "commodity": c["name_ko"] if c else None,
            "material_eok": round(amount), "chg_1y": chg,
            "variance_eok": round(contrib), "fu": "U" if contrib > 0 else ("F" if contrib < 0 else "—"),
        })
    contribs.sort(key=lambda x: abs(x["variance_eok"]), reverse=True)

    rev = cur["revenue_eok"] or 1
    price_pp = round(price_var / rev * 100, 1)
    actual_pp = round((cur["cogs_ratio"] - prev["cogs_ratio"]) * 100, 1)
    eff_pp = round(actual_pp - price_pp, 1)
    change_3y_pp = round((cur["cogs_ratio"] - fin3y[-1]["cogs_ratio"]) * 100, 1) if len(fin3y) >= 2 else None

    return {
        "basis": "원자재 시세 기준원가 vs DART 매출원가 (최근 1년 FY-1→FY)",
        "years": f"FY{prev['year']}→FY{cur['year']}",
        "price_variance_eok": round(price_var),
        "price_variance_pp": price_pp,
        "price_fu": "U" if price_var > 0 else ("F" if price_var < 0 else "—"),
        "actual_change_pp": actual_pp,
        "actual_fu": "U" if actual_pp > 0 else ("F" if actual_pp < 0 else "—"),
        "efficiency_pp": eff_pp,
        "efficiency_fu": "U" if eff_pp > 0 else ("F" if eff_pp < 0 else "—"),
        "cogs_ratio_change_3y_pp": change_3y_pp,
        "contributions": contribs,
        "material_ratio_of_cogs": measured_mr,
        "material_ratio_source": ("사업보고서 「비용의 성격별 분류」 실측"
                                  if measured_mr else "제품 KB 가정(0.8 등)"),
        "note": "노무·제조간접의 표준임률/시간차이는 미공시(⚪) → 능률·기타차이(잔차)에 포함.",
        "verdict": _variance_verdict(price_var, eff_pp),
    }


def _variance_verdict(price_var: float, eff_pp: float) -> str:
    up = price_var > 1
    defended = eff_pp < -0.3
    if up and defended:
        return "원자재 상승(U)을 판가·믹스로 방어(F) — 전가력 있음"
    if up and not defended:
        return "원자재 상승(U)이 원가로 전이 — 전가력 약함"
    if not up and eff_pp > 0.3:
        return "원자재는 안정인데 원가율 악화 — 효율·믹스 점검 필요"
    return "원자재·효율 모두 중립"


def list_companies() -> list[dict]:
    """레벨1 회사 목록(업종 태그 포함). 티커로 그룹.

    개요라 **DART 실측을 조회하지 않는다**(회사당 DuckDB 쿼리 222회 → 목록 4초).
    목록의 원가율/영익은 수작업 KB 추정 평균이고, 정확한 DART 실측값은 회사를
    클릭한 상세(``analyze``)에서 표시한다.

    단, 야간 배치(I1)가 돌아 ``company_costmodels.json`` 이 있으면 그 실측값으로
    덮어쓴다 — 파일 읽기 한 번이라 목록 속도는 그대로다.
    """
    models = _all_models()
    batch = (load_batch() or {}).get("companies") or {}
    by_ticker: dict[str, list[tuple[str, dict]]] = {}
    for pid, m in models.items():
        by_ticker.setdefault(m["ticker"], []).append((pid, m))

    out = []
    for ticker, items in by_ticker.items():
        mods = [m for _, m in items]
        sector = ue._SECTOR_BY_ID.get(items[0][0], ue.AUTO_SECTOR)
        row = {
            "ticker": ticker,
            "company": mods[0]["company"],
            "sector": sector,
            "n_products": len(items),
            "cogs_ratio": _avg(mods, "cogs"),   # 추정 평균(빠름) — 상세에서 DART 실측
            "op_margin": _avg(mods, "op"),
            "basis": "개요(추정)",
        }
        b = batch.get(ticker)
        if b and b.get("basis") == "DART 실측":
            yr = " · FY%s" % b["year"] if b.get("year") else ""
            row.update({
                "cogs_ratio": b["cogs_ratio"],
                "op_margin": b["op_margin"],
                "basis": "배치(DART 실측%s)" % yr,
                "production_type": b.get("production_type"),
                "verdict": b.get("verdict"),
            })
        out.append(row)
    out.sort(key=lambda x: (x["sector"], x["company"]))
    return out


def sectors() -> list[str]:
    """업종 필터용 유니크 섹터 목록(정렬)."""
    return sorted({c["sector"] for c in list_companies()})


# --- I1: 전 종목 야간 배치 + 캐시 -----------------------------------------
# 목록(레벨1)은 속도 때문에 DART 를 조회하지 않고 수작업 KB 추정 평균을 쓴다.
# 배치가 밤에 전 종목 ``analyze`` 를 돌려 실측값을 파일에 채워 두면, 목록이 그
# 실측값으로 덮어써진다(사용자 대기 없음). 주기 결정: **매일 야간 1회**
# (docs/원가분석_개편계획.md §8) — 재무제표는 분기지만 원자재 시세·차이분해는
# 매일 바뀌므로 하루 1회가 적정.
_BATCH_NAME = "company_costmodels.json"
_batch_cache: dict = {"mtime": None, "data": None}
_batch_lock = threading.Lock()


def _batch_path():
    return get_settings().data_dir / _BATCH_NAME


def _batch_row(a: dict) -> dict:
    """배치 파일에 남길 회사 1개 요약(전체 analyze 응답은 무겁다)."""
    v = a.get("variance") or {}
    ja = a.get("joint_allocation") or {}
    sa = a.get("statement_audit") or {}
    lb = (a.get("labor") or {}).get("current") or {}
    rn = (a.get("report_notes") or {}).get("audit") or {}
    return {
        "company": a["company"],
        "sector": a["sector"],
        "cogs_ratio": a["summary"]["cogs_ratio"],
        "op_margin": a["summary"]["op_margin"],
        "revenue_eok": a["summary"].get("revenue_eok"),
        "basis": a["basis"]["source"],
        "year": a["basis"].get("year"),
        "n_products": len(a.get("products") or []),
        "production_type": (a.get("production_type") or {}).get("type"),
        "joint_products": len(ja.get("products") or []),
        "price_variance_pp": v.get("price_variance_pp"),
        "efficiency_pp": v.get("efficiency_pp"),
        "verdict": v.get("verdict"),
        "recon_status": (a.get("reconciliation") or {}).get("status"),
        # 아래 4개는 F1(전 종목 재무제표 이상 랭킹)의 재료 — 배치가 밤에 미리 계산해 둔다.
        "audit_score": sa.get("score"),
        "audit_verdict": sa.get("verdict"),
        "audit_opinion": rn.get("opinion"),
        "headcount": lb.get("headcount"),
        "avg_salary": lb.get("avg_salary"),
        "material_ratio_of_cogs": v.get("material_ratio_of_cogs"),
        "coverage": a.get("coverage"),
    }


def build_batch(sleep_sec: float | None = None, tickers: list[str] | None = None) -> dict:
    """전 종목 원가모델을 돌려 ``data/company_costmodels.json`` 을 원자적으로 교체.

    종목마다 DART 사업보고서 파싱이 붙으므로 ``sleep_sec`` 만큼 쉬며 진행한다
    (DART rate limit 준수). 한 종목이 실패해도 나머지는 계속 간다.
    """
    s = get_settings()
    if sleep_sec is None:
        sleep_sec = s.costmodel_batch_sleep
    t0 = time.time()
    if tickers is None:
        tickers = sorted({m["ticker"] for m in _all_models().values()})

    rows: dict[str, dict] = {}
    errors: list[dict] = []
    for t in tickers:
        try:
            rows[t] = _batch_row(analyze(t))
        except Exception as e:
            errors.append({"ticker": t, "error": f"{type(e).__name__}: {str(e)[:80]}"})
        if sleep_sec:
            time.sleep(sleep_sec)

    payload = {
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "as_of": commodities.AS_OF,
        "n_companies": len(rows),
        "n_errors": len(errors),
        "elapsed_sec": round(time.time() - t0, 1),
        "errors": errors[:20],
        "companies": rows,
    }
    path = _batch_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    os.replace(tmp, path)
    with _batch_lock:
        _batch_cache["mtime"] = None      # 다음 조회 때 다시 읽도록
    return {k: v for k, v in payload.items() if k != "companies"}


def load_batch() -> dict | None:
    """배치 결과 로드(파일 mtime 기준 메모리 캐시). 없으면 None."""
    path = _batch_path()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    with _batch_lock:
        if _batch_cache["mtime"] == mtime:
            return _batch_cache["data"]
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None
    with _batch_lock:
        _batch_cache["mtime"] = mtime
        _batch_cache["data"] = data
    return data


def batch_status() -> dict:
    """배치 파일 메타(있는지·언제·몇 개·실패 몇 건)."""
    b = load_batch()
    if not b:
        return {"available": False, "path": str(_batch_path())}
    return {
        "available": True,
        "path": str(_batch_path()),
        **{k: b[k] for k in ("built_at", "as_of", "n_companies", "n_errors", "elapsed_sec") if k in b},
        "errors": b.get("errors", []),
    }


# --- P1: DART 사업보고서 품목별 매출구성 자동 발굴 -------------------------
_products_cache: dict[str, dict] = {}
_products_lock = threading.Lock()
_PROD_TTL = 6 * 3600  # 6시간 (사업보고서는 자주 안 바뀜)


_SKIP_NAME = re.compile(r"^(소계|합계|계|구분|부문|주요제품|제품|품목|비고|기타|총계|-)$")
_NOISE_NAME = re.compile(r"(총계|합계|소계|내부거래|제거|부문간|조정|공통및기타|연결조정|해당없음|"
                         r"사외이사|참석|여부|이사회|감사|위원|주주|파생상품|이자율|변동성|평가|처분|"
                         r"부원료|원료|철스크랩|합금철|레미콘|시멘트|용역)")
_CHAN_NAME = re.compile(r"(대리점|온라인|직거래|슈퍼|백화점|편의점|수출|내수|국내|아시아|유럽|미주|"
                        r"미국|중국|일본|기타지역|직영|도매|소매|양판)")
_SEG_NAME = re.compile(r"(부문|사업|의약품|반도체|화학|철강|건설|금융|증권|카드|생명|손해|바이오|"
                       r"디스플레이|배터리|소재|엔터|게임|통신|플랫폼)")


def _dedupe(raw: list[dict], cap: int = 10) -> list[dict]:
    seen, out = set(), []
    for p in raw:
        nm = p["name"]
        if not nm or nm in seen:
            continue
        seen.add(nm)
        out.append(p)
        if len(out) >= cap:
            break
    return out


def _clean_name(cells: list[str]) -> str | None:
    for c in cells:
        cc = re.sub(r"\s+", "", c)
        if re.search(r"[가-힣A-Za-z]", cc) and not _SKIP_NAME.match(cc) and not re.fullmatch(r"[\d.,%()]+", cc):
            return cc
    return None


def _parse_segment_mix(txt: str) -> list[dict]:
    """부문/제품별 매출 '비중' 표 파싱(반도체·화학·바이오 등). 엄격 규칙 — 애매하면 빈 목록.

    깔끔한 부문표만 잡고, 유통·지역·거버넌스·원재료 표는 배제한다(쓰레기보다 [] 가 낫다).
    """
    from app.data.fundamentals import auto_costmodel as ac
    best, best_score = [], -1e9
    for m in re.finditer(r"<TABLE\b.*?</TABLE>", txt, re.S | re.I):
        rows = ac._table_rows(m.group(0))
        if len(rows) < 2:
            continue
        head = " ".join(rows[0])
        if not (("비중" in head or "비율" in head)
                and any(k in head for k in ("부문", "제품", "품목", "매출", "매출유형"))):
            continue
        if any(k in head for k in ("원재료", "원료", "매입", "가격변동", "생산능력", "생산실적")):
            continue
        items, seen = [], set()
        for r in rows[1:]:
            nm = _clean_name(r)
            pct = ac._ratio_cell(r)
            if not nm or pct is None or nm in seen or _NOISE_NAME.search(nm) or pct >= 99.5:
                continue
            seen.add(nm)
            items.append({"name": nm, "pct": round(pct, 1)})
        if len(items) < 2:
            continue
        chan = sum(1 for x in items if _CHAN_NAME.search(x["name"]))
        if chan >= max(1, len(items) * 0.5):      # 유통/지역 표 배제
            continue
        seg = sum(1 for x in items if _SEG_NAME.search(x["name"]))
        s = sum(x["pct"] for x in items)
        score = seg * 8 + len(items) - abs(s - 100) / 25
        if score > best_score:
            best, best_score = items[:10], score
    return best


def dart_products(ticker: str) -> dict:
    """(P1) DART 사업보고서 「사업의 내용」 매출실적표 → 회사가 실제로 파는 품목·매출비중%.

    수작업 KB(품목 1~3개)의 한계를 넘어 **전 품목**을 공시에서 자동 발굴. 실패 시 빈 목록.
    """
    now = time.time()
    with _products_lock:
        c = _products_cache.get(ticker)
        if c and now - c["ts"] < _PROD_TTL:
            return c["data"]

    items: list[dict] = []
    try:
        from app.data.fundamentals import auto_costmodel as ac
        from app.data.fundamentals.dart import _load_corp_map, enabled
        if enabled():
            corp = _load_corp_map().get(ticker)
            rcept = ac._latest_business_rcept(corp) if corp else None
            txt = ac._fetch_main_xml(rcept) if rcept else None
            if txt:
                # 1) 원본 파서(가격변동추이 앵커) — 소비재 제품 매출현황에 강함
                raw = [{"name": re.sub(r"\s+", "", p["name"]), "pct": round(p["pct"], 1)}
                       for p in ac._parse_products(txt)
                       if p.get("name") and p.get("pct") and 0 < p["pct"] < 99.5]
                raw = [p for p in raw if not _NOISE_NAME.search(p["name"])]  # 원재료·노이즈 제거
                items = _dedupe(raw)
                # 2) 부족하면 부문별 매출비중 표 파싱(반도체·화학·바이오 등)
                if len(items) < 2:
                    items = _parse_segment_mix(txt)
    except Exception:
        items = []

    data = {
        "ticker": ticker,
        "products": items,
        "source": "DART 사업보고서 매출실적표(자동 파싱)" if items else "미공시/파싱실패",
        "coverage": "parsed" if items else "none",
    }
    with _products_lock:
        _products_cache[ticker] = {"ts": now, "data": data}
    return data


# --- 회사 상세 (레벨 2·3) --------------------------------------------------
def analyze(ticker: str) -> dict:
    """회사 1개의 통합 분석: 품목별 원가·영익 + 원재료 시세 + 마진 정합성 + 재무근거."""
    models = _all_models()
    items = [(pid, m) for pid, m in models.items() if m["ticker"] == ticker]
    if not items:
        raise KeyError(ticker)

    company = items[0][1]["company"]
    mods = [m for _, m in items]
    ratios, basis = _company_ratios(ticker, mods)
    sector = ue._SECTOR_BY_ID.get(items[0][0], ue.AUTO_SECTOR)

    # ① 품목별 원가·영익 — 기존 teardown 재사용
    products: list[dict] = []
    for pid, m in items:
        try:
            td = ue.teardown(pid)
        except Exception:
            continue
        s = td["summary"]
        top = sorted(td["materials"], key=lambda x: x["won"], reverse=True)[:3]
        products.append({
            "id": pid,
            "product": m["product"],
            "unit": m["unit"],
            "retail_price": s["retail_price"],
            "cogs_ratio": s["cogs_ratio"],
            "op_margin": s["op_margin"],
            "profit_per_unit": s["profit_per_unit"],
            "top_materials": [t["item"] for t in top],
            "material_names": [t.get("commodity") or t["item"] for t in top],
        })
    products.sort(key=lambda x: x["op_margin"], reverse=True)

    # ② 회사 전체 원재료 묶음 — 품목별 material_mix 를 커모디티 기준 집계(등가중)
    materials = _company_materials(mods, ratios["cogs"])

    # ③ 마진 정합성: 품목 영익(평균) ↔ 회사 보고 영익
    bottom_up = round(sum(p["op_margin"] for p in products) / len(products), 4) if products else 0.0
    reported = ratios["op"]
    gap_pp = round((bottom_up - reported) * 100, 1)
    a = abs(gap_pp)

    # 적자기업 판별: 큰 gap 의 상당수는 '가정오류'가 아니라 전사 영업적자
    # (R&D 소진·가동률 저하·일회성) 때문 → 품목 추정 마진으로는 설명 불가.
    loss_making = reported < 0
    if loss_making and a > 5:
        status = "loss"
        if reported <= -0.5:
            reason = "대규모 영업적자(적자율 %.0f%%) — 매출 대비 R&D·비용이 압도, 품목 추정 마진으론 설명 불가" % (reported * 100)
        elif reported <= -0.10:
            reason = "영업적자 — 가동률 저하·일회성·R&D 부담 등 전사 손실이 품목 마진에 미반영"
        else:
            reason = "영업적자 전환 — 품목 추정(정상가동 가정)과 실적 괴리"
    else:
        status = "ok" if a <= 2 else ("warn" if a <= 5 else "mismatch")
        reason = ("정합(±2%p)" if status == "ok"
                  else "품목 매출비중 미반영 등 가정 편차(±5%p 이내)" if status == "warn"
                  else "가정 편차 큼 — 품목 매출비중·부문 원가율 점검 필요")

    reconciliation = {
        "bottom_up_op_margin": bottom_up,
        "reported_op_margin": reported,
        "gap_pp": gap_pp,
        "status": status,                # ok | warn | mismatch | loss
        "loss_making": loss_making,
        "reason": reason,
        "assumptions": [
            f"부문 원가율 = 회사평균 {ratios['cogs']*100:.1f}% 상속",
            "가공비 = 매출원가에서 원재료비 제외분",
            "품목별 영익 단순평균(매출비중 미반영 — DART 연결 시 가중평균)"
            if basis["source"] != "DART 실측" else "판관비 = DART 실측",
        ],
    }

    # Phase A: 3개년 손익 실측
    financials_3y = income_ratios_3y(ticker)

    # 사업보고서 원문 실측(비용의 성격별 분류 · 감사보고서) — 추정을 실측으로 대체
    try:
        notes = report_notes.notes(ticker)
    except Exception:
        notes = None

    # B3·B4: 사업의 내용 — 실제 단가 변동 + 생산 물량·가동률
    try:
        biz = report_business.business(ticker)
    except Exception:
        biz = None

    # Phase B: 표준(기준)원가 vs 실제 원가차이 분해(최근 1년) — 재료비 비중은 주석 실측 우선
    variance = _variance(mods, financials_3y, notes)

    # Phase C(C2·C3): 생산유형 태깅 + 결합원가 배분(연산·등급 업종만)
    ptype = joint_costing.production_type(ticker, sector)
    joint_allocation = _joint_allocation(ticker, sector, financials_3y, ratios, basis)

    # W1: 노무비(인건비) 레이어 — DART 직원현황 실측 + 노동생산성 + 조작탐지 플래그
    try:
        labor = labor_cost.analyze(ticker, financials_3y, notes)
    except Exception:
        labor = None

    # 재무제표 3종 감사 — 커버리지 + 정합성 + 감사보고서(의견·KAM) + 물량 대조(B4)
    try:
        vol = report_business.volume_check(biz, financials_3y)
        audit = statement_audit.audit(ticker, notes, [vol] if vol else None)
    except Exception:
        audit = None

    # 레벨3 재무제표 근거
    financials_detail = _financials_detail(ticker, ratios, basis)

    return {
        "ticker": ticker,
        "company": company,
        "sector": sector,
        "as_of": commodities.AS_OF,
        "basis": basis,
        "summary": {
            "cogs_ratio": ratios["cogs"],
            "sga_ratio": ratios["sga"],
            "op_margin": ratios["op"],
            "revenue_eok": round(basis["sales"] / 1e8) if basis.get("sales") else None,
        },
        "financials_3y": financials_3y,          # Phase A
        "variance": variance,                    # Phase B
        "production_type": ptype,                # C2
        "joint_allocation": joint_allocation,    # C3
        "labor": labor,                          # W1 (§12)
        "statement_audit": audit,                # 재무제표 3종 감사
        "report_notes": notes,                   # 사업보고서 원문 실측(성격별 비용·감사의견)
        "business": biz,                         # B3·B4 실단가·생산물량·가동률
        "products": products,
        "materials": materials,
        "reconciliation": reconciliation,
        "financials_detail": financials_detail,
        "company_block": ue._company_block(ticker),
        "coverage": {
            "products": "curated" if all(pid in ue.PRODUCTS for pid, _ in items) else "auto",
            "sales_mix": "missing",   # DART 연결 시 parsed
            "financials": "dart" if basis["source"] == "DART 실측" else "estimate",
            "financials_3y": "dart" if len(financials_3y) >= 2 else "insufficient",
            "variance": "estimate" if variance else "unavailable",
            "joint_allocation": "estimate" if joint_allocation else (
                "no-mix" if ptype["is_joint"] else "not-applicable"),
            "labor": (labor or {}).get("coverage", "unavailable"),
            "statement_audit": "ok" if (audit or {}).get("available") else "unavailable",
            "report_notes": "parsed" if (notes or {}).get("available") else "unavailable",
            "business": "parsed" if (biz or {}).get("available") else "unavailable",
        },
    }


def _joint_allocation(ticker: str, sector: str, fin3y: list[dict],
                      ratios: dict, basis: dict) -> dict | None:
    """C3: 결합원가(=매출원가) 를 사업보고서 품목 매출비중으로 배분(상대판매가치법).

    매출·매출원가는 DART 3개년 최신연도 우선, 없으면 ``basis`` 의 단년 실측.
    품목 매출비중이 없으면(파싱 실패) 배분하지 않는다 — 근거 없이 만들지 않는다.
    """
    if fin3y:
        rev = fin3y[0]["revenue_eok"]
        cogs = rev * fin3y[0]["cogs_ratio"]
    elif basis.get("sales"):
        rev = round(basis["sales"] / 1e8)
        cogs = rev * ratios["cogs"]
    else:
        return None
    # 파싱된 매출구성엔 품목(정유부문·윤활부문)과 판매채널·지역(내수·수출)이 섞여 들어올
    # 때가 있다. 채널·지역 행을 그대로 두면 같은 매출을 두 번 세어 배분이 망가지므로
    # 제거하고 남은 품목만 100% 로 재정규화한다(_norm).
    mix = [p for p in (dart_products(ticker).get("products") or [])
           if not _CHAN_NAME.search(p.get("name", ""))]
    return joint_costing.allocate(ticker, sector, cogs, rev, mix)


def _company_materials(mods: list[dict], cogs_ratio: float) -> list[dict]:
    """회사 품목들의 원재료를 커모디티 기준으로 집계 → 매출원가내 비중 + 현재 시세."""
    agg: dict[str, dict] = {}
    for m in mods:
        mat_of_cogs = m.get("material_ratio_of_cogs", 0.8)
        for x in m.get("material_mix", []):
            key = x.get("commodity") or f"__{x['item']}"
            w = x["weight"] * mat_of_cogs
            if key not in agg:
                agg[key] = {"item": x["item"], "commodity": x.get("commodity"), "w": 0.0}
            agg[key]["w"] += w
    tot = sum(v["w"] for v in agg.values()) or 1.0
    out = []
    for v in agg.values():
        c = commodities.get(v["commodity"]) if v["commodity"] else None
        out.append({
            "item": v["item"],
            "pct_of_cogs": round(v["w"] / tot * 100, 1),
            "commodity": c["name_ko"] if c else None,
            "commodity_key": v["commodity"],
            "price": c["price"] if c else None,
            "unit": c["unit"] if c else None,
            "chg_1y": c["chg_1y"] if c else None,
            "direction": c["direction"] if c else None,
        })
    out.sort(key=lambda x: x["pct_of_cogs"], reverse=True)
    return out


def _financials_detail(ticker: str, ratios: dict, basis: dict) -> dict:
    """레벨3: 손익계산서 원장에서 매출→원가→판관→영익이 어떻게 나왔는지."""
    sales = basis.get("sales")
    if sales:
        eok = lambda v: round(v / 1e8)  # noqa: E731
        return {
            "source": "DART 손익계산서",
            "year": basis.get("year"),
            "rows": [
                {"label": "매출액", "eok": eok(sales), "pct": 100.0},
                {"label": "매출원가", "eok": eok(sales * ratios["cogs"]), "pct": round(ratios["cogs"] * 100, 1)},
                {"label": "판매관리비", "eok": eok(sales * ratios["sga"]), "pct": round(ratios["sga"] * 100, 1)},
                {"label": "영업이익", "eok": eok(sales * ratios["op"]), "pct": round(ratios["op"] * 100, 1)},
            ],
            "note": f"가공비=매출원가의 일부. 부문 원가율=회사평균 {ratios['cogs']*100:.1f}% 상속.",
        }
    # 실측 없음 → 매출 1,000원 기준 비율 설명
    return {
        "source": "추정(DART 미연결 — 수작업 KB 비율)",
        "year": None,
        "rows": [
            {"label": "매출(기준)", "eok": None, "pct": 100.0},
            {"label": "매출원가", "eok": None, "pct": round(ratios["cogs"] * 100, 1)},
            {"label": "판매관리비", "eok": None, "pct": round(ratios["sga"] * 100, 1)},
            {"label": "영업이익", "eok": None, "pct": round(ratios["op"] * 100, 1)},
        ],
        "note": "DART_API_KEY 설정 시 손익계산서 실측 금액(억원)으로 대체됩니다.",
    }
