"""관리종목·상장폐지 위험 스크리너 + 감사 정정(어닝쇼크) 공시 경보.

두 층위로 위험을 표시한다.

A. 재무요건 위험 (오프라인 · dart_financials 2015~ 다년치로 계산)
   - 영업손실 연속(코스닥 4년 관리 / 5년 상폐)
   - 매출액 미달(코스닥 30억 · 유가 50억, 2년 연속)
   - 자본잠식(자본잠식률 50%↑ 관리 / 완전자본잠식 상폐)
   - 법인세비용차감전계속사업손실 > 자기자본 50%(&10억↑) 최근3년 2회(코스닥)
   ※ 스팩·외국기업 제외, 기술성장기업부는 영업손실·매출 요건 유예 반영.

B. 감사 정정 경보 (라이브 DART 공시목록 스캔 · 디스크 캐시)
   상폐를 피하려 잠정 영업이익을 아슬아슬 흑자로 냈다가 감사에서 적자로 정정되는
   패턴을 공시 제목으로 포착: [정정]사업/분기보고서·감사보고서, 매출액또는손익구조
   30%이상변동, 관리종목지정·상장적격성실질심사·주권매매거래정지 등.

시장 구분(코스피/코스닥)·소속부(관리종목/투자주의환기/기술성장/스팩)는 FinanceDataReader
상장목록에서 받아 data/market_class.json 에 캐시한다.
"""
from __future__ import annotations

import json
import re
import threading
import time

from app.core.config import get_settings
from app.data.infra import store

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 1800.0  # 30분

# 매출액 관리·상폐 기준 (원)
_SALES_THR = {"KOSDAQ": 3e9, "KOSPI": 5e9}
_UNIT = 1e8  # 억


def _data_dir():
    return get_settings().data_dir


def _market_class_path():
    return _data_dir() / "market_class.json"


def _alerts_path():
    return _data_dir() / "delisting_alerts.json"


# ── 시장/소속부 분류 (FDR 상장목록) ─────────────────────────────────────────
def load_market_class() -> dict[str, dict]:
    p = _market_class_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("map", {})
    except Exception:
        return {}


def refresh_market_class() -> dict[str, dict]:
    """FinanceDataReader 로 코스피/코스닥 상장목록·소속부를 받아 캐시. (배치용)"""
    import FinanceDataReader as fdr

    out: dict[str, dict] = {}
    for mk in ("KOSPI", "KOSDAQ"):
        df = fdr.StockListing(mk)
        for r in df.to_dict("records"):
            code = str(r.get("Code") or "").zfill(6)
            if not code or code == "000000":
                continue
            out[code] = {"market": mk, "dept": str(r.get("Dept") or "").strip(),
                         "name": str(r.get("Name") or "").strip()}
    _market_class_path().write_text(
        json.dumps({"generated_at": _now(), "map": out}, ensure_ascii=False),
        encoding="utf-8")
    return out


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M")


# ── 재무 계정 추출 ──────────────────────────────────────────────────────────
_PREFIX = re.compile(r'^[\sⅠ-ⅩIVXivx0-9.\-()]+')
_SALES_PRI = ['매출액', '수익(매출액)', '영업수익', '매출']
_PRETAX_PRI = ['법인세비용차감전계속영업이익', '법인세비용차감전계속영업순이익(손실)',
               '법인세비용차감전순이익(손실)', '법인세비용차감전순이익', '법인세비용차감전이익(손실)']


def _norm(s: str) -> str:
    s = _PREFIX.sub('', (s or '').replace(' ', ''))
    return s.replace('(손실)', '').replace('(손익)', '')


def _series_map(conn=None) -> dict[str, dict]:
    """전 종목의 연도별 영업이익·매출·자본총계·자본금·법인세차감전손익. 단일 벌크 쿼리.

    conn 을 주면 해당 커넥션으로 조회(배치·검증용), 없으면 store 커넥션 사용."""
    placeholders = ",".join("?" for _ in _SALES_PRI + _PRETAX_PRI)
    sql = f"""
        SELECT ticker, sj_div, year, account_nm, amount
        FROM dart_financials
        WHERE amount IS NOT NULL AND (
            (sj_div IN ('IS','CIS') AND (
                account_nm LIKE '%영업이익%' OR account_nm IN ({placeholders})))
            OR (sj_div = 'BS' AND account_nm IN ('자본총계','자본금'))
        )
    """
    if conn is not None:
        df = conn.execute(sql, _SALES_PRI + _PRETAX_PRI).df()
    else:
        with store.connection() as c:
            df = c.execute(sql, _SALES_PRI + _PRETAX_PRI).df()

    out: dict[str, dict] = {}
    for r in df.to_dict("records"):
        tk, sj, yr, nm, amt = r["ticker"], r["sj_div"], int(r["year"]), r["account_nm"], r["amount"]
        d = out.setdefault(tk, {"op": {}, "sales": {}, "equity": {}, "capital": {},
                                "pretax": {}, "_srank": {}, "_prank": {}})
        if sj in ("IS", "CIS"):
            if _norm(nm) == "영업이익":
                d["op"][yr] = amt
            if nm in _SALES_PRI:
                rk = _SALES_PRI.index(nm)
                if yr not in d["_srank"] or rk < d["_srank"][yr]:
                    d["sales"][yr] = amt; d["_srank"][yr] = rk
            if nm in _PRETAX_PRI:
                rk = _PRETAX_PRI.index(nm)
                if yr not in d["_prank"] or rk < d["_prank"][yr]:
                    d["pretax"][yr] = amt; d["_prank"][yr] = rk
        elif sj == "BS":
            n = _norm(nm)
            if n == "자본총계":
                d["equity"][yr] = amt
            elif n == "자본금":
                d["capital"][yr] = amt
    return out


def _consec_loss(op: dict) -> int:
    """최신연도부터 연속 영업손실 연수."""
    n = 0
    for y in sorted(op, reverse=True):
        if op[y] < 0:
            n += 1
        else:
            break
    return n


# ── 위험 판정 ───────────────────────────────────────────────────────────────
def _assess(tk: str, ser: dict, cls: dict, name: str | None) -> dict | None:
    market = cls.get("market") or "KR"
    dept = cls.get("dept") or ""
    nm = name or cls.get("name") or tk
    # 스팩·외국기업은 상폐요건 대상 아님
    if "SPAC" in dept.upper() or "스팩" in nm or "외국기업" in dept:
        return None
    tech = "기술성장" in dept  # 기술특례: 영업손실·매출 요건 유예

    op, sales = ser["op"], ser["sales"]
    equity, capital, pretax = ser["equity"], ser["capital"], ser["pretax"]
    if not op and not sales and not equity:
        return None

    years = sorted(set(op) | set(sales) | set(equity), reverse=True)
    latest = years[0] if years else None
    reasons: list[dict] = []
    level = 0  # 0 안전 · 1 주의 · 2 관리위험 · 3 상폐위험

    def add(sev: int, text: str):
        nonlocal level
        level = max(level, sev)
        reasons.append({"sev": sev, "text": text})

    # 1. 영업손실 연속 (코스닥, 기술특례 유예)
    nloss = _consec_loss(op)
    if market == "KOSDAQ" and not tech:
        if nloss >= 5:
            add(3, f"영업손실 {nloss}년 연속 — 상폐 요건")
        elif nloss == 4:
            add(2, "영업손실 4년 연속 — 관리종목 요건")
        elif nloss == 3:
            add(1, "영업손실 3년 연속 — 올해 적자 시 관리종목 편입")
    elif market == "KOSDAQ" and tech and nloss >= 4:
        add(1, f"영업손실 {nloss}년 연속(기술성장기업부 — 요건 유예)")

    # 2. 매출액 미달 (기술특례 유예)
    thr = _SALES_THR.get(market)
    sy = sorted(sales, reverse=True)
    if thr and sy and sales[sy[0]] < thr and not tech:
        two = len(sy) >= 2 and sales[sy[1]] < thr
        cur = sales[sy[0]] / _UNIT
        if two:
            add(2, f"매출액 {cur:.1f}억 < {thr/_UNIT:.0f}억 2년 연속 — 관리종목 요건")
        else:
            add(1, f"매출액 {cur:.1f}억 < {thr/_UNIT:.0f}억")

    # 3. 자본잠식
    impair_rate = None
    if latest in equity and latest in capital and capital[latest] > 0:
        eq, cap = equity[latest], capital[latest]
        impair_rate = round((cap - eq) / cap * 100, 1)
        if eq < 0:
            add(3, "완전자본잠식 — 상폐 요건")
        elif impair_rate >= 50:
            prev_bad = False
            if len(years) >= 2:
                py = years[1]
                if py in equity and py in capital and capital[py] > 0:
                    prev_bad = (capital[py] - equity[py]) / capital[py] >= 0.5
            add(3 if prev_bad else 2,
                f"자본잠식률 {impair_rate:.0f}%{' 2년 연속' if prev_bad else ''}")

    # 4. 법인세비용차감전계속사업손실 > 자기자본 50%(&10억↑), 최근3년 2회 (코스닥)
    if market == "KOSDAQ":
        cnt = 0
        for y in years[:3]:
            if y in pretax and y in equity and pretax[y] < 0 and equity[y] > 0:
                loss = -pretax[y]
                if loss > equity[y] * 0.5 and loss > 1e9:
                    cnt += 1
        if cnt >= 2:
            add(2, f"법인세차감전손실 > 자기자본 50%, 최근 3년 {cnt}회 — 관리종목 요건")

    # 실측 소속부 지정 (거래소 지정 = 확정 사실)
    designated = None
    if "관리" in dept:
        designated = "관리종목"; level = max(level, 2)
    elif "투자주의" in dept:
        designated = "투자주의환기"; level = max(level, 1)

    if level == 0 and not designated:
        return None

    return {
        "ticker": tk, "name": nm, "market": market, "dept": dept or None,
        "level": level, "designated": designated, "tech_special": tech,
        "reasons": reasons,
        "consec_op_loss": nloss,
        "latest_year": latest,
        "latest_op": op.get(latest) if latest in op else None,
        "latest_sales": sales.get(sy[0]) if sy else None,
        "impair_rate": impair_rate,
        # B(공시 경보)는 board()에서 병합
        "alerts": [],
    }


_LEVEL_NAME = {3: "상폐위험", 2: "관리위험", 1: "주의", 0: "안전"}


# ── 감사 정정 공시 경보 (Feature B) ─────────────────────────────────────────
# 위험도 높은 순: 관리/상폐 직접 → 감사·실적정정 → 잠정.
# 노이즈 억제: 평범한 '감사보고서제출'(전 종목 매년 제출)·'거래정지해제'·병합/분할성
# 거래정지는 제외하고, 정정·손익구조변동·비적정 의견·관리/상폐 사유만 잡는다.
_STRONG = re.compile(r"상장폐지|상장적격성|실질심사|관리종목지정|자본잠식|불성실공시|횡령|배임|"
                     r"증권선물위원회|검찰고발|회계처리기준|분식회계|과징금")
_HALT = re.compile(r"매매거래정지")
_HALT_BENIGN = re.compile(r"해제|병합|분할|액면|변경상장|정정공시")
_RESTATE = re.compile(r"정정].{0,8}(사업|반기|분기)보고서|정정].{0,8}감사보고서|"
                      r"매출액또는손익구조|의견거절|한정의견|부적정|계속기업")
_PROV = re.compile(r"영업\(?잠정\)?실적|잠정실적")


def _classify_disclosure(report_nm: str):
    rn = report_nm or ""
    if _STRONG.search(rn):
        return 3, "관리·상폐"
    if _HALT.search(rn) and not _HALT_BENIGN.search(rn):
        return 3, "관리·상폐"
    if _RESTATE.search(rn):
        return 2, "감사·정정"
    if _PROV.search(rn):
        return 1, "잠정실적"
    return None


def scan_disclosures(tickers: list[str], bgn: str = "20230101") -> dict[str, list]:
    """주어진 종목의 DART 공시목록을 훑어 감사 정정·관리종목 경보 공시를 수집. (배치용)"""
    import requests

    from app.data.fundamentals.dart import _load_corp_map, enabled
    if not enabled():
        return {}
    key = get_settings().dart_api_key
    cmap = _load_corp_map()
    out: dict[str, list] = {}
    for tk in tickers:
        corp = cmap.get(tk)
        if not corp:
            continue
        try:
            r = requests.get("https://opendart.fss.or.kr/api/list.json", params={
                "crtfc_key": key, "corp_code": corp, "bgn_de": bgn,
                "page_count": "100"}, timeout=30)
            rows = r.json().get("list") or []
        except Exception:
            continue
        hits = []
        for it in rows:
            rn = (it.get("report_nm") or "").strip()
            cl = _classify_disclosure(rn)
            if not cl:
                continue
            hits.append({"date": it.get("rcept_dt"), "report_nm": rn,
                         "sev": cl[0], "kind": cl[1], "rcept_no": it.get("rcept_no")})
        if hits:
            hits.sort(key=lambda x: x["date"], reverse=True)
            out[tk] = hits[:12]
    return out


def load_alerts() -> dict:
    p = _alerts_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def refresh_alerts(tickers: list[str], bgn: str = "20230101") -> dict:
    """위험 종목 공시 스캔 결과를 디스크에 캐시."""
    data = scan_disclosures(tickers, bgn)
    payload = {"generated_at": _now(), "map": data}
    _alerts_path().write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return payload


# ── 통합 보드 ───────────────────────────────────────────────────────────────
def _build() -> dict:
    cls_map = load_market_class()
    series = _series_map()
    alerts_blob = load_alerts()
    alerts = alerts_blob.get("map", {})

    rows = []
    for tk, ser in series.items():
        a = _assess(tk, ser, cls_map.get(tk, {}), None)
        if not a:
            continue
        a["alerts"] = alerts.get(tk, [])
        a["level_name"] = _LEVEL_NAME[a["level"]]
        rows.append(a)

    # 상폐위험 → 관리위험 → 주의, 그 안에서 연속영업손실·경보수 순
    rows.sort(key=lambda x: (-x["level"], -(x["consec_op_loss"] or 0), -len(x["alerts"])))

    from collections import Counter
    lc = Counter(r["level_name"] for r in rows)
    return {
        "generated_at": _now(),
        "count": len(rows),
        "summary": {"상폐위험": lc.get("상폐위험", 0), "관리위험": lc.get("관리위험", 0),
                    "주의": lc.get("주의", 0),
                    "지정_관리종목": sum(1 for r in rows if r["designated"] == "관리종목"),
                    "공시경보_종목": sum(1 for r in rows if r["alerts"])},
        "alerts_generated_at": alerts_blob.get("generated_at"),
        "market_class_ready": bool(cls_map),
        "rows": rows,
        "note": "코스닥 4년연속 영업손실→관리·5년→상폐, 매출 코스닥30억/유가50억, 자본잠식 50%↑. "
                "스팩·외국기업 제외, 기술성장기업부 요건유예. 공시경보는 DART 제목 기준.",
    }


def board() -> dict:
    now = time.time()
    with _lock:
        if _cache["data"] is not None and now - _cache["ts"] < TTL:
            return _cache["data"]
    data = _build()
    with _lock:
        _cache.update(ts=now, data=data)
    return data


def invalidate():
    with _lock:
        _cache.update(ts=0.0, data=None)


def at_risk_tickers(min_level: int = 1, conn=None) -> list[str]:
    """공시 스캔 대상(위험 종목) 티커 목록 — 배치에서 사용."""
    series = _series_map(conn)
    cls_map = load_market_class()
    out = []
    for tk, ser in series.items():
        a = _assess(tk, ser, cls_map.get(tk, {}), None)
        if a and a["level"] >= min_level:
            out.append(tk)
    return out
