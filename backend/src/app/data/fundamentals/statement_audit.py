"""재무제표 3종 감사 — 잘 갖춰져 있는가, 그리고 **말이 맞는가**.

두 가지를 한다.

**① 커버리지 점검**: 재무상태표(BS)·손익계산서(IS/CIS)·현금흐름표(CF)가 몇 개년,
   몇 계정이나 들어와 있는지. 빠진 표가 있으면 그 위에 쌓은 분석은 신뢰할 수 없다.

**② 정합성(articulation) 검증 = 조작 탐지**: 재무제표 3종은 서로 물려 있어서
   한 곳을 손보면 다른 곳이 어긋난다. 큰 회사일수록 손익은 다듬기 쉽지만
   **현금은 다듬기 어렵다.** 그 어긋남을 찾는 게 이 모듈의 임무다.

     A1 재무상태표 항등식   자산총계 = 부채총계 + 자본총계
     A2 손익계산서 정합     매출 − 매출원가 − 판관비 = 영업이익
     A3 현금흐름표 항등식   영업 + 투자 + 재무 ≈ 현금 순증감
     D1 발생액 비율         (순이익 − 영업CF) ÷ 자산총계   ← 이익은 나는데 현금이 없다
     D2 흑자·영업CF 적자    순이익 > 0 인데 영업CF < 0 (연속이면 심각)
     D3 매출채권 vs 매출    매출채권이 매출보다 훨씬 빨리 증가 → 가공매출 의심
     D4 재고 vs 매출원가    재고가 원가보다 훨씬 빨리 증가 → 원가 이연(§11.4-②)
     D5 자본잠식            자본총계 < 0

   판정은 **의심 제기**이지 확정이 아니다. 업종 특성(수주산업·성장기 재고 확충)으로
   설명되는 경우가 많으므로 항상 수치·연도와 함께 보여준다.

개편계획 §11.4(조작 탐지) · §12.5(인건비 통로)의 재무제표 축.
"""
from __future__ import annotations

from app.data.infra import store

# 계정을 찾을 표(sj_div). '자본총계'는 재무상태표에도 **자본변동표에도** 있어서
# 표를 고정하지 않으면 자본변동표의 기초잔액이 잡혀 항등식이 깨진다(실제로 발생).
_SJ_OF = {
    "assets": ("BS",), "liabilities": ("BS",), "equity": ("BS",),
    "inventory": ("BS",), "receivable": ("BS",),
    "revenue": ("IS", "CIS"), "cogs": ("IS", "CIS"), "sga": ("IS", "CIS"),
    "op": ("IS", "CIS"), "net": ("IS", "CIS"),
    "other_op_income": ("IS", "CIS"), "other_op_expense": ("IS", "CIS"),
    "cfo": ("CF",), "cfi": ("CF",), "cff": ("CF",),
    "cash_delta": ("CF",), "cash_begin": ("CF",), "cash_end": ("CF",), "fx": ("CF",),
    # 아래 5개는 §15 교차검증(X19·X25·X32·X33)이 쓴다 — audit() 자체는 안 쓰지만
    # 계정 정의를 두 군데 두면 언젠가 어긋나므로 여기 한곳에 모아 둔다.
    "ppe": ("BS",), "intangible_bs": ("BS",),
    "tax": ("IS", "CIS"), "pretax": ("IS", "CIS"), "dividend_paid": ("CF",),
}

# (account_id 후보, account_nm 후보) — DART는 회사마다 계정명이 달라 둘 다로 잡는다.
_PICK = {
    "assets":      (("ifrs-full_Assets",), ("자산총계",)),
    "liabilities": (("ifrs-full_Liabilities",), ("부채총계",)),
    "equity":      (("ifrs-full_Equity",), ("자본총계",)),
    "inventory":   (("ifrs-full_Inventories",), ("재고자산",)),
    "receivable":  (("ifrs-full_CurrentTradeReceivables", "ifrs-full_TradeAndOtherCurrentReceivables"),
                    ("매출채권", "매출채권및기타유동채권", "매출채권 및 기타유동채권")),
    "revenue":     (("ifrs-full_Revenue",), ("매출액", "수익(매출액)", "영업수익", "매출")),
    "cogs":        (("ifrs-full_CostOfSales",), ("매출원가",)),
    "sga":         (("dart_TotalSellingGeneralAdministrativeExpenses",),
                    ("판매비와관리비", "판매비와 관리비")),
    "op":          (("dart_OperatingIncomeLoss", "ifrs-full_ProfitLossFromOperatingActivities"),
                    ("영업이익", "영업이익(손실)")),
    "net":         (("ifrs-full_ProfitLoss",), ("당기순이익", "당기순이익(손실)", "분기순이익")),
    # 영업이익에 **기타영업손익**을 넣는 회사가 있다(LG화학: 매출총이익−판관비+기타영업수익=영업이익).
    # 이걸 빼고 항등식을 보면 멀쩡한 회사가 '손익계산서 불일치'로 찍힌다. '기타영업외수익'과
    # 헷갈리면 안 되므로 계정명은 정확히 일치시킨다.
    "other_op_income":  (("dart_OtherOperatingIncome",), ("기타영업수익",)),
    "other_op_expense": (("dart_OtherOperatingExpenses",), ("기타영업비용",)),
    "cfo":         (("ifrs-full_CashFlowsFromUsedInOperatingActivities",),
                    ("영업활동현금흐름", "영업활동으로인한현금흐름")),
    "cfi":         (("ifrs-full_CashFlowsFromUsedInInvestingActivities",),
                    ("투자활동현금흐름", "투자활동으로인한현금흐름")),
    "cff":         (("ifrs-full_CashFlowsFromUsedInFinancingActivities",),
                    ("재무활동현금흐름", "재무활동으로인한현금흐름")),
    "cash_delta":  (("ifrs-full_IncreaseDecreaseInCashAndCashEquivalents",
                     "ifrs-full_IncreaseDecreaseInCashAndCashEquivalentsBeforeEffectOfExchangeRateChanges"),
                    ("현금및현금성자산의순증가", "현금및현금성자산의증가", "현금및현금성자산의순증가(감소)",
                     "현금및현금성자산의증가(감소)")),
    "cash_begin":  (("dart_CashAndCashEquivalentsAtBeginningOfPeriodCf",),
                    ("기초현금및현금성자산", "기초의현금및현금성자산", "기초의현금및현금성자산")),
    "cash_end":    (("dart_CashAndCashEquivalentsAtEndOfPeriodCf",),
                    ("기말현금및현금성자산", "기말의현금및현금성자산")),
    "fx":          (("ifrs-full_EffectOfExchangeRateChangesOnCashAndCashEquivalents",),
                    ("현금및현금성자산에대한환율변동효과", "환율변동효과", "외화환산으로인한현금의변동")),
    "ppe":         (("ifrs-full_PropertyPlantAndEquipment",), ("유형자산",)),
    "intangible_bs": (("ifrs-full_IntangibleAssetsOtherThanGoodwill",), ("무형자산", "개발비")),
    "tax":         (("ifrs-full_IncomeTaxExpenseContinuingOperations",),
                    ("법인세비용", "법인세비용(수익)", "법인세수익")),
    "pretax":      (("ifrs-full_ProfitLossBeforeTax",),
                    ("법인세비용차감전순이익", "법인세비용차감전순이익(손실)", "법인세차감전순이익")),
    "dividend_paid": (("ifrs-full_DividendsPaidClassifiedAsFinancingActivities",),
                      ("배당금지급", "배당금의지급", "배당금지급액", "현금배당금의지급")),
}

_SJ_LABEL = {"BS": "재무상태표", "IS": "손익계산서", "CIS": "포괄손익계산서",
             "CF": "현금흐름표", "SCE": "자본변동표"}


def _norm(s: str) -> str:
    return str(s).replace(" ", "").strip()


def _one_basis(df):
    """**연도마다 연결(CFS)/별도(OFS) 중 하나로 통일.**

    이게 없으면 한 해의 자산은 연결, 자본은 별도가 잡혀 항등식이 깨지고
    멀쩡한 회사가 '분식 의심'으로 찍힌다(삼성전자에서 실제로 발생). 오탐의 최대 원인.
    """
    if "fs_div" not in df.columns:
        return df, {}
    keep, basis = [], {}
    for y, g in df.groupby("year"):
        div = "CFS" if (g["fs_div"] == "CFS").any() else (
            g["fs_div"].dropna().iloc[0] if not g["fs_div"].dropna().empty else None)
        basis[int(y)] = "연결" if div == "CFS" else ("별도" if div == "OFS" else "혼합")
        keep.append(g[g["fs_div"] == div] if div else g)
    import pandas as pd
    return (pd.concat(keep) if keep else df), basis


def _series(df, key: str) -> dict[int, float]:
    """계정 하나의 {year: amount}. account_id 우선, 없으면 계정명. 중복은 ord 최소 행.

    ord 최소 행의 금액이 0이고 다른 행에 값이 있으면 값이 있는 쪽을 쓴다(빈 합계행 회피).
    """
    ids, names = _PICK[key]
    df = df[df["sj_div"].isin(_SJ_OF[key])]          # 표 고정(동명 계정 혼입 방지)
    sub = df[df["account_id"].isin(ids)] if "account_id" in df.columns else df.iloc[0:0]
    if sub.empty:
        norm = {_norm(n) for n in names}
        sub = df[df["account_nm"].map(lambda x: _norm(x) in norm)]
    if sub.empty:
        return {}
    out: dict[int, tuple[int, float]] = {}
    for r in sub.to_dict("records"):
        try:
            y, amt, ordv = int(r["year"]), float(r["amount"]), int(r.get("ord") or 0)
        except (TypeError, ValueError):
            continue
        if amt != amt:                       # NaN
            continue
        cur = out.get(y)
        if cur is None or (ordv < cur[0] and amt) or (cur[1] == 0 and amt):
            out[y] = (ordv, amt)
    return {y: v[1] for y, v in out.items()}


def _series_labeled(df, key: str) -> dict[int, tuple[float, str, str]]:
    """``_series`` 와 같은 규칙이되, **어느 계정을 읽었는지**(계정명·표준코드)까지 돌려준다.

    "이 숫자를 어디서 가져왔나"를 화면에 그대로 보여주려면 금액만으론 부족하다.
    """
    ids, names = _PICK[key]
    d = df[df["sj_div"].isin(_SJ_OF[key])]
    sub = d[d["account_id"].isin(ids)] if "account_id" in d.columns else d.iloc[0:0]
    if sub.empty:
        norm = {_norm(n) for n in names}
        sub = d[d["account_nm"].map(lambda x: _norm(x) in norm)]
    if sub.empty:
        return {}
    out: dict[int, tuple[int, float, str, str]] = {}
    for r in sub.to_dict("records"):
        try:
            y, amt, ordv = int(r["year"]), float(r["amount"]), int(r.get("ord") or 0)
        except (TypeError, ValueError):
            continue
        if amt != amt:
            continue
        cur = out.get(y)
        if cur is None or (ordv < cur[0] and amt) or (cur[1] == 0 and amt):
            out[y] = (ordv, amt, str(r.get("account_nm") or ""), str(r.get("account_id") or ""))
    return {y: (v[1], v[2], v[3]) for y, v in out.items()}


# 원장으로 보여줄 계정 — (키, 한글 라벨, 소속 표). 검증이 실제로 읽은 숫자들이다.
_LEDGER = (
    ("assets", "자산총계", "재무상태표"), ("liabilities", "부채총계", "재무상태표"),
    ("equity", "자본총계", "재무상태표"), ("receivable", "매출채권", "재무상태표"),
    ("inventory", "재고자산", "재무상태표"), ("ppe", "유형자산", "재무상태표"),
    ("revenue", "매출액", "손익계산서"), ("cogs", "매출원가", "손익계산서"),
    ("sga", "판매비와관리비", "손익계산서"), ("op", "영업이익", "손익계산서"),
    ("pretax", "법인세차감전순이익", "손익계산서"), ("tax", "법인세비용", "손익계산서"),
    ("net", "당기순이익", "손익계산서"),
    ("cfo", "영업활동현금흐름", "현금흐름표"), ("cfi", "투자활동현금흐름", "현금흐름표"),
    ("cff", "재무활동현금흐름", "현금흐름표"), ("fx", "환율변동효과", "현금흐름표"),
    ("cash_begin", "기초현금", "현금흐름표"), ("cash_end", "기말현금", "현금흐름표"),
    ("dividend_paid", "배당금지급", "현금흐름표"),
)


def _build_ledger(df, years: list[int], basis: dict) -> list[dict]:
    """검증이 실제로 읽은 **원장**. 연도별로 계정·금액·출처 계정명을 그대로 편다."""
    labeled = {k: _series_labeled(df, k) for k, _, _ in _LEDGER}
    out = []
    for y in years:
        rows = []
        for key, label, stmt in _LEDGER:
            hit = labeled.get(key, {}).get(y)
            if hit is None:
                continue
            amt, nm, aid = hit
            rows.append({"label": label, "statement": stmt, "eok": _eok(amt),
                         "won": amt, "account_nm": nm, "account_id": aid})
        out.append({"year": y, "basis": basis.get(y), "accounts": rows})
    return out


def _eok(v):
    return round(v / 1e8) if v is not None else None


def _pct(a, b):
    """상대오차. b=0 이면 None."""
    return None if not b else (a - b) / abs(b)


def _chk(code, label, status, detail, year=None, **extra):
    return {"code": code, "label": label, "status": status, "detail": detail,
            "year": year, **extra}


def _audit_report_checks(nt: dict | None) -> list[dict]:
    """감사보고서(사업보고서 원문) 기반 검증 — 감사인이 직접 찍어준 신호.

    우리가 숫자로 추정하는 것보다 **감사인의 의견**이 상위 신호다.
    """
    a = (nt or {}).get("audit") if nt else None
    if not a:
        return []
    out = []
    op = a.get("opinion")
    if op and op != "적정":
        out.append(_chk("R1", "감사의견", "fail", f"{op} 의견 — 재무제표를 신뢰할 수 없다",
                        why="적정의견이 아니면 상장폐지 사유가 될 수 있다."))
    elif op:
        out.append(_chk("R1", "감사의견", "ok", "적정의견"))
    if a.get("going_concern_doubt"):
        out.append(_chk("R2", "계속기업 관련 중요한 불확실성", "fail",
                        "감사보고서에 계속기업 불확실성 항목이 있다",
                        why="감사인이 존속 자체를 의심한 것 — 가장 강한 경보."))
    if a.get("internal_control_issue"):
        out.append(_chk("R3", "내부회계관리제도", "warn", "비적정/중요한 취약점 언급",
                        why="장부를 만드는 절차 자체에 구멍이 있다는 뜻."))
    if a.get("emphasis"):
        out.append(_chk("R4", "강조사항 기재", "warn", "감사보고서에 강조사항이 있다",
                        why="의견에는 영향 없지만 감사인이 특별히 짚은 사안."))
    n = a.get("n_kam") or len(a.get("kam") or [])
    if n:
        titles = ", ".join(a.get("kam") or []) or "제목 추출 실패"
        out.append(_chk("R5", "핵심감사사항(KAM)", "ok", f"{n}건 — {titles}",
                        why="감사인이 '가장 위험하다'고 지목한 회계 영역. 이 부분의 수치를 "
                            "먼저 의심하면 된다(신호이지 이상 아님)."))
    return out


def audit(ticker: str, notes: dict | None = None,
          extra_checks: list[dict] | None = None) -> dict:
    """재무제표 3종 커버리지 + 정합성·조작탐지. DB에 자료가 없으면 coverage만 반환.

    ``notes`` 로 ``report_notes.notes(ticker)`` 를 넘기면 **감사의견·계속기업·KAM** 검증이
    추가된다(네트워크 호출이라 호출부에서 선택).
    """
    try:
        df = store.dart_financials(ticker)
    except Exception:
        df = None
    if df is None or df.empty:
        return {"ticker": ticker, "available": False, "statements": [], "checks": [],
                "score": None, "verdict": "DART 재무제표 미적재 — 원가·품질 분석 불가",
                "note": "관리자 > 데이터에서 DART 재무제표를 적재하면 활성화된다."}

    # --- ① 커버리지 -------------------------------------------------------
    # 손익계산서는 IS(별도표시)·CIS(포괄) 중 하나만 내는 회사가 많다 → 한 줄로 묶는다.
    groups = (("BS", ("BS",), "재무상태표"), ("IS", ("IS", "CIS"), "손익계산서"),
              ("CF", ("CF",), "현금흐름표"), ("SCE", ("SCE",), "자본변동표"))
    statements = []
    for code, sjs, label in groups:
        s = df[df["sj_div"].isin(sjs)]
        if s.empty:
            statements.append({"sj_div": code, "label": label, "years": [],
                               "n_years": 0, "n_accounts": 0, "ok": False})
            continue
        yrs = sorted({int(y) for y in s["year"].tolist()})
        statements.append({
            "sj_div": code, "label": label, "years": yrs, "n_years": len(yrs),
            "n_accounts": int(s["account_nm"].nunique()), "ok": True,
            "forms": sorted({str(x) for x in s["sj_div"].tolist()}),
        })
    has = {s["sj_div"]: s["ok"] for s in statements}
    core_ok = has.get("BS") and has.get("IS") and has.get("CF")

    df, basis = _one_basis(df)               # 연결/별도 혼재 제거(오탐 방지)
    v = {k: _series(df, k) for k in _PICK}
    years = sorted(set(v["assets"]) | set(v["revenue"]), reverse=True)[:3]
    checks: list[dict] = []

    if not core_ok:
        miss = [s["label"] for s in statements
                if s["sj_div"] in ("BS", "IS", "CF") and not s["ok"]]
        checks.append(_chk("C0", "재무제표 3종 구비", "fail",
                           f"누락: {', '.join(miss)} — 이 위에 쌓은 분석은 신뢰 불가"))

    for y in years:
        # A1 재무상태표 항등식
        a, l, e = v["assets"].get(y), v["liabilities"].get(y), v["equity"].get(y)
        if a and l is not None and e is not None:
            gap = _pct(l + e, a)
            checks.append(_chk(
                "A1", "재무상태표 항등식(자산=부채+자본)",
                "ok" if abs(gap) < 0.005 else ("warn" if abs(gap) < 0.02 else "fail"),
                f"자산 {_eok(a):,}억 vs 부채+자본 {_eok(l + e):,}억 (오차 {gap*100:+.2f}%)", y))

        # A2 손익계산서 정합
        rev, cogs, sga, op = (v["revenue"].get(y), v["cogs"].get(y),
                              v["sga"].get(y), v["op"].get(y))
        if rev and cogs is not None and sga is not None and op is not None:
            calc = (rev - cogs - sga
                    + (v["other_op_income"].get(y) or 0.0) - (v["other_op_expense"].get(y) or 0.0))
            gap = _pct(calc, op)
            checks.append(_chk(
                "A2", "손익계산서 정합(매출−원가−판관비=영익)",
                "ok" if abs(gap) < 0.02 else ("warn" if abs(gap) < 0.10 else "fail"),
                f"계산 {_eok(calc):,}억 vs 공시 영업이익 {_eok(op):,}억 (오차 {gap*100:+.1f}%)", y))

        # A3 현금흐름표 항등식 — 영업+투자+재무+환율효과 = 기말현금 − 기초현금
        o, i, f_ = v["cfo"].get(y), v["cfi"].get(y), v["cff"].get(y)
        fx = v["fx"].get(y) or 0.0
        cb, ce = v["cash_begin"].get(y), v["cash_end"].get(y)
        target = (ce - cb) if (cb is not None and ce is not None) else v["cash_delta"].get(y)
        if None not in (o, i, f_) and target is not None:
            s = o + i + f_ + fx
            base = max(abs(target), abs(o) * 0.01, 1.0)     # 현금증감이 0 근처면 영업CF 기준
            gap = (s - target) / base
            checks.append(_chk(
                "A3", "현금흐름표 항등식(영업+투자+재무+환율=현금증감)",
                "ok" if abs(gap) < 0.03 else ("warn" if abs(gap) < 0.15 else "fail"),
                f"3활동+환율 {_eok(s):,}억 vs 현금증감 {_eok(target):,}억 (오차 {gap*100:+.1f}%)", y))

        # D1 발생액 비율 — 이익과 현금의 괴리
        net, a2 = v["net"].get(y), v["assets"].get(y)
        # 부호가 중요하다: (+)이익>현금 = 위험신호 / (−)현금>이익 = 보수적(정상).
        # 감가상각이 큰 장치산업은 (−)가 정상이라 절대값으로 보면 멀쩡한 회사가 경고로 찍힌다.
        if net is not None and o is not None and a2:
            acc = (net - o) / a2
            status = "ok" if acc < 0.05 else ("warn" if acc < 0.10 else "fail")
            tail = ("" if acc >= 0.05 else
                    ("  → 현금이 이익보다 많음(보수적)" if acc < 0 else "  → 정상 범위"))
            checks.append(_chk(
                "D1", "발생액 비율((순이익−영업CF)÷자산)", status,
                f"순이익 {_eok(net):,}억 − 영업CF {_eok(o):,}억 = {_eok(net - o):,}억 "
                f"(자산 대비 {acc*100:+.1f}%){tail}", y,
                why="이익은 나는데 현금이 안 들어오면(발생액 +) 매출채권·재고로 이익을 "
                    "만들었을 수 있다. 반대로 현금이 더 많으면(−) 이익의 질이 좋다."))

        # D2 흑자인데 영업현금 적자
        if net is not None and o is not None and net > 0 and o < 0:
            checks.append(_chk("D2", "흑자·영업현금 적자", "fail",
                               f"순이익 {_eok(net):,}억 흑자인데 영업CF {_eok(o):,}억 적자", y,
                               why="장부이익과 실제 현금의 방향이 반대 — 분식의 대표 신호."))

        # D5 자본잠식
        if e is not None and e < 0:
            checks.append(_chk("D5", "자본잠식", "fail", f"자본총계 {_eok(e):,}억 (음수)", y))

    # D3·D4 — 증가율 비교(전년 대비)
    if len(years) >= 2:
        y0, y1 = years[0], years[1]

        def g(m):
            a, b = m.get(y0), m.get(y1)
            return _pct(a, b) if (a is not None and b) else None

        gr, grec, gcogs, ginv = g(v["revenue"]), g(v["receivable"]), g(v["cogs"]), g(v["inventory"])
        if gr is not None and grec is not None:
            d = grec - gr
            checks.append(_chk(
                "D3", "매출채권 증가율 vs 매출 증가율",
                "ok" if d < 0.10 else ("warn" if d < 0.25 else "fail"),
                f"매출 {gr*100:+.1f}% vs 매출채권 {grec*100:+.1f}% (격차 {d*100:+.1f}%p)", y0,
                why="매출채권이 매출보다 훨씬 빨리 늘면 안 받은 돈으로 매출을 만든(밀어내기·가공매출) "
                    "것일 수 있다. 단 M&A로 연결범위가 바뀐 해나 수주산업(공사미수금)은 "
                    "정상적으로도 급증한다."))
        if gcogs is not None and ginv is not None:
            d = ginv - gcogs
            checks.append(_chk(
                "D4", "재고 증가율 vs 매출원가 증가율",
                "ok" if d < 0.10 else ("warn" if d < 0.25 else "fail"),
                f"매출원가 {gcogs*100:+.1f}% vs 재고 {ginv*100:+.1f}% (격차 {d*100:+.1f}%p)", y0,
                why="재고가 원가보다 빨리 늘면 당기 원가를 재고자산으로 미뤄 이익을 좋게 "
                    "보이게 했을 수 있다(§11.4-②). 증설·연결범위 변경기에는 정상일 수 있다."))

    checks.extend(_audit_report_checks(notes))     # 감사보고서 기반(선택)
    checks.extend([c for c in (extra_checks or []) if c])   # 물량 기반(B4) 등 외부 검증

    # --- 스코어 -----------------------------------------------------------
    # 같은 검증이 3개년 내내 걸리면 3건이 아니라 1건으로 센다(연도 반복 = 같은 문제).
    fail_codes = {c["code"] for c in checks if c["status"] == "fail"}
    warn_codes = {c["code"] for c in checks if c["status"] == "warn"} - fail_codes
    fails, warns = len(fail_codes), len(warn_codes)
    score = max(0, 100 - fails * 20 - warns * 7 - (0 if core_ok else 25))

    # 점수를 어떻게 깎았는지 **한 줄도 숨기지 않는다.** 93이라는 숫자만 보여주면 믿을 근거가 없다.
    deductions = []
    if not core_ok:
        deductions.append({"reason": "재무제표 3종 중 누락", "points": -25, "codes": ["C0"]})
    if fails:
        deductions.append({"reason": f"이상(fail) {fails}종 × 20점", "points": -fails * 20,
                           "codes": sorted(fail_codes)})
    if warns:
        deductions.append({"reason": f"관찰(warn) {warns}종 × 7점", "points": -warns * 7,
                           "codes": sorted(warn_codes)})
    scoring = {
        "base": 100,
        "deductions": deductions,
        "final": score,
        "formula": "100 − (이상 종류 × 20) − (관찰 종류 × 7) − (3종 누락 시 25). "
                   "같은 검증이 여러 해 걸려도 '종류' 1건으로 센다(연도 반복=같은 문제).",
    }

    if not core_ok:
        verdict = "재무제표 누락 — 먼저 데이터 적재 필요"
    elif fails:
        verdict = f"이상 신호 {fails}건 — 재무제표 간 정합이 깨졌거나 이익·현금 괴리가 크다"
    elif warns:
        verdict = f"관찰 필요 {warns}건 — 업종 특성으로 설명되는지 확인"
    else:
        verdict = "재무제표 3종 정합 — 이익과 현금이 같은 방향"

    return {
        "ticker": ticker,
        "available": True,
        "statements": statements,
        "core_ok": bool(core_ok),
        "basis": {str(y): basis.get(y) for y in years},   # 연도별 연결/별도
        "years": years,
        "checks": checks,
        "score": score,
        "scoring": scoring,                               # 점수 산식(감점 내역 전부)
        "ledger": _build_ledger(df, years, basis),        # 검증이 읽은 원장(계정·금액·출처)
        "verdict": verdict,
        "source": "DART 재무제표(OpenDART fnlttSinglAcntAll, DuckDB 적재분)",
        "note": "정합성 위반은 '의심 제기'이지 확정이 아니다. 업종 특성(수주산업·성장기 "
                "재고 확충·계절성)으로 설명되는 경우가 많으므로 수치와 함께 판단한다.",
    }


def coverage_summary(limit: int | None = None) -> dict:
    """전 종목 재무제표 적재 현황 — 표별 종목수·연도범위 + 3종 미비 종목.

    "우리 재무제표 데이터가 잘 되어 있나"를 한 화면에서 답한다.
    """
    try:
        with store.connection() as conn:
            per = conn.execute(
                "SELECT sj_div, COUNT(DISTINCT ticker) tickers, MIN(year) y0, MAX(year) y1, "
                "COUNT(*) rows FROM dart_financials GROUP BY sj_div ORDER BY sj_div"
            ).df()
            tot = conn.execute("SELECT COUNT(DISTINCT ticker) FROM dart_financials").fetchone()[0]
            miss = conn.execute(
                """
                SELECT ticker,
                       MAX(CASE WHEN sj_div = 'BS' THEN 1 ELSE 0 END) bs,
                       MAX(CASE WHEN sj_div IN ('IS','CIS') THEN 1 ELSE 0 END) is_,
                       MAX(CASE WHEN sj_div = 'CF' THEN 1 ELSE 0 END) cf,
                       COUNT(DISTINCT year) yrs
                FROM dart_financials GROUP BY ticker
                """
            ).df()
    except Exception as e:
        return {"available": False, "error": str(e),
                "note": "DuckDB 접근 실패(다른 프로세스가 쓰기 잠금 중일 수 있음)."}

    rows = miss.to_dict("records")
    complete = [r for r in rows if r["bs"] and r["is_"] and r["cf"]]
    incomplete = [{"ticker": r["ticker"],
                   "missing": [n for n, k in (("재무상태표", "bs"), ("손익계산서", "is_"),
                                              ("현금흐름표", "cf")) if not r[k]],
                   "years": int(r["yrs"])}
                  for r in rows if not (r["bs"] and r["is_"] and r["cf"])]
    thin = sorted([{"ticker": r["ticker"], "years": int(r["yrs"])}
                   for r in complete if r["yrs"] < 3], key=lambda x: x["years"])

    return {
        "available": True,
        "total_tickers": int(tot),
        "complete_3": len(complete),
        "complete_pct": round(len(complete) / tot * 100, 1) if tot else 0.0,
        "by_statement": [
            {"sj_div": r["sj_div"], "label": _SJ_LABEL.get(r["sj_div"], r["sj_div"]),
             "tickers": int(r["tickers"]), "year_from": int(r["y0"]), "year_to": int(r["y1"]),
             "rows": int(r["rows"])}
            for r in per.to_dict("records")
        ],
        "incomplete": incomplete[:limit] if limit else incomplete,
        "incomplete_n": len(incomplete),
        "thin_years": thin[:limit] if limit else thin[:50],
        "note": "3종(재무상태표·손익계산서·현금흐름표)이 모두 있어야 정합성 검증이 가능하다. "
                "현금흐름표가 빠지면 발생액·이익의 질 검증(D1·D2)을 못 한다.",
    }
