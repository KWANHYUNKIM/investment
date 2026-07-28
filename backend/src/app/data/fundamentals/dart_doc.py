"""사업보고서 원문을 **절(節) 단위**로 다루는 공용 인프라 (개편계획 §15의 토대).

§14까지는 "키워드를 찾아 그 뒤 표를 읽는" 방식이었다. 절이 154개인 문서에서 그 방식은
목차·다른 절의 같은 낱말에 걸린다(실제로 「비용의 성격별 분류」가 판관비 명세를 집었다).

그런데 DART 본문에는 **서식이 정해 준 절 코드**가 그대로 실려 있다.

    <TITLE AASSOCNOTE="D-0-3-8-0" ENG="8. Other financial matters">8. 기타 재무에 관한 사항
    <TITLE AASSOCNOTE="L-0-2-3-L1" ENG="3. Raw materials...">3. 원재료 및 생산설비

``AASSOCNOTE`` 는 회사가 짓는 이름이 아니라 **서식의 항목 코드**라 회사가 달라도 같다.
재무제표 주석은 절 코드가 없는 대신 편집기 북마크가 남는다.

    <P ID="28. 영업부문">28. 영업부문

그래서 이 모듈은 세 층으로 위치를 잡는다 — ① 절 코드 → ② 주석 ID 앵커 → ③ 제목 텍스트.
①이 되면 ②·③은 안 쓴다. **못 찾으면 None 을 준다.** 근처 표를 아무거나 집어오는 것보다
"확인불가"가 낫다(§15.1 — 확인불가는 분모에서 빠지므로 점수를 왜곡하지 않는다).

문서 취득도 여기서 맡는다. 사업보고서 zip 은 본문(5MB) + 연결감사보고서 + 별도감사보고서로
오는데, **재무제표 주석은 감사보고서 쪽에** 들어 있어 둘 다 필요하다.
"""
from __future__ import annotations

import io
import re
import zipfile

import requests

from app.core.config import get_settings
from app.data.fundamentals import auto_costmodel as ac
from app.data.fundamentals.dart import _load_corp_map, enabled
# 병합셀(COLSPAN/ROWSPAN)을 펼쳐 직사각형 격자로 만드는 파서는 §14에서 이미 검증됐다.
# 같은 문서를 읽는 이상 구현이 둘이면 언젠가 어긋난다 → 하나만 쓴다.
from app.data.fundamentals.report_business import _cell, _flat, _grid, _num  # noqa: F401

_BASE = "https://opendart.fss.or.kr/api"
_MAIN_MIN = 2_000_000        # 이보다 크면 본문(사업의 내용) — 주석 멤버가 아니다

# 서식 절 코드(AASSOCNOTE). 이름이 아니라 **코드**로 잡는다.
SEC = {
    "I-1": "D-0-1-1-0",      # 회사의 개요
    "I-2": "D-0-1-2-0",      # 회사의 연혁
    "I-3": "D-0-1-3-0",      # 자본금 변동사항
    "I-4": "D-0-1-4-0",      # 주식의 총수
    "II-1": "L-0-2-1-L1",    # 사업의 개요
    "II-2": "L-0-2-2-L1",    # 주요 제품 및 서비스
    "II-3": "L-0-2-3-L1",    # 원재료 및 생산설비   ← D1·B3·B4·D5
    "II-4": "L-0-2-4-L1",    # 매출 및 수주상황     ← D2·D8
    "II-5": "L-0-2-5-L1",    # 위험관리 및 파생거래
    "II-6": "L-0-2-6-L1",    # 주요계약 및 연구개발활동 ← D9
    "II-7": "L-0-2-7-L1",    # 기타 참고사항
    "III-1": "D-0-3-1-0",    # 요약재무정보
    "III-2": "D-0-3-2-0",    # 연결재무제표
    "III-3": "D-0-3-3-0",    # 연결재무제표 주석
    "III-4": "D-0-3-4-0",    # (별도)재무제표
    "III-5": "D-0-3-5-0",    # (별도)재무제표 주석
    "III-6": "D-0-3-6-0",    # 배당에 관한 사항
    "III-7": "D-0-3-7-0",    # 증권의 발행을 통한 자금조달  ← D10
    "III-7-1": "D-0-3-7-1",
    "III-7-2": "D-0-3-7-2",  # 조달자금 사용실적
    "III-8": "D-0-3-8-0",    # 기타 재무에 관한 사항        ← D6
    "IV": "D-0-4-0-0",       # 이사의 경영진단
    "IV-5": "D-0-4-5-0",     # 부외거래
    "V-1": "D-0-5-1-0",      # 외부감사에 관한 사항
    "V-2": "D-0-5-2-0",      # 내부통제에 관한 사항
    "VII": "D-0-7-0-0",      # 주주에 관한 사항
    "VIII-1": "D-0-8-1-0",   # 임원 및 직원 등의 현황
    "VIII-2": "D-0-8-2-0",   # 임원의 보수 등
    "IX": "D-0-9-0-0",       # 계열회사 등에 관한 사항      ← D7
    "X": "D-0-10-0-0",       # 대주주 등과의 거래내용       ← D7
    "XI-2": "D-0-11-2-0",    # 우발부채
    "XI-3": "D-0-11-3-0",    # 제재 등과 관련된 사항
    "XII": "TTL_APPENDIX",   # 상세표                       ← D11
}

# 절 코드가 없는(또는 서식이 다른) 문서를 위한 제목 폴백.
SEC_TITLE = {
    "II-3": r"원재료\s*및\s*생산설비",
    "II-4": r"매출\s*및\s*수주",
    "III-7": r"증권의\s*발행을\s*통한\s*자금조달",
    "III-8": r"기타\s*재무에\s*관한\s*사항",
    "V-1": r"외부감사에\s*관한\s*사항",
    "IX": r"계열회사\s*등에\s*관한\s*사항",
    "X": r"대주주\s*등과의\s*거래",
    "XII": r"상세표",
}


# --- 문서 취득 --------------------------------------------------------------
def _dir():
    d = get_settings().data_dir / "dart_business"
    d.mkdir(parents=True, exist_ok=True)
    return d


def latest_rcept(ticker: str) -> str | None:
    """최신 사업보고서 접수번호(없으면 반기·분기)."""
    if not enabled():
        return None
    corp = _load_corp_map().get(ticker)
    return ac._latest_business_rcept(corp) if corp else None


def main_text(rcept: str) -> str | None:
    """본문(사업의 내용 등 154항목). §14의 디스크 캐시를 그대로 쓴다."""
    return ac._fetch_main_xml(rcept) if rcept else None


def statement_texts(rcept: str) -> dict[str, str]:
    """{'연결': 연결감사보고서, '별도': 별도감사보고서} — **재무제표 주석이 여기 있다**.

    본문(수 MB)은 제외하고 작은 멤버만 디스크에 캐시한다. 어느 쪽이 연결인지는 파일명으로
    알 수 없어 '연결' 낱말 빈도로 가른다(연결감사보고서는 '연결실체'가 문서 전체에 깔린다).
    """
    if not rcept:
        return {}
    cached = {}
    for kind in ("연결", "별도"):
        p = _dir() / f"fs_{rcept}_{kind}.txt"
        if p.exists():
            try:
                cached[kind] = p.read_text(encoding="utf-8")
            except OSError:
                pass
    if cached:
        return cached

    try:
        r = requests.get(f"{_BASE}/document.xml", params={
            "crtfc_key": get_settings().dart_api_key, "rcept_no": rcept}, timeout=180)
        zf = zipfile.ZipFile(io.BytesIO(r.content))
    except Exception:
        return {}

    cands: list[tuple[int, str]] = []          # (연결 낱말수, 본문)
    for name in zf.namelist():
        b = zf.read(name)
        for enc in ("utf-8", "euc-kr", "cp949"):
            try:
                t = b.decode(enc)
                break
            except Exception:
                continue
        else:
            t = b.decode("utf-8", "ignore")
        if len(t) > _MAIN_MIN or "주석" not in t:
            continue                            # 본문(대용량)·표지 등은 주석 멤버가 아니다
        cands.append((len(re.findall(r"연결실체|연결재무제표", t)), t))
    if not cands:
        return {}
    cands.sort(key=lambda x: x[0], reverse=True)
    out = {"연결": cands[0][1]}
    if len(cands) > 1 and cands[-1][0] < cands[0][0]:
        out["별도"] = cands[-1][1]
    for kind, t in out.items():
        try:
            (_dir() / f"fs_{rcept}_{kind}.txt").write_text(t, encoding="utf-8")
        except OSError:
            pass
    return out


# --- 절 인덱스 --------------------------------------------------------------
def sections(txt: str) -> list[dict]:
    """본문 → [{code, title, eng, start, end}] (문서 순서)."""
    out = []
    for m in re.finditer(r"<TITLE\b([^>]*)>([^<]*)", txt):
        attrs, title = m.group(1), re.sub(r"\s+", " ", m.group(2)).strip()
        code = re.search(r'AASSOCNOTE="([^"]*)"', attrs)
        eng = re.search(r'ENG="([^"]*)"', attrs)
        out.append({"code": (code.group(1) if code else ""),
                    "eng": (eng.group(1) if eng else ""),
                    "title": title, "start": m.start(), "end": None})
    for i, s in enumerate(out):
        s["end"] = out[i + 1]["start"] if i + 1 < len(out) else len(txt)
    return out


def section(txt: str, key: str) -> str | None:
    """절 하나의 본문. ``key`` 는 ``SEC`` 의 키('III-8')나 코드('D-0-3-8-0')."""
    code = SEC.get(key, key)
    idx = sections(txt)
    for s in idx:
        if s["code"] == code:
            return txt[s["start"]:s["end"]]
    # 폴백 ①: 절 제목(서식 코드를 안 넣은 문서)
    pat = SEC_TITLE.get(key)
    if pat and idx:
        for i, s in enumerate(idx):
            if re.search(pat, s["title"]):
                return txt[s["start"]:s["end"]]
    # 폴백 ②: TITLE 태그 자체가 없는 문서 → 제목 문자열 근처를 잘라 쓴다
    if pat:
        m = re.search(pat, txt)
        if m:
            return txt[m.start():m.start() + 120_000]
    return None


def note(txt: str, kw: str, alt: tuple[str, ...] = (), span: int = 40_000) -> str | None:
    """재무제표 주석 한 개를 **제목으로** 찾는다.

    번호는 회사마다 다르다 — 재고자산이 한국콜마는 12번, 삼성전자는 7번, 특수관계자는
    각각 37번·31번이다. 그래서 번호를 고정하면 남의 주석을 읽는다. 제목으로 찾되
    ``<P ID="28. 영업부문">`` 앵커가 있으면 그쪽이 더 정확하다.

    같은 제목은 보통 세 번 나온다 — ① 주석 목차 표 ② 회계정책('2.8 재고자산') ③ 진짜 주석.
    번호가 붙은 것만 남기면 ②가 빠지고, 그중 **마지막**이 ③이다.
    """
    cands: list[tuple[int, int]] = []
    for k in (kw,) + tuple(alt):
        p = re.escape(k)
        for m in re.finditer(r'ID="\s*(\d{1,3})\s*[.．][^"]{0,20}%s' % p, txt):
            cands.append((m.start(), int(m.group(1))))
        # 앞에 숫자·점·하이픈이 붙은 건 **소제목**('37-2. 특수관계자…'·'2.15 무형자산')이다.
        # 이걸 제목으로 세면 주석의 한복판부터 잘라 읽게 된다.
        for m in re.finditer(r"(?<![\d.\-－―–])(\d{1,3})\s*[.．]\s*%s" % p, txt):
            cands.append((m.start(), int(m.group(1))))
        if cands:
            break
    if not cands:
        return None
    cands.sort()
    with_table = [c for c in cands if "<TABLE" in txt[c[0]:c[0] + 8_000]]
    start, num = (with_table or cands)[-1]
    # 앵커가 태그 **속성** 안이라(``<P ID="28. 영업부문">``) 그 자리에서 자르면 태그가
    # 반쪽만 남아 텍스트 정리 때 속성 문자열이 본문으로 새 나온다 → 여는 '<' 까지 물린다.
    lt = txt.rfind("<", max(0, start - 200), start)
    start = lt if lt >= 0 else start
    end = start + span
    nxt = re.search(r'(?<![\d.\-－―–])%d\s*[.．]\s*[가-힣]' % (num + 1), txt[start + 30:])
    if nxt:
        end = start + 30 + nxt.start()
    return txt[start:min(end, len(txt))]


# --- 표 -------------------------------------------------------------------
def grids(seg: str, limit: int = 12) -> list[list[list[str]]]:
    """구간 안의 <TABLE> 들을 병합 펼친 격자로. (단위 캡션만 든 1×1 표는 버린다)"""
    out = []
    for m in re.finditer(r"<TABLE\b.*?</TABLE>", seg, re.S | re.I):
        g = _grid(m.group(0))
        if not g or (len(g) == 1 and len(g[0]) <= 1):
            continue
        out.append(g)
        if len(out) >= limit:
            break
    return out


def head_text(grid: list[list[str]], rows: int = 3) -> str:
    return " ".join(c for r in grid[:rows] for c in r)


def pick_grid(seg: str, must: tuple[str, ...] = (), any_of: tuple[str, ...] = (),
              forbid: tuple[str, ...] = (), min_rows: int = 2,
              limit: int = 12) -> list[list[str]] | None:
    """구간에서 **조건에 맞는 표 중 가장 그럴듯한 것**. 첫 매칭을 쓰지 않는 이유는 §15.8-4.

    점수 = 필수어 전부 + 선택어 개수 + 행 수. 못 고르면 None(=확인불가).
    """
    best, best_score = None, -1
    for g in grids(seg, limit):
        if len(g) < min_rows:
            continue
        head = re.sub(r"\s+", "", head_text(g))
        whole = re.sub(r"\s+", "", " ".join(c for r in g for c in r[:2]))
        if any(re.sub(r"\s+", "", f) in head for f in forbid):
            continue
        if not all(re.sub(r"\s+", "", k) in head for k in must):
            continue
        score = sum(1 for k in any_of if re.sub(r"\s+", "", k) in head + whole) * 5 + len(g)
        if score > best_score:
            best, best_score = g, score
    return best


_UNITS = (("십억원", 1e9), ("백만원", 1e6), ("천원", 1e3), ("억원", 1e8),
          ("백만", 1e6), ("천", 1e3), ("원", 1.0))


def unit_won(text: str, default: float = 1.0) -> float:
    """'(단위 : 백만원)' → 1e6. 표 캡션·머리행 어디에 있어도 잡는다."""
    m = re.search(r"단위\s*[:：]?\s*[^)\n<]{0,12}?(십억원|백만원|천원|억원|원)", _flat(text)[:4000])
    return dict(_UNITS).get(m.group(1), default) if m else default


def header_row(grid: list[list[str]], keys: tuple[str, ...]) -> int | None:
    """머리행 위치 — ``keys`` 중 하나라도 든 마지막 행(2단 헤더면 아래쪽이 실제 라벨)."""
    hit = None
    for i, row in enumerate(grid[:4]):
        line = re.sub(r"\s+", "", " ".join(row))
        if any(re.sub(r"\s+", "", k) in line for k in keys):
            hit = i
    return hit


def col_of(row: list[str], *keys: str) -> int | None:
    """머리행에서 키워드가 든 첫 열 번호."""
    for j, c in enumerate(row):
        cc = re.sub(r"\s+", "", c or "")
        if any(re.sub(r"\s+", "", k) in cc for k in keys):
            return j
    return None


_SUB_RATIO = re.compile(r"비중|비율|구성비|수량|물량|증감")
_SUB_VALUE = re.compile(r"금액|매출액|가액|매입액|판매액|투입액")


def years_in_header(grid: list[list[str]]) -> dict[int, str]:
    """{열: '2025'} — 머리행의 **값(금액) 연도열**. 연도가 없으면 기수('제14기')를 라벨로.

    2단 헤더를 조심해야 한다. 연도 아래가 다시 `금액|비중`으로 갈리는 표(한국항공우주
    매출실적)에서 두 열을 다 연도로 잡으면 **뒤 열(비중 38.28)이 매출액을 덮어써서**
    3.7조 매출이 1억으로 잡힌다. 그래서 아래 행에 '비중·수량'이 보이면 금액 열만 남긴다.
    """
    for ri, row in enumerate(grid[:3]):
        cols = {}
        for j, c in enumerate(row):
            cc = re.sub(r"\s+", "", c or "")
            y = re.search(r"(20\d\d)년?", cc)
            if y:
                cols[j] = y.group(1)
            elif re.search(r"제\d+\(?[당전]?\)?기", cc):
                cols[j] = cc[:12]
        if len(cols) < 2:
            continue
        sub = grid[ri + 1] if ri + 1 < len(grid) else []
        if any(_SUB_RATIO.search(sub[j] or "") for j in cols if j < len(sub)):
            keep = {j: y for j, y in cols.items()
                    if j < len(sub) and _SUB_VALUE.search(sub[j] or "")}
            return keep                      # 금액 열을 못 가리면 비우고 만다(섞느니 버린다)
        return cols
    return {}


TOTAL = re.compile(r"^(합계|소계|계|총계|총합계|전체|부문계|부문합계|부문소계|연결계|누계)$")
# '…계'로 끝나지만 합계가 아닌 낱말 — 이걸 합계로 세면 멀쩡한 부문·항목이 사라진다.
_NOT_TOTAL = {"관계", "한계", "세계", "기계", "통계", "회계", "시계", "경계", "단계",
              "체계", "설계", "생계", "학계", "업계", "가계", "중계", "연계"}


def is_total(s: str) -> bool:
    """합계 행·열인가.

    이름이 회사마다 다르다 — '계(*)'(삼성전자)·'부문계'(농심)·'합 계'. 각주를 안 떼거나
    '부문계'를 놓치면 **합이 정확히 두 배**가 되어 멀쩡한 회사가 불일치로 찍힌다.
    """
    t = re.sub(r"\s+", "", re.sub(r"\(.*?\)|[*※]|\d", "", s or ""))
    if not t:
        return False
    if TOTAL.match(t):
        return True
    return len(t) <= 5 and t.endswith("계") and t not in _NOT_TOTAL


def dart_url(rcept: str) -> str:
    return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept}"
