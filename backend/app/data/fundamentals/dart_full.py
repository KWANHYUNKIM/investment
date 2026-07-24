"""사업보고서 **전 항목** 파싱 — 원재료·생산·매출·재무·주석을 한 묶음으로 (개편계획 §15.2).

§14까지가 "필요한 표 몇 개"를 집어왔다면 여기는 **문서 전체를 항목별로 훑는다**.
목적은 하나 — §15.3의 교차검증(X1~X35)이 쓸 재료를 다 갖춰 두는 것.
검증은 *서로 다른 절에서 온 두 숫자*를 맞대볼 때만 의미가 있어서, 한 절만 잘 읽어서는
아무것도 검증되지 않는다.

  D1  II-3-가  주요 원재료 등의 현황      → 원재료별 매입액
  D2  II-4-가  매출실적                  → 품목×지역×법인 매출 3년
  D3  주석12 + III-8-다/라               → 재고 구성·평가손·장기체화
  D4  주석28   영업부문                  → 부문별 매출·영익  ← 부문 원가율의 실측
  D5  II-3-마 + 주석13                    → 생산설비 장부가·감가상각
  D6  III-8    기타 재무에 관한 사항      → 재작성·대손·경과기간·수주·공정가치
  D7  주석37 + IX + X                     → 특수관계자 거래·계열사
  D9  주석15 + II-6                       → 개발비 자본화·R&D
  D10 III-7                               → 자금조달·사용실적
  D11 주석1·38 + III-8-가                 → 연결범위 변동·사업결합
  D12 §15.4                               → **원단위 역산**(매입액÷단가÷생산량)

원칙 세 가지. ① **못 읽으면 None** — 근처 표를 대충 집어오지 않는다(그 값이 검증에 쓰이면
없느니만 못하다). ② **단위는 공시 그대로 보존**하고 환산이 확실할 때만 계산한다.
③ 파서를 고치면 ``_PARSER_VERSION`` 을 올려 옛 캐시를 버린다(§14.6에서 실제로 물린 부분).
"""
from __future__ import annotations

import json
import re
import time

from app.core.config import get_settings
from app.data.fundamentals import dart_doc as dd
from app.data.fundamentals.dart import enabled

_TTL = 30 * 24 * 3600.0
_PARSER_VERSION = 3          # v3: 2단 헤더(연도 아래 금액/비중) 열 선별

_SEG_KEYS = ("사업부문", "부문", "구분")
_NOISE = re.compile(r"^(합계|소계|계|총계|-|—|주\d*|비고)$")


def _cache_path(ticker: str):
    d = get_settings().data_dir / "dart_business"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"full_{ticker}.json"


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _key(s: str) -> str:
    """조인용 정규화 — 공백·괄호주석·특수문자를 없앤 뒤 비교한다('화장품(주1)'='화장품')."""
    t = re.sub(r"\(.*?\)", "", s or "")
    return re.sub(r"[\s㈜()（）\[\]·,./-]", "", t)


def _row_nums(row: list[str], cols: dict[int, str]) -> dict[str, float]:
    out = {}
    for ci, label in cols.items():
        if ci < len(row):
            v = dd._num(row[ci])
            if v is not None:
                out[label] = v
    return out


# --- D1  II-3-가 주요 원재료 등의 현황 --------------------------------------
def _materials_purchase(sec: str) -> dict | None:
    """[{segment, type, item, use, amount_won, pct}] + 합계. 단위는 표 캡션에서."""
    if not sec:
        return None
    i = sec.find("원재료 등의 현황")
    seg = sec[max(0, i - 400):i + 30_000] if i >= 0 else sec[:30_000]
    g = dd.pick_grid(seg, must=("품목",),
                     any_of=("매입액", "투입액", "매입유형", "구체적용도", "비중", "비율", "금액"),
                     forbid=("가격변동", "생산능력", "생산실적", "가동률"), min_rows=3)
    if not g:
        return None
    hdr = dd.header_row(g, ("품목", "매입액", "매입유형")) or 0
    head = [" ".join(x) for x in zip(*[r + [""] * (len(g[0]) - len(r)) for r in g[:hdr + 1]])] \
        if hdr else g[0]
    c_seg = dd.col_of(head, "사업부문", "부문")
    c_type = dd.col_of(head, "매입유형", "구분")
    c_item = dd.col_of(head, "품목", "원재료")
    c_use = dd.col_of(head, "구체적용도", "용도")
    # 같은 칸을 회사마다 다르게 부른다 — 매입액(대부분)·투입액(SK하이닉스)·구매액.
    c_amt = dd.col_of(head, "매입액", "매입금액", "투입액", "구매액", "금액")
    c_pct = dd.col_of(head, "비중", "비율")
    if c_item is None:
        return None
    yrs = dd.years_in_header(g)
    amt_cols: dict[int, str] = {}           # {열: 연도} — 3개년 매입액을 내는 회사도 있다
    if c_amt is None:                       # 연도열만 있는 서식 → 연도열 전부가 매입액
        amt_cols = dict(yrs)
        c_amt = min(yrs) if yrs else None
    else:
        amt_cols = {c_amt: yrs.get(c_amt) or (max(yrs.values()) if yrs else "최근")}
    if c_amt is None:
        return None

    mult = dd.unit_won(seg[:sec.find("<TABLE") + 4000] if "<TABLE" in seg else seg, 1e6)
    rows, total = [], None
    for r in g[hdr + 1:]:
        item = _clean(r[c_item]) if c_item < len(r) else ""
        segn = _clean(r[c_seg]) if (c_seg is not None and c_seg < len(r)) else ""
        typ = _clean(r[c_type]) if (c_type is not None and c_type < len(r)) else ""
        amt = dd._num(r[c_amt]) if c_amt < len(r) else None
        if amt is None:
            continue
        if dd.is_total(item) or dd.is_total(segn):
            if dd.is_total(segn) or dd.is_total(item):
                total = amt * mult if (dd.is_total(segn) and dd.is_total(item)) else total
            continue
        if dd.is_total(typ):                # 부문 소계 행
            continue
        rows.append({
            "segment": segn or None, "type": typ or None, "item": item,
            "use": _clean(r[c_use]) if (c_use is not None and c_use < len(r)) else None,
            "amount_won": amt * mult,
            "amounts": {y: dd._num(r[ci]) * mult for ci, y in amt_cols.items()
                        if ci < len(r) and dd._num(r[ci]) is not None},
            "pct": dd._num(r[c_pct]) if (c_pct is not None and c_pct < len(r)) else None,
        })
    if not rows:
        return None
    if total is None:
        total = sum(x["amount_won"] for x in rows)
    return {"rows": rows[:40], "total_won": total, "unit_won": mult,
            "source": "II-3-가 주요 원재료 등의 현황"}


# --- II-3-나 가격변동추이 (원단위의 분모가 될 단가) --------------------------
def _material_prices(sec: str) -> dict | None:
    """[{segment, type, item, price_by_year}] + 단위 사전({'원료': '원/Kg'})."""
    if not sec:
        return None
    i = sec.find("가격변동추이")
    if i < 0:
        return None
    seg = sec[max(0, i - 400):i + 12_000]
    cap = dd._flat(sec[max(0, i - 200):i + 600])
    units = {k: v for k, v in re.findall(r"([가-힣A-Za-z]{1,10})\s*[-–]\s*(원\s*/\s*[A-Za-z가-힣]{1,6})", cap)}
    g = dd.pick_grid(seg, must=("품목",), any_of=("사업부문", "매입유형"),
                     forbid=("매입액", "생산능력", "가동률"), min_rows=2)
    if not g:
        return None
    yrs = dd.years_in_header(g)
    if len(yrs) < 2:
        return None
    hdr = dd.header_row(g, ("품목",)) or 0
    head = g[hdr]
    c_seg = dd.col_of(head, "사업부문", "부문")
    c_type = dd.col_of(head, "매입유형", "구분")
    c_item = dd.col_of(head, "품목", "원재료")
    if c_item is None:
        return None
    rows = []
    for r in g[hdr + 1:]:
        item = _clean(r[c_item]) if c_item < len(r) else ""
        if not item or _NOISE.match(item):
            continue
        vals = {y: dd._num(r[ci]) for ci, y in yrs.items()
                if ci < len(r) and dd._num(r[ci]) is not None}
        if not vals:
            continue
        typ = _clean(r[c_type]) if (c_type is not None and c_type < len(r)) else None
        rows.append({
            "segment": _clean(r[c_seg]) if (c_seg is not None and c_seg < len(r)) else None,
            "type": typ, "item": item, "prices": vals,
            "unit": units.get(_clean(typ or ""), None) or (list(units.values())[0] if len(units) == 1 else None),
        })
    if not rows:
        return None
    return {"rows": rows[:40], "unit_map": units, "caption": cap[:160],
            "source": "II-3-나 원재료 가격변동추이"}


# --- II-3-다/라 생산능력·생산실적 (부문별) ----------------------------------
def _production(sec: str, kind: str) -> list[dict]:
    """생산능력('능력') 또는 생산실적('실적') 표들 → [{segment, item, site, unit, values{연도:값}}].

    회사가 **부문마다 표를 따로**(단위도 따로) 내는 경우가 많아 표를 하나만 집으면 안 된다.
    """
    if not sec:
        return []
    anchor = "생산능력" if kind == "능력" else "생산실적"
    out: list[dict] = []
    for m in re.finditer(anchor, sec):
        seg = sec[m.start():m.start() + 9_000]
        unit_cap = dd._flat(sec[max(0, m.start() - 100):m.start() + 700])
        mu = re.search(r"단위\s*[:：]\s*([^)<\n]{1,80})", unit_cap)
        unit = _clean(mu.group(1)) if mu else None
        for g in dd.grids(seg, 2):
            if len(g) < 2:
                continue
            yrs = dd.years_in_header(g)
            hdr = dd.header_row(g, ("사업부문", "품목", "사업소")) or 0
            if len(yrs) < 2 or dd.col_of(g[hdr], "가동률") is not None:
                continue
            head = g[hdr]
            c_seg = dd.col_of(head, "사업부문", "부문")
            c_item = dd.col_of(head, "품목")
            c_site = dd.col_of(head, "사업소", "공장", "생산공장")
            for r in g[hdr + 1:]:
                name = _clean(r[c_seg]) if (c_seg is not None and c_seg < len(r)) else ""
                if not name or dd.is_total(name):
                    continue
                vals = {y: dd._num(r[ci]) for ci, y in yrs.items()
                        if ci < len(r) and dd._num(r[ci]) is not None}
                if not vals:
                    continue
                out.append({
                    "segment": name,
                    "item": _clean(r[c_item]) if (c_item is not None and c_item < len(r)) else None,
                    "site": _clean(r[c_site]) if (c_site is not None and c_site < len(r)) else None,
                    "unit": unit, "values": vals,
                })
            break
    # 같은 표를 두 번 잡는 경우(제목이 두 번 나오는 서식) 제거
    seen, uniq = set(), []
    for x in out:
        k = (x["segment"], x["site"], x["item"], tuple(sorted(x["values"].items())))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(x)
    return uniq[:60]


# --- D2  II-4-가 매출실적 ----------------------------------------------------
def _sales_mix(sec: str) -> dict | None:
    """[{region, entity, segment, sale_type, item, qualifier, values{연도:원}}] + 연도별 합계."""
    if not sec:
        return None
    i = sec.find("매출실적")
    seg = sec[max(0, i - 400):i + 60_000] if i >= 0 else sec[:60_000]
    g = dd.pick_grid(seg, must=("품목",), any_of=("사업부문", "매출유형", "지역", "법인"),
                     forbid=("수주", "원재료", "가격변동"), min_rows=3, limit=6)
    if not g:
        return None
    yrs = dd.years_in_header(g)
    if not yrs:
        return None
    hdr = dd.header_row(g, ("품목", "매출유형", "사업부문")) or 0
    head = g[hdr]
    c_reg = dd.col_of(head, "지역")
    c_ent = dd.col_of(head, "법인", "회사")
    c_seg = dd.col_of(head, "사업부문", "부문")
    c_typ = dd.col_of(head, "매출유형")
    c_item = dd.col_of(head, "품목")
    first_val = min(yrs)
    mult = dd.unit_won(dd._flat(seg[:3000]), 1e6)

    rows, totals = [], {}
    _QUAL = ("수출", "내수", "소계", "합계", "계", "국내", "해외")
    for r in g[hdr + 1:]:
        labels = [_clean(c) for c in r[:first_val]]
        vals = {y: dd._num(r[ci]) for ci, y in yrs.items()
                if ci < len(r) and dd._num(r[ci]) is not None}
        if not vals:
            continue
        qual = next((x for x in reversed(labels) if x in _QUAL), None)
        # 표 맨 아래 총계 블록(농심 '매출총계', LG '합계')은 수출/내수/합계 세 줄로 온다.
        # 그중 **합계 줄만** 총계로 쓴다 — 수출 줄을 총계로 잡으면 매출이 절반이 된다.
        if labels and dd.is_total(labels[0]):
            if qual in (None, "합계", "계", "소계"):
                totals = {y: v * mult for y, v in vals.items()}
            continue
        rows.append({
            "region": labels[c_reg] if (c_reg is not None and c_reg < len(labels)) else None,
            "entity": labels[c_ent] if (c_ent is not None and c_ent < len(labels)) else None,
            "segment": labels[c_seg] if (c_seg is not None and c_seg < len(labels)) else None,
            "sale_type": labels[c_typ] if (c_typ is not None and c_typ < len(labels)) else None,
            "item": labels[c_item] if (c_item is not None and c_item < len(labels)) else None,
            "qualifier": qual,
            "values": {y: v * mult for y, v in vals.items()},
        })
    if not rows:
        return None
    if not totals:
        # 품목별 소계 행이 있으면 그것만 더한다(수출+내수를 또 더하면 이중계상).
        # 회사에 따라 소계를 '합계'로 적는다(농심·LG화학) — 매출에누리 차감행도 여기 들어 있어
        # 함께 더해야 총계가 맞는다.
        subs = [x for x in rows if x["qualifier"] in ("소계", "합계", "계")]
        base = subs or [x for x in rows if x["qualifier"] not in ("소계", "합계", "계")]
        for x in base:
            for y, v in x["values"].items():
                totals[y] = totals.get(y, 0.0) + v
    return {"rows": rows[:80], "total_by_year": totals, "unit_won": mult,
            "latest_period": yrs[min(yrs)],       # 표는 최신 연도가 왼쪽이다
            "source": "II-4-가 매출실적"}


# --- D4  주석28 영업부문 ------------------------------------------------------
# 부문 표의 행 이름 → 지표. **외부매출과 총부문수익을 갈라야** X11(부문합=연결매출)이 맞는다.
# 총부문수익엔 부문간 내부거래가 들어 있어 그대로 더하면 연결매출보다 항상 크다.
_SEG_METRIC = (("inter", ("부문간", "내부거래", "내부매출", "연결조정", "부문간거래")),
               ("revenue_ext", ("외부고객", "외부매출", "외부수익", "외부고객으로부터의수익")),
               ("op", ("영업손익", "영업이익", "영업이익(손실)")),
               ("depreciation", ("감가상각", "상각비")),
               ("revenue", ("총부문수익", "부문수익", "매출액", "매출", "영업수익", "수익")),
               ("assets", ("부문자산", "총자산", "자산")))


def _metric_of(name: str) -> str | None:
    n = re.sub(r"\s+", "", name or "")
    if not n or n.startswith("("):
        return None
    for key, kws in _SEG_METRIC:
        if any(k in n for k in kws):
            if key in ("revenue", "revenue_ext") and re.search(r"원가|총이익|채권|비용|이익률", n):
                continue
            if key == "assets" and re.search(r"부채|감소|증가|상각", n):
                continue
            return key
    return None


def _segments(nt: str | None) -> dict | None:
    """부문별 매출·영업손익·자산. **금액이 열(부문)로 눕는 서식**이 흔해 양쪽을 다 본다."""
    if not nt:
        return None
    mult = dd.unit_won(nt, 1e3)
    for g in dd.grids(nt, 8):
        if len(g) < 3:
            continue
        # ① 지표가 행 라벨(0열), 부문이 열 — 한국콜마형
        metrics = {i: m for i, r in enumerate(g) if (m := _metric_of(r[0] if r else ""))}
        if {"revenue", "revenue_ext"} & set(metrics.values()) and len(metrics) >= 2:
            names_row = None
            for i in range(min(4, len(g))):
                if i in metrics:
                    break
                cand = g[i]
                nonnum = [c for c in cand[1:] if c and not re.fullmatch(r"[\d,.\s()-]+", c)]
                if len(nonnum) >= 2 and not all(re.search(r"당기|전기|기말|단위", c or "") for c in nonnum):
                    names_row = i
            if names_row is None:
                continue
            hdr = g[names_row]
            segs: dict[str, dict] = {}
            for ci in range(1, len(hdr)):
                name = _clean(hdr[ci])
                if not name or dd.is_total(name) or re.search(r"단위|당기|전기", name):
                    continue
                rec = segs.setdefault(name, {"name": name})
                for ri, key in metrics.items():
                    v = dd._num(g[ri][ci]) if ci < len(g[ri]) else None
                    if v is not None and (key + "_won") not in rec:
                        rec[key + "_won"] = v * mult
            for rec in segs.values():
                ext, tot, inter = (rec.pop("revenue_ext_won", None), rec.get("revenue_won"),
                                   rec.pop("inter_won", None))
                if ext is not None:
                    rec["revenue_won"] = ext                     # 외부매출이 있으면 그게 정답
                elif tot is not None and inter is not None:
                    rec["revenue_won"] = tot - inter             # 총부문수익 − 부문간
            segs = {k: v for k, v in segs.items() if v.get("revenue_won")}
            if len(segs) >= 2:
                return _seg_out(list(segs.values()), mult)
        # ② 부문이 행 라벨, 지표가 열 머리 — 흔한 반대 서식
        hdr_i = dd.header_row(g, ("매출", "영업")) or 0
        head = g[hdr_i]
        c_rev = dd.col_of(head, "외부고객", "외부매출", "매출액", "매출", "영업수익")
        c_op = dd.col_of(head, "영업이익", "영업손익")
        if c_rev is None or c_op is None:
            continue
        rows = []
        for r in g[hdr_i + 1:]:
            name = _clean(r[0]) if r else ""
            if not name or dd.is_total(name) or _NOISE.match(name):
                continue
            rev = dd._num(r[c_rev]) if c_rev < len(r) else None
            if rev is None:
                continue
            rows.append({"name": name, "revenue_won": rev * mult,
                         "op_won": (dd._num(r[c_op]) * mult) if (c_op < len(r) and dd._num(r[c_op]) is not None) else None})
        if len(rows) >= 2:
            return _seg_out(rows, mult)
    return None


def _seg_out(rows: list[dict], mult: float) -> dict:
    tot = sum(r["revenue_won"] for r in rows if r.get("revenue_won")) or 1.0
    for r in rows:
        if r.get("revenue_won") and r.get("op_won") is not None:
            r["op_margin"] = round(r["op_won"] / r["revenue_won"], 4)
        r["revenue_pct"] = round(r["revenue_won"] / tot * 100, 1) if r.get("revenue_won") else None
    rows.sort(key=lambda x: x.get("revenue_won") or 0, reverse=True)
    return {"rows": rows[:12], "total_revenue_won": tot, "unit_won": mult,
            "source": "연결재무제표 주석 「영업부문」"}


# --- D3  주석12 재고자산 ------------------------------------------------------
_INV_CAT = (("raw", ("원재료", "원료", "재료")), ("wip", ("재공품", "반제품")),
            ("fg", ("제품", "상품")), ("supply", ("저장품", "미착품", "부재료")))


def _inventory(nt: str | None) -> dict | None:
    if not nt:
        return None
    mult = dd.unit_won(nt, 1e3)
    g = dd.pick_grid(nt, any_of=("장부금액", "평가손실", "총장부금액", "취득원가"), min_rows=3, limit=4)
    if not g:
        return None
    hdr = dd.header_row(g, ("장부금액", "평가손실", "총장부금액", "당기말", "구분")) or 0
    head = g[hdr]
    c_gross = dd.col_of(head, "총장부금액", "취득원가")
    c_loss = dd.col_of(head, "평가손실", "평가충당금", "손실충당금")
    c_book = dd.col_of(head, "장부금액")
    if c_book is not None and c_book == c_gross:
        c_book = None
    agg: dict[str, float] = {}
    loss_total, book_total, gross_total = 0.0, 0.0, 0.0
    items = []
    for r in g[hdr + 1:]:
        name = _clean(r[0]) if r else ""
        if not name:
            continue
        nums = [dd._num(c) for c in r[1:]]
        nums = [n for n in nums if n is not None]
        if not nums:
            continue
        gross = dd._num(r[c_gross]) if (c_gross is not None and c_gross < len(r)) else nums[0]
        loss = dd._num(r[c_loss]) if (c_loss is not None and c_loss < len(r)) else None
        book = dd._num(r[c_book]) if (c_book is not None and c_book < len(r)) else (
            (gross + loss) if (gross is not None and loss is not None) else gross)
        if dd.is_total(name):
            gross_total, book_total = (gross or 0) * mult, (book or 0) * mult
            loss_total = abs(loss or 0) * mult
            continue
        items.append({"name": name, "book_won": (book or 0) * mult,
                      "loss_won": abs(loss or 0) * mult})
        for key, kws in _INV_CAT:
            if any(k in name for k in kws):
                agg[key] = agg.get(key, 0.0) + (book or 0) * mult
                break
    if not items:
        return None
    if not book_total:
        book_total = sum(x["book_won"] for x in items)
        loss_total = sum(x["loss_won"] for x in items)
    return {"items": items[:12], "total_won": book_total, "gross_won": gross_total or None,
            "valuation_loss_won": loss_total, "unit_won": mult,
            "loss_pct": round(loss_total / gross_total * 100, 2) if gross_total else None,
            **{f"{k}_won": v for k, v in agg.items()},
            "source": "연결재무제표 주석 「재고자산」"}


# --- D6  III-8 기타 재무에 관한 사항 ------------------------------------------
def _other_financial(sec: str) -> dict:
    """재작성·대손·경과기간·재고실사·수주진행률·공정가치 서열 — **분식 탐지의 노른자**."""
    out: dict = {}
    if not sec:
        return out
    flat = dd._flat(sec)

    # 가. 재무제표 재작성 — "없습니다"를 먼저 본다(있다고 잘못 찍으면 치명 검증이 오탐).
    # 제목('가. 재무제표 재작성 등 유의사항')과 항목('1) 재무제표 재작성 - …')이 잇달아 나온다.
    # 제목 쪽을 읽으면 설명이 "등 유의사항 …"으로 시작해 읽히지 않는다 → 뒤엣것을 쓴다.
    ms = list(re.finditer(r"재무제표\s*재작성", flat))[:2]
    m = ms[-1] if ms else None
    if m:
        tail = flat[m.end():m.end() + 260]
        none = bool(re.search(r"해당\s*사항\s*없|해당없|없습니다|미해당", tail))
        # 재작성에도 결이 있다. **오류수정**은 "지난 숫자가 틀렸다"는 뜻이고,
        # 사업 매각에 따른 **중단영업 재분류**는 비교표시를 맞추려 다시 쓴 것이다.
        # 둘을 같은 무게로 다루면 멀쩡한 회사가 치명 감점을 받는다.
        kind = None
        if not none:
            if re.search(r"오류|정정|수정", tail):
                kind = "오류수정"
            elif re.search(r"중단영업|매각|처분|회계정책|기준서", tail):
                kind = "중단영업·회계정책 변경"
            else:
                kind = "사유 미상"
        out["restatement"] = {"occurred": not none, "kind": kind, "detail": _clean(tail[:160])}

    # 나. 대손충당금 — 설정률과 경과기간별 잔액
    m = re.search(r"경과기간별[^<]{0,20}매출채권", sec)
    if m:
        g = dd.pick_grid(sec[m.start():m.start() + 6000], any_of=("1년초과", "3월", "6월", "구성비율"),
                         min_rows=2, limit=3)
        if g:
            mult = dd.unit_won(sec[m.start():m.start() + 1200], 1e6)
            hdr = g[0]
            amt_row = next((r for r in g[1:] if re.search(r"금액", r[0] or "")), None)
            pct_row = next((r for r in g[1:] if re.search(r"구성|비율", r[0] or "")), None)
            buckets = []
            for ci in range(1, len(hdr)):
                label = _clean(hdr[ci])
                if not label or dd.is_total(label):
                    continue
                amt = dd._num(amt_row[ci]) if (amt_row and ci < len(amt_row)) else None
                pc = dd._num(pct_row[ci]) if (pct_row and ci < len(pct_row)) else None
                if amt is None and pc is None:
                    continue
                buckets.append({"bucket": label, "amount_won": (amt * mult) if amt is not None else None,
                                "pct": pc})
            if buckets:
                over1y = [b for b in buckets if re.search(r"1년\s*초과|1년초과|초과", b["bucket"])]
                out["receivable_aging"] = {
                    "buckets": buckets,
                    "over_1y_pct": over1y[0]["pct"] if over1y else None,
                    "source": "III-8-나 경과기간별 매출채권 잔액현황",
                }

    # 라. 재고자산 실사 — 감사인 입회 여부·장기체화
    m = re.search(r"실사(?:내역|방법)", flat)
    if m:
        seg = flat[m.start():m.start() + 1400]
        out["inventory_audit"] = {
            "auditor_attended": bool(re.search(r"(외부감사인|감사인)[^.]{0,80}(입회|참여)", seg)),
            "long_stale_mentioned": bool(re.search(r"장기체화", seg)),
            "detail": _clean(seg[:200]),
        }
    m = re.search(r"장기체화재고[^<]{0,40}", sec)
    if m:
        # 장기체화 금액을 안 적고 바로 다음 절 표가 이어지는 회사가 많다 → **바로 뒤 3천 자**
        # 안의 작은 표만 인정한다. 아니면 전사 재고표를 집어 '장기체화 111%'가 나온다.
        near = sec[m.start():m.start() + 3000]
        g = dd.pick_grid(near, min_rows=2, limit=1)
        stale = None
        if g and len(g) <= 8 and re.search(r"체화|장기", dd.head_text(g) + dd._flat(near[:600])):
            mult = dd.unit_won(near[:1500], 1e3)
            tot = next((dd._num(c) for r in g for c in r[1:]
                        if dd.is_total(_clean(r[0])) and dd._num(c)), None)
            stale = (tot * mult) if tot else None
        out.setdefault("inventory_audit", {})["stale_won"] = stale

    # 마. 진행률적용 수주계약
    m = re.search(r"진행률\s*적용\s*수주|진행률적용\s*수주", flat)
    if m:
        tail = flat[m.end():m.end() + 160]
        out["poc"] = {"applicable": not bool(re.search(r"해당\s*사항\s*없|해당없|없습니다", tail)),
                      "detail": _clean(tail[:120])}

    # 바. 공정가치 서열체계 — 레벨3(회사가 스스로 매긴 값) 비중
    m = re.search(r"서열체계", sec)
    if m:
        g = dd.pick_grid(sec[m.start():m.start() + 9000], any_of=("수준3", "수준 3", "수준1"),
                         min_rows=2, limit=4)
        if g:
            mult = dd.unit_won(sec[m.start():m.start() + 2000], 1e3)
            hdr_i = dd.header_row(g, ("수준", "합계")) or 0
            head = g[hdr_i]
            c3 = dd.col_of(head, "수준3", "수준 3", "레벨3")
            ctot = dd.col_of(head, "합계", "계")
            if c3 is not None:
                # 이 표엔 **공정가치로 측정되지 않는 금융부채**(차입금 등)까지 서열만 표기해
                # 같이 실린다. 그걸 더하면 LG화학이 '레벨3 26%'로 찍힌다(차입금 21조).
                # 자산 구간만, 그것도 부채 행을 빼고 센다.
                lv3 = tot = 0.0
                for r in g[hdr_i + 1:]:
                    name = _clean(r[0]) if r else ""
                    if re.search(r"측정되지\s*않는", name.replace(" ", "")):
                        break
                    if dd.is_total(name) or "부채" in name:
                        continue
                    lv3 += (dd._num(r[c3]) or 0) if c3 < len(r) else 0
                    if ctot is not None and ctot < len(r):
                        tot += dd._num(r[ctot]) or 0
                out["fair_value"] = {
                    "level3_won": lv3 * mult, "total_won": (tot * mult) if tot else None,
                    "level3_pct": round(lv3 / tot * 100, 1) if tot else None,
                    "basis": "공정가치로 측정되는 금융자산(부채·비측정 항목 제외)",
                    "source": "III-8-바 공정가치 서열체계",
                }

    # 다. 최근 3사업연도 재고자산 보유현황(전사 합계표)
    m = re.search(r"재고자산\s*현황|재고자산의\s*사업부문별|재고자산\s*보유현황", sec)
    if m:
        g = dd.pick_grid(sec[m.start():m.start() + 25_000], must=("계정과목",), min_rows=3, limit=6)
        if g:
            yrs = dd.years_in_header(g)
            mult = dd.unit_won(sec[m.start():m.start() + 3000], 1e6)
            if yrs:
                tot_row = next((r for r in g[1:] if dd.is_total(_clean(r[0]))), None)
                if tot_row:
                    out["inventory_3y"] = {
                        "total_by_year": {y: (dd._num(tot_row[ci]) or 0) * mult
                                          for ci, y in yrs.items() if ci < len(tot_row)},
                        "unit_won": mult, "source": "III-8-다 재고자산 보유현황",
                    }
    return out


# --- D7  주석37 특수관계자 + IX 계열회사 + X 대주주 거래 ----------------------
def _related_party(nt: str | None) -> dict | None:
    if not nt:
        return None
    m = re.search(r"주요\s*거래\s*내역|거래내역", nt)
    seg = nt[m.start():m.start() + 20_000] if m else nt
    g = dd.pick_grid(seg, any_of=("매출", "매입", "특수관계자"), min_rows=3, limit=5)
    if not g:
        return None
    mult = dd.unit_won(nt, 1e3)
    hdr_i = dd.header_row(g, ("매출", "매입")) or 0
    head = g[hdr_i]
    c_sale = dd.col_of(head, "매출")
    c_buy = dd.col_of(head, "매입")
    c_name = dd.col_of(head, "특수관계자", "회사명", "거래처", "명칭")
    if c_sale is None and c_buy is None:
        return None
    first_val = min(x for x in (c_sale, c_buy) if x is not None)
    if c_name is None:
        c_name = max(0, first_val - 1)
    sales = buys = 0.0
    parties = []
    for r in g[hdr_i + 1:]:
        labels = [_clean(c) for c in r[:first_val]]
        name = _clean(r[c_name]) if c_name < len(r) else ""
        s = dd._num(r[c_sale]) if (c_sale is not None and c_sale < len(r)) else None
        b = dd._num(r[c_buy]) if (c_buy is not None and c_buy < len(r)) else None
        if s is None and b is None:
            continue
        # 합계행을 같이 더하면 총액이 정확히 두 배가 된다(실제로 발생) → 라벨 어디든 '합계'면 버린다.
        if any(dd.is_total(x) for x in labels) or not re.search(r"[가-힣A-Za-z]", name):
            continue
        sales += (s or 0)
        buys += (b or 0)
        parties.append({"name": name, "sales_won": (s or 0) * mult, "purchase_won": (b or 0) * mult})
    if not parties:
        return None
    parties.sort(key=lambda x: x["sales_won"] + x["purchase_won"], reverse=True)
    return {"parties": parties[:12], "sales_won": sales * mult, "purchase_won": buys * mult,
            "n_parties": len(parties), "unit_won": mult,
            "source": "연결재무제표 주석 「특수관계자와의 거래」"}


def _affiliates(sec_ix: str | None, sec_x: str | None) -> dict:
    out: dict = {}
    if sec_ix:
        flat = dd._flat(sec_ix)
        m = re.search(r"계열회사[^0-9]{0,20}(\d+)\s*개", flat)
        if m:
            out["n_affiliates"] = int(m.group(1))
        g = dd.pick_grid(sec_ix, any_of=("회사명", "상장", "법인"), min_rows=3, limit=6)
        if g:
            names = [_clean(r[c]) for r in g[1:] for c in range(min(3, len(r)))
                     if _clean(r[c]) and re.search(r"[가-힣A-Za-z]", _clean(r[c]))]
            out.setdefault("n_affiliates", len({n for n in names}) or None)
    if sec_x:
        flat = dd._flat(sec_x)
        out["major_shareholder_tx"] = not bool(re.search(r"해당\s*사항\s*없|해당없|없습니다", flat[:600]))
        out["major_shareholder_note"] = _clean(flat[:200])
    return out


# --- D9  주석15 무형자산(개발비) + II-6 연구개발 ------------------------------
def _intangible(nt: str | None) -> dict | None:
    if not nt:
        return None
    mult = dd.unit_won(nt, 1e3)
    for g in dd.grids(nt, 6):
        rows = {re.sub(r"\s+", "", (r[0] or "")): r for r in g}
        dev = next((v for k, v in rows.items() if k.startswith("개발비")), None)
        if dev is None:
            continue
        # 무형자산 주석은 취득원가·상각누계액·장부금액이 한 줄에 온다. 장부금액 열이
        # 헤더로 잡히면 그걸 쓰고, 못 잡으면 최대값(대개 취득원가)임을 basis 로 밝힌다.
        hdr_i = dd.header_row(g, ("장부금액", "기말", "취득원가")) or 0
        c_book = dd.col_of(g[hdr_i], "기말장부금액", "장부금액", "기말")
        v = dd._num(dev[c_book]) if (c_book is not None and c_book < len(dev)) else None
        basis = "장부금액"
        if v is None:
            nums = [n for n in (dd._num(c) for c in dev[1:]) if n is not None]
            if not nums:
                continue
            v, basis = max(nums), "표 내 최대값(장부금액 열 미식별)"
        return {"development_won": v * mult, "basis": basis, "unit_won": mult,
                "source": "연결재무제표 주석 「무형자산」 개발비"}
    return None


def _rnd(sec: str | None) -> dict | None:
    """II-6 연구개발활동 — 연구개발비 총액·매출대비 비율."""
    if not sec:
        return None
    flat = dd._flat(sec)
    m = re.search(r"매출액\s*대비\s*(?:연구개발비\s*)?비율[^0-9]{0,20}([\d.]+)\s*%", flat)
    g = dd.pick_grid(sec, any_of=("연구개발비용", "연구개발비", "매출액대비"), min_rows=2, limit=6)
    total = None
    if g:
        mult = dd.unit_won(sec, 1e3)
        for r in g:
            nm = re.sub(r"\s+", "", r[0] or "")
            if re.search(r"연구개발비용계|연구개발비계|합계|연구개발비용합계", nm):
                nums = [dd._num(c) for c in r[1:]]
                nums = [n for n in nums if n is not None]
                if nums:
                    total = max(nums) * mult
                    break
    if total is None and not m:
        return None
    return {"rnd_won": total, "rnd_pct_of_sales": float(m.group(1)) if m else None,
            "source": "II-6 연구개발활동"}


# --- D10  III-7 자금조달·사용실적 ----------------------------------------------
def _funding(sec7: str | None, sec72: str | None) -> dict | None:
    out: dict = {}
    if sec72:
        flat = dd._flat(sec72)
        out["use_reported"] = not bool(re.search(r"해당\s*사항\s*없|해당없", flat[:400]))
        g = dd.pick_grid(sec72, any_of=("실제자금사용", "사용내역", "조달금액", "차이발생"), min_rows=2, limit=6)
        if g:
            hdr = g[0]
            c_plan = dd.col_of(hdr, "사용용도", "자금사용계획", "사용계획")
            c_act = dd.col_of(hdr, "실제자금사용", "실제사용", "사용내역")
            rows = []
            for r in g[1:]:
                if not any(_clean(c) for c in r):
                    continue
                plan = _clean(r[c_plan]) if (c_plan is not None and c_plan < len(r)) else None
                act = _clean(r[c_act]) if (c_act is not None and c_act < len(r)) else None
                # 2단 헤더의 아래 머리행이 데이터로 새어 들어오면 '계획≠실제'가 1건 잡힌다.
                if re.fullmatch(r"사용용도|내용|구분|사용목적", plan or "") or \
                        re.fullmatch(r"내용|구분|사용내역", act or ""):
                    continue
                rows.append({"plan": plan, "actual": act})
            if rows:
                out["use_rows"] = rows[:8]
                # '채무상환자금및시설자금'으로 신고하고 '시설자금'에 썼다면 **용도 안**이다.
                # 문자열이 다르다고 어긋났다고 하면 정상 집행이 전부 경보가 된다.
                def _off(x):
                    p, a = _key(x["plan"] or ""), _key(x["actual"] or "")
                    return bool(p and a and p not in a and a not in p)

                mismatch = [x for x in rows if _off(x)]
                out["use_mismatch"] = len(mismatch)
    if sec7:
        flat = dd._flat(sec7)
        out["issued"] = not bool(re.search(r"해당\s*사항\s*없|해당없", flat[:400]))
    return out or None


# --- D11  연결범위·사업결합 ----------------------------------------------------
def _consolidation(nt_general: str | None, nt_comb: str | None, sec38: str | None) -> dict:
    out: dict = {"changed": False}
    if nt_comb:
        flat = dd._flat(nt_comb)
        none = bool(re.search(r"해당\s*사항\s*없|해당없|없습니다", flat[:400]))
        out["business_combination"] = not none
        if not none:
            out["changed"] = True
            # 피취득자와 이전대가를 뽑아 둔다 — **규모를 모르면** 3년 비교를 통째로 버려야 하지만,
            # 매출의 1%짜리 인수까지 무효 처리하면 멀쩡한 추세 검증이 다 날아간다(§15.8-3 보정).
            who = re.search(r"피취득자\s*명칭\s*([^\s]{2,30}?)\s*(?:피취득자|취득일|사업)", flat)
            amt = re.search(r"이전대가[^\d]{0,40}([\d,]{4,})", flat)
            mult = dd.unit_won(nt_comb, 1e3)
            out["acquiree"] = _clean(who.group(1)) if who else None
            out["consideration_won"] = (dd._num(amt.group(1)) * mult) if amt else None
            out["detail"] = "사업결합 있음" + (f" — 취득: {out['acquiree']}" if out["acquiree"] else "")
    if nt_general:
        flat = dd._flat(nt_general)
        m = re.search(r"(신규\s*(?:연결|편입)|연결\s*제외|지배력\s*상실)", flat)
        if m:
            out["changed"] = True
            out.setdefault("detail", _clean(flat[max(0, m.start() - 60):m.start() + 160]))
        # 종속기업 수(당기/전기)는 표 행수로 센다 — 회사마다 표기가 달라 숫자 추출은 안 한다.
        g = dd.pick_grid(nt_general, any_of=("종속기업", "지분율", "소재지"), min_rows=3, limit=6)
        if g:
            out["n_subsidiaries"] = max(0, len(g) - 1)
    if sec38:
        flat = dd._flat(sec38)
        if re.search(r"합병|분할|영업양수도|주식교환", flat[:3000]) and not re.search(
                r"해당\s*사항\s*없", flat[:200]):
            out["merger_mentioned"] = True
    return out


# --- V-1 외부감사(감사의견·감사시간) -------------------------------------------
def _audit_meta(sec: str | None) -> dict | None:
    """감사인·감사의견 3개년 + 감사보수·시간 3개년. **감사시간 급감은 그 자체로 신호다.**"""
    if not sec:
        return None
    out: dict = {}
    g = dd.pick_grid(sec, any_of=("감사의견", "감사인", "핵심감사사항"),
                     forbid=("보수",), min_rows=2, limit=4)
    if g:
        hdr_i = dd.header_row(g, ("감사의견", "감사인")) or 0
        head = g[hdr_i]
        c_y = dd.col_of(head, "사업연도")
        c_kind = dd.col_of(head, "구분")
        c_auditor = dd.col_of(head, "감사인")
        c_op = dd.col_of(head, "감사의견")
        c_gc = dd.col_of(head, "계속기업")
        c_emph = dd.col_of(head, "강조사항")
        c_kam = dd.col_of(head, "핵심감사사항")
        years = []
        for r in g[hdr_i + 1:]:
            if c_op is None or c_op >= len(r):
                continue
            op = _clean(r[c_op])
            if not op:
                continue
            kind = _clean(r[c_kind]) if (c_kind is not None and c_kind < len(r)) else ""
            years.append({
                "period": _clean(r[c_y]) if (c_y is not None and c_y < len(r)) else None,
                "kind": kind or None,
                "auditor": _clean(r[c_auditor]) if (c_auditor is not None and c_auditor < len(r)) else None,
                "opinion": op,
                "going_concern": _clean(r[c_gc]) if (c_gc is not None and c_gc < len(r)) else None,
                "emphasis": _clean(r[c_emph]) if (c_emph is not None and c_emph < len(r)) else None,
                "kam": _clean(r[c_kam])[:80] if (c_kam is not None and c_kam < len(r)) else None,
            })
        if years:
            cons = [y for y in years if y["kind"] and "연결" in y["kind"]] or years
            out["opinions"] = years[:8]
            out["latest_opinion"] = cons[0]["opinion"]
            out["auditors"] = [y["auditor"] for y in cons if y["auditor"]][:4]
            out["auditor_changed"] = bool(len({a for a in out["auditors"][:2] if a}) > 1)

    m = re.search(r"감사용역\s*체결\s*현황", sec)
    if m:
        g2 = dd.pick_grid(sec[m.start():m.start() + 9000], any_of=("보수", "시간"), min_rows=2, limit=3)
        if g2:
            hdr_i = dd.header_row(g2, ("보수", "시간")) or 0
            head = g2[hdr_i]
            # '감사계약내역 / 실제수행내역' 이 각각 (보수, 시간) 2열 → 실제수행 쪽을 쓴다
            time_cols = [j for j, c in enumerate(head) if "시간" in re.sub(r"\s+", "", c or "")]
            fee_cols = [j for j, c in enumerate(head) if "보수" in re.sub(r"\s+", "", c or "")]
            rows = []
            for r in g2[hdr_i + 1:]:
                per = _clean(r[0]) if r else ""
                if not per or "기" not in per:
                    continue
                hours = next((dd._num(r[j]) for j in reversed(time_cols) if j < len(r) and dd._num(r[j])), None)
                fee = next((dd._num(r[j]) for j in reversed(fee_cols) if j < len(r) and dd._num(r[j])), None)
                if hours or fee:
                    rows.append({"period": per, "hours": hours, "fee_mn": fee})
            if rows:
                out["audit_service"] = rows[:4]
                if len(rows) >= 2 and rows[0]["hours"] and rows[1]["hours"]:
                    out["hours_chg"] = round(rows[0]["hours"] / rows[1]["hours"] - 1, 4)
                if len(rows) >= 2 and rows[0]["fee_mn"] and rows[1]["fee_mn"]:
                    out["fee_chg"] = round(rows[0]["fee_mn"] / rows[1]["fee_mn"] - 1, 4)
    return out or None


# --- XI 제재·우발부채 -----------------------------------------------------------
def _sanctions(sec_xi3: str | None, sec_xi2: str | None, nt_cont: str | None) -> dict:
    """제재 이력과 우발부채 — 숫자가 아니라 **회사가 남긴 흔적**이라 텍스트로 읽는다."""
    out: dict = {}
    if sec_xi3:
        flat = dd._flat(sec_xi3)
        none = bool(re.search(r"해당\s*사항\s*없|해당없|없습니다", flat[:600]))
        out["sanctioned"] = not none
        if not none:
            out["sanction_note"] = _clean(flat[:200])
    if sec_xi2 or nt_cont:
        flat = dd._flat(sec_xi2 or nt_cont or "")
        out["contingency_note"] = _clean(flat[:200])
        out["litigation"] = bool(re.search(r"소송|계류|피소", flat[:4000]))
    return out


# --- D5  생산설비 --------------------------------------------------------------
def _facilities(sec: str | None) -> dict | None:
    if not sec:
        return None
    m = re.search(r"생산설비\s*(?:현황|의\s*현황)", sec)
    if not m:
        return None
    flat = dd._flat(sec[m.start():m.start() + 12_000])
    mv = re.search(r"장부가액은?\s*([\d,]+)\s*(천원|백만원|억원|원)", flat)
    out: dict = {"note": _clean(flat[:200]), "source": "II-3-마 생산설비의 현황"}
    if mv:
        mult = dict((("천원", 1e3), ("백만원", 1e6), ("억원", 1e8), ("원", 1.0)))[mv.group(2)]
        out["book_value_won"] = dd._num(mv.group(1)) * mult
    return out


# --- D8  수주상황 ---------------------------------------------------------------
def _orders(sec: str | None) -> dict | None:
    if not sec:
        return None
    # 절 제목이 「매출 및 수주상황」이라 앞부분에서 찾으면 제목에 걸린다 → 소제목만 본다.
    m = next((x for x in re.finditer(r"수주\s*(?:에\s*관한\s*사항|현황|총액|잔고)", sec)
              if x.start() > 300), None)
    if not m:
        return None
    tail = dd._flat(sec[m.end():m.end() + 300])
    if re.search(r"해당\s*사항\s*없|해당없|없습니다", tail[:150]):
        return {"applicable": False, "detail": _clean(tail[:120])}
    g = dd.pick_grid(sec[m.start():m.start() + 12_000], any_of=("수주잔고", "수주총액", "기납품"),
                     min_rows=2, limit=4)
    if not g:
        return {"applicable": True, "detail": _clean(tail[:120])}
    mult = dd.unit_won(sec[m.start():m.start() + 2000], 1e6)
    hdr_i = dd.header_row(g, ("수주잔고", "수주총액")) or 0
    c_bal = dd.col_of(g[hdr_i], "수주잔고")
    bal = None
    if c_bal is not None:
        vals = [dd._num(r[c_bal]) for r in g[hdr_i + 1:] if c_bal < len(r)]
        vals = [v for v in vals if v is not None]
        if vals:
            bal = max(vals) * mult
    return {"applicable": True, "backlog_won": bal, "source": "II-4-다 수주에 관한 사항"}


# --- D12  원단위(原單位) 역산 ----------------------------------------------------
# 단위 사전 — **환산이 확실한 것만** 넣는다. 없는 단위는 계산하지 않는다(§15.4).
_MASS = {"kg": 1.0, "KG": 1.0, "Kg": 1.0, "g": 0.001, "ton": 1000.0, "t": 1000.0,
         "톤": 1000.0, "MT": 1000.0}
_COUNT_MULT = {"천": 1e3, "백만": 1e6, "만": 1e4, "억": 1e8}


def _price_unit(u: str | None) -> tuple[str, float] | None:
    """'원/Kg' → ('kg', 1.0) · '원/EA' → ('ea', 1.0). 모르는 단위면 None."""
    if not u:
        return None
    m = re.search(r"원\s*/\s*([A-Za-z가-힣]+)", u)
    if not m:
        return None
    tok = m.group(1).strip()
    if tok in _MASS:
        return ("kg", _MASS[tok])
    if tok.lower() in ("ea", "개", "본", "매", "대", "pcs"):
        return ("ea", 1.0)
    if tok.lower() in ("kg",):
        return ("kg", 1.0)
    return None


def _output_unit(u: str | None) -> tuple[str, float] | None:
    """'천개' → ('ea', 1e3) · 'ton' → ('kg', 1000). 복합 캡션(부문별 단위)은 포기한다."""
    if not u:
        return None
    t = re.sub(r"\s+", "", u)
    if "," in t or t.count("-") > 1:        # '완제의약품-백만정, 수액-백만bag' 같은 복합
        return None
    m = re.match(r"^(천|백만|만|억)?\s*([A-Za-z가-힣]+)$", t)
    if not m:
        return None
    mult = _COUNT_MULT.get(m.group(1) or "", 1.0)
    tok = m.group(2)
    if tok in _MASS:
        return ("kg", _MASS[tok] * mult)
    if tok in ("개", "EA", "ea", "정", "매", "본", "대", "병", "포"):
        return ("ea", mult)
    return None


def _unit_consumption(purch: dict | None, prices: dict | None,
                      output: list[dict]) -> list[dict]:
    """§15.4 식1~3 — 매입액 ÷ 단가 = 수량, 수량 ÷ 생산량 = 원단위.

    **품목 단위 원단위는 다품종 회사에서 성립하지 않는다**(원재료 품목과 제품 품목이 다르다).
    그래서 부문(사업부문) 단위까지만 낸다. 표 A·B의 품목명이 실제로 같으면 품목 단위로,
    아니면 (사업부문·매입유형)으로 붙이고 그 사실을 ``join`` 에 적어 둔다.
    """
    if not purch or not prices or not output:
        return []
    # 부문별 생산량(같은 단위끼리만 합산)
    prod: dict[str, dict] = {}
    for o in output:
        pu = _output_unit(o.get("unit"))
        if not pu:
            continue
        kind, mult = pu
        seg = _key(o.get("segment") or "")
        if not seg:
            continue
        years = sorted(o["values"], reverse=True)
        if not years:
            continue
        rec = prod.setdefault(seg, {"kind": kind, "by_year": {}, "label": o.get("segment")})
        if rec["kind"] != kind:
            rec["mixed"] = True
            continue
        for y in years:
            rec["by_year"][y] = rec["by_year"].get(y, 0.0) + o["values"][y] * mult

    # 단가: (부문, 유형, 품목) → {연도: 단가}
    price_idx: dict[tuple, dict] = {}
    for p in prices["rows"]:
        pu = _price_unit(p.get("unit"))
        if not pu:
            continue
        price_idx[(_key(p.get("segment") or ""), _key(p.get("type") or ""), _key(p["item"]))] = {
            "prices": p["prices"], "kind": pu[0], "mult": pu[1], "unit": p.get("unit"),
            "item": p["item"],
        }

    out = []
    for m in purch["rows"]:
        seg_k = _key(m.get("segment") or "")
        typ_k = _key(m.get("type") or "")
        rec = prod.get(seg_k)
        if not rec or rec.get("mixed") or not rec["by_year"]:
            continue
        exact = price_idx.get((seg_k, typ_k, _key(m["item"])))
        cand = exact
        join = "품목"
        if cand is None:
            same = [v for k, v in price_idx.items() if k[0] == seg_k and k[1] == typ_k]
            if len(same) != 1:
                continue
            cand, join = same[0], "부문·유형"
        # **매입액이 있는 해만** 계산한다. 최신연도 매입액을 옛 단가·생산량에 대입하면
        # 추세처럼 보이지만 실제로는 단가 변동을 원단위 변화로 착각하는 그림이 된다.
        amounts = m.get("amounts") or {}
        years = sorted(set(amounts) & set(cand["prices"]) & set(rec["by_year"]), reverse=True)
        if not years:
            continue
        trend = []
        for y in years[:3]:
            price, outq = cand["prices"].get(y), rec["by_year"].get(y)
            if not price or not outq:
                continue
            qty = amounts[y] / price * cand["mult"]        # 식1: 매입수량
            trend.append({"year": y, "u": round(qty / outq, 6), "qty": round(qty),
                          "output": round(outq)})
        if not trend:
            continue
        us = [t["u"] for t in trend]
        stable = (max(us) - min(us)) / max(us) < 0.10 if len(us) >= 2 else None
        # 표시 단위: kg/개가 0.2 같은 숫자로 나오면 읽히지 않는다 → g/개로 내린다.
        qty_lbl = {"kg": "kg", "ea": "EA"}[cand["kind"]]
        out_lbl = {"kg": "kg", "ea": "개"}[rec["kind"]]
        scale, u_unit = 1.0, f"{qty_lbl}/{out_lbl}"
        if cand["kind"] == "kg" and max(us) < 1:
            scale, u_unit = 1000.0, f"g/{out_lbl}"
        for t in trend:
            t["u"] = round(t["u"] * scale, 4)
        out.append({
            "segment": m.get("segment"), "type": m.get("type"), "material": m["item"],
            "price_item": cand["item"], "join": join,
            "year": trend[0]["year"],
            "unit_price": cand["prices"].get(trend[0]["year"]), "price_unit": cand["unit"],
            "amount_won": amounts[trend[0]["year"]],
            "qty": trend[0]["qty"], "qty_unit": cand["kind"],
            "output": trend[0]["output"], "output_unit": rec["kind"],
            "u": trend[0]["u"], "u_unit": u_unit,
            "trend": trend, "stable": stable,
            "note": ("매입액 ÷ 매입단가 = 매입수량, 매입수량 ÷ 생산수량 = 원단위. "
                     "매입액이 단년만 공시되면 3년 추세는 내지 않는다(확인불가)."),
        })
    out.sort(key=lambda x: -(x["qty"] or 0))
    return out[:12]


def _separate(ticker: str) -> dict:
    """별도(OFS) 손익 최근 1개 연도. dart_financials 는 연도당 연결/별도 하나만 담는다."""
    from app.data.fundamentals import separate_fin
    from app.data.fundamentals.dart import _load_corp_map
    corp = _load_corp_map().get(ticker)
    if not corp:
        return {}
    fy = separate_fin._latest_fy()
    return separate_fin.fetch_ofs(corp, [fy, fy - 1])


# --- 공개 API -------------------------------------------------------------------
def full(ticker: str, refresh: bool = False) -> dict:
    """사업보고서 전 항목 파싱 결과(디스크 캐시). 실패해도 available=False 로 조용히 반환."""
    cp = _cache_path(ticker)
    if cp.exists() and not refresh:
        try:
            d = json.loads(cp.read_text(encoding="utf-8"))
            if time.time() - d.get("_ts", 0) < _TTL and d.get("_v") == _PARSER_VERSION:
                d.pop("_ts", None)
                d.pop("_v", None)
                return d
        except Exception:
            pass

    out: dict = {"ticker": ticker, "available": False, "sections_found": [],
                 "source": "DART 사업보고서 전 항목(§15.2 매핑)"}
    if not enabled():
        out["reason"] = "DART_API_KEY 미설정"
        return out
    rcept = dd.latest_rcept(ticker)
    if not rcept:
        out["reason"] = "사업보고서 없음"
        return out
    main = dd.main_text(rcept)
    if not main:
        out["reason"] = "본문 취득 실패"
        return out
    out["rcept"] = rcept
    out["url"] = dd.dart_url(rcept)

    sec = {k: dd.section(main, k) for k in
           ("II-3", "II-4", "II-6", "III-7", "III-7-2", "III-8", "V-1", "IX", "X",
            "XI-2", "XI-3")}
    out["sections_found"] = [k for k, v in sec.items() if v]

    fs = dd.statement_texts(rcept)
    cons = fs.get("연결") or fs.get("별도")
    out["notes_basis"] = "연결" if fs.get("연결") else ("별도" if fs.get("별도") else None)
    nt = {}
    if cons:
        for key, kw, alt in (
                ("general", "일반사항", ("일반적 사항", "회사의 개요")),
                ("inventory", "재고자산", ()),
                ("ppe", "유형자산", ()),
                ("intangible", "무형자산", ()),
                ("segment", "영업부문", ("부문별 정보", "부문정보", "부문별 보고", "부문 정보",
                                       "영업부문정보", "보고부문")),
                ("sga", "판매비와관리비", ("판매비와 관리비",)),
                ("tax", "법인세비용", ("법인세",)),
                ("contingency", "우발", ("약정사항", "우발부채")),
                ("related", "특수관계자", ()),
                ("combination", "사업결합", ())):
            nt[key] = dd.note(cons, kw, alt)
        out["notes_found"] = [k for k, v in nt.items() if v]

    def _try(fn, *a):
        try:
            return fn(*a)
        except Exception:
            return None

    out["materials_purchase"] = _try(_materials_purchase, sec["II-3"])
    out["material_prices"] = _try(_material_prices, sec["II-3"])
    out["capacity"] = _try(_production, sec["II-3"], "능력") or []
    out["output"] = _try(_production, sec["II-3"], "실적") or []
    out["sales_mix"] = _try(_sales_mix, sec["II-4"])
    out["orders"] = _try(_orders, sec["II-4"])
    out["segments"] = _try(_segments, nt.get("segment"))
    out["inventory"] = _try(_inventory, nt.get("inventory"))
    out["other_financial"] = _try(_other_financial, sec["III-8"]) or {}
    out["related_party"] = _try(_related_party, nt.get("related"))
    out["affiliates"] = _try(_affiliates, sec["IX"], sec["X"]) or {}
    out["intangible"] = _try(_intangible, nt.get("intangible"))
    out["rnd"] = _try(_rnd, sec["II-6"])
    out["funding"] = _try(_funding, sec["III-7"], sec["III-7-2"])
    out["consolidation"] = _try(_consolidation, nt.get("general"), nt.get("combination"),
                                sec["III-8"]) or {}
    out["audit_meta"] = _try(_audit_meta, sec["V-1"])
    out["sanctions"] = _try(_sanctions, sec["XI-3"], sec["XI-2"], nt.get("contingency")) or {}
    out["facilities"] = _try(_facilities, sec["II-3"])
    out["unit_consumption"] = _try(_unit_consumption, out["materials_purchase"],
                                   out["material_prices"], out["output"]) or []
    # 별도(OFS) 손익 — X26(연결 ≥ 별도)용. DuckDB 는 연도당 한 기준만 담아 별도를 못 넣는다.
    out["separate"] = _try(_separate, ticker) or {}

    got = [k for k in ("materials_purchase", "sales_mix", "segments", "inventory",
                       "related_party", "audit_meta") if out.get(k)]
    out["available"] = bool(got)
    out["parsed"] = got
    if not out["available"]:
        out["reason"] = "전 항목 파싱 실패(서식 상이)"

    try:
        cp.write_text(json.dumps({**out, "_ts": time.time(), "_v": _PARSER_VERSION},
                                 ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return out
