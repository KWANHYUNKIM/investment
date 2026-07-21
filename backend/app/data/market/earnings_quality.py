"""이익의 질·회계 착시 탐지 — 연결범위·비지배지분·일회성이익·특수관계자 거래.

'숫자가 좋아 보이는데 실속이 없는' 회사를 재무제표·손익계산서·연결구조로 잡아낸다.

탐지 항목
  D1 연결범위 매출 착시  : 연결매출 급증(+비지배지분 급증) → 종속회사 편입에 의한 외형 성장 의심
  D2 비지배지분 착시     : 연결 외형·자본은 크나 지배주주 실질 몫(지배지분·지배순이익)이 작음
  D3 일회성/영업외 이익  : 영업손실인데 순이익 흑자, 또는 순이익이 영업외·처분이익에 의존
  D4 자산 처분이익 착시  : 유형·무형자산 처분이익이 이익의 큰 부분(특수관계자 거래 가능성)

DART fnlttSinglAcntAll(연결 CFS 우선)로 이미 적재된 dart_financials 를 벌크 조회해 계산한다.
연결 vs 별도(같은 해) 정밀 비교는 별도(OFS) 라이브 조회가 필요해 v1은 프록시로 표기한다.
"""
from __future__ import annotations

import re
import threading
import time

from app.data.infra import store

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 1800.0
_UNIT = 1e8  # 억

_PREFIX = re.compile(r'^[\sⅠ-ⅩIVXivx0-9.\-()]+')
_SALES_PRI = ['매출액', '수익(매출액)', '영업수익', '매출']
_NI_PRI = ['당기순이익(손실)', '당기순이익', '연결당기순이익', '계속영업당기순이익(손실)', '계속영업당기순이익']
_DISPOSAL = ('유형자산처분이익', '무형자산처분이익', '투자자산처분이익', '자산처분이익',
             '종속기업투자처분이익', '관계기업투자처분이익')
_NONOP = ('금융수익', '기타수익', '기타영업외수익', '영업외수익', '기타영업외이익')


def _norm(s: str) -> str:
    s = _PREFIX.sub('', (s or '').replace(' ', ''))
    return s.replace('(손실)', '').replace('(손익)', '')


def _is_ctrl_equity(n: str) -> bool:
    return n.startswith('지배기업') and ('지분' in n or '소유' in n)


def _is_minor_equity(n: str) -> bool:
    return n.startswith('비지배') and '부채' not in n and ('지분' in n or '주주' in n)


def _series_map(conn=None) -> dict[str, dict]:
    sql = """
        SELECT ticker, sj_div, year, account_nm, amount
        FROM dart_financials
        WHERE amount IS NOT NULL AND (
            (sj_div IN ('IS','CIS') AND (
                account_nm LIKE '%영업이익%' OR account_nm LIKE '%당기순이익%'
                OR account_nm LIKE '%매출%' OR account_nm LIKE '%영업수익%'
                OR account_nm LIKE '%처분이익%' OR account_nm LIKE '%금융수익%'
                OR account_nm LIKE '%기타수익%' OR account_nm LIKE '%영업외%'))
            OR (sj_div = 'BS' AND (
                account_nm = '자본총계' OR account_nm LIKE '%지배%'
                OR account_nm LIKE '%매출채권%' OR account_nm LIKE '%자본금%'))
        )
    """
    if conn is not None:
        df = conn.execute(sql).df()
    else:
        with store.connection() as c:
            df = c.execute(sql).df()

    out: dict[str, dict] = {}
    for r in df.to_dict("records"):
        tk, sj, yr, nm, amt = r["ticker"], r["sj_div"], int(r["year"]), r["account_nm"], r["amount"]
        d = out.setdefault(tk, {"rev": {}, "op": {}, "ni": {}, "ni_ctrl": {}, "ni_minor": {},
                                "eq": {}, "eq_ctrl": {}, "eq_minor": {}, "capital": {}, "disposal": {},
                                "nonop": {}, "cogs": {}, "gross": {}, "merch": {}, "prod": {},
                                "prod_cogs": {}, "ar": {}, "_sr": {}, "_nr": {}, "_ar": {}})
        n = _norm(nm)
        if sj in ("IS", "CIS"):
            if n == "영업이익":
                d["op"][yr] = amt
            elif n == "매출원가":
                d["cogs"][yr] = amt
            elif n == "매출총이익":
                d["gross"][yr] = amt
            elif n in ("상품매출액", "상품매출"):
                d["merch"][yr] = amt
            elif n in ("제품매출액", "제품매출"):
                d["prod"][yr] = amt
            elif n == "제품매출원가":
                d["prod_cogs"][yr] = amt
            if nm in _SALES_PRI:
                rk = _SALES_PRI.index(nm)
                if yr not in d["_sr"] or rk < d["_sr"][yr]:
                    d["rev"][yr] = amt; d["_sr"][yr] = rk
            if nm in _NI_PRI:
                rk = _NI_PRI.index(nm)
                if yr not in d["_nr"] or rk < d["_nr"][yr]:
                    d["ni"][yr] = amt; d["_nr"][yr] = rk
            if "비지배" in nm and "당기순이익" in nm:
                d["ni_minor"][yr] = amt
            elif "지배기업" in nm and "당기순이익" in nm:
                d["ni_ctrl"][yr] = amt
            if nm in _DISPOSAL:
                d["disposal"][yr] = d["disposal"].get(yr, 0) + amt
            if nm in _NONOP:
                d["nonop"][yr] = d["nonop"].get(yr, 0) + amt
        elif sj == "BS":
            if n == "자본총계":
                d["eq"][yr] = amt
            elif n == "자본금":
                d["capital"][yr] = amt
            elif _is_minor_equity(n):
                d["eq_minor"][yr] = amt
            elif _is_ctrl_equity(n):
                d["eq_ctrl"][yr] = amt
            elif "매출채권" in n and "장기" not in n:  # 유동 매출채권 우선
                rk = _AR_PRI.index(n) if n in _AR_PRI else 99
                if yr not in d["_ar"] or rk < d["_ar"][yr]:
                    d["ar"][yr] = amt; d["_ar"][yr] = rk
    return out


_AR_PRI = ['매출채권', '매출채권및기타유동채권', '매출채권및기타채권']


def _assess(tk: str, s: dict, name: str | None, sep: dict | None = None,
            market: str | None = None) -> dict | None:
    years = sorted(set(s["rev"]) | set(s["op"]) | set(s["ni"]) | set(s["eq"]), reverse=True)
    if not years:
        return None
    y = years[0]
    py = years[1] if len(years) >= 2 else None
    flags: list[dict] = []
    score = 0  # 착시 강도 누적

    def g(m, yr):
        return m.get(yr)

    rev, op, ni = g(s["rev"], y), g(s["op"], y), g(s["ni"], y)
    eq, eqm, eqc = g(s["eq"], y), g(s["eq_minor"], y), g(s["eq_ctrl"], y)
    nim, nic = g(s["ni_minor"], y), g(s["ni_ctrl"], y)
    disposal, nonop = g(s["disposal"], y), g(s["nonop"], y)

    def add(sev, kind, text):
        nonlocal score
        score += sev
        flags.append({"sev": sev, "kind": kind, "text": text})

    # D2 — 비지배지분 착시
    minor_eq_ratio = None
    if eq and eqm is not None and eq > 0:
        minor_eq_ratio = round(eqm / eq * 100, 1)
        if minor_eq_ratio >= 50:
            add(3, "비지배지분", f"연결자본의 {minor_eq_ratio:.0f}%가 비지배지분 — 지배주주 실질 몫 {100-minor_eq_ratio:.0f}%뿐")
        elif minor_eq_ratio >= 30:
            add(2, "비지배지분", f"연결자본 중 비지배지분 {minor_eq_ratio:.0f}% — 외형 대비 지배주주 몫 적음")
    minor_ni_ratio = None
    if ni and ni > 0 and nim is not None and nim > 0:
        minor_ni_ratio = round(nim / ni * 100, 1)
        if minor_ni_ratio >= 40:
            add(2, "비지배지분", f"연결순이익의 {minor_ni_ratio:.0f}%가 비지배주주 몫")

    # D1 — 연결범위 매출 착시 (프록시)
    rev_yoy = None
    if rev and py in s["rev"] and s["rev"][py]:
        base = s["rev"][py]
        if base > 0:
            rev_yoy = round((rev / base - 1) * 100, 1)
            eqm_grew = (eqm or 0) > (g(s["eq_minor"], py) or 0) * 1.3 if py else False
            if rev_yoy >= 40 and (eqm_grew or (minor_eq_ratio or 0) >= 20):
                add(2, "연결범위", f"매출 전년比 +{rev_yoy:.0f}% 급증 + 비지배지분 확대 — 종속회사 편입(연결범위 변동) 가능성")

    # D3 — 일회성/영업외 이익 착시
    if op is not None and ni is not None:
        if op < 0 and ni > 0:
            add(3, "일회성이익", "영업손실인데 순이익 흑자 — 본업 아닌 영업외이익으로 흑자 방어")
        elif op > 0 and ni > op * 2 and (nonop or 0) > op:
            add(2, "일회성이익", f"순이익이 영업이익의 {ni/op:.1f}배 — 영업외수익 의존 큼")

    # D5 — 관리종목 회피 흑자전환 (3년 연속 영업손실 후 4년째 흑자)
    op_years = sorted(s["op"], reverse=True)
    if len(op_years) >= 4:
        y0, y1, y2, y3 = op_years[:4]
        o0 = s["op"][y0]
        if o0 is not None and o0 > 0 and s["op"][y1] < 0 and s["op"][y2] < 0 and s["op"][y3] < 0:
            margin = (o0 / rev * 100) if (rev and rev > 0) else None
            thin = margin is not None and margin < 3
            ctx = "관리종목 회피·영업이익 조정" if market == "KOSDAQ" else "영업이익 조정"
            add(3 if thin else 2, "흑자전환",
                f"3년 연속 영업손실 후 {y0}년 흑자 전환"
                + (f"(영업이익률 {margin:.1f}%로 빠듯)" if thin else "")
                + f" — {ctx} 의심")

    # D4 — 자산 처분이익 착시 (특수관계자 거래 가능성)
    #   주석에만 있는 특허권 등 무형자산 처분이익은 못 잡으므로 구조화 계정 한정 프록시.
    if disposal and disposal > 0:
        vs_op = disposal / abs(op) if op else None
        vs_ni = disposal / ni if (ni and ni > 0) else None
        best = max(v for v in (vs_op, vs_ni) if v is not None) if (vs_op or vs_ni) else None
        if best and best >= 0.3:
            ref_txt = "영업이익" if (vs_op and vs_op >= (vs_ni or 0)) else "순이익"
            add(3 if best >= 0.7 else 2, "처분이익",
                f"자산 처분이익 {disposal/_UNIT:.1f}억이 {ref_txt}의 {best*100:.0f}% — 일회성/특수관계자 거래 점검")

    # D7 — 밑지고 파는 제조사 (매출총이익률 음수 = 원가 이하 판매)
    cogs, gross = g(s["cogs"], y), g(s["gross"], y)
    prod, prod_cogs = g(s["prod"], y), g(s["prod_cogs"], y)
    gm = None
    if rev and rev > 0:
        if gross is not None:
            gm = gross / rev
        elif cogs is not None:
            gm = (rev - cogs) / rev
    pgm = (prod - prod_cogs) / prod if (prod and prod > 0 and prod_cogs is not None) else None
    if gm is not None and gm < 0:
        add(3, "밑지고팜", f"매출총이익률 {gm*100:.1f}% — 매출원가가 매출액보다 큼(원가 이하 판매)")
    elif pgm is not None and pgm < 0:
        add(3, "밑지고팜", f"제품 매출총이익률 {pgm*100:.1f}% — 제품을 원가 이하로 판매")
    elif gm is not None and 0 <= gm < 0.02:
        add(1, "밑지고팜", f"매출총이익률 {gm*100:.1f}% — 극저마진(원가 근접 판매)")

    # D8 — 상품매출 급증 (통행/밀어내기 매출 의심)
    merch = g(s["merch"], y)
    if merch and rev and rev > 0:
        mr = merch / rev
        pm, pr = (g(s["merch"], py) if py else None), (g(s["rev"], py) if py else None)
        prev_mr = pm / pr if (pm and pr and pr > 0) else 0
        if mr >= 0.3 and prev_mr < 0.15:
            add(2, "상품매출", f"상품매출 비중 {mr*100:.0f}% 급증(전년 {prev_mr*100:.0f}%) — 통행/밀어내기 매출 의심")

    # D9 — 매출채권 급증 (밀어내기·가공매출 흔적)
    ar = g(s["ar"], y)
    ar_ratio = None
    if ar and rev and rev > 0:
        ar_ratio = ar / rev
        pa, pr = (g(s["ar"], py) if py else None), (g(s["rev"], py) if py else None)
        ar_yoy = (ar / pa - 1) if (pa and pa > 0) else None
        r_yoy = (rev / pr - 1) if (pr and pr > 0) else None
        fast = (ar_yoy is not None and r_yoy is not None and ar_yoy - r_yoy > 0.3 and ar_yoy > 0.2)
        if ar_ratio >= 0.5:
            add(2 if fast else 1, "매출채권",
                f"매출채권이 매출액의 {ar_ratio*100:.0f}%" + ("·매출보다 빠르게 급증" if fast else "")
                + " — 밀어내기·회수지연 의심")
        elif fast:
            add(1, "매출채권",
                f"매출채권 {ar_yoy*100:+.0f}%가 매출 {r_yoy*100:+.0f}%보다 빠름 — 회수지연 점검")

    # D10 — 자본잠식 (자본총계 < 자본금 = 원금 잠식). 부분잠식부터 조기 경보.
    capital = g(s["capital"], y)
    cap_impair = None
    if capital and capital > 0 and eq is not None:
        cap_impair = (capital - eq) / capital
        if eq <= 0:
            add(3, "자본잠식", f"완전자본잠식(자본총계 {eq/_UNIT:.1f}억 ≤ 0) — 자본금 전액 잠식")
        elif cap_impair >= 0.5:
            add(3, "자본잠식",
                f"자본잠식률 {cap_impair*100:.0f}% (자본금 {capital/_UNIT:.0f}억 vs 자본총계 {eq/_UNIT:.0f}억) — 관리종목 요건")
        elif cap_impair > 0:
            add(2, "자본잠식",
                f"부분자본잠식 {cap_impair*100:.0f}% — 자본총계<자본금(원금 잠식 시작)")

    # D6 — 연결/별도 이익 괴리 (내부거래 이전가격 착시)
    sep_op = None
    if sep and str(y) in sep:
        sep_op = sep[str(y)].get("op")
        if sep_op is not None and op is not None:
            if op < 0 and sep_op > 0:
                add(3, "이전가격",
                    f"연결 영업손실 {op/_UNIT:.1f}억인데 별도 영업이익 흑자 {sep_op/_UNIT:.1f}억 "
                    "— 내부거래 이전가격으로 별도 이익 부풀림 의심")
            elif sep_op > 0 and op > 0 and sep_op > op * 1.5:
                add(2, "이전가격",
                    f"별도 영업이익({sep_op/_UNIT:.1f}억)이 연결({op/_UNIT:.1f}억)의 "
                    f"{sep_op/op:.1f}배 — 내부거래 이익 점검")

    if not flags:
        return None
    flags.sort(key=lambda f: -f["sev"])
    return {
        "ticker": tk, "name": name or tk,
        "score": score, "latest_year": y,
        "rev": rev, "op": op, "ni": ni,
        "rev_yoy": rev_yoy,
        "minor_eq_ratio": minor_eq_ratio,
        "minor_ni_ratio": minor_ni_ratio,
        "ctrl_equity": eqc,
        "disposal_gain": disposal or None,
        "sep_op": sep_op,
        "gross_margin": round(gm * 100, 1) if gm is not None else None,
        "ar_ratio": round(ar_ratio * 100, 1) if ar_ratio is not None else None,
        "capital": capital,
        "cap_impair_rate": round(cap_impair * 100, 1) if cap_impair is not None else None,
        "flags": flags,
    }


def _build() -> dict:
    series = _series_map()
    # 종목명
    names = {}
    try:
        q = store.latest_quotes(market="KR")
        if q is not None and not q.empty:
            names = {r["ticker"]: r.get("name") for r in q.to_dict("records")}
    except Exception:
        pass

    try:
        from app.data.fundamentals import separate_fin
        sep_map = separate_fin.load()
    except Exception:
        sep_map = {}
    try:
        from app.data.market import delisting
        cls_map = delisting.load_market_class()
    except Exception:
        cls_map = {}

    rows = []
    for tk, s in series.items():
        a = _assess(tk, s, names.get(tk), sep_map.get(tk),
                    (cls_map.get(tk) or {}).get("market"))
        if a:
            rows.append(a)
    rows.sort(key=lambda x: -x["score"])

    from collections import Counter
    kinds = Counter(f["kind"] for r in rows for f in r["flags"])
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M"),
        "count": len(rows),
        "summary": {"밑지고팜": kinds.get("밑지고팜", 0), "자본잠식": kinds.get("자본잠식", 0),
                    "매출채권": kinds.get("매출채권", 0),
                    "상품매출": kinds.get("상품매출", 0), "비지배지분": kinds.get("비지배지분", 0),
                    "연결범위": kinds.get("연결범위", 0), "일회성이익": kinds.get("일회성이익", 0),
                    "흑자전환": kinds.get("흑자전환", 0), "이전가격": kinds.get("이전가격", 0),
                    "처분이익": kinds.get("처분이익", 0)},
        "rows": rows,
        "note": "연결 재무제표(CFS) 기준. 밑지고팜(매출총이익률<0)·매출채권·비지배지분·이익의 질은 실측, "
                "연결범위·처분이익은 프록시(추정). 특수관계자 거래·처분 상세는 사업보고서 주석 확인 필요.",
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
