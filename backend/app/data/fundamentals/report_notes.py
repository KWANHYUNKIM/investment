"""사업보고서 **원문**에서 실측을 꺼내온다 — 추정을 실측으로 바꾸는 레이어.

지금까지 원가 구성은 가정이었다(`material_ratio_of_cogs=0.80` 같은 상수).
그런데 사업보고서 원문(document.xml)에는 **재무제표 주석과 감사보고서가 통째로** 들어 있고,
거기에 우리가 추정하던 값의 **실측**이 있다.

  ① 「비용의 성격별 분류」 주석  → 원재료 사용액 · 종업원급여 · 감가상각비 · 기타
     = 총비용을 **재료비 / 노무비 / 감가상각 / 경비**로 쪼갠 실측.
       (예: 삼성전자 FY2025 연결 — 원재료 103.0조 · 급여 37.1조 · 감가상각 43.6조)
     → 개편계획 §11(물리 BOM)의 재료비 비중, §12(노무비)의 인건비를 **가정 없이** 채운다.

  ② 감사보고서 → **감사의견** · **핵심감사사항(KAM)** · 계속기업 불확실성 · 강조사항
     → 감사인이 "여기가 제일 위험하다"고 찍어준 지점. 조작 탐지(§13)의 최상위 신호.

연결/별도가 모두 들어 있어 **금액이 큰 쪽을 연결**로 판별한다(원재료 사용액은 연결 ≥ 별도).
"""
from __future__ import annotations

import io
import json
import re
import time
import zipfile

import requests

from app.core.config import get_settings
from app.data.fundamentals.dart import _load_corp_map, enabled
from app.data.fundamentals import auto_costmodel as ac

_BASE = "https://opendart.fss.or.kr/api"
_MAIN_MAX = 2_000_000        # 이보다 큰 멤버는 본문(사업의 내용) — 주석 파싱에서 제외
_TTL = 30 * 24 * 3600.0
_PARSER_VERSION = 4          # 파서 수정 시 올린다 → 옛 결과 캐시를 자동 무효화

_UNIT = (("십억원", 1e9), ("백만원", 1e6), ("천원", 1e3), ("억원", 1e8), ("원", 1.0))

# 「비용의 성격별 분류」 항목 → 원가 3요소
_CAT = (
    ("재고변동", ("재공품", "제품")),                       # 변동분 — 비용이 아니라 조정
    ("노무비", ("종업원급여", "급여", "퇴직급여", "복리후생", "주식보상", "인건비")),
    ("재료비", ("원재료", "상품", "재료비", "매입")),
    ("감가상각", ("감가상각", "상각비")),
)


def _cache_path(ticker: str):
    d = get_settings().data_dir / "dart_business"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"notes_{ticker}.json"


def _flat(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))


def _num(s: str) -> float | None:
    """'(29,436,673)' → -29436673. 숫자 없으면 None."""
    t = (s or "").strip()
    if not t or not re.search(r"\d", t):
        return None
    neg = t.startswith("(") and t.endswith(")")
    m = re.search(r"-?\d[\d,]*", t)
    if not m:
        return None
    try:
        v = float(m.group(0).replace(",", ""))
    except ValueError:
        return None
    return -v if (neg or t.lstrip().startswith("-")) else v


def _members(rcept: str) -> dict[str, str]:
    """document.xml zip → {파일명: 텍스트}. 실패 시 {}."""
    try:
        r = requests.get(f"{_BASE}/document.xml", params={
            "crtfc_key": get_settings().dart_api_key, "rcept_no": rcept}, timeout=120)
        zf = zipfile.ZipFile(io.BytesIO(r.content))
    except Exception:
        return {}
    out = {}
    for name in zf.namelist():
        b = zf.read(name)
        for enc in ("utf-8", "euc-kr", "cp949"):
            try:
                out[name] = b.decode(enc)
                break
            except Exception:
                continue
        else:
            out[name] = b.decode("utf-8", "ignore")
    return out


# --- ① 비용의 성격별 분류 --------------------------------------------------
def _cat_of(name: str) -> str:
    n = name.replace(" ", "")
    for cat, kws in _CAT:
        if any(k in n for k in kws):
            return cat
    return "기타경비"


def _parse_cost_nature(txt: str) -> dict | None:
    """「비용의 성격별 분류」 표 → {unit, items[{name,cat,cur,prev}], totals}."""
    # 제목이 회사마다 다르다: '비용의 성격별 분류'(농심·POSCO) / '비용의 성격별 공시'(삼성SDI).
    # 게다가 목차·판관비 명세 등 **다른 절에도** 같은 말이 나온다.
    # 그래서 후보를 모두 파싱한 뒤 **원가 3요소(재료비·노무비)가 들어 있는 표**를 고른다.
    # 첫 매칭을 그냥 쓰면 판관비 성격별 표가 잡혀 재료비가 통째로 빠진다(POSCO에서 실제로 발생).
    best, best_score = None, -1
    for m0 in list(re.finditer(r"비용의\s*성격별|성격별\s*(?:분류|공시|정보|비용)", txt))[:8]:
        got = _parse_at(txt, m0.start())
        if not got:
            continue
        cats = {it["cat"] for it in got["items"]}
        score = (100 if "재료비" in cats else 0) + (50 if "노무비" in cats else 0) + len(got["items"])
        if score > best_score:
            best, best_score = got, score
    return best


def _parse_at(txt: str, i: int) -> dict | None:
    """제목 위치 ``i`` 뒤의 표에서 성격별 비용을 읽는다. 실패하면 None."""
    # 단위는 제목 문단 뒤 설명문·표 캡션 어디에나 온다(포스코는 표 안 첫 행) → 넉넉히 훑는다.
    head = _flat(txt[i:i + 4000])
    mu = re.search(r"단위\s*[:：]?\s*(십억원|백만원|천원|억원|원)", head)
    mult = dict(_UNIT).get(mu.group(1), 1.0) if mu else 1.0

    # 제목 뒤 표들을 훑어 실제 데이터 표(숫자 2열 이상)를 찾는다. 첫 표는 단위 캡션인 경우가 많다.
    pos = i
    for _ in range(4):
        j = txt.find("<TABLE", pos)
        if j < 0 or j - i > 6000:
            return None
        end = txt.find("</TABLE>", j)
        rows = ac._table_rows(txt[j:end + 8])
        pos = end + 8
        items, cur_t, prev_t = [], 0.0, 0.0
        for r in rows:
            if len(r) < 2:
                continue
            name = (r[0] or "").strip()
            if not name or not re.search(r"[가-힣]", name):
                continue
            if re.fullmatch(r"구\s*분|과\s*목|항\s*목", name):      # 헤더행('제 58(당) 기'에 숫자가 있어 걸림)
                continue
            nums = [_num(c) for c in r[1:]]
            nums = [n for n in nums if n is not None]
            if not nums:
                continue
            cur, prev = nums[0], (nums[1] if len(nums) > 1 else None)
            if re.search(r"^(합\s*계|계|총\s*계)$", name.replace(" ", "")):
                cur_t, prev_t = cur, (prev or 0.0)
                continue
            items.append({"name": name, "cat": _cat_of(name),
                          "cur": cur * mult, "prev": (prev * mult) if prev is not None else None})
        if len(items) >= 4:
            if not cur_t:                        # 합계 행이 없으면 항목 합으로
                cur_t = sum(x["cur"] for x in items) / mult
                prev_t = sum(x["prev"] or 0.0 for x in items) / mult
            return {"unit_won": mult, "items": items,
                    "total_cur": cur_t * mult,
                    "total_prev": (prev_t * mult) if prev_t else None}
    return None


def _summarize(cn: dict) -> dict:
    """항목 → 재료비/노무비/감가상각/기타 집계 + 비중."""
    agg: dict[str, float] = {}
    for it in cn["items"]:
        if it["cat"] == "재고변동":
            continue                                   # 변동분은 비용 구성에서 제외
        agg[it["cat"]] = agg.get(it["cat"], 0.0) + it["cur"]
    base = sum(agg.values()) or 1.0
    order = ("재료비", "노무비", "감가상각", "기타경비")
    return {
        "breakdown": [{"cat": c, "amount_eok": round(agg.get(c, 0.0) / 1e8),
                       "pct": round(agg.get(c, 0.0) / base * 100, 1)} for c in order if agg.get(c)],
        "material_ratio": round(agg.get("재료비", 0.0) / base, 4),
        "labor_ratio": round(agg.get("노무비", 0.0) / base, 4),
        "depreciation_ratio": round(agg.get("감가상각", 0.0) / base, 4),
        "total_cost_eok": round(base / 1e8),
        "labor_eok": round(agg.get("노무비", 0.0) / 1e8),
        "material_eok": round(agg.get("재료비", 0.0) / 1e8),
    }


# --- ② 감사보고서 ----------------------------------------------------------
_OPINIONS = (("의견거절", "의견거절"), ("부적정의견", "부적정"), ("한정의견", "한정"))


def _parse_audit(txt: str) -> dict | None:
    """감사의견 · 핵심감사사항(KAM) · 계속기업 불확실성 · 강조사항."""
    i = txt.find("감사의견")
    if i < 0:
        return None
    seg = _flat(txt[i:i + 6000])

    opinion = None
    for kw, label in _OPINIONS:
        if kw in seg:
            opinion = label
            break
    if opinion is None and ("공정하게 표시" in seg or "적정의견" in seg):
        opinion = "적정"

    kam: list[str] = []
    n_kam = 0
    for m in re.finditer(r"핵심감사(?:항목|사항)으로 결정한 이유", txt):
        n_kam += 1
        # 제목은 보통 직전의 **독립 텍스트 노드**(별도 <P>/<SPAN>)다 → 마지막 태그 뒤만 취한다.
        raw = txt[max(0, m.start() - 500):m.start()]
        title = raw.rsplit(">", 1)[-1] if ">" in raw else raw
        title = re.sub(r"\s+", " ", title).strip(" .·-–— ")
        if not (4 <= len(title) <= 40):          # 노드 분리 실패 → 문장 끝 기준 폴백
            title = re.sub(r"^.*[.。]\s*", "", _flat(raw)).strip()
        title = re.sub(r"^\d+\s*[).]\s*", "", title)
        title = re.sub(r"\s*\d+\s*[).]?\s*$", "", title).strip()
        # 감사절차 서술이 섞여 들어온 건 제목이 아니다 → 지어내느니 버린다(건수는 n_kam 으로 보고).
        if len(title) > 40 or re.search(r"(표본추출|문서검사|질문하|확인하였|평가하였|하였습니다)", title):
            continue
        if len(title) >= 4 and title not in kam:
            kam.append(title)

    # 계속기업: 감사보고서 **모든** 본문에 나오는 감사인 책임 상용문구("…존속능력에 유의적
    # 의문을 초래할 수 있는 …중요한 불확실성이 존재하는지 여부에 대하여 결론을 내립니다")를
    # 잡으면 전 종목이 위험으로 찍힌다. 실제 신호는 **별도 항목 제목**이라 근접 매칭만 인정.
    going = bool(re.search(r"계속기업[^.]{0,12}중요한\s*불확실성", _flat(txt[:80000])))
    emphasis = "강조사항" in txt
    ic_qualified = bool(re.search(r"내부회계관리제도[^.]{0,200}(비적정|부적정|의견거절|중요한 취약점)",
                                  _flat(txt[:60000])))
    return {"opinion": opinion, "kam": kam[:5], "n_kam": n_kam,
            "going_concern_doubt": going,
            "emphasis": emphasis, "internal_control_issue": ic_qualified}


# --- 공개 API ---------------------------------------------------------------
def notes(ticker: str, refresh: bool = False) -> dict:
    """사업보고서 원문 기반 실측 묶음. 실패해도 available=False 로 조용히 반환."""
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

    out = {"ticker": ticker, "available": False, "rcept": None,
           "cost_nature": None, "audit": None,
           "source": "DART 사업보고서 원문(재무제표 주석·감사보고서)",
           "note": "「비용의 성격별 분류」는 매출원가+판관비 합계 기준(제조원가명세서와 다름)."}
    if not enabled():
        out["reason"] = "DART_API_KEY 미설정"
        return out
    corp = _load_corp_map().get(ticker)
    if not corp:
        out["reason"] = "corp_code 없음"
        return out
    rcept = ac._latest_business_rcept(corp)
    if not rcept:
        out["reason"] = "사업보고서 없음"
        return out
    out["rcept"] = rcept
    out["url"] = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept}"

    docs = _members(rcept)
    if not docs:
        out["reason"] = "원문 취득 실패"
        return out

    # 주석: 본문(대용량) 제외한 멤버들에서 파싱 → 금액 큰 쪽이 연결
    parsed = []
    for name, t in docs.items():
        if len(t) > _MAIN_MAX:
            continue
        cn = _parse_cost_nature(t)
        if cn:
            s = _summarize(cn)
            parsed.append((s["total_cost_eok"], name, cn, s))
    if parsed:
        parsed.sort(key=lambda x: x[0], reverse=True)
        _, name, cn, s = parsed[0]
        out["cost_nature"] = {
            "basis": "연결" if len(parsed) > 1 else "단일(연결/별도 구분 불가)",
            "member": name, **s,
            "items": [{"name": it["name"], "cat": it["cat"],
                       "amount_eok": round(it["cur"] / 1e8),
                       "prev_eok": round(it["prev"] / 1e8) if it["prev"] else None}
                      for it in cn["items"]],
        }
        if len(parsed) > 1:
            out["cost_nature"]["separate_total_eok"] = parsed[1][0]

    for name, t in docs.items():
        if len(t) > _MAIN_MAX:
            continue
        a = _parse_audit(t)
        if a and a.get("opinion"):
            out["audit"] = {**a, "member": name}
            break

    out["available"] = bool(out["cost_nature"] or out["audit"])
    try:
        cp.write_text(json.dumps({**out, "_ts": time.time(), "_v": _PARSER_VERSION},
                                 ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return out
