"""사업보고서 「사업의 내용」에서 **단가와 물량**을 꺼낸다 (개편계획 §11 B3·B4).

§14에서 재무제표 주석(금액)을 실측으로 바꿨다면, 여기는 **단가 × 물량**이다.

  **B3 「가격변동추이」** → 회사가 실제로 **산 값(원재료)·판 값(제품)**.
      국제시세가 아니라 *이 회사의* 단가다. 다만 "정보유출 우려로 미표기"(POSCO 일부)처럼
      **안 적는 회사도 많다** → 없으면 없다고 한다.

  **B4 「생산능력·생산실적·가동률」** → 물량. 금액은 다듬어도 **물량은 다듬기 어렵다**.
      가동률·생산량이 제자리인데 매출만 뛰면 매출 부풀리기를 의심할 근거가 된다(§11.4-①).

핵심은 **표를 제대로 읽는 것**이다. DART 표는 병합셀(COLSPAN/ROWSPAN)을 쓴다:

    [품 목|c2] [제62기] [제61기] [제60기]        ← 헤더
    [소맥|r2 ] [국내  ] [-]      [-]   [-]       ← 품목이 세로 병합
    [수입    ] [196   ] [210]    [236]           ← 이 행엔 '소맥'이 아예 없다

병합을 무시하고 셀을 왼쪽부터 세면 품목명이 '수입'이 되고, 2단 헤더(기수 아래 수량/금액)에서는
한 해는 수량, 다른 해는 금액이 잡혀 증가율이 수백 %가 된다. 그래서 먼저 **병합을 펼쳐
직사각형 격자로 만든 뒤** 헤더를 해석한다.

단위는 회사 공시 그대로 보존한다(천상자·천톤·천배럴). 임의 환산은 지어내기의 시작이다.
"""
from __future__ import annotations

import json
import re
import time

from app.core.config import get_settings
from app.data.fundamentals.dart import _load_corp_map, enabled
from app.data.fundamentals import auto_costmodel as ac

_TTL = 30 * 24 * 3600.0
# 파서를 고치면 올린다. 캐시에 같이 적어두고 다르면 무시 → **옛 파서 결과가 남지 않는다.**
# (실제로 겪음: 배치가 만든 구버전 캐시 때문에 고친 뒤에도 '백만개'가 품목명으로 남아 있었다)
_PARSER_VERSION = 3          # v3: TE/TU 셀 인식(서식 표의 데이터가 통째로 비던 문제)

# 품목명이 아니라 '구분' 값 — 이게 이름이 되면 전 품목이 '수입'이 된다.
_QUALIFIER = re.compile(r"^(수입|국내|내수|수출|해외|직수출|로컬)$")
_TOTAL = re.compile(r"^(합계|소계|계|총계|총합계)$")
_HDR_NOISE = re.compile(r"^(구분|품목|과목|제품|사업부문|부문|비고|단위|법인명|회사명|-)$")
# 단위 열('천배럴'·'원/톤')이 품목명으로 잡히면 전 품목 이름이 '천배럴'이 된다.
_UNIT_CELL = re.compile(
    r"(원|톤|kg|Kg|KG|배럴|MT|개|대|매|본|㎥|리터|ℓ|L)\s*/\s*"
    r"|/\s*(MT|톤|kg|배럴|개|대)"
    r"|^(천|백만|억|만)?\s*(배럴|톤|상자|포|개|대|매|본|kg|KG|MT|리터|ℓ|㎥|원)$")
_NUMERIC_NAME = re.compile(r"^[\d,.\s%()-]+$")


def _cache_path(ticker: str):
    d = get_settings().data_dir / "dart_business"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"business_{ticker}.json"


def _flat(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def _cell(inner: str) -> str:
    """셀 텍스트. DART가 정렬용으로 넣은 한글 사이 공백을 붙인다('냉 연'→'냉연')."""
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", inner)).strip()
    return re.sub(r"(?<=[가-힣]) (?=[가-힣])", "", t)


def _attr(attrs: str, name: str) -> int:
    m = re.search(name + r'\s*=\s*"?(\d+)', attrs, re.I)
    try:
        return max(1, int(m.group(1))) if m else 1
    except ValueError:
        return 1


def _grid(tbl: str) -> list[list[str]]:
    """<TABLE> → **병합을 펼친 직사각형 격자**. 이 모듈의 정확도는 전부 여기서 나온다."""
    out: list[list[str]] = []
    carry: dict[int, list] = {}                 # col -> [text, 남은 행수]
    for tr in re.findall(r"<TR\b.*?</TR>", tbl, re.S | re.I):
        line: dict[int, str] = {c: v[0] for c, v in carry.items()}
        added: dict[int, list] = {}
        ci = 0
        # 셀 태그가 TD/TH 만인 게 아니다. DART 서식이 정해 준 표(감사의견·직원현황·자금조달
        # 등 ACLASS="EXTRACTION")는 **<TE>(추출값)·<TU>(단위값)** 로 온다. TD/TH 만 읽으면
        # 그런 표는 머리행만 남고 **데이터가 통째로 빈다**(삼성전자 감사의견표에서 실제 발생).
        for attrs, inner in re.findall(r"<T[DHEU]\b([^>]*)>(.*?)</T[DHEU]>", tr, re.S | re.I):
            while ci in line:
                ci += 1
            txt = _cell(inner)
            cs, rs = _attr(attrs, "COLSPAN"), _attr(attrs, "ROWSPAN")
            for k in range(cs):
                line[ci + k] = txt
                if rs > 1:
                    added[ci + k] = [txt, rs - 1]
            ci += cs
        for c in list(carry):                    # 이번 행에서 한 칸 소비
            carry[c][1] -= 1
            if carry[c][1] <= 0:
                del carry[c]
        carry.update(added)
        w = (max(line) + 1) if line else 0
        out.append([line.get(i, "") for i in range(w)])
    w = max((len(r) for r in out), default=0)
    return [r + [""] * (w - len(r)) for r in out]


def _num(s: str) -> float | None:
    t = (s or "").strip()
    if not t or t in ("-", "—") or not re.search(r"\d", t):
        return None
    neg = t.startswith("(") and t.endswith(")")
    m = re.search(r"-?\d[\d,]*\.?\d*", t)
    if not m:
        return None
    try:
        v = float(m.group(0).replace(",", ""))
    except ValueError:
        return None
    return -v if neg else v


def _period(cell: str) -> str | None:
    """'제49기 (2023년)'·'2024년'·'제 51 기' → 기간 라벨. 연도가 있으면 연도 우선."""
    c = re.sub(r"\s+", "", cell or "")
    y = re.search(r"(20\d\d)년?", c)
    if y:
        return y.group(1)
    g = re.search(r"제(\d+)\(?[당전]?\)?기", c)
    return f"제{g.group(1)}기" if g else None


def _tables(txt: str, start: int, limit: int = 4, max_gap: int = 3500):
    """제목 이후의 <TABLE> 들. 너무 멀면 다른 절이므로 멈춘다."""
    pos = start
    for _ in range(limit):
        j = txt.find("<TABLE", pos)
        if j < 0 or j - start > max_gap:
            return
        end = txt.find("</TABLE>", j)
        if end < 0:
            return
        yield _grid(txt[j:end + 8])
        pos = end + 8


def _unit_of(s: str) -> str | None:
    m = re.search(r"단위\s*[:：]\s*([^)<]{1,40})", s)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None


# --- 헤더 해석 --------------------------------------------------------------
def _read_header(grid: list[list[str]]) -> tuple[dict[int, str], int, int] | None:
    """(기간열 {열: 기간}, 데이터 시작행, 라벨열 개수). 기간열이 2개 미만이면 None.

    2단 헤더(기수 아래 수량/금액)면 **수량 열만** 남긴다. 못 가리면 표를 버린다.
    """
    for ri, row in enumerate(grid[:3]):
        periods = {ci: p for ci, c in enumerate(row) if (p := _period(c))}
        if len(periods) < 2:
            continue
        first = min(periods)
        sub_i = ri + 1
        sub = grid[sub_i] if sub_i < len(grid) else []
        has_qty = any(re.search(r"(수량|물량|생산량|판매량)", c) for c in sub)
        has_amt = any(re.search(r"(금액|매출액|가액)", c) for c in sub)
        if has_qty and has_amt:
            keep = {ci: p for ci, p in periods.items()
                    if ci < len(sub) and re.search(r"(수량|물량|생산량|판매량)", sub[ci])}
            if len(keep) < 2:
                return None                      # 수량/금액 구분 불가 → 섞느니 버린다
            return keep, sub_i + 1, first
        return periods, ri + 1, first
    return None


def _row_label(cells: list[str], n_label: int) -> tuple[str, str | None, str | None]:
    """라벨열들 → (이름, 상위구분, 단위). '소맥/수입'은 이름=소맥·구분=수입."""
    labels = [c.strip() for c in cells[:n_label] if c and c.strip()]
    labels = [c for c in labels if not _HDR_NOISE.match(c) and not _NUMERIC_NAME.match(c)]
    unit = next((c for c in labels if _UNIT_CELL.search(c)), None)
    if unit:
        labels = [c for c in labels if c != unit]
    if not labels:
        return "", None, unit
    # 중복 제거(병합으로 같은 값이 반복됨)
    seen, uniq = set(), []
    for c in labels:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    name, qual = uniq[-1], None
    if len(uniq) >= 2 and _QUALIFIER.match(name):
        name, qual = uniq[-2], uniq[-1]
    group = uniq[-2] if (len(uniq) >= 2 and uniq[-2] != name and not qual) else None
    return name[:40], (qual or group), unit


def _parse_series(grid: list[list[str]]) -> list[dict] | None:
    """격자 → [{name, group, unit, values:{기간: 값}}]. 헤더 해석 실패 시 None."""
    h = _read_header(grid)
    if not h:
        return None
    periods, start, n_label = h
    items = []
    for row in grid[start:]:
        name, group, unit = _row_label(row, n_label)
        if not name or _TOTAL.match(name.replace(" ", "")):
            continue
        vals = {}
        for ci, p in periods.items():
            v = _num(row[ci]) if ci < len(row) else None
            if v is not None:
                vals[p] = v
        if len(vals) >= 2:
            items.append({"name": name, "group": group, "unit": unit, "values": vals})
    return items or None


def _chg(vals: dict) -> dict:
    keys = sorted(vals, reverse=True)
    if not keys:
        return {}
    cur, prev, old = vals[keys[0]], (vals[keys[1]] if len(keys) > 1 else None), vals[keys[-1]]
    return {
        "latest_period": keys[0], "latest": cur,
        "chg_1y": round((cur - prev) / prev, 4) if (prev not in (None, 0)) else None,
        "chg_span": round((cur - old) / old, 4) if (old not in (None, 0) and len(keys) > 2) else None,
        "span": f"{keys[-1]}→{keys[0]}" if len(keys) > 1 else keys[0],
    }


# --- B3: 가격변동추이 -------------------------------------------------------
def _parse_price_trend(txt: str) -> list[dict]:
    """「… 가격변동추이」 → [{scope:'제품'|'원재료', unit, items:[...]}]."""
    out, seen_scope = [], set()
    for m in re.finditer(r"가격\s*변동\s*추이", txt):
        head = _flat(txt[max(0, m.start() - 160):m.start()])
        if re.search(r"(미표기|기재하지|생략|해당\s*없)", _flat(txt[m.start():m.start() + 300])):
            continue                                    # 정보유출 우려 등으로 미공시
        scope = "원재료" if "원재료" in head[-80:] else "제품"
        if scope in seen_scope:
            continue
        unit = _unit_of(_flat(txt[m.start():m.start() + 700]))
        for grid in _tables(txt, m.start(), 4, max_gap=2500):
            items = _parse_series(grid)
            if not items:
                continue
            for it in items:
                it.update(_chg(it["values"]))
            out.append({"scope": scope, "unit": unit, "items": items[:20]})
            seen_scope.add(scope)
            break
    return out


# --- B4: 생산능력·생산실적·가동률 -------------------------------------------
def _parse_utilization(txt: str) -> list[dict]:
    """헤더에 생산능력·생산실적·가동률이 함께 있는 표."""
    for m in re.finditer(r"가동률", txt):
        unit = _unit_of(_flat(txt[max(0, m.start() - 120):m.start() + 400]))
        for grid in _tables(txt, m.start(), 3, max_gap=2500):
            if len(grid) < 2:
                continue
            hdr = grid[0]
            col = {}
            for key, kw in (("capacity", "생산능력"), ("output", "생산실적"), ("util", "가동률")):
                for j, c in enumerate(hdr):
                    if kw in re.sub(r"\s+", "", c or ""):
                        col[key] = j
                        break
            if "util" not in col:
                continue
            n_label = min(col.values())
            items = []
            for row in grid[1:]:
                name, group, _u = _row_label(row, n_label)
                u = _num(row[col["util"]]) if col["util"] < len(row) else None
                if not name or u is None or not (0 < u <= 200):
                    continue
                items.append({
                    "name": name, "group": group,
                    "capacity": _num(row[col["capacity"]]) if col.get("capacity", 99) < len(row) else None,
                    "output": _num(row[col["output"]]) if col.get("output", 99) < len(row) else None,
                    "utilization_pct": round(u, 1),
                    "is_total": bool(_TOTAL.match(name.replace(" ", ""))),
                })
            if items:
                return [{"unit": unit, "items": items[:15]}]
    return []


def _parse_output_series(txt: str) -> list[dict]:
    """「생산실적」 3개년 표."""
    for m in re.finditer(r"생산\s*실적", txt):
        unit = _unit_of(_flat(txt[max(0, m.start() - 120):m.start() + 400]))
        for grid in _tables(txt, m.start(), 4, max_gap=2500):
            items = _parse_series(grid)
            if not items:
                continue
            kept, dropped = [], 0
            for it in items:
                ch = _chg(it["values"])
                # 생산량이 1년 만에 ±200% 넘게 변하면 대개 표 오독 → 지어내느니 버린다.
                if ch.get("chg_1y") is not None and abs(ch["chg_1y"]) > 2.0:
                    dropped += 1
                    continue
                kept.append({**it, **ch})
            if kept:
                return [{"unit": unit, "items": kept[:15], "dropped_rows": dropped}]
    return []


# --- 공개 API ---------------------------------------------------------------
def business(ticker: str, refresh: bool = False) -> dict:
    """(B3·B4) 사업보고서 「사업의 내용」 실측 — 단가 변동 + 생산 물량·가동률."""
    cp = _cache_path(ticker)
    if cp.exists() and not refresh:
        try:
            d = json.loads(cp.read_text(encoding="utf-8"))
            if (time.time() - d.get("_ts", 0) < _TTL
                    and d.get("_v") == _PARSER_VERSION):
                d.pop("_ts", None)
                d.pop("_v", None)
                return d
        except Exception:
            pass

    out = {"ticker": ticker, "available": False, "price_trend": [], "utilization": [],
           "output_series": [],
           "source": "DART 사업보고서 「사업의 내용」(가격변동추이·생산실적)",
           "note": "단위는 회사 공시 그대로 보존한다(천상자·천톤·천배럴 등). 임의 환산 안 함."}
    if not enabled():
        out["reason"] = "DART_API_KEY 미설정"
        return out
    corp = _load_corp_map().get(ticker)
    rcept = ac._latest_business_rcept(corp) if corp else None
    txt = ac._fetch_main_xml(rcept) if rcept else None
    if not txt:
        out["reason"] = "사업보고서 본문 취득 실패"
        return out
    out["rcept"] = rcept

    for key, fn in (("price_trend", _parse_price_trend),
                    ("utilization", _parse_utilization),
                    ("output_series", _parse_output_series)):
        try:
            out[key] = fn(txt)
        except Exception:
            out[key] = []

    # 가격변동추이 절에 표가 없어 **생산실적 표를 대신 집어온** 경우를 걸러낸다.
    prod_names = {it["name"] for blk in out["output_series"] for it in blk["items"]}
    if prod_names:
        out["price_trend"] = [
            b for b in out["price_trend"]
            if len({it["name"] for it in b["items"]} & prod_names) < max(2, len(b["items"]) * 0.6)
        ]

    out["available"] = bool(out["price_trend"] or out["utilization"] or out["output_series"])
    if not out["available"]:
        out["reason"] = "가격변동추이·생산실적 표 미공시 또는 파싱 실패"
    try:
        cp.write_text(json.dumps({**out, "_ts": time.time(), "_v": _PARSER_VERSION},
                                 ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return out


def volume_check(biz: dict | None, fin3y: list[dict] | None) -> dict | None:
    """§11.4-① 물량 vs 매출 — **금액은 다듬어도 물량은 어렵다.**

    단위 환산이 필요 없는 **증가율 비교**라 업종을 안 가린다.
    """
    if not biz or not fin3y or len(fin3y) < 2:
        return None
    series = (biz.get("output_series") or [{}])[0].get("items") or []
    growths = [it["chg_1y"] for it in series if it.get("chg_1y") is not None]
    if not growths:
        return None
    vol_g = sum(growths) / len(growths)
    cur, prev = fin3y[0], fin3y[1]
    if not prev.get("revenue_eok"):
        return None
    rev_g = (cur["revenue_eok"] - prev["revenue_eok"]) / prev["revenue_eok"]
    gap = rev_g - vol_g
    status = "ok" if gap < 0.15 else ("warn" if gap < 0.30 else "fail")
    return {
        "code": "V1", "label": "생산량 증가율 vs 매출 증가율", "status": status,
        "year": cur["year"],
        "detail": f"생산량 {vol_g*100:+.1f}% vs 매출 {rev_g*100:+.1f}% (격차 {gap*100:+.1f}%p, "
                  f"품목 {len(growths)}개 평균)",
        "why": "물량은 그대로인데 매출만 뛰면 단가 인상·믹스 개선이거나 매출 부풀리기다. "
               "판가가 실제로 올랐는지(가격변동추이)와 함께 봐야 한다.",
    }
