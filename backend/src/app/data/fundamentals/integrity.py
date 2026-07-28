"""원가 진실성 스코어 — 교차검증 X1~X35 집계 (개편계획 §15.1·§15.3·D13).

**"이 회사가 정직한가"를 재는 게 아니다.** 회사가 공시한 숫자들이 서로 맞물리는지를 본다.
부문매출을 더하면 연결매출이 되는가, 원재료 매입액이 성격별 비용의 원재료 사용액과 맞는가,
생산량이 늘지 않았는데 매출만 뛰지 않았는가 — 같은 문서 안에서 서로를 검증한다.

세 가지 설계 원칙이 점수의 성격을 결정한다.

**① 확인불가는 분모에서 뺀다.** 회사가 안 적은 항목을 감점하면 "공시를 적게 한 회사가
유리"해지는 역설이 생긴다. 대신 **검증범위(%)** 를 따로 내서 "38개 중 몇 개를 봤는지"를
같이 보여 준다. 진실성만 높고 검증범위가 낮으면 "확인할 수 있는 게 적었다"는 뜻이다.

**② A와 B는 서로 다른 절에서 와야 한다.** 같은 표 안에서 더하고 빼는 건 검증이 아니다.
그래서 각 항목에 `source_a`·`source_b`(어느 절의 숫자인지)를 반드시 적어 화면에 내보낸다.

**③ 연결범위가 바뀌면 3년 비교는 통째로 무효다.** M&A가 있었던 해에 매출채권 증가율을
따지는 건 의미가 없다 → X27이 걸리면 관련 검증을 자동으로 '해당없음' 처리한다(§15.8-3).

가중치는 §15.1 — 치명 5(회계 자체가 성립 안 됨) / 중대 3(이익과 현금·물량의 방향이 다름)
/ 일반 2(부문 간 숫자가 안 맞음) / 참고 1(있으면 좋은 방증).
"""
from __future__ import annotations

from app.data.fundamentals import commodities
from app.data.fundamentals import commodity_map
from app.data.fundamentals import statement_audit as sa
from app.data.infra import store

# 가중 등급
CRIT, MAJOR, NORM, INFO = "치명", "중대", "일반", "참고"
WEIGHT = {CRIT: 5, MAJOR: 3, NORM: 2, INFO: 1}
CREDIT = {"ok": 1.0, "warn": 0.5, "fail": 0.0}

GRADES = ((85, "양호", "공시된 원재료·생산량·재무제표가 서로 들어맞습니다"),
          (70, "보통", "일부 항목이 어긋납니다 — 업종 특성일 수 있습니다"),
          (50, "주의", "여러 항목이 어긋납니다 — 근거를 확인하세요"),
          (0, "경고", "재무제표 간 정합이 깨졌습니다"))

# 3개년 비교에 기대는 검증 — 연결범위가 바뀌면 통째로 무효(§15.8-3)
_TREND_CODES = {"X9", "X10", "X15", "X16", "X31"}


def _pct(a, b):
    """상대오차. b=0 이면 None."""
    return None if not b else (a - b) / abs(b)


def _eok(v):
    return None if v is None else round(v / 1e8)


class _Checks:
    """검증 결과를 모으는 그릇. 값이 없으면 ``na``(확인불가)로 남긴다 — 절대 지어내지 않는다."""

    def __init__(self):
        self.rows: list[dict] = []

    def add(self, code, label, grade, status, detail, *, a=None, b=None,
            source_a=None, source_b=None, why=None, year=None):
        self.rows.append({
            "code": code, "label": label, "grade": grade, "weight": WEIGHT[grade],
            "status": status, "detail": detail, "a": a, "b": b,
            "source_a": source_a, "source_b": source_b, "why": why, "year": year,
        })

    def na(self, code, label, grade, reason, **kw):
        self.add(code, label, grade, "na", reason, **kw)

    def ratio(self, code, label, grade, sum_a, ref_b, ok, warn, detail, **kw):
        """A/B 비교 전용 — **비상식적인 비율은 판정이 아니라 파싱 실패**로 본다.

        합이 연결매출의 1/5 미만이거나 3배를 넘으면 회사가 그렇게 공시한 게 아니라
        우리가 표를 잘못 읽은 것이다(§15.8-4 "못 고르면 버린다"). 확인불가로 남기면
        분모에서 빠져 점수를 왜곡하지 않고, 화면엔 이유가 그대로 남는다.
        """
        if not sum_a or not ref_b:
            return self.na(code, label, grade, "비교할 두 숫자 중 하나가 없습니다", **kw)
        r = sum_a / ref_b
        if r < 0.2 or r > 3.0:
            return self.na(code, label, grade,
                           f"파싱 결과가 비상식적({r * 100:.0f}%) — 표 서식이 달라 검증에서 제외했습니다",
                           **kw)
        self.band(code, label, grade, abs(r - 1), ok, warn, detail, **kw)

    def band(self, code, label, grade, value, ok, warn, detail, *, higher_bad=True, **kw):
        """value 가 ok 이내면 ok, warn 이내면 warn, 넘으면 fail."""
        if value is None:
            return self.na(code, label, grade, "계산에 필요한 값이 없습니다", **kw)
        v = value if higher_bad else -value
        st = "ok" if v <= ok else ("warn" if v <= warn else "fail")
        self.add(code, label, grade, st, detail, **kw)


def _series(df, key):
    try:
        return sa._series(df, key)
    except Exception:
        return {}


def _fin(ticker: str) -> tuple[dict, list[int]]:
    """DuckDB 재무제표 → {계정: {연도: 금액}} + 최근 연도 목록(내림차순)."""
    try:
        df = store.dart_financials(ticker)
    except Exception:
        return {}, []
    if df is None or df.empty:
        return {}, []
    df, _basis = sa._one_basis(df)          # 연결/별도 혼재 제거(오탐의 최대 원인)
    v = {k: _series(df, k) for k in sa._PICK}
    years = sorted(set(v.get("revenue", {})) | set(v.get("assets", {})), reverse=True)[:3]
    return v, years


# --- 개별 검증 ---------------------------------------------------------------
def _statement_checks(c: _Checks, v: dict, years: list[int]):
    """X1~X3·X7~X10 — 재무제표 3종이 서로 물려 있는지."""
    if not years:
        for code, label, grade in (("X1", "자산 = 부채 + 자본", CRIT),
                                   ("X2", "매출 − 매출원가 − 판관비 = 영업이익", CRIT),
                                   ("X3", "영업+투자+재무+환율 = 현금증감", CRIT)):
            c.na(code, label, grade, "DART 재무제표 미적재")
        return
    y = years[0]
    g = lambda k: v.get(k, {}).get(y)  # noqa: E731

    a, l, e = g("assets"), g("liabilities"), g("equity")
    if a and l is not None and e is not None:
        gap = _pct(l + e, a)
        c.band("X1", "자산 = 부채 + 자본", CRIT, abs(gap), 0.005, 0.02,
               f"자산 {_eok(a):,}억 vs 부채+자본 {_eok(l + e):,}억 (오차 {gap * 100:+.2f}%)",
               a=_eok(a), b=_eok(l + e), source_a="연결 재무상태표", source_b="연결 재무상태표",
               year=y, why="회계 항등식이 깨지면 그 위의 모든 분석이 무의미하다.")
    else:
        c.na("X1", "자산 = 부채 + 자본", CRIT, "재무상태표 계정 없음")

    rev, cogs, sga, op = g("revenue"), g("cogs"), g("sga"), g("op")
    if rev and cogs is not None and sga is not None and op is not None:
        # 기타영업손익을 영업이익에 넣는 회사가 있다 — 빼고 보면 멀쩡한 회사가 불일치로 찍힌다.
        oi, oe = g("other_op_income") or 0.0, g("other_op_expense") or 0.0
        calc = rev - cogs - sga + oi - oe
        gap = _pct(calc, op)
        extra = " (기타영업손익 반영)" if (oi or oe) else ""
        c.band("X2", "매출 − 매출원가 − 판관비 = 영업이익", CRIT, abs(gap), 0.02, 0.10,
               f"계산 {_eok(calc):,}억 vs 공시 영업이익 {_eok(op):,}억 (오차 {gap * 100:+.1f}%){extra}",
               a=_eok(calc), b=_eok(op), source_a="연결 손익계산서", source_b="연결 손익계산서", year=y)
    else:
        c.na("X2", "매출 − 매출원가 − 판관비 = 영업이익", CRIT, "손익 계정 일부 없음(매출원가·판관비 미표시)")

    o, i, f_ = g("cfo"), g("cfi"), g("cff")
    fx = g("fx") or 0.0
    cb, ce = g("cash_begin"), g("cash_end")
    target = (ce - cb) if (cb is not None and ce is not None) else g("cash_delta")
    if None not in (o, i, f_) and target is not None:
        s = o + i + f_ + fx
        base = max(abs(target), abs(o) * 0.01, 1.0)
        gap = (s - target) / base
        c.band("X3", "영업+투자+재무+환율 = 현금증감", CRIT, abs(gap), 0.03, 0.15,
               f"3활동+환율 {_eok(s):,}억 vs 현금증감 {_eok(target):,}억 (오차 {gap * 100:+.1f}%)",
               a=_eok(s), b=_eok(target), source_a="연결 현금흐름표", source_b="연결 현금흐름표", year=y)
    else:
        c.na("X3", "영업+투자+재무+환율 = 현금증감", CRIT, "현금흐름표 미적재")

    net = g("net")
    if net is not None and o is not None and a:
        acc = (net - o) / a
        tail = "  → 현금이 이익보다 많음(보수적)" if acc < 0 else ""
        c.band("X7", "발생액 비율 (순이익−영업CF)÷자산", MAJOR, acc, 0.05, 0.10,
               f"순이익 {_eok(net):,}억 − 영업CF {_eok(o):,}억 = {_eok(net - o):,}억 "
               f"(자산 대비 {acc * 100:+.1f}%){tail}",
               a=_eok(net), b=_eok(o), source_a="연결 손익계산서", source_b="연결 현금흐름표", year=y,
               why="이익은 나는데 현금이 안 들어오면 매출채권·재고로 이익을 만들었을 수 있다.")
    else:
        c.na("X7", "발생액 비율 (순이익−영업CF)÷자산", MAJOR, "순이익 또는 영업CF 없음")

    if net is not None and o is not None:
        bad = net > 0 and o < 0
        c.add("X8", "흑자인데 영업현금 적자 아님", MAJOR, "fail" if bad else "ok",
              f"순이익 {_eok(net):,}억 · 영업CF {_eok(o):,}억",
              a=_eok(net), b=_eok(o), source_a="연결 손익계산서", source_b="연결 현금흐름표", year=y,
              why="장부이익과 실제 현금의 방향이 반대 — 분식의 대표 신호.")
    else:
        c.na("X8", "흑자인데 영업현금 적자 아님", MAJOR, "순이익 또는 영업CF 없음")

    if len(years) >= 2:
        y0, y1 = years[0], years[1]

        def gr(k):
            aa, bb = v.get(k, {}).get(y0), v.get(k, {}).get(y1)
            return _pct(aa, bb) if (aa is not None and bb) else None

        grev, grec, gcogs, ginv = gr("revenue"), gr("receivable"), gr("cogs"), gr("inventory")
        if grev is not None and grec is not None:
            d = grec - grev
            c.band("X9", "매출채권 증가율 ≈ 매출 증가율", MAJOR, d, 0.10, 0.25,
                   f"매출 {grev * 100:+.1f}% vs 매출채권 {grec * 100:+.1f}% (격차 {d * 100:+.1f}%p)",
                   a=round(grev * 100, 1), b=round(grec * 100, 1),
                   source_a="연결 손익계산서", source_b="연결 재무상태표", year=y0,
                   why="매출채권이 매출보다 훨씬 빨리 늘면 안 받은 돈으로 매출을 만든 것일 수 있다.")
        else:
            c.na("X9", "매출채권 증가율 ≈ 매출 증가율", MAJOR, "2개년 매출채권 없음")
        if gcogs is not None and ginv is not None:
            d = ginv - gcogs
            c.band("X10", "재고 증가율 ≈ 매출원가 증가율", MAJOR, d, 0.10, 0.25,
                   f"매출원가 {gcogs * 100:+.1f}% vs 재고 {ginv * 100:+.1f}% (격차 {d * 100:+.1f}%p)",
                   a=round(gcogs * 100, 1), b=round(ginv * 100, 1),
                   source_a="연결 손익계산서", source_b="연결 재무상태표", year=y0,
                   why="재고가 원가보다 빨리 늘면 당기 원가를 재고자산으로 미뤄 이익을 좋게 보이게 했을 수 있다.")
        else:
            c.na("X10", "재고 증가율 ≈ 매출원가 증가율", MAJOR, "2개년 재고 없음")
    else:
        c.na("X9", "매출채권 증가율 ≈ 매출 증가율", MAJOR, "2개년 자료 없음")
        c.na("X10", "재고 증가율 ≈ 매출원가 증가율", MAJOR, "2개년 자료 없음")


def _audit_checks(c: _Checks, notes: dict | None, dfull: dict | None):
    """X4~X6·X28·X29·X35 — 감사인이 남긴 것과 회사가 남긴 흔적."""
    am = (dfull or {}).get("audit_meta") or {}
    na = (notes or {}).get("audit") or {}
    op = am.get("latest_opinion") or na.get("opinion")
    if op:
        ok = "적정" in op
        c.add("X4", "감사의견 적정", CRIT, "ok" if ok else "fail", op,
              a=op, source_a="V-1 외부감사에 관한 사항",
              why="적정의견이 아니면 상장폐지 사유가 될 수 있다.")
    else:
        c.na("X4", "감사의견 적정", CRIT, "감사의견을 찾지 못했습니다")

    gc = None
    if am.get("opinions"):
        raw = " ".join(str(x.get("going_concern") or "") for x in am["opinions"][:2])
        gc = bool(raw.strip()) and not all(
            (str(x.get("going_concern") or "").strip() in ("-", "", "해당사항 없음", "해당사항없음"))
            for x in am["opinions"][:2])
    if gc is None and na:
        gc = bool(na.get("going_concern_doubt"))
    if gc is None:
        c.na("X5", "계속기업 관련 중요한 불확실성 없음", CRIT, "감사보고서 항목을 찾지 못했습니다")
    else:
        c.add("X5", "계속기업 관련 중요한 불확실성 없음", CRIT, "fail" if gc else "ok",
              "기재 있음" if gc else "해당사항 없음", source_a="V-1 / 감사보고서",
              why="감사인이 존속 자체를 의심한 것 — 가장 강한 경보.")

    rst = ((dfull or {}).get("other_financial") or {}).get("restatement")
    if rst is None:
        c.na("X6", "재무제표 재작성 없음", CRIT, "III-8-가를 찾지 못했습니다")
    else:
        kind = rst.get("kind")
        # 중단영업 재분류·회계정책 변경에 따른 재작성은 '숫자가 틀렸다'는 뜻이 아니다 → 관찰.
        st = ("ok" if not rst.get("occurred")
              else ("warn" if kind == "중단영업·회계정책 변경" else "fail"))
        c.add("X6", "재무제표 재작성 없음", CRIT, st,
              (f"재작성 있음 — {kind}" if rst.get("occurred") else "해당사항 없음")
              + (f" · {rst.get('detail', '')[:90]}" if rst.get("occurred") else ""),
              source_a="III-8-가 재무제표 재작성 등 유의사항",
              why="과거에 공시한 숫자를 나중에 고쳤다는 뜻 — 오류수정이면 최우선 경보이고, "
                  "사업 매각에 따른 비교표시 재작성이면 성격이 다르다.")

    hc, fc = am.get("hours_chg"), am.get("fee_chg")
    if hc is None and fc is None:
        c.na("X28", "감사시간·감사보수 급감 아님", NORM, "감사용역 체결현황을 찾지 못했습니다")
    else:
        worst = min(x for x in (hc, fc) if x is not None)
        detail = " · ".join(filter(None, [
            f"감사시간 {hc * 100:+.1f}%" if hc is not None else None,
            f"감사보수 {fc * 100:+.1f}%" if fc is not None else None]))
        st = "ok" if worst > -0.30 else ("warn" if worst > -0.50 else "fail")
        c.add("X28", "감사시간·감사보수 급감 아님", NORM, st, detail + " (전년 대비)",
              a=hc, b=fc, source_a="V-1 감사용역 체결현황", source_b="전년 공시",
              why="감사에 들인 시간이 갑자기 줄면 감사 품질 자체가 흔들린다.")

    sc = (dfull or {}).get("sanctions") or {}
    if "sanctioned" not in sc:
        c.na("X29", "제재·우발부채 없음", NORM, "XI-3 제재 항목을 찾지 못했습니다")
    else:
        lit = sc.get("litigation")
        # 소송 계류는 상장사 대부분이 적는다 — 그걸로 감점하면 신호가 아니라 잡음이 된다.
        # 감점은 **제재 이력**에만 준다.
        st = "fail" if sc["sanctioned"] else "ok"
        c.add("X29", "제재·우발부채 없음", NORM, st,
              ("제재 이력 있음" if sc["sanctioned"] else "제재 없음")
              + (" · 소송 계류 기재(참고)" if lit else ""),
              source_a="XI-3 제재 등과 관련된 사항", source_b="주석 「우발상황 및 중요 약정」",
              why="제재는 신뢰의 문제고, 우발부채는 재무상태표에 아직 안 잡힌 빚이다.")

    kam = na.get("kam") or []
    n_kam = na.get("n_kam") or len(kam)
    if not n_kam and not am.get("opinions"):
        c.na("X35", "KAM이 우리 경보와 겹치는가", INFO, "핵심감사사항을 찾지 못했습니다")
    else:
        titles = ", ".join(kam) if kam else " / ".join(
            filter(None, [x.get("kam") for x in (am.get("opinions") or [])[:2]])) or "제목 추출 실패"
        c.add("X35", "KAM이 우리 경보와 겹치는가", INFO, "ok", f"{n_kam or '—'}건 — {titles}",
              source_a="V-1 / 감사보고서 핵심감사사항",
              why="감사인이 '가장 위험하다'고 지목한 회계 영역. 신호이지 이상이 아니다.")


def _cross_checks(c: _Checks, v: dict, years: list[int], dfull: dict | None,
                  notes: dict | None, labor: dict | None, biz: dict | None):
    """X11~X26·X30~X34 — **절을 넘나드는** 검증. 여기가 §15의 본체다."""
    d = dfull or {}
    y = years[0] if years else None
    rev = v.get("revenue", {}).get(y) if y else None
    cogs = v.get("cogs", {}).get(y) if y else None
    sga = v.get("sga", {}).get(y) if y else None
    assets = v.get("assets", {}).get(y) if y else None

    # X11 부문매출 합 = 연결매출
    seg = d.get("segments")
    if seg and rev:
        s = seg["total_revenue_won"]
        gap = _pct(s, rev)
        c.ratio("X11", "부문매출 합 = 연결매출", MAJOR, s, rev, 0.01, 0.05,
               f"부문 합 {_eok(s):,}억 vs 연결매출 {_eok(rev):,}억 (차이 {gap * 100:+.2f}%)",
               a=_eok(s), b=_eok(rev), source_a=seg["source"], source_b="연결 손익계산서", year=y,
               why="부문을 다 더하면 회사가 된다. 안 맞으면 부문 공시나 연결 조정 어느 한쪽이 어긋난 것.")
    else:
        c.na("X11", "부문매출 합 = 연결매출", MAJOR,
             "영업부문 주석을 찾지 못했습니다" if rev else "연결매출 없음")

    # X12 품목별 매출 합 = 연결매출
    sm = d.get("sales_mix")
    tot_by_year = (sm or {}).get("total_by_year") or {}
    if sm and rev and tot_by_year:
        # 기수 표기('제25기')면 연도로 못 고른다 → 표의 **최신 열**을 쓴다.
        # 금액이 가장 큰 열을 고르면 매출이 줄어든 회사가 옛 연도와 비교돼 늘 불일치가 된다.
        key = str(y) if str(y) in tot_by_year else (
            sm.get("latest_period") if sm.get("latest_period") in tot_by_year
            else max(tot_by_year))
        s = tot_by_year[key]
        gap = _pct(s, rev)
        c.ratio("X12", "품목별 매출 합 = 연결매출", MAJOR, s, rev, 0.02, 0.08,
               f"매출실적표 합 {_eok(s):,}억({key}) vs 연결매출 {_eok(rev):,}억 (차이 {gap * 100:+.2f}%)",
               a=_eok(s), b=_eok(rev), source_a=sm["source"], source_b="연결 손익계산서", year=y,
               why="사업의 내용에 적은 품목별 매출을 다 더하면 재무제표의 매출이 되어야 한다.")
    else:
        c.na("X12", "품목별 매출 합 = 연결매출", MAJOR, "매출실적표를 찾지 못했습니다")

    # X13 성격별 비용 합 = 매출원가 + 판관비
    cn = (notes or {}).get("cost_nature") or {}
    # 공시된 합계(재고 변동분 포함)가 손익계산서와 맞대볼 짝이다. 없으면 구성 합으로 대신한다.
    nature_total = cn.get("disclosed_total_eok") or cn.get("total_cost_eok")
    if nature_total and cogs is not None and sga is not None:
        s = nature_total * 1e8
        base = cogs + sga
        gap = _pct(s, base)
        c.ratio("X13", "성격별 비용 합 = 매출원가 + 판관비", MAJOR, s, base, 0.02, 0.10,
               f"성격별 비용 {_eok(s):,}억 vs 매출원가+판관비 {_eok(base):,}억 (차이 {gap * 100:+.2f}%)",
               a=_eok(s), b=_eok(base), source_a="주석 「비용의 성격별 분류」",
               source_b="연결 손익계산서", year=y,
               why="같은 비용을 기능별(원가/판관비)과 성격별(재료·인건·상각)로 두 번 적은 것이라 합이 같아야 한다.")
    else:
        c.na("X13", "성격별 비용 합 = 매출원가 + 판관비", MAJOR, "성격별 비용 주석 또는 판관비 없음")

    # X14 원재료 매입액 ≈ 성격별 원재료 사용액 (± 재고변동)
    mp = d.get("materials_purchase")
    mat_eok = cn.get("material_eok")
    if mp and mat_eok:
        buy = mp["total_won"]
        use = mat_eok * 1e8
        inv = d.get("inventory") or {}
        raw_delta = None                      # 재고 증감분(있으면 매입−사용 차이를 설명한다)
        gap = _pct(buy, use)
        detail = f"매입 {_eok(buy):,}억 vs 성격별 원재료 사용 {_eok(use):,}억 ({gap * 100:+.1f}%)"
        if inv.get("raw_won"):
            raw_delta = inv["raw_won"]
            detail += f" · 기말 원재료 재고 {_eok(raw_delta):,}억"
        # 두 숫자의 범위가 애초에 조금 다르다 — 성격별 사용액엔 부재료·상품매입까지 들어가고,
        # II-3-가는 '주요' 원재료만 적는다. 그래서 ±25%까지는 정상으로 본다.
        c.band("X14", "원재료 매입액 ≈ 성격별 원재료 사용액", MAJOR, abs(gap), 0.25, 0.60, detail,
               a=_eok(buy), b=_eok(use), source_a=mp["source"],
               source_b="주석 「비용의 성격별 분류」", year=y,
               why="산 만큼 쓰는 게 정상이다. 차이는 재고 증감으로 설명돼야 한다. "
                   "다만 성격별 사용액엔 부재료·상품매입이 섞여 있어 '주요 원재료' 매입액보다 크게 나온다.")
    else:
        c.na("X14", "원재료 매입액 ≈ 성격별 원재료 사용액", MAJOR,
             "원재료 매입액표 또는 성격별 원재료 사용액이 없습니다")

    # X15 생산량 증가율 ≈ 매출 증가율
    growths = []
    for o in d.get("output") or []:
        ys = sorted(o["values"], reverse=True)
        if len(ys) >= 2 and o["values"][ys[1]]:
            growths.append((o["values"][ys[0]] - o["values"][ys[1]]) / o["values"][ys[1]])
    if growths and len(years) >= 2 and v.get("revenue", {}).get(years[1]):
        vol = sum(growths) / len(growths)
        rg = _pct(v["revenue"][years[0]], v["revenue"][years[1]])
        gap = rg - vol
        c.band("X15", "생산량 증가율 ≈ 매출 증가율", NORM, gap, 0.15, 0.30,
               f"생산량 {vol * 100:+.1f}% vs 매출 {rg * 100:+.1f}% (격차 {gap * 100:+.1f}%p, 품목 {len(growths)}개 평균)",
               a=round(vol * 100, 1), b=round(rg * 100, 1),
               source_a="II-3-라 생산실적", source_b="연결 손익계산서", year=years[0],
               why="금액은 다듬어도 물량은 다듬기 어렵다. 물량은 그대로인데 매출만 뛰면 "
                   "판가 인상·믹스 개선이거나 매출 부풀리기다.")
    else:
        c.na("X15", "생산량 증가율 ≈ 매출 증가율", NORM, "생산실적 3개년 또는 매출 2개년이 없습니다")

    # X16 원단위 3년 안정
    uc = [x for x in (d.get("unit_consumption") or []) if x.get("stable") is not None]
    if uc:
        bad = [x for x in uc if not x["stable"]]
        st = "ok" if not bad else ("warn" if len(bad) < len(uc) else "fail")
        head = uc[0]
        c.add("X16", "원단위(제품 1개당 원재료) 3년 안정", NORM, st,
              f"{len(uc)}건 중 {len(bad)}건 변동 10% 초과 · 예: {head['material']} "
              f"{head['u']}{head['u_unit']}",
              a=head["u"], source_a="II-3-가 매입액 ÷ II-3-나 단가", source_b="II-3-라 생산실적",
              why="원단위가 안정적이면 구매·생산·재무 숫자가 서로 맞물린다는 뜻이다. "
                  "튀면 공정 변화·제품 믹스 변화·숫자 오류 셋 중 하나다.")
    elif d.get("unit_consumption"):
        c.na("X16", "원단위(제품 1개당 원재료) 3년 안정", NORM,
             "매입액이 단년만 공시돼 3년 추세를 낼 수 없습니다")
    else:
        c.na("X16", "원단위(제품 1개당 원재료) 3년 안정", NORM,
             "매입액·단가·생산량 중 하나가 없거나 단위 환산이 불가합니다")

    # X17 매입단가 방향 ≈ 국제시세 방향
    mprices = (d.get("material_prices") or {}).get("rows") or []
    dirs = []
    for row in mprices:
        ys = sorted(row["prices"], reverse=True)
        if len(ys) < 2 or not row["prices"][ys[1]]:
            continue
        chg = (row["prices"][ys[0]] - row["prices"][ys[1]]) / row["prices"][ys[1]]
        key = commodity_map.to_commodity(row["item"])
        cm = commodities.get(key) if key else None
        if cm and cm.get("chg_1y") is not None:
            dirs.append((row["item"], chg, cm["chg_1y"]))
    if dirs:
        same = sum(1 for _, a, b in dirs if (a >= 0) == (b >= 0))
        st = "ok" if same >= len(dirs) * 0.6 else "warn"
        c.add("X17", "회사 매입단가 방향 ≈ 국제시세 방향", NORM, st,
              f"{len(dirs)}개 중 {same}개 방향 일치 (예: {dirs[0][0]} {dirs[0][1] * 100:+.1f}% vs 시세 {dirs[0][2] * 100:+.1f}%)",
              source_a="II-3-나 가격변동추이", source_b="원자재 시세",
              why="회사가 산 값이 국제시세와 반대로 움직이면 특수관계자 거래·장기계약을 의심할 근거가 된다.")
    else:
        c.na("X17", "회사 매입단가 방향 ≈ 국제시세 방향", NORM,
             "매입단가 3개년 또는 대응 원자재 시세가 없습니다")

    # X18 종업원급여(연결) ≥ 직원 급여총액(제출법인)
    lb = (labor or {}).get("current") or {}
    labor_won = cn.get("labor_eok") * 1e8 if cn.get("labor_eok") else None
    if labor_won and lb.get("annual_labor"):
        s = lb["annual_labor"]
        ok = labor_won >= s * 0.95
        c.add("X18", "연결 종업원급여 ≥ 제출법인 급여총액", NORM, "ok" if ok else "fail",
              f"연결 종업원급여 {_eok(labor_won):,}억 vs 제출법인 급여총액 {_eok(s):,}억",
              a=_eok(labor_won), b=_eok(s), source_a="주석 「비용의 성격별 분류」",
              source_b="VIII-1 직원 등의 현황",
              why="연결은 제출법인을 품는다. 연결이 더 작으면 어느 한쪽 숫자가 틀렸다.")
    else:
        c.na("X18", "연결 종업원급여 ≥ 제출법인 급여총액", NORM, "성격별 인건비 또는 직원 급여총액이 없습니다")

    # X19 감가상각비 ≈ 유형자산 대비 정상
    dep_eok = None
    for b in cn.get("breakdown") or []:
        if b["cat"] == "감가상각":
            dep_eok = b["amount_eok"]
    ppe = v.get("ppe", {}).get(y) if y else None
    if dep_eok and ppe:
        rate = dep_eok * 1e8 / ppe
        life = 1 / rate if rate else None
        st = "ok" if 0.03 <= rate <= 0.35 else "warn"
        c.add("X19", "감가상각비 ≈ 유형자산 대비 정상", NORM, st,
              f"감가상각 {dep_eok:,}억 ÷ 유형자산 {_eok(ppe):,}억 = {rate * 100:.1f}% "
              f"(역산 내용연수 {life:.1f}년)",
              a=dep_eok, b=_eok(ppe), source_a="주석 「비용의 성격별 분류」",
              source_b="연결 재무상태표", year=y,
              why="상각을 덜 하면 이익이 좋아 보인다. 역산 내용연수가 업계 상식을 벗어나면 확인이 필요하다.")
    else:
        c.na("X19", "감가상각비 ≈ 유형자산 대비 정상", NORM, "성격별 감가상각비 또는 유형자산이 없습니다")

    # X20 개발비 자본화 ↔ 인건비 감소 동시발생 아님
    hist = (labor or {}).get("years") or []
    dev = (d.get("intangible") or {}).get("development_won")
    if dev and len(hist) >= 2 and hist[0].get("annual_labor") and hist[1].get("annual_labor"):
        labor_chg = _pct(hist[0]["annual_labor"], hist[1]["annual_labor"])
        both = (labor_chg is not None and labor_chg < -0.05) and dev > 0
        c.add("X20", "개발비 자본화 ↔ 인건비 감소 동시발생 아님", MAJOR,
              "warn" if both else "ok",
              f"개발비 {_eok(dev):,}억 · 급여총액 {labor_chg * 100:+.1f}%",
              a=_eok(dev), b=round(labor_chg * 100, 1),
              source_a="주석 「무형자산」 개발비", source_b="VIII-1 직원 급여총액",
              why="인건비를 비용이 아니라 개발비(자산)로 돌리면 인건비는 줄고 이익은 늘어난다. "
                  "둘이 동시에 나타나면 그 통로를 의심한다(§12.5-⑤).")
    else:
        c.na("X20", "개발비 자본화 ↔ 인건비 감소 동시발생 아님", MAJOR, "개발비 또는 급여총액 2개년이 없습니다")

    # X21 특수관계자 매출 비중
    rp = d.get("related_party")
    if rp and rev:
        share = rp["sales_won"] / rev
        c.band("X21", "특수관계자 매출 비중 과다 아님", MAJOR, share, 0.30, 0.50,
               f"특수관계자 매출 {_eok(rp['sales_won']):,}억 ÷ 연결매출 {_eok(rev):,}억 = {share * 100:.1f}%",
               a=_eok(rp["sales_won"]), b=_eok(rev), source_a=rp["source"],
               source_b="연결 손익계산서", year=y,
               why="계열 안에서 도는 매출은 가격을 회사가 정할 수 있다 — 이전가격·순환거래의 통로.")
    else:
        c.na("X21", "특수관계자 매출 비중 과다 아님", MAJOR, "특수관계자 거래 주석을 찾지 못했습니다")

    # X22 미청구공사(진행률) 급증 아님
    poc = (d.get("other_financial") or {}).get("poc")
    orders = d.get("orders")
    if poc and poc.get("applicable") is False:
        c.add("X22", "미청구공사 급증 아님", NORM, "ok", "진행률적용 수주계약 해당사항 없음",
              source_a="III-8-마 진행률적용 수주계약",
              why="수주산업이 아니면 이 통로 자체가 없다.")
    elif poc or orders:
        c.add("X22", "미청구공사 급증 아님", NORM, "warn",
              "진행률적용 수주계약 있음 — 미청구공사 금액은 별도 확인 필요",
              source_a="III-8-마 진행률적용 수주계약", source_b="II-4-다 수주에 관한 사항",
              why="진행률로 매출을 인식하면 아직 청구도 못 한 돈이 매출이 된다.")
    else:
        c.na("X22", "미청구공사 급증 아님", NORM, "수주·진행률 항목을 찾지 못했습니다")

    # X23 장기체화재고 비중
    ia = (d.get("other_financial") or {}).get("inventory_audit") or {}
    inv = d.get("inventory") or {}
    stale_share = (ia["stale_won"] / inv["total_won"]
                   if (ia.get("stale_won") and inv.get("total_won")) else None)
    if stale_share is not None and stale_share <= 1.0:   # 100% 초과면 표를 잘못 집은 것
        share = stale_share
        c.band("X23", "장기체화재고 비중 과다 아님", NORM, share, 0.10, 0.25,
               f"장기체화 {_eok(ia['stale_won']):,}억 ÷ 재고 {_eok(inv['total_won']):,}억 = {share * 100:.1f}%",
               a=_eok(ia["stale_won"]), b=_eok(inv["total_won"]),
               source_a="III-8-라 재고자산 실사내역", source_b="주석 「재고자산」", year=y)
    elif inv.get("loss_pct") is not None:
        c.band("X23", "재고 평가손실충당금 비중 과다 아님", NORM, inv["loss_pct"] / 100, 0.10, 0.25,
               f"평가손실충당금 {_eok(inv['valuation_loss_won']):,}억 ÷ 총장부금액 = {inv['loss_pct']}%",
               a=inv["loss_pct"], source_a="주석 「재고자산」",
               why="장기체화 금액을 안 적은 회사가 많아 평가손실충당금 비중으로 대신 본다. "
                   "충당금이 크다는 건 이미 안 팔리는 재고가 쌓였다는 뜻이다.")
    else:
        c.na("X23", "장기체화재고 비중 과다 아님", NORM, "장기체화·평가손실 금액이 없습니다")

    # X24 경과 1년 초과 매출채권 비중
    ra = (d.get("other_financial") or {}).get("receivable_aging") or {}
    if ra.get("over_1y_pct") is not None:
        c.band("X24", "경과 1년 초과 매출채권 비중 과다 아님", MAJOR, ra["over_1y_pct"] / 100,
               0.10, 0.25,
               f"1년 초과 {ra['over_1y_pct']}% (구간 {len(ra.get('buckets') or [])}개 공시)",
               a=ra["over_1y_pct"], source_a=ra.get("source"), source_b="연결 재무상태표",
               why="오래된 매출채권은 못 받을 가능성이 큰 돈이다. 비중이 크면 매출의 질이 낮다.")
    else:
        c.na("X24", "경과 1년 초과 매출채권 비중 과다 아님", MAJOR, "경과기간별 매출채권표를 찾지 못했습니다")

    # X25 레벨3 공정가치 비중
    fv = (d.get("other_financial") or {}).get("fair_value") or {}
    if fv.get("level3_won") is not None and assets:
        share = fv["level3_won"] / assets
        c.band("X25", "레벨3 공정가치 비중 과다 아님", NORM, share, 0.10, 0.25,
               f"레벨3 {_eok(fv['level3_won']):,}억 ÷ 자산총계 {_eok(assets):,}억 = {share * 100:.1f}%",
               a=_eok(fv["level3_won"]), b=_eok(assets), source_a=fv.get("source"),
               source_b="연결 재무상태표", year=y,
               why="레벨3은 시장가격이 없어 **회사가 스스로 매긴 값**이다. 많을수록 판단의 몫이 크다.")
    else:
        c.na("X25", "레벨3 공정가치 비중 과다 아님", NORM, "공정가치 서열체계표 또는 자산총계가 없습니다")

    # X30 가동률 3년 급변 아님
    util = [(x.get("utilization_pct"), x.get("name")) for blk in ((biz or {}).get("utilization") or [])
            for x in blk.get("items", []) if x.get("utilization_pct")]
    if util:
        vals = [u for u, _ in util]
        lo, hi = min(vals), max(vals)
        st = "ok" if hi <= 130 and lo >= 40 else "warn"
        c.add("X30", "가동률 정상 범위", INFO, st,
              f"{len(vals)}개 라인 · {lo:.0f}~{hi:.0f}%",
              a=lo, b=hi, source_a="II-3-라 가동률",
              why="가동률이 100%를 크게 넘거나 반토막이면 생산능력·생산실적 어느 한쪽 표기가 다르다.")
    else:
        c.na("X30", "가동률 정상 범위", INFO, "가동률표를 찾지 못했습니다")

    # X31 인당매출 급증 아님
    if len(hist) >= 2 and rev and len(years) >= 2:
        h0, h1 = hist[0], hist[1]
        r1 = v["revenue"].get(years[1])
        if h0.get("headcount") and h1.get("headcount") and r1:
            a0 = rev / h0["headcount"]
            a1 = r1 / h1["headcount"]
            chg = _pct(a0, a1)
            c.band("X31", "인당매출 급증 아님", INFO, chg, 0.30, 0.60,
                   f"인당매출 {a0 / 1e8:.1f}억 vs 전년 {a1 / 1e8:.1f}억 ({chg * 100:+.1f}%)",
                   a=round(a0 / 1e8, 1), b=round(a1 / 1e8, 1),
                   source_a="연결 손익계산서", source_b="VIII-1 직원 등의 현황", year=years[0],
                   why="사람은 그대로인데 매출만 뛰면 자동화이거나, 매출이 부풀려진 것이다.")
        else:
            c.na("X31", "인당매출 급증 아님", INFO, "직원수 2개년이 없습니다")
    else:
        c.na("X31", "인당매출 급증 아님", INFO, "직원수 또는 매출 2개년이 없습니다")

    # X32 유효세율
    tax = v.get("tax", {}).get(y) if y else None
    pre = v.get("pretax", {}).get(y) if y else None
    if tax is not None and pre and pre > 0:
        rate = tax / pre
        st = "ok" if 0.05 <= rate <= 0.35 else "warn"
        c.add("X32", "유효세율 정상 범위(5~35%)", INFO, st,
              f"법인세 {_eok(tax):,}억 ÷ 세전이익 {_eok(pre):,}억 = {rate * 100:.1f}%",
              a=_eok(tax), b=_eok(pre), source_a="연결 손익계산서", source_b="연결 손익계산서", year=y,
              why="세금은 국세청이 걷는다 — 이익을 부풀리면 세금이 따라 늘거나, 안 늘면 그 차이가 신호다.")
    else:
        c.na("X32", "유효세율 정상 범위(5~35%)", INFO, "법인세비용 또는 세전이익이 없습니다(적자 포함)")

    # X33 배당 ≤ 영업CF
    div = v.get("dividend_paid", {}).get(y) if y else None
    cfo = v.get("cfo", {}).get(y) if y else None
    if div is not None and cfo is not None:
        d_abs = abs(div)
        st = "ok" if d_abs <= max(cfo, 0) else "warn"
        c.add("X33", "배당 ≤ 영업현금흐름", INFO, st,
              f"배당 {_eok(d_abs):,}억 vs 영업CF {_eok(cfo):,}억",
              a=_eok(d_abs), b=_eok(cfo), source_a="연결 현금흐름표", source_b="연결 현금흐름표", year=y,
              why="벌어들인 현금보다 많이 나눠주면 빚이나 자산을 헐어 배당하는 것이다.")
    else:
        c.na("X33", "배당 ≤ 영업현금흐름", INFO, "배당금지급 계정이 없습니다(무배당 포함)")

    # X34 조달자금 사용실적 = 목적대로
    fund = d.get("funding") or {}
    if fund.get("use_rows"):
        mm = fund.get("use_mismatch") or 0
        c.add("X34", "조달자금 사용실적 = 신고 목적", INFO, "ok" if mm == 0 else "warn",
              f"사용내역 {len(fund['use_rows'])}건 중 계획과 다른 항목 {mm}건",
              a=mm, source_a="III-7-2 조달자금 사용실적",
              why="돈을 어디 쓰겠다고 신고하고 다른 데 썼다면, 그 자체가 공시의 신뢰 문제다.")
    elif fund.get("issued") is False:
        c.add("X34", "조달자금 사용실적 = 신고 목적", INFO, "ok", "증권 발행을 통한 자금조달 없음",
              source_a="III-7 증권의 발행을 통한 자금조달")
    else:
        c.na("X34", "조달자금 사용실적 = 신고 목적", INFO, "자금 사용실적표를 찾지 못했습니다")


def _basis_checks(c: _Checks, dfull: dict | None, sep: dict | None, v: dict, years: list[int]):
    """X26·X27 — 연결과 별도, 그리고 연결범위."""
    d = dfull or {}
    y = years[0] if years else None
    rev = v.get("revenue", {}).get(y) if y else None
    if sep and rev:
        s = sep.get("rev")
        if s:
            ok = rev >= s * 0.98
            c.add("X26", "연결 ≥ 별도 (매출)", NORM, "ok" if ok else "fail",
                  f"연결매출 {_eok(rev):,}억 vs 별도매출 {_eok(s):,}억",
                  a=_eok(rev), b=_eok(s), source_a="연결 손익계산서", source_b="별도 손익계산서", year=y,
                  why="연결은 별도를 품는다. 별도가 더 크면 내부거래 제거나 연결범위에 문제가 있다.")
        else:
            c.na("X26", "연결 ≥ 별도 (매출)", NORM, "별도 손익이 없습니다")
    else:
        c.na("X26", "연결 ≥ 별도 (매출)", NORM, "별도재무제표를 수집하지 않았습니다")

    con = d.get("consolidation") or {}
    if not con:
        c.na("X27", "연결범위 변동 없음(3년 비교 유효)", NORM, "일반사항·사업결합 주석을 찾지 못했습니다")
    else:
        changed = bool(con.get("changed"))
        cons_won = con.get("consideration_won")
        # 규모를 알고 그게 매출의 3% 미만이면 추세 검증까지 버리진 않는다 — 다만 사실은 남긴다.
        material = True
        if changed and cons_won and rev:
            material = cons_won / rev >= 0.03
        detail = con.get("detail") or "사업결합·연결범위 변동 기재 있음"
        if changed and cons_won and rev:
            detail += f" · 이전대가 {_eok(cons_won):,}억 (매출의 {cons_won / rev * 100:.1f}%)"
        c.add("X27", "연결범위 변동 없음(3년 비교 유효)", NORM,
              ("warn" if material else "ok") if changed else "ok",
              detail[:160] if changed else "변동 기재 없음",
              a=_eok(cons_won) if cons_won else None, b=_eok(rev) if rev else None,
              source_a="주석 「일반사항」·「사업결합」", source_b="연결 손익계산서",
              why="합병·인수로 연결범위가 바뀐 해엔 전년 대비 증감률이 전부 무의미해진다 — "
                  "규모가 크면 3년 비교 검증을 자동으로 제외한다(매출의 3% 미만이면 유지).")


# --- 공개 API ---------------------------------------------------------------
def evaluate(ticker: str, *, dfull: dict | None = None, notes: dict | None = None,
             labor: dict | None = None, biz: dict | None = None,
             separate: dict | None = None) -> dict:
    """X1~X35 → 진실성%·검증범위%·등급. 재료는 호출부가 넘긴다(네트워크 중복 방지)."""
    v, years = _fin(ticker)
    c = _Checks()
    _statement_checks(c, v, years)
    _audit_checks(c, notes, dfull)
    _cross_checks(c, v, years, dfull, notes, labor, biz)
    _basis_checks(c, dfull, separate, v, years)

    # 연결범위가 바뀌었으면 3년 비교 검증은 통째로 무효(§15.8-3)
    x27 = next((x for x in c.rows if x["code"] == "X27"), None)
    if x27 and x27["status"] == "warn":
        for row in c.rows:
            if row["code"] in _TREND_CODES and row["status"] in CREDIT:
                row["status"] = "na"
                row["detail"] = "연결범위 변동(X27) — 3년 비교가 성립하지 않아 제외했습니다"

    order = {CRIT: 0, MAJOR: 1, NORM: 2, INFO: 3}
    c.rows.sort(key=lambda r: (order[r["grade"]], r["code"].rjust(4)))

    checked = [r for r in c.rows if r["status"] in CREDIT]
    w_all = sum(r["weight"] for r in c.rows)
    w_chk = sum(r["weight"] for r in checked)
    score = round(sum(r["weight"] * CREDIT[r["status"]] for r in checked) / w_chk * 100) if w_chk else None
    coverage = round(w_chk / w_all * 100) if w_all else 0

    grade, phrase = "확인불가", "검증할 수 있는 항목이 없습니다"
    if score is not None:
        for lo, g, p in GRADES:
            if score >= lo:
                grade, phrase = g, p
                break
        # 금융·지주처럼 원재료·생산·재고가 없는 회사는 검증 가능한 항목 자체가 적다.
        # 그럴 때 "숫자들이 들어맞습니다"만 보여주면 **확인한 게 적었다는 사실이 가려진다.**
        if coverage < 50:
            phrase = (f"확인할 수 있는 항목이 적었습니다 — {len(checked)}개만 검증"
                      f"(검증범위 {coverage}%). 점수보다 이 숫자를 먼저 보세요.")

    n = {k: sum(1 for r in c.rows if r["status"] == k) for k in ("ok", "warn", "fail", "na")}
    return {
        "ticker": ticker,
        "available": score is not None,
        "score_pct": score,
        "coverage_pct": coverage,
        "grade": grade,
        "phrase": phrase,
        "n_ok": n["ok"], "n_warn": n["warn"], "n_fail": n["fail"], "n_unavailable": n["na"],
        "n_total": len(c.rows),
        "checked": len(checked),
        "by_grade": [
            {"grade": g,
             "n": sum(1 for r in c.rows if r["grade"] == g),
             "ok": sum(1 for r in c.rows if r["grade"] == g and r["status"] == "ok"),
             "warn": sum(1 for r in c.rows if r["grade"] == g and r["status"] == "warn"),
             "fail": sum(1 for r in c.rows if r["grade"] == g and r["status"] == "fail"),
             "na": sum(1 for r in c.rows if r["grade"] == g and r["status"] == "na")}
            for g in (CRIT, MAJOR, NORM, INFO)
        ],
        "checks": c.rows,
        "rcept": (dfull or {}).get("rcept"),
        "url": (dfull or {}).get("url"),
        "note": "공시된 숫자들끼리의 정합성만 본다. 숫자가 처음부터 일관되게 조작됐다면 "
                "서로 맞아떨어질 수 있다 — 낮은 점수가 곧 분식이 아니고, 높은 점수가 무죄 증명도 아니다.",
        "weights": {"치명": 5, "중대": 3, "일반": 2, "참고": 1,
                    "rule": "진실성% = 일치 가중합 ÷ 검증가능 가중합 (관찰=0.5). 확인불가는 분모에서 제외."},
    }
