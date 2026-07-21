"""DART 사업보고서 자동 파싱 → 제품 원가모델 자동 생성 (전 종목 확장 파이프라인).

수작업 PRODUCTS(정답지)를 넘어, 상장사 사업보고서의 「원재료 및 생산설비」·「주요 제품」
표를 파싱해 원가모델을 자동 생성한다. 흐름:

  1. list.json      → 최신 사업보고서 rcept_no
  2. document.xml   → 본문 XML (원재료 매입 현황·제품 매출 현황·가격변동 서술)
  3. commodity_map  → 원재료명 → 커모디티 키
  4. DART 재무      → 매출원가율·영업이익률
  5. teardown 호환 dict 생성 → data/costmodels_auto.json 에 적재

파싱 실패(원재료 표 없음: 금융·서비스 등)는 '원자재 무관' 폴백 모델로 처리한다.
"""
from __future__ import annotations

import io
import json
import re
import zipfile

import requests

from app.core.config import get_settings
from app.data.fundamentals import commodity_map
from app.data.fundamentals.dart import _load_corp_map, _float, enabled

_BASE = "https://opendart.fss.or.kr/api"


def _cache_dir():
    d = get_settings().data_dir / "dart_business"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _auto_path():
    return get_settings().data_dir / "costmodels_auto.json"


# --- DART 문서 취득 --------------------------------------------------------
def _latest_business_rcept(corp: str) -> str | None:
    """최신 사업보고서(없으면 반기/분기) 접수번호."""
    try:
        r = requests.get(f"{_BASE}/list.json", params={
            "crtfc_key": get_settings().dart_api_key, "corp_code": corp,
            "bgn_de": "20230101", "pblntf_ty": "A", "page_count": "50",
        }, timeout=30)
        rows = r.json().get("list") or []
    except Exception:
        return None
    for key in ("사업보고서", "반기보고서", "분기보고서"):
        for it in rows:
            if key in (it.get("report_nm") or ""):
                return it.get("rcept_no")
    return rows[0].get("rcept_no") if rows else None


def _fetch_main_xml(rcept: str) -> str | None:
    """본문(가장 큰 XML) 텍스트. 디스크 캐시."""
    cf = _cache_dir() / f"doc_{rcept}.txt"
    if cf.exists():
        return cf.read_text(encoding="utf-8")
    try:
        r = requests.get(f"{_BASE}/document.xml", params={
            "crtfc_key": get_settings().dart_api_key, "rcept_no": rcept}, timeout=60)
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        # '사업의 내용' 키워드를 가진 가장 큰 파일 선택
        best, best_len = None, 0
        for name in zf.namelist():
            b = zf.read(name)
            for enc in ("utf-8", "euc-kr", "cp949"):
                try:
                    t = b.decode(enc); break
                except Exception:
                    t = b.decode("utf-8", "ignore")
            if ("원재료" in t or "주요 제품" in t) and len(t) > best_len:
                best, best_len = t, len(t)
        if best:
            cf.write_text(best, encoding="utf-8")
        return best
    except Exception:
        return None


# --- 표 파싱 ---------------------------------------------------------------
def _table_rows(tbl: str) -> list[list[str]]:
    out = []
    for tr in re.findall(r'<TR\b.*?</TR>', tbl, re.S | re.I):
        cells = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', c)).strip()
                 for c in re.findall(r'<T[DH]\b.*?</T[DH]>', tr, re.S | re.I)]
        if any(cells):
            out.append(cells)
    return out


def _pct(s: str) -> float | None:
    m = re.search(r'-?\d[\d,]*\.?\d*', (s or "").replace("%", ""))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _ratio_cell(cells: list[str]) -> float | None:
    """행에서 '비율(%)' 값. '%' 포함 셀 우선, 없으면 마지막 ≤100 순수 숫자 셀."""
    for c in reversed(cells):
        if "%" in c:
            v = _pct(c)
            if v is not None and 0 < v <= 100:
                return v
    for c in reversed(cells):
        if re.fullmatch(r'[\d.,]+%?', c.strip()):
            v = _pct(c)
            if v is not None and 0 < v <= 100:
                return v
    return None


def _find_row_table(seg: str, need_cols: tuple[str, ...]) -> list[list[str]]:
    """구간 내에서 헤더에 need_cols 를 모두 포함하는 첫 표의 행들."""
    for m in re.finditer(r'<TABLE\b.*?</TABLE>', seg, re.S | re.I):
        rows = _table_rows(m.group(0))
        if len(rows) < 2:
            continue
        head = " ".join(rows[0])
        if all(any(nc in " ".join(r) for r in rows[:2]) for nc in need_cols):
            return rows
    return []


def _parse_products(txt: str) -> list[dict]:
    """제품 매출 현황: [{name, pct}]. '가격변동추이'(제품) 앞 품목/비율 표."""
    i = txt.find("가격변동추이")
    if i < 0:
        return []
    rows = []
    # i 이전 마지막 '비율' 포함 표
    for m in re.finditer(r'<TABLE\b.*?</TABLE>', txt[:i], re.S | re.I):
        rr = _table_rows(m.group(0))
        if len(rr) >= 2 and any("비율" in " ".join(r) or "비 율" in " ".join(r) for r in rr[:1]):
            rows = rr
    return [x for x in (_row_item(r, "") for r in rows[1:]) if x]


_CAT = re.compile(r'^(원재료|부재료|상품|제품|제조|식품제조|매입|구분|소계|비고|-)$')
_SKIP = re.compile(r'^(소계|합계|계|해당없음|미해당|기타등|비고|-)$')


def _row_item(cells: list[str], narr: str) -> dict | None:
    """표 한 행 → {name, pct}. 커모디티에 매핑되는 셀을 품목명으로 우선 선택."""
    if not cells or "계" == cells[0].strip() or any("합계" in c for c in cells):
        return None
    first = re.sub(r'\s+', '', cells[0])
    if _SKIP.match(first) or all(_SKIP.match(re.sub(r'\s+', '', c)) or not re.search(r'[가-힣A-Za-z]', c) for c in cells):
        return None
    pct = _ratio_cell(cells)
    if not pct:
        return None
    # 1) 셀 자체가 커모디티로 매핑되면(narr 없이) 그걸 품목명으로
    for c in cells:
        if commodity_map.to_commodity(c):
            return {"name": c, "pct": pct}
    # 2) 짧은 한글 명사 셀(카테고리·용도·수식어 제외)
    cands = [c for c in cells if re.search(r'[가-힣]', c)
             and not _CAT.match(c.strip())
             and not re.search(r'(및|등|용|제조|판매|매출|서비스)', c)]
    name = min(cands, key=len) if cands else (cells[0] if cells else "기타")
    return {"name": name, "pct": pct}


def _parse_materials(txt: str) -> tuple[list[dict], str]:
    """원재료 매입 현황: [{name, pct}] + 서술. 본문(마지막) 앵커 + 커모디티 매핑
    행이 가장 많은 표를 선택(생산설비·사업부문 표 오인 방지)."""
    anchors = [m.start() for m in re.finditer("주요 원재료", txt)] + \
              [m.start() for m in re.finditer("원재료 및 생산설비", txt)]
    if not anchors:
        return [], ""
    best, best_score, best_narr = [], 0, ""
    for a in sorted(set(anchors))[:8]:
        seg = txt[a:a + 25000]
        narr = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', seg))[:2000]
        for m in re.finditer(r'<TABLE\b.*?</TABLE>', seg, re.S | re.I):
            rows = _table_rows(m.group(0))
            if len(rows) < 2:
                continue
            items = [x for x in (_row_item(r, "") for r in rows[1:]) if x]
            if not items:
                continue
            score = sum(1 for x in items if commodity_map.to_commodity(x["name"]))
            # 매핑 비율도 가중(제품/사업부문 표 배제): score는 매핑된 행 수
            if score > best_score:
                best, best_score, best_narr = items, score, narr
    if best_score == 0:
        return [], best_narr
    return best, best_narr


# --- 재무비율 (DART 최신 사업연도) ----------------------------------------
_SALES = ("매출액", "수익(매출액)", "영업수익", "매출")


def _income_ratios(corp: str) -> dict | None:
    for year in (_latest_fy(), _latest_fy() - 1):
        for fs in ("CFS", "OFS"):
            try:
                r = requests.get(f"{_BASE}/fnlttSinglAcntAll.json", params={
                    "crtfc_key": get_settings().dart_api_key, "corp_code": corp,
                    "bsns_year": str(year), "reprt_code": "11011", "fs_div": fs}, timeout=30)
                items = r.json().get("list") or []
            except Exception:
                items = []
            if not items:
                continue
            acc = {}
            for it in items:
                if it.get("sj_div") not in ("IS", "CIS"):
                    continue
                nm = (it.get("account_nm") or "").strip()
                amt = _float(it.get("thstrm_amount"))
                if amt is not None and nm not in acc:
                    acc[nm] = amt
            sales = next((acc[k] for k in _SALES if k in acc), None)
            cogs = acc.get("매출원가")
            op = acc.get("영업이익", acc.get("영업이익(손실)"))
            if sales and cogs and 0.2 < cogs / sales < 1.2:
                return {"cogs": round(cogs / sales, 4),
                        "op": round(op / sales, 4) if op is not None else None,
                        "year": year}
    return None


def _latest_fy() -> int:
    import time
    y, m = int(time.strftime("%Y")), int(time.strftime("%m"))
    return y - 1 if m >= 4 else y - 2


# --- 모델 생성 -------------------------------------------------------------
def build(ticker: str, company: str) -> dict | None:
    """단일 종목 자동 원가모델(teardown 호환). 실패 시 None."""
    if not enabled():
        return None
    corp = _load_corp_map().get(ticker)
    if not corp:
        return None
    rcept = _latest_business_rcept(corp)
    txt = _fetch_main_xml(rcept) if rcept else None
    fin = _income_ratios(corp)

    materials, narr, products = [], "", []
    if txt:
        materials, narr = _parse_materials(txt)
        products = _parse_products(txt)

    # material_mix: 파싱된 매입비중 → 커모디티 매핑, 합 1.0 정규화
    mix = []
    tot = sum(m["pct"] for m in materials) or 0
    if materials and tot > 0:
        for m in materials:
            mix.append({"item": m["name"], "weight": round(m["pct"] / tot, 4),
                        "commodity": commodity_map.to_commodity(m["name"], narr)})
        # 반올림 오차 보정
        drift = round(1.0 - sum(x["weight"] for x in mix), 4)
        if mix:
            mix[0]["weight"] = round(mix[0]["weight"] + drift, 4)
        mat_note = "DART 원재료 매입 현황 자동 파싱"
    else:
        mix = [{"item": "영업비용(원재료 무관/미공시)", "weight": 1.0, "commodity": None}]
        mat_note = "원재료 표 없음 → 원자재 무관/폴백"

    cogs = fin["cogs"] if fin else 0.85
    op = fin["op"] if (fin and fin["op"] is not None) else round(max(-0.1, 1 - cogs - 0.12), 3)

    prod_summary = ", ".join(f"{p['name']} {p['pct']:.0f}%" for p in products[:4]) or "종합"
    return {
        "ticker": ticker, "company": company,
        "product": f"{company} 종합(매출 1,000원)", "unit": "매출 1,000원",
        "channel": "자동", "channel_label": "유통(해당없음)",
        "retail_price": 1000, "distribution_margin": 0.0, "material_ratio_of_cogs": 1.0,
        "material_mix": mix,
        "default_ratios": {"cogs": round(cogs, 4), "op": round(op, 4)},
        "note": f"[자동생성] {mat_note}. 재무: {('DART %d' % fin['year']) if fin else '추정'}. 주력: {prod_summary}.",
        "_auto": True,
        "_products": products,
    }


def generate(tickers: dict[str, str], limit: int | None = None) -> dict:
    """{ticker: company} → 자동모델 dict 생성 후 JSON 적재. 반환: {product_id: model}."""
    out = {}
    done = 0
    for tk, name in tickers.items():
        if limit and done >= limit:
            break
        try:
            m = build(tk, name)
        except Exception:
            m = None
        if m:
            out[f"{tk}:auto"] = m
            done += 1
    # 병합 저장(기존 유지 + 갱신)
    existing = load_auto()
    existing.update(out)
    _auto_path().write_text(json.dumps(existing, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def load_auto() -> dict:
    p = _auto_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}
