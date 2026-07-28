"""노무비(인건비) 레이어 — "사람값"을 원가표에 넣는다 (개편계획 §12 / W1).

원가는 **재료비 + 노무비 + 경비**인데 지금까지 우리는 재료비만 정밀했다.
노무비는 추정할 필요가 없다 — DART가 **법정 공시**한다:

  empSttus.json (사업보고서 「직원 등의 현황」)
    → 사업부문별 직원수 · 연간급여총액 · 1인평균급여 · 평균근속 · 정규/계약직

여기서 3개년을 받아(§12.3):
  [식4] 총인건비   L      = Σ(부문 직원수 × 부문 1인평균급여)
  [식5] 제조노무비 L_mfg  = L × (생산부문 인원 ÷ 전체 인원)
  [식6] 단위노무비        = L_mfg ÷ 생산수량      ← 생산실적 파서(B4) 붙으면 활성

그리고 인건비는 **분식의 단골 통로**라 조작 탐지에 쓴다(§12.5):
  ⑤ 인건비 자본화  : 인원은 그대로인데 비용화 인건비 급감 + 개발비 급증 → 이익 부풀리기
  ⑦ 인당지표 급변  : 인원·설비 안 늘었는데 인당매출 급증 → 매출 부풀리기 방증

**인원 수는 못 숨긴다.** 그래서 이 축이 재무제표를 감시할 수 있다.
"""
from __future__ import annotations

import json
import time

import requests

from app.core.config import get_settings
from app.data.fundamentals.dart import _load_corp_map, enabled
from app.data.infra import store

_BASE = "https://opendart.fss.or.kr/api"
_TTL = 30 * 24 * 3600.0          # 30일 (사업보고서는 연 1회)
_WORK_HOURS = 2000               # 연근로시간 상수(식6 분모) — 개편계획 §8 열린질문

# 공시 행 중 '합계' 성격(= 부문 행과 중복 계상되므로 부문에서 제외)
_TOTAL_KW = ("합계", "소계", "총계", "전체", "전사")

# fo_bbm 이 **직능**(사무직/생산직)인지 **사업부문**(DS/DX·정유부문)인지 판별.
# 사업부문 기준이면 생산/비생산 분리가 불가능하다 → 제조노무비를 지어내지 않는다.
_JOB_EXACT = ("생산", "제조", "사무", "영업", "관리", "연구", "기술", "현장",
              "기능", "판매", "서비스", "노무")
_MFG_KW = ("생산", "제조", "기능", "현장", "공장", "기술", "정비")
_RND_KW = ("연구", "개발")


def _cache_path(ticker: str):
    d = get_settings().data_dir / "dart_business"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"labor_{ticker}.json"


def _int(s) -> int:
    try:
        return int(float(str(s).replace(",", "").strip()))
    except (TypeError, ValueError):
        return 0


def _f(s) -> float | None:
    try:
        v = float(str(s).replace(",", "").strip())
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def _latest_fy() -> int:
    """가장 최근 '확정 사업연도'(사업보고서는 3월 말 제출 → 4월 이후 전년도 확정)."""
    y, m = int(time.strftime("%Y")), int(time.strftime("%m"))
    return y - 1 if m >= 4 else y - 2


def _is_total(name: str) -> bool:
    """'성별합계'처럼 부문 행과 중복되는 총계 행인가."""
    n = name.replace(" ", "")
    return n == "계" or any(k in n for k in _TOTAL_KW)


def _is_job_type(name: str) -> bool:
    """직능 구분(사무직·생산직)인가. 사업부문(DS·정유부문·식품제조)이면 False."""
    n = name.replace(" ", "")
    return n.endswith("직") or n in _JOB_EXACT


def _seg_kind(name: str, job_type: bool) -> str:
    """직능 구분일 때만 생산/연구/관리로 나눈다. 사업부문이면 '사업부문'."""
    if not job_type:
        return "사업부문"
    n = name.replace(" ", "")
    if any(k in n for k in _RND_KW):
        return "연구"
    if any(k in n for k in _MFG_KW):
        return "생산"
    return "관리·영업"


def _agg(rows: list[dict]) -> dict[str, dict]:
    """공시 행(부문×성별) → 부문별 집계."""
    out: dict[str, dict] = {}
    for it in rows:
        seg = (it.get("fo_bbm") or "기타").strip() or "기타"
        d = out.setdefault(seg, {"name": seg, "headcount": 0, "annual_labor": 0,
                                 "regular": 0, "contract": 0, "_tsum": 0.0, "_tw": 0,
                                 "_jsum": 0.0, "_jw": 0})
        n = _int(it.get("sm"))
        d["headcount"] += n
        d["annual_labor"] += _int(it.get("fyer_salary_totamt"))
        d["regular"] += _int(it.get("rgllbr_co"))
        d["contract"] += _int(it.get("cnttk_co"))
        t = _f(it.get("avrg_cnwk_sdytrn"))
        if t and n:
            d["_tsum"] += t * n
            d["_tw"] += n
        j = _f(it.get("jan_salary_am"))          # 공시된 1인평균급여액(교차검증용)
        if j and n:
            d["_jsum"] += j * n
            d["_jw"] += n
    return out


def _emp_year(corp: str, year: int) -> dict | None:
    """한 사업연도의 직원현황 → 부문별 집계. 공시 없으면 None.

    주의 2가지(실제 공시를 보고 교정한 부분):
      · '성별합계' 같은 **총계 행이 부문 행과 함께** 오는 회사(삼성전자)가 있다.
        총계를 부문에 섞으면 인원이 2배가 된다 → 총계는 폴백으로만 쓴다.
      · fo_bbm 은 대개 **사업부문**(DS·DX·정유부문)이지 직능이 아니다 →
        생산/비생산 분리가 불가능하므로 mfg_ratio 를 만들지 않는다(지어내지 않기).
    """
    try:
        r = requests.get(f"{_BASE}/empSttus.json", params={
            "crtfc_key": get_settings().dart_api_key, "corp_code": corp,
            "bsns_year": str(year), "reprt_code": "11011"}, timeout=30)
        j = r.json()
    except Exception:
        return None
    if j.get("status") != "000":
        return None
    rows = j.get("list") or []
    if not rows:
        return None

    segs = _agg([r for r in rows if not _is_total((r.get("fo_bbm") or "").strip())])
    tots = _agg([r for r in rows if _is_total((r.get("fo_bbm") or "").strip())])
    if not segs:                                  # 총계만 공시한 회사
        segs, tots = tots, {}

    job_type = any(_is_job_type(n) for n in segs)
    by_segment = []
    for d in segs.values():
        head, labor = d["headcount"], d["annual_labor"]
        by_segment.append({
            "name": d["name"], "kind": _seg_kind(d["name"], job_type),
            "headcount": head or None, "annual_labor": labor or None,
            "avg_salary": (labor // head) if (head and labor) else None,
            "tenure": round(d["_tsum"] / d["_tw"], 1) if d["_tw"] else None,
            "regular": d["regular"] or None, "contract": d["contract"] or None,
        })
    by_segment.sort(key=lambda x: x["headcount"] or 0, reverse=True)

    head = sum(s["headcount"] or 0 for s in by_segment)
    labor = sum(s["annual_labor"] or 0 for s in by_segment)
    contract = sum(s["contract"] or 0 for s in by_segment)
    src = "DART 직원 등의 현황(empSttus)"
    if not labor and tots:                        # 급여총액을 총계 행에만 적은 회사
        labor = sum(d["annual_labor"] for d in tots.values())
        src += " · 급여총액은 총계 행"
    if not head and tots:
        head = sum(d["headcount"] for d in tots.values())

    # 공시된 1인평균급여액(가중) — 계산값(총액÷인원)과 교차검증용
    src_j = segs if any(d["_jw"] for d in segs.values()) else tots
    jw = sum(d["_jw"] for d in src_j.values())
    disclosed = round(sum(d["_jsum"] for d in src_j.values()) / jw) if jw else None

    avg = (labor // head) if (head and labor) else None
    mfg_head = sum(s["headcount"] or 0 for s in by_segment if s["kind"] == "생산")
    return {
        "year": year,
        "headcount": head or None,
        "annual_labor": labor or None,
        "annual_labor_eok": round(labor / 1e8) if labor else None,
        "avg_salary": avg,
        "avg_salary_disclosed": disclosed,
        "hourly_cost": round(avg / _WORK_HOURS) if avg else None,   # 식6용 1인시 원가
        # 식5 — 직능 공시일 때만. 사업부문 공시면 None(분리 불가).
        "mfg_ratio": round(mfg_head / head, 3) if (job_type and head) else None,
        "mfg_labor_eok": round(labor * mfg_head / head / 1e8) if (job_type and head and labor) else None,
        "mfg_basis": "직능(사무직/생산직) 공시" if job_type else "사업부문 공시 — 생산/비생산 분리 불가",
        "contract_ratio": round(contract / head, 3) if head else None,
        "by_segment": by_segment,
        "source": src,
    }


def labor_3y(ticker: str) -> list[dict]:
    """최근 3개 사업연도 인건비 실측(내림차순). 디스크 캐시. 실패 시 []."""
    cp = _cache_path(ticker)
    if cp.exists():
        try:
            d = json.loads(cp.read_text(encoding="utf-8"))
            if time.time() - d.get("_ts", 0) < _TTL:
                return d.get("years") or []
        except Exception:
            pass
    if not enabled():
        return []
    corp = _load_corp_map().get(ticker)
    if not corp:
        return []

    fy = _latest_fy()
    out: list[dict] = []
    for y in (fy, fy - 1, fy - 2, fy - 3):     # 최신 연도 미공시 대비 1년 여유
        d = _emp_year(corp, y)
        if d:
            out.append(d)
        if len(out) >= 3:
            break
    try:
        cp.write_text(json.dumps({"years": out, "_ts": time.time()}, ensure_ascii=False),
                      encoding="utf-8")
    except Exception:
        pass
    return out


# --- 무형자산(개발비) — 인건비 자본화 탐지용 -------------------------------
def _intangible_dev(ticker: str) -> dict[int, float]:
    """연도별 개발비(없으면 무형자산) 잔액. {year: amount}."""
    try:
        df = store.dart_financials(ticker)
    except Exception:
        return {}
    if df is None or df.empty:
        return {}
    bs = df[df["sj_div"] == "BS"]
    if bs.empty:
        return {}
    for names in (("개발비",), ("무형자산", "무형자산 합계")):
        sub = bs[bs["account_nm"].isin(names)]
        if not sub.empty:
            out: dict[int, float] = {}
            for _, r in sub.iterrows():
                y = int(r["year"])
                out[y] = max(out.get(y, 0.0), float(r["amount"]))
            return out
    return {}


def _flags(hist: list[dict], fin3y: list[dict], dev: dict[int, float]) -> list[dict]:
    """§12.5 인건비 기반 조작 탐지 ⑤⑦ + 인력구조 변화 신호."""
    out: list[dict] = []
    if len(hist) < 2:
        return out
    cur, prev = hist[0], hist[1]
    fin = {f["year"]: f for f in fin3y}

    def chg(a, b):
        return (a - b) / b if (a and b) else None

    head_chg = chg(cur.get("headcount"), prev.get("headcount"))
    labor_chg = chg(cur.get("annual_labor"), prev.get("annual_labor"))

    # ⑤ 인건비 자본화 의심 — 인원 유지·증가 + 인건비 급감 + 개발비 급증
    dev_chg = chg(dev.get(cur["year"]), dev.get(prev["year"]))
    if (head_chg is not None and labor_chg is not None
            and head_chg >= -0.02 and labor_chg <= -0.08):
        detail = f"인원 {head_chg*100:+.1f}% / 인건비 {labor_chg*100:+.1f}%"
        sev = "warn"
        if dev_chg is not None and dev_chg >= 0.15:
            detail += f" / 개발비 {dev_chg*100:+.1f}%"
            sev = "alert"
        out.append({"type": "인건비 자본화 의심", "severity": sev, "detail": detail,
                    "why": "인원은 그대로인데 비용화 인건비만 줄면 인건비를 자산(개발비)으로 "
                           "돌려 이익을 부풀렸을 수 있다. 인원 수는 못 숨긴다."})

    # ⑦ 인당매출 급증 — 인원·설비 증가 없이 매출만 뛰면 매출 부풀리기 방증
    rc, rp = fin.get(cur["year"]), fin.get(prev["year"])
    if rc and rp and cur.get("headcount") and prev.get("headcount"):
        rph_c = rc["revenue_eok"] / cur["headcount"]
        rph_p = rp["revenue_eok"] / prev["headcount"]
        d = chg(rph_c, rph_p)
        if d is not None and d >= 0.30 and (head_chg or 0) <= 0.05:
            out.append({"type": "인당매출 급증", "severity": "warn",
                        "detail": f"인당매출 {d*100:+.1f}% (인원 {(head_chg or 0)*100:+.1f}%)",
                        "why": "인원이 안 늘었는데 인당매출이 급증 — 실제 생산능력으로 "
                               "설명되는지 매출 물량(생산실적)과 교차검증 필요."})

    # 인력구조: 구조조정 / 대량채용
    if head_chg is not None and head_chg <= -0.08:
        out.append({"type": "인원 급감(구조조정)", "severity": "info",
                    "detail": f"인원 {head_chg*100:+.1f}%",
                    "why": "일회성 퇴직급여로 당기 비용이 튀고 이듬해 이익이 좋아 보일 수 있다."})
    if (cur.get("contract_ratio") or 0) >= 0.20:
        out.append({"type": "계약직 비중 높음", "severity": "info",
                    "detail": f"계약직 {cur['contract_ratio']*100:.0f}%",
                    "why": "공시 평균급여가 실제 정규직 임금보다 낮게 보인다. 하청(소속 외) "
                           "규모까지 봐야 진짜 인건비가 나온다(W3)."})
    return out


def analyze(ticker: str, fin3y: list[dict] | None = None,
            notes: dict | None = None) -> dict:
    """(W1) 회사 인건비 블록 — 3년 실측 + 노동생산성 + 조작탐지 플래그.

    ``fin3y`` 는 ``company_costmodel.income_ratios_3y`` 결과(있으면 재조회 안 함).
    ``notes`` 는 ``report_notes.notes`` — 사업보고서 「비용의 성격별 분류」의 **연결 종업원급여**.
    empSttus 는 보통 **국내 별도** 기준이라, 둘의 차이가 곧 해외·연결 인력 규모다.
    """
    hist = labor_3y(ticker)
    if fin3y is None:
        from app.data.fundamentals import company_costmodel as cc
        fin3y = cc.income_ratios_3y(ticker)
    fin = {f["year"]: f for f in (fin3y or [])}

    # 노동생산성(§12.6) — 연도별
    prod = []
    for h in hist:
        f = fin.get(h["year"])
        head, labor = h.get("headcount"), h.get("annual_labor")
        if not (f and head):
            continue
        rev_eok = f["revenue_eok"]
        op_eok = rev_eok * f["op_margin"] if f.get("op_margin") is not None else None
        prod.append({
            "year": h["year"],
            "rev_per_head_eok": round(rev_eok / head, 2),
            "op_per_head_eok": round(op_eok / head, 3) if op_eok is not None else None,
            "labor_to_revenue": round(labor / (rev_eok * 1e8), 4) if labor else None,
            "labor_to_cogs": round(labor / (rev_eok * 1e8 * f["cogs_ratio"]), 4)
            if (labor and f.get("cogs_ratio")) else None,
        })

    dev = _intangible_dev(ticker) if hist else {}
    flags = _flags(hist, fin3y or [], dev)
    cur = hist[0] if hist else None

    # 연결 총급여(주석 실측) vs 공시 직원급여(국내) — 차이 = 해외·연결 인력 몫
    cons = None
    cn = (notes or {}).get("cost_nature") or {}
    if cn.get("labor_eok") and cur and cur.get("annual_labor"):
        dom = cur["annual_labor"] / 1e8
        cons = {
            "consolidated_labor_eok": cn["labor_eok"],
            "disclosed_domestic_eok": round(dom),
            # 지주사(포스코홀딩스)는 '해외'가 아니라 **국내 자회사** 몫이 대부분이다 → 중립 표현.
            "subsidiary_share": round(max(0.0, 1 - dom / cn["labor_eok"]), 3)
            if cn["labor_eok"] else None,
            "source": "「비용의 성격별 분류」 종업원급여(연결) vs 직원 등의 현황(제출법인)",
            "note": "연결 인건비가 훨씬 크면 인력의 대부분이 자회사(국내·해외)에 있다는 뜻. "
                    "지주회사면 사실상 전부가 자회사 몫이다.",
        }

    return {
        "ticker": ticker,
        "years": hist,                       # 🟢 3년 실측(부문별 포함)
        "current": cur,
        "productivity": prod,                # §12.6
        "flags": flags,                      # §12.5 ⑤⑦
        "consolidated": cons,                # 주석 실측(연결) vs 공시(국내)
        "outsourced": None,                  # W3: 고용형태공시(소속 외 근로자) 미연동
        "market_salary": None,               # W4: 취업사이트 교차검증 미연동
        "unit_labor": None,                  # W2/B4: 생산실적 붙으면 단위노무비 산출
        "assumptions": [
            f"연근로시간 {_WORK_HOURS:,}h 기준 1인시 원가",
            (f"제조노무비 = 총인건비 × 생산부문 인원비중 ({cur['mfg_basis']})" if cur
             else "제조노무비 분리 근거 없음"),
            "하청(소속 외 근로자)·취업사이트 시장연봉 미반영 → 실제 인건비는 이보다 큼",
        ],
        "coverage": ("dart" if hist else ("no-key" if not enabled() else "missing")),
        "note": "DART 「직원 등의 현황」 법정 공시 실측. 하청 인건비는 여기에 잡히지 않는다(W3).",
    }
