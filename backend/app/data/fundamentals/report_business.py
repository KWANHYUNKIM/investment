"""사업보고서 「사업의 내용」에서 **단가와 물량**을 꺼낸다 (개편계획 §11 B3·B4).

§14에서 재무제표 주석(금액)을 실측으로 바꿨다면, 여기는 **단가 × 물량**이다.
물리 BOM(§11)과 조작 탐지(§11.4)가 요구하는 두 축:

  **B3 「가격변동추이」** → 회사가 실제로 **산 값(원재료)·판 값(제품)**.
      국제시세가 아니라 *이 회사의* 단가라, 시세와 벌어지면 이전가격·특수관계자 거래 신호.
      다만 "정보유출 우려로 미표기"(POSCO)처럼 **안 적는 회사도 많다** → 없으면 없다고 한다.

  **B4 「생산능력·생산실적·가동률」** → 물량. 금액은 다듬어도 **물량은 다듬기 어렵다.**
      가동률이 그대로인데 매출만 뛰면 매출 부풀리기를 의심할 근거가 된다(§11.4-①).

단위가 회사마다 제각각(천상자·천톤·천배럴·시간)이라 **단위를 그대로 보존**하고,
서로 다른 단위를 임의로 환산하지 않는다. 환산은 지어내기의 시작이다.
"""
from __future__ import annotations

import json
import re
import time

from app.core.config import get_settings
from app.data.fundamentals.dart import _load_corp_map, enabled
from app.data.fundamentals import auto_costmodel as ac

_TTL = 30 * 24 * 3600.0
_SKIP = re.compile(r"^(합\s*계|소\s*계|계|구\s*분|품\s*목|비\s*고|-)$")


def _cache_path(ticker: str):
    d = get_settings().data_dir / "dart_business"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"business_{ticker}.json"


def _flat(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def _num(s: str) -> float | None:
    t = (s or "").strip()
    if not t or not re.search(r"\d", t):
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
    """헤더 셀 → 기간 라벨. '제49기 (2023년)'·'2024년'·'제 51 기' 모두 처리."""
    c = re.sub(r"\s+", "", cell or "")
    y = re.search(r"(20\d\d)년?", c)
    if y:
        return y.group(1)
    g = re.search(r"제(\d+)\s*\(?[당전]?\)?\s*기", c)
    if g:
        return f"제{g.group(1)}기"
    return None


def _tables(txt: str, start: int, limit: int = 6, max_gap: int = 3000):
    """start 이후의 <TABLE> 들을 (행렬, 원문구간) 으로. 제목에서 너무 먼 표는 다른 절이다."""
    pos = start
    for _ in range(limit):
        j = txt.find("<TABLE", pos)
        if j < 0 or j - start > max_gap:
            return
        end = txt.find("</TABLE>", j)
        if end < 0:
            return
        yield ac._table_rows(txt[j:end + 8]), txt[j:end + 8]
        pos = end + 8


# 표 왼쪽의 '구분' 값(품목명이 아님) — 이걸 이름으로 잡으면 '수입/국내'가 품목이 된다.
_SEGMENT_CELL = re.compile(r"^(수입|국내|내수|수출|해외|합계|소계|계|당기|전기|전전기)$")
_QTY_HDR = re.compile(r"(수량|물량|생산량|판매량)")
_AMT_HDR = re.compile(r"(금액|매출액|가액)")


def _row_name(cells: list[str]) -> str | None:
    """행의 품목명. 첫 칸이 비었거나 '수입/국내' 같은 구분값이면 다음 칸을 붙여 쓴다."""
    parts = []
    for c in cells[:3]:
        cc = re.sub(r"\s+", " ", (c or "")).strip()
        if not cc or not re.search(r"[가-힣A-Za-z]", cc) or re.fullmatch(r"[\d.,%()]+", cc):
            continue
        if _SKIP.match(cc.replace(" ", "")) or _SEGMENT_CELL.match(cc.replace(" ", "")):
            continue
        parts.append(cc)
        if len("".join(parts)) >= 3:
            break
    if not parts:
        return None
    return " ".join(parts)[:40]


def _period_cols(rows: list[list[str]]) -> tuple[list[tuple[int, str]], int]:
    """헤더에서 (열번호, 기간) 목록과 헤더 행 번호.

    2단 헤더(기수 아래 '수량/금액')면 **금액 열을 버리고 수량 열만** 남긴다.
    안 그러면 한 해는 수량, 다른 해는 금액이 잡혀 증가율이 1875% 같은 값이 된다.
    """
    for ri, r in enumerate(rows[:3]):
        ps = [(ci, _period(c)) for ci, c in enumerate(r)]
        ps = [(ci, p) for ci, p in ps if p]
        if len(ps) < 2:
            continue
        sub = rows[ri + 1] if ri + 1 < len(rows) else []
        if sub and any(_QTY_HDR.search(c or "") for c in sub) and any(_AMT_HDR.search(c or "") for c in sub):
            keep = [(ci, p) for ci, p in ps
                    if ci < len(sub) and _QTY_HDR.search(sub[ci] or "")]
            # 서브헤더가 병합되어 열이 어긋나면 판단 불가 → 이 표는 버린다(섞느니 버림).
            return (keep if len(keep) >= 2 else []), ri + 1
        return ps, ri
    return [], 0


def _unit_of(s: str) -> str | None:
    m = re.search(r"단위\s*[:：]\s*([^)<]{1,40})", s)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None


# --- B3: 가격변동추이 -------------------------------------------------------
def _parse_price_trend(txt: str) -> list[dict]:
    """「… 가격변동추이」 표 → [{scope, unit, items:[{name, values:{기간: 단가}}]}].

    scope: '제품'(판매단가) | '원재료'(매입단가) — 제목 문구로 판별.
    """
    out = []
    for m in re.finditer(r"가격\s*변동\s*추이", txt):
        head = _flat(txt[max(0, m.start() - 200):m.start() + 400])
        if "미표기" in head or "기재하지" in head or "생략" in head:
            continue                                  # 정보유출 우려 등으로 미공시
        scope = "원재료" if "원재료" in head[-120:] else "제품"
        unit = _unit_of(_flat(txt[m.start():m.start() + 600]))
        for rows, _raw in _tables(txt, m.start(), 3, max_gap=2500):
            if len(rows) < 2:
                continue
            periods, hdr_i = _period_cols(rows)
            if not periods:
                continue
            items = []
            for r in rows[hdr_i + 1:]:
                name = _row_name(r)
                if not name:
                    continue
                vals = {}
                for ci, p in periods:
                    v = _num(r[ci]) if ci < len(r) else None
                    if v is not None:
                        vals[p] = v
                if len(vals) >= 2:
                    items.append({"name": name, "values": vals})
            if items:
                out.append({"scope": scope, "unit": unit, "items": items[:20]})
                break
    return out


def _chg(vals: dict) -> dict:
    """{기간: 단가} → 최신/직전/최고·최저 + 1년 변동률. 기간 정렬은 연도 우선."""
    keys = sorted(vals, reverse=True)
    if not keys:
        return {}
    cur = vals[keys[0]]
    prev = vals[keys[1]] if len(keys) > 1 else None
    old = vals[keys[-1]]
    return {
        "latest_period": keys[0], "latest": cur,
        "chg_1y": round((cur - prev) / prev, 4) if (prev and prev != 0) else None,
        "chg_span": round((cur - old) / old, 4) if (old and old != 0 and len(keys) > 2) else None,
        "span": f"{keys[-1]}→{keys[0]}" if len(keys) > 1 else keys[0],
    }


# --- B4: 생산능력·생산실적·가동률 -------------------------------------------
def _parse_utilization(txt: str) -> list[dict]:
    """헤더에 생산능력·생산실적·가동률이 함께 있는 표 → [{name, capacity, output, utilization}]."""
    out = []
    for m in re.finditer(r"가동률", txt):
        unit = _unit_of(_flat(txt[m.start():m.start() + 400]))
        for rows, _raw in _tables(txt, m.start(), 2, max_gap=2500):
            if len(rows) < 2:
                continue
            hdr = " ".join(rows[0])
            if not ("가동률" in hdr and "생산" in hdr):
                continue
            ci = {}
            for k, kw in (("capacity", "생산능력"), ("output", "생산실적"), ("util", "가동률")):
                for j, c in enumerate(rows[0]):
                    if kw in re.sub(r"\s+", "", c or ""):
                        ci[k] = j
                        break
            if "util" not in ci:
                continue
            items = []
            for r in rows[1:]:
                name = _row_name(r)
                if not name:
                    continue
                u = _num(r[ci["util"]]) if ci["util"] < len(r) else None
                if u is None or not (0 < u <= 200):     # 가동률은 %라 범위를 벗어나면 오파싱
                    continue
                items.append({
                    "name": name,
                    "capacity": _num(r[ci["capacity"]]) if ci.get("capacity", 99) < len(r) else None,
                    "output": _num(r[ci["output"]]) if ci.get("output", 99) < len(r) else None,
                    "utilization_pct": round(u, 1),
                })
            if items:
                out.append({"unit": unit, "items": items[:15]})
                break
        if out:
            break
    return out


def _parse_output_series(txt: str) -> list[dict]:
    """「생산실적」 표 중 **연도 열이 2개 이상**인 것 → [{name, unit, values:{기간: 수량}}]."""
    for m in re.finditer(r"생산\s*실적", txt):
        unit = _unit_of(_flat(txt[m.start():m.start() + 400]))
        for rows, _raw in _tables(txt, m.start(), 3, max_gap=2500):
            if len(rows) < 3:
                continue
            periods, hdr_i = _period_cols(rows)
            if not periods:
                continue
            items, dropped = [], 0
            for r in rows[hdr_i + 1:]:
                name = _row_name(r)
                if not name:
                    continue
                vals = {}
                for ci, p in periods:
                    v = _num(r[ci]) if ci < len(r) else None
                    if v is not None:
                        vals[p] = v
                if len(vals) < 2:
                    continue
                ch = _chg(vals)
                # 생산량이 1년 만에 ±200% 넘게 변하는 건 대개 파싱 오류(수량↔금액 혼입).
                # 지어내느니 버리고, 몇 개 버렸는지 보고한다.
                if ch.get("chg_1y") is not None and abs(ch["chg_1y"]) > 2.0:
                    dropped += 1
                    continue
                items.append({"name": name, "values": vals, **ch})
            if items:
                return [{"unit": unit, "items": items[:15], "dropped_rows": dropped}]
    return []


# --- 공개 API ---------------------------------------------------------------
def business(ticker: str, refresh: bool = False) -> dict:
    """(B3·B4) 사업보고서 「사업의 내용」 실측 — 단가 변동 + 생산 물량·가동률."""
    cp = _cache_path(ticker)
    if cp.exists() and not refresh:
        try:
            d = json.loads(cp.read_text(encoding="utf-8"))
            if time.time() - d.get("_ts", 0) < _TTL:
                d.pop("_ts", None)
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

    try:
        pt = _parse_price_trend(txt)
    except Exception:
        pt = []
    for blk in pt:
        for it in blk["items"]:
            it.update(_chg(it["values"]))
    try:
        out["utilization"] = _parse_utilization(txt)
    except Exception:
        out["utilization"] = []
    try:
        out["output_series"] = _parse_output_series(txt)
    except Exception:
        out["output_series"] = []

    # 가격변동추이 절에 표가 없어 **생산실적 표를 대신 집어온** 경우(삼성전자)를 걸러낸다.
    prod_names = {it["name"] for blk in out["output_series"] for it in blk["items"]}
    if prod_names:
        pt = [b for b in pt
              if len({it["name"] for it in b["items"]} & prod_names) < max(2, len(b["items"]) * 0.6)]
    out["price_trend"] = pt

    out["available"] = bool(pt or out["utilization"] or out["output_series"])
    if not out["available"]:
        out["reason"] = "가격변동추이·생산실적 표 미공시 또는 파싱 실패"
    try:
        cp.write_text(json.dumps({**out, "_ts": time.time()}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return out


def volume_check(biz: dict | None, fin3y: list[dict] | None) -> dict | None:
    """§11.4-① 물량 vs 매출 — **금액은 다듬어도 물량은 어렵다.**

    생산량(또는 가동률)이 제자리인데 매출만 크게 늘었으면 매출 부풀리기를 의심한다.
    단위 환산이 필요 없는 **증가율 비교**라 업종을 안 가리고 쓸 수 있다.
    """
    if not biz or not fin3y or len(fin3y) < 2:
        return None
    series = (biz.get("output_series") or [{}])[0].get("items") or []
    growths = [it["chg_1y"] for it in series if it.get("chg_1y") is not None]
    if not growths:
        return None
    vol_g = sum(growths) / len(growths)                    # 품목 평균 생산량 증가율
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
