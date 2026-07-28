"""관리종목·상장폐지 위험 스크리너 + 감사 정정(어닝쇼크) 공시 경보.

세 층위로 위험을 표시한다.

A. 재무요건 위험 (오프라인 · dart_financials 2015~ 다년치 + dart_half 반기)
   - 매출액 미달(유가 50억·코스닥 30억: 1회 관리 / 2년 연속 상폐)
   - 법인세비용차감전계속사업손실 > 자기자본 50%(&10억↑) 최근3년 2회(코스닥 관리),
     관리종목 지정 후 재발생 시 상폐
   - 장기간 영업손실(코스닥 4년 관리 / 5년 상폐)
   - 자본잠식 — 유가: 50%↑ 관리 / 전액잠식·50% 2년연속 상폐
              코스닥: (A) 자본잠식률 50%↑ (B) 자기자본 10억 미만
                      (C) 반기 검토·감사의견 비적정/의견거절/범위제한·미제출
                      → 각 관리, A·B·C 후 재발생 시 상폐
   ※ 스팩·외국기업 제외, 기술성장기업부는 영업손실·매출 요건 유예 반영.

B. 비재무 요건 (시세·공시 기반)
   - 시가총액 미달(유가 50억·코스닥 40억): 30거래일 연속 관리 / 90거래일 상폐
   - 거래량 미달(월평균거래량 < 유동주식수 1%) — 유동주식수 미공시라 상장주식수
     근사이므로 과탐 방향. 확정 요건이 아니라 '주의'로만 표시한다.
   - 공시의무 위반(불성실공시법인 지정) — 벌점 누계는 KIND 에만 있어 지정 횟수로 근사.

C. 감사 정정 경보 (라이브 DART 공시목록 스캔 · 디스크 캐시)
   상폐를 피하려 잠정 영업이익을 아슬아슬 흑자로 냈다가 감사에서 적자로 정정되는
   패턴을 공시 제목으로 포착: [정정]사업/분기보고서·감사보고서, 매출액또는손익구조
   30%이상변동, 관리종목지정·상장적격성실질심사·주권매매거래정지 등.

시장 구분(코스피/코스닥)·소속부(관리종목/투자주의환기/기술성장/스팩)는 FinanceDataReader
상장목록에서 받아 data/market_class.json 에 캐시한다. **이 캐시가 없으면 시장을 몰라
매출·영업손실·법인세 요건이 통째로 적용되지 않으므로**, 배치(`refresh_all`)가 돌았는지
`market_class_ready` 로 확인한다.
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

# ── 현행 기준값 (2026.7 시행 개혁안 반영) ─────────────────────────────────
# 매출액 (관리종목 지정 기준). 2027.1 부터 단계적 상향 → 미리 예고 표시한다.
_SALES_THR = {"KOSDAQ": 3e9, "KOSPI": 5e9}            # 코스닥 30억 · 유가 50억
_SALES_THR_NEXT = {"KOSDAQ": 5e9, "KOSPI": 1e10}      # 2027.1 코스닥 50억 · 유가 100억
_SALES_NEXT_LABEL = "2027.1"
# 시가총액 — 2026.7 상향(코스닥 150→200억 · 유가 200→300억), 2027.1 재상향 예정
_MCAP_THR = {"KOSDAQ": 2e10, "KOSPI": 3e10}
_MCAP_THR_NEXT = {"KOSDAQ": 3e10, "KOSPI": 5e10}      # 2027.1 코스닥 300억 · 유가 500억
# 동전주 요건 — 2026.7 신설. 주가 1,000원 미만.
_PENNY_PRICE = 1000.0
# 시총 상향·동전주 요건의 **시행일**. 신설/상향된 기준을 시행 전 기간까지 소급해서
# 미달일수를 세면 시행 첫날부터 "90일 회복 실패"가 나와 버린다(과탐). 그래서 이
# 날짜 이후의 시세만 가지고 30일/90일을 센다.
_RULE_EFFECTIVE = "2026-07-01"
# 시총·주가 미달의 지속 판정: 30일 연속 미달 → 관리종목,
# 지정 후 90일 동안 45일 연속 기준 회복 못하면 상장폐지.
_SHORTFALL_MANAGE_DAYS = 30
_SHORTFALL_WINDOW = 90
_SHORTFALL_RECOVER = 45
_EQUITY_MIN = 1e9           # 코스닥 자본잠식 (B) 자기자본 10억원
_DEMERIT_LIMIT = 10         # 공시위반 벌점 누계 (2026 개혁: 15 → 10점)
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


# ── 자본잠식 기간(연말·반기말) 시계열 ──────────────────────────────────────
def _impair_periods(equity: dict, capital: dict, half: dict) -> list[dict]:
    """연말·반기말을 시간순(과거→최근)으로 늘어놓고 각 시점의 자본잠식률·자기자본.

    반기(``dart_half``)가 없으면 연말만 쓴다 — 요건 자체가 "사업연도(반기)말"이라
    반기 데이터가 있어야 원문대로 판정된다.
    """
    out = []
    for y in sorted(set(equity) | set(capital)):
        eq, cap = equity.get(y), capital.get(y)
        if eq is None or not cap or cap <= 0:
            continue
        out.append({"label": f"FY{y}말", "year": y, "half": False,
                    "equity": eq, "rate": round((cap - eq) / cap * 100, 1)})
    for y, acc in (half or {}).items():
        eq, cap = acc.get("자본총계"), acc.get("자본금")
        if eq is None or not cap or cap <= 0:
            continue
        out.append({"label": f"FY{y}반기말", "year": y, "half": True,
                    "equity": eq, "rate": round((cap - eq) / cap * 100, 1)})
    # 같은 해는 반기말 → 연말 순
    out.sort(key=lambda p: (p["year"], 0 if p["half"] else 1))
    return out


_ALERT_WINDOW_DAYS = 550   # 요건 판정에 쓰는 공시 유효기간(≈18개월)


def _recent(alerts: list, days: int = _ALERT_WINDOW_DAYS) -> list:
    """요건 판정용으로 최근 공시만 남긴다(date 는 'YYYYMMDD')."""
    cutoff = time.strftime("%Y%m%d", time.localtime(time.time() - days * 86400))
    return [a for a in alerts if (a.get("date") or "") >= cutoff]


# ── 위험 판정 ───────────────────────────────────────────────────────────────
def _assess(tk: str, ser: dict, cls: dict, name: str | None,
            half: dict | None = None, alerts: list | None = None,
            mkt: dict | None = None) -> dict | None:
    market = cls.get("market") or "KR"
    dept = cls.get("dept") or ""
    nm = name or cls.get("name") or tk
    # 스팩·외국기업은 상폐요건 대상 아님
    if "SPAC" in dept.upper() or "스팩" in nm or "외국기업" in dept:
        return None
    tech = "기술성장" in dept  # 기술특례: 영업손실·매출 요건 유예
    designated_mgmt = "관리" in dept   # 거래소가 이미 관리종목으로 지정한 상태
    # 요건 판정엔 최근 공시만 쓴다(스캔 자체는 2023년치까지 보관하지만, 3년 전
    # 감사의견·불성실공시로 지금 관리종목 요건이라고 말하면 오탐이다). 표시는 전체.
    alerts = _recent(alerts or [])

    op, sales = ser["op"], ser["sales"]
    equity, capital, pretax = ser["equity"], ser["capital"], ser["pretax"]
    if not op and not sales and not equity:
        return None

    years = sorted(set(op) | set(sales) | set(equity), reverse=True)
    latest = years[0] if years else None
    reasons: list[dict] = []
    level = 0  # 0 안전 · 1 주의 · 2 관리위험 · 3 상폐위험

    def add(sev: int, text: str, kind: str = "재무"):
        nonlocal level
        level = max(level, sev)
        reasons.append({"sev": sev, "text": text, "kind": kind})

    # 1. 영업손실 연속 — 코스닥 4사업연도 연속이면 관리종목.
    #    '5년 연속 → 상장폐지'는 2022.10 개정으로 삭제됐고, 장기 손실 기업은
    #    자본잠식 요건으로 심사한다. 그래서 5년 이상이어도 등급을 올리지 않는다.
    nloss = _consec_loss(op)
    if market == "KOSDAQ" and not tech:
        if nloss >= 5:
            add(2, f"영업손실 {nloss}년 연속 — 관리종목 요건"
                   " (5년 연속 상폐 요건은 2022.10 삭제 · 자본잠식 요건으로 심사)")
        elif nloss == 4:
            add(2, "영업손실 4년 연속 — 관리종목 요건")
        elif nloss == 3:
            add(1, "영업손실 3년 연속 — 올해 적자 시 관리종목 편입")
    elif market == "KOSDAQ" and tech and nloss >= 4:
        add(1, f"영업손실 {nloss}년 연속(기술성장기업부 — 요건 유예)")

    # 2. 매출액 미달 — 1회 미달이면 관리종목. 2년 연속이면 **상장적격성 실질심사**
    #    (2022.10 개정으로 재무요건 상장폐지가 형식요건에서 실질심사로 전환됐다).
    thr = _SALES_THR.get(market)
    sy = sorted(sales, reverse=True)
    if thr and sy and not tech:
        cur_amt = sales[sy[0]]
        if cur_amt < thr:
            two = len(sy) >= 2 and sales[sy[1]] < thr
            base = f"매출액 {cur_amt/_UNIT:.1f}억 < {thr/_UNIT:.0f}억"
            if two:
                add(3, f"{base} 2년 연속 — 상장적격성 실질심사 대상")
            else:
                add(2, f"{base} — 관리종목 요건")
        else:
            nxt = _SALES_THR_NEXT.get(market)
            if nxt and cur_amt < nxt:      # 상향 예고 기준으로는 미달
                add(1, f"매출액 {cur_amt/_UNIT:.1f}억 — {_SALES_NEXT_LABEL} 상향 기준"
                       f" {nxt/_UNIT:.0f}억 미달 예고")

    # 3. 자본잠식 — 시장별로 요건이 다르다.
    #    자본잠식률·자기자본 요건은 2022.10 개정으로 **반기 → 연 단위**가 됐다.
    #    다만 2026.7 개혁으로 **완전자본잠식만 반기말도** 본다 → 반기는 별도로 확인.
    all_periods = _impair_periods(equity, capital, half or {})
    periods = [p for p in all_periods if not p["half"]]
    impair_rate = periods[-1]["rate"] if periods else None
    latest_equity = periods[-1]["equity"] if periods else None
    #    (C) 반기 검토·감사의견 비적정/의견거절/범위제한·미제출 — 공시 기반
    opinion_all = [a for a in alerts if a.get("kind") == "감사의견"]
    opinion_bad = next((a for a in opinion_all if a.get("sev") == 2), None)   # 반기 검토의견 (C)
    opinion_annual = next((a for a in opinion_all if a.get("sev") == 3), None)  # 사업보고서 감사의견
    if opinion_annual:
        add(3, f"감사의견 비적정/의견거절/범위제한 — 상폐 사유 "
               f"[{opinion_annual.get('date')} {opinion_annual.get('report_nm')}]", "공시")

    # 완전자본잠식 — 사업연도말 + (2026.7 개혁) 반기말. 형식적 상장폐지 사유.
    last = all_periods[-1] if all_periods else None
    if last and (last["equity"] < 0 or last["rate"] >= 100):
        add(3, f"완전자본잠식({last['label']}) — 상장폐지 사유"
               + (" · 2026.7 개혁으로 반기말도 심사" if last["half"] else ""))

    if periods:
        cur = periods[-1]
        prev = periods[-2] if len(periods) >= 2 else None
        a_now = cur["rate"] >= 50
        a_prev = bool(prev and prev["rate"] >= 50)
        b_now = cur["equity"] < _EQUITY_MIN
        b_prev = bool(prev and prev["equity"] < _EQUITY_MIN)

        if cur["equity"] >= 0 and cur["rate"] < 100:   # 완전잠식은 위에서 처리
            if market == "KOSPI":
                if a_now:
                    add(3 if a_prev else 2,
                        f"자본잠식률 {cur['rate']:.0f}%({cur['label']})"
                        + (" 2년 연속 — 상장적격성 실질심사 대상" if a_prev else " — 관리종목 요건"))
            elif market == "KOSDAQ":
                if a_now:  # (A) 자본잠식률 50% 이상 — 2회 연속이면 실질심사
                    add(3 if a_prev else 2,
                        f"(A) 자본잠식률 {cur['rate']:.0f}%({cur['label']})"
                        + (" 2회 연속 — 상장적격성 실질심사 대상" if a_prev else " — 관리종목 요건"))
                if b_now:  # (B) 자기자본 10억원 미만 — 2회 연속이면 실질심사
                    add(3 if b_prev else 2,
                        f"(B) 자기자본 {cur['equity']/_UNIT:.1f}억 < 10억({cur['label']})"
                        + (" 2회 연속 — 상장적격성 실질심사 대상" if b_prev else " — 관리종목 요건"))
            elif a_now:   # 시장 미상(market_class 캐시 없음) — 보수적으로 관리 수준만
                add(2, f"자본잠식률 {cur['rate']:.0f}%({cur['label']}) — 시장 미상, 관리 수준으로 표시")

    if opinion_bad and market == "KOSDAQ":  # (C) 반기 검토의견 미달 — 관리종목 요건
        add(2, f"(C) 반기 검토의견 비적정/의견거절/범위제한 — 관리종목 요건 "
               f"[{opinion_bad.get('date')} {opinion_bad.get('report_nm')}]", "공시")

    # 4. 법인세비용차감전계속사업손실 > 자기자본 50%(&10억↑), 최근3년 2회 (코스닥)
    #    관리종목 지정 상태에서 최근연도에 또 발생하면 상폐 요건.
    #    2회 **연속**이면 상장적격성 실질심사 대상(2022.10 전환).
    if market == "KOSDAQ":
        hit_years = []
        for y in years[:3]:
            if y in pretax and y in equity and pretax[y] < 0 and equity[y] > 0:
                loss = -pretax[y]
                if loss > equity[y] * 0.5 and loss > _EQUITY_MIN:
                    hit_years.append(y)
        if len(hit_years) >= 2:
            consecutive = len(hit_years) >= 2 and hit_years[0] - hit_years[1] == 1
            add(3 if consecutive else 2,
                f"법인세차감전손실 > 자기자본 50%, 최근 3년 {len(hit_years)}회"
                + (" · 2회 연속 — 상장적격성 실질심사 대상" if consecutive else " — 관리종목 요건"))

    # 5·6·7. 비재무 요건 — 시가총액 · 동전주(2026.7 신설) · 거래량
    if mkt:
        cap_thr = _MCAP_THR.get(market)
        cap = mkt.get("cap_state") or {}
        if cap_thr and mkt.get("market_cap") is not None:
            capeok = mkt["market_cap"] / _UNIT
            head = f"시가총액 {capeok:.0f}억 < {cap_thr/_UNIT:.0f}억"
            if cap.get("state") == "delist":
                add(3, f"{head} — 관리종목 지정 후 90일간 45일 연속 회복 실패 → 상폐 요건", "비재무")
            elif cap.get("state") == "manage":
                add(2, f"{head} {cap.get('streak', 0)}거래일 연속 — 관리종목 요건", "비재무")
            elif cap.get("state") == "watch":
                add(1, f"{head} ({cap.get('streak', 0)}거래일째 · 30일 도달 시 관리종목)", "비재무")
            else:
                nxt = _MCAP_THR_NEXT.get(market)
                if nxt and mkt["market_cap"] < nxt:
                    add(1, f"시가총액 {capeok:.0f}억 — {_SALES_NEXT_LABEL} 상향 기준"
                           f" {nxt/_UNIT:.0f}억 미달 예고", "비재무")

        penny = mkt.get("penny_state") or {}
        if penny.get("state") in ("manage", "delist", "watch"):
            px = mkt.get("close")
            head = f"주가 {px:,.0f}원 < 1,000원(동전주 요건, 2026.7 신설)" if px else "동전주 요건"
            if penny["state"] == "delist":
                add(3, f"{head} — 지정 후 90일간 45일 연속 회복 실패 → 상폐 요건", "비재무")
            elif penny["state"] == "manage":
                add(2, f"{head} {penny.get('streak', 0)}거래일 연속 — 관리종목 요건", "비재무")
            else:
                add(1, f"{head} ({penny.get('streak', 0)}거래일째)", "비재무")

        r = mkt.get("vol_ratio")
        if r is not None and r < 0.01:
            add(1, f"월평균거래량이 주식수의 {r*100:.2f}% (<1%) — 거래량 미달 요건 근접"
                   " ※유동주식수 미공시라 상장주식수 근사", "비재무")

    # 8. 공시의무 위반 — 불성실공시법인 지정. 2026 개혁으로 벌점 기준 15 → 10점,
    #    중대·고의적 위반은 1회로도 상장폐지 대상. 벌점은 KIND 전용이라 횟수로 근사.
    unfaithful = [a for a in alerts if "불성실공시" in (a.get("report_nm") or "")]
    if unfaithful:
        add(2 if len(unfaithful) >= 2 else 1,
            f"불성실공시법인 지정 {len(unfaithful)}건 — 공시의무 위반"
            + (f" (벌점 누계 {_DEMERIT_LIMIT}점 시 관리종목 · 중대·고의 1회로도 상폐 대상)"
               if len(unfaithful) < 2 else " · 관리종목 요건 근접"),
            "공시")

    # 실측 소속부 지정 (거래소 지정 = 확정 사실)
    designated = None
    if designated_mgmt:
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
        "equity": latest_equity,
        "impair_basis": periods[-1]["label"] if periods else None,
        "half_ready": bool(half),
        "market_cap": (mkt or {}).get("market_cap"),
        "cap_days_below": ((mkt or {}).get("cap_state") or {}).get("streak"),
        "cap_state": ((mkt or {}).get("cap_state") or {}).get("state"),
        "close": (mkt or {}).get("close"),
        "penny_state": ((mkt or {}).get("penny_state") or {}).get("state"),
        "penny_days": ((mkt or {}).get("penny_state") or {}).get("streak"),
        "vol_ratio": (mkt or {}).get("vol_ratio"),
        # C(공시 경보)는 board()에서 병합
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
# 감사·검토의견 미달 — 자본잠식 요건 (C) 와 감사의견 상폐요건의 근거가 된다.
_OPINION = re.compile(r"의견거절|부적정|범위제한|한정의견|"
                      r"(감사|검토)보고서.{0,10}미제출|미제출.{0,10}(감사|검토)보고서")
# "감사의견거절 사유 **해소**" 같은 해소·해제 공시가 같은 단어를 달고 나온다.
# 그대로 두면 사유가 풀린 회사를 상폐 사유로 표시하게 되므로 제외한다.
_OPINION_RESOLVED = re.compile(r"해소|해제|미해당|해당없음|아님")
_RESTATE = re.compile(r"정정].{0,8}(사업|반기|분기)보고서|정정].{0,8}감사보고서|"
                      r"매출액또는손익구조|계속기업")
_PROV = re.compile(r"영업\(?잠정\)?실적|잠정실적")


def _classify_disclosure(report_nm: str):
    rn = report_nm or ""
    if _STRONG.search(rn):
        return 3, "관리·상폐"
    if _HALT.search(rn) and not _HALT_BENIGN.search(rn):
        return 3, "관리·상폐"
    if _OPINION.search(rn) and not _OPINION_RESOLVED.search(rn):
        # 반기 검토의견 미달 = 관리종목 요건(C). 사업보고서 감사의견 미달은 상폐 사유.
        return (2 if ("반기" in rn or "분기" in rn) else 3), "감사의견"
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


# ── 비재무 요건: 시가총액·거래량 (시세 기반) ───────────────────────────────
# 상장주식수는 어디에도 저장돼 있지 않아 최신 시가총액 ÷ 최신 종가로 역산한다.
# 그 주식수를 과거 종가에 곱하면 시가총액 시계열이 복원된다(주식수 변동은 무시 — 근사).
_VOL_WINDOW = {"KOSDAQ": 63, "KOSPI": 126}   # 분기(코스닥)·반기(유가) 거래일 수
_DAYS_PER_MONTH = 21


def _shortfall_state(below: list[bool]) -> dict:
    """시총·주가 미달의 지속 상태 판정.

    현행 규정: **30일 연속 미달 → 관리종목**, 지정 후 **90일 동안 45일 연속** 기준을
    회복하지 못하면 **상장폐지**. ``below[i]`` 는 그 날이 기준 미달이었는지.

    반환 ``state``: none(정상) · watch(미달이지만 30일 미만) · manage(관리종목 요건)
    · delist(90일 창에서 회복 실패 → 상폐 요건).
    """
    streak = 0
    for b in reversed(below):
        if b:
            streak += 1
        else:
            break

    # '30일 연속 미달'이 완성된 지점 = 관리종목 지정일. 한 미달 구간당 한 번 생긴다.
    marks, run = [], 0
    for i, b in enumerate(below):
        run = run + 1 if b else 0
        if run == _SHORTFALL_MANAGE_DAYS:
            marks.append(i)
    if not marks:
        return {"state": "watch" if streak else "none", "streak": streak, "since_manage": 0}

    def longest_recovery(idx: int) -> tuple[list, int]:
        after = below[idx + 1: idx + 1 + _SHORTFALL_WINDOW]
        best = cur = 0
        for b in after:                   # 기준을 회복(=not below)한 최장 연속일
            cur = 0 if b else cur + 1
            best = max(best, cur)
        return after, best

    # 지정이 여러 번이면 **하나라도** 90일 창에서 회복에 실패한 적이 있으면 상폐 요건.
    for idx in marks:
        after, best = longest_recovery(idx)
        if len(after) >= _SHORTFALL_WINDOW and best < _SHORTFALL_RECOVER:
            return {"state": "delist", "streak": streak, "since_manage": len(after),
                    "best_recovery": best}
    after, best = longest_recovery(marks[-1])
    return {"state": "manage", "streak": streak, "since_manage": len(after),
            "best_recovery": best}


def _market_stats(cls_map: dict, conn=None) -> dict[str, dict]:
    import pandas as pd  # noqa: F401  (duckdb .df() 경유)

    sql_cap = """
        SELECT ticker, market_cap FROM (
            SELECT ticker, market_cap,
                   row_number() OVER (PARTITION BY ticker ORDER BY date DESC) rn
            FROM fundamentals WHERE market_cap IS NOT NULL AND market_cap > 0
        ) WHERE rn = 1
    """
    # 30일(관리) + 90일(회복창) 을 평가하려면 최소 120 거래일이 필요 → 400일치를 본다.
    sql_px = """
        SELECT ticker, date, close, volume FROM prices
        WHERE date >= (SELECT max(date) FROM prices) - INTERVAL 400 DAY
          AND close IS NOT NULL AND close > 0
        ORDER BY ticker, date
    """
    if conn is not None:
        cap_df, px_df = conn.execute(sql_cap).df(), conn.execute(sql_px).df()
    else:
        with store.connection() as c:
            cap_df, px_df = c.execute(sql_cap).df(), c.execute(sql_px).df()
    if px_df.empty:
        return {}

    caps = dict(zip(cap_df["ticker"], cap_df["market_cap"])) if not cap_df.empty else {}
    out: dict[str, dict] = {}
    for tk, g in px_df.groupby("ticker", sort=False):
        mcap = caps.get(tk)
        closes = g["close"].tolist()
        if not closes or not mcap:
            continue
        shares = mcap / closes[-1]
        if shares <= 0:
            continue
        market = (cls_map.get(tk) or {}).get("market")
        thr = _MCAP_THR.get(market)
        # 시총 상향·동전주는 2026.7 시행 → 시행일 이후 시세만으로 30일/90일을 센다.
        eff = [c for d, c in zip(g["date"].tolist(), closes) if str(d)[:10] >= _RULE_EFFECTIVE]
        cap_state = _shortfall_state([px * shares < thr for px in eff]) if thr else None
        # 동전주 요건(2026.7 신설) — 종가 1,000원 미만
        penny_state = _shortfall_state([px < _PENNY_PRICE for px in eff])

        win = _VOL_WINDOW.get(market, 63)
        vols = g["volume"].tolist()[-win:]
        vol_ratio = None
        if vols and shares:
            avg_month = (sum(v for v in vols if v == v) / max(1, len(vols))) * _DAYS_PER_MONTH
            vol_ratio = round(avg_month / shares, 5)
        out[tk] = {
            "market_cap": float(mcap), "shares": round(shares),
            "close": closes[-1],
            "cap_state": cap_state, "cap_days_below": (cap_state or {}).get("streak", 0),
            "penny_state": penny_state,
            "vol_ratio": vol_ratio, "price_days": len(closes),
        }
    return out


# ── 통합 보드 ───────────────────────────────────────────────────────────────
def _build() -> dict:
    cls_map = load_market_class()
    series = _series_map()
    alerts_blob = load_alerts()
    alerts = alerts_blob.get("map", {})
    try:
        half_map = store.dart_half_map()
    except Exception:
        half_map = {}
    try:
        mkt_map = _market_stats(cls_map)
    except Exception:
        mkt_map = {}

    rows = []
    for tk, ser in series.items():
        a = _assess(tk, ser, cls_map.get(tk, {}), None,
                    half=half_map.get(tk), alerts=alerts.get(tk, []),
                    mkt=mkt_map.get(tk))
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
        "half_ready": len(half_map),
        "market_stats_ready": len(mkt_map),
        "rows": rows,
        "note": "현행 규정 기준(2022.10 재무요건 실질심사 전환 + 2026.7 개혁 시행). "
                "매출 유가50억/코스닥30억(1회 관리·2년연속 실질심사, 2027.1 상향 예정), "
                "코스닥 영업손실 4년 관리(5년 상폐 요건은 2022.10 삭제), "
                "자본잠식 연 단위 — 유가 50%↑·코스닥 (A)50%↑ (B)자기자본 10억 미만 2회연속 실질심사, "
                "완전자본잠식은 반기말도 심사(2026.7). 세전손실>자기자본50% 2회연속 실질심사. "
                "비재무: 시총 유가300억/코스닥200억·동전주 1,000원 미만 — 30거래일 연속 관리, "
                "지정 후 90일간 45일 연속 회복 실패 시 상폐. 거래량 미달은 유동주식수 미공시라 "
                "상장주식수 근사(주의만), 공시위반 벌점 10점 기준은 지정 횟수로 근사. "
                "스팩·외국기업 제외, 기술성장기업부 요건유예."
                + ("" if cls_map else " ※시장구분 캐시 없음 — 매출·영업손실·법인세 요건 미적용 상태."),
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
    try:
        mkt_map = _market_stats(cls_map, conn)
    except Exception:
        mkt_map = {}
    out = []
    for tk, ser in series.items():
        a = _assess(tk, ser, cls_map.get(tk, {}), None, mkt=mkt_map.get(tk))
        if a and a["level"] >= min_level:
            out.append(tk)
    return out


def refresh_all(min_level: int = 1, half_cap: int = 400, bgn: str = "20230101") -> dict:
    """스크리너가 쓰는 외부 데이터를 한 번에 갱신(야간 배치).

    ① 시장구분·소속부(FDR 상장목록) → ② 위험종목 추출 → ③ 그 종목의 DART 공시
    스캔(감사의견·불성실공시 포함) → ④ 그 종목의 반기 자본계정 적재.

    ②~④ 는 위험종목에만 돌린다. 전 종목에 DART 를 때리면 rate limit 에 걸리고,
    애초에 반기말 자본잠식·감사의견 판정이 필요한 곳은 위험군뿐이다.
    """
    t0 = time.time()
    out: dict = {"started_at": _now()}
    try:
        cls = refresh_market_class()
        out["market_class"] = len(cls)
    except Exception as e:
        out["market_class_error"] = f"{type(e).__name__}: {str(e)[:100]}"

    risky = at_risk_tickers(min_level)
    out["at_risk"] = len(risky)

    try:
        blob = refresh_alerts(risky, bgn)
        out["alerts"] = len(blob.get("map", {}))
    except Exception as e:
        out["alerts_error"] = f"{type(e).__name__}: {str(e)[:100]}"

    try:
        from app.data.fundamentals import dart_financials as dfin
        out["half"] = dfin.refresh_half(risky[:half_cap])
    except Exception as e:
        out["half_error"] = f"{type(e).__name__}: {str(e)[:100]}"

    invalidate()
    out["elapsed_sec"] = round(time.time() - t0, 1)
    out["finished_at"] = _now()
    return out
