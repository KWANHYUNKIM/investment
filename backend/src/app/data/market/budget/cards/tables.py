"""카드사가 준 파일을 '표(행 × 셀)'로 바꾸는 층 — 포맷 판별은 여기서 끝낸다.

카드사 파일에서 제일 자주 걸리는 함정이 여기 있다.

**``.xls`` 인데 엑셀이 아니다.** 신한카드가 내려주는 이용대금명세서는 확장자만
``.xls`` 이고 내용은 ``<html xmln:x="urn:schemas-microsoft-com:office:excel">`` 로
시작하는 **HTML 표**다. 엑셀이 열어주니 사용자는 엑셀인 줄 알지만
``pandas.read_excel`` 은 열지 못한다(이 프로젝트도 그래서 0건 파싱됐다).
그래서 확장자가 아니라 **내용의 첫 바이트**로 포맷을 정한다.

**인코딩.** 한국 카드사 CSV 는 EUC-KR(cp949)이 아직 많고, HTML 은 meta charset 에
적어 준다. BOM → meta charset → UTF-8 → cp949 순으로 시도한다.

이 모듈은 의미를 해석하지 않는다. 어떤 컬럼이 금액인지는 카드사별 파서가 정한다.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

_WS = re.compile(r"\s+")


def _squash(s: str) -> str:
    return _WS.sub(" ", s).strip()


# --- 포맷 판별 --------------------------------------------------------------
_XLSX_MAGIC = b"PK\x03\x04"                      # zip (xlsx)
_XLS_MAGIC = b"\xd0\xcf\x11\xe0"                 # OLE2 (진짜 xls)


def sniff(data: bytes, filename: str = "") -> str:
    """``xlsx`` | ``xls`` | ``html`` | ``text`` — 확장자가 아니라 내용으로 판별."""
    head = data[:2048]
    if head.startswith(_XLSX_MAGIC):
        return "xlsx"
    if head.startswith(_XLS_MAGIC):
        return "xls"
    probe = head.lstrip(b"\xef\xbb\xbf \r\n\t")[:400].lower()
    if probe.startswith(b"<") and (b"<html" in probe or b"<table" in probe or b"<?xml" in probe):
        return "html"
    return "text"


# --- 디코딩 ----------------------------------------------------------------
_META_CHARSET = re.compile(rb"charset\s*=\s*[\"']?\s*([\w\-]+)", re.I)


def decode(data: bytes) -> str:
    """바이트 → 문자열. BOM · meta charset · UTF-8 · cp949 순으로 시도."""
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="replace")
    m = _META_CHARSET.search(data[:4096])
    if m:
        enc = m.group(1).decode("ascii", "ignore").lower()
        alias = {"ks_c_5601-1987": "cp949", "euc-kr": "cp949", "ksc5601": "cp949"}.get(enc, enc)
        try:
            return data.decode(alias)
        except (UnicodeDecodeError, LookupError):
            pass
    for enc in ("utf-8", "cp949"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


# --- HTML 표 ---------------------------------------------------------------
class _TableExtractor(HTMLParser):
    """중첩 ``<table>`` 을 견디는 최소 표 추출기.

    카드사 HTML 은 레이아웃용 표 안에 데이터 표를 넣는 경우가 흔해서 스택으로
    받는다. ``rowspan``/``colspan`` 은 펴지 않는다 — 명세서 본문 표는 격자가
    반듯하고, 억지로 펴면 오히려 컬럼이 밀린다.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._stack: list[list[list[str]]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "table":
            self._stack.append([])
        elif tag == "tr" and self._stack:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag in ("br", "p", "div") and self._cell is not None:
            self._cell.append(" ")

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(_squash("".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(c for c in self._row):
                self._stack[-1].append(self._row)
            self._row = None
        elif tag == "table" and self._stack:
            rows = self._stack.pop()
            if rows:
                self.tables.append(rows)


def html_tables(text: str) -> list[list[list[str]]]:
    p = _TableExtractor()
    try:
        p.feed(text)
        p.close()
    except Exception:
        pass                        # 깨진 태그가 있어도 그때까지 모은 표는 쓴다
    # 미닫힌 <table> 이 남아 있으면 마저 거둔다.
    for rows in reversed(p._stack):
        if rows:
            p.tables.append(rows)
    return p.tables


# --- 엑셀 ------------------------------------------------------------------
def excel_tables(data: bytes, kind: str) -> list[list[list[str]]]:
    try:
        import pandas as pd
    except ImportError:
        return []
    engine = "openpyxl" if kind == "xlsx" else "xlrd"
    try:
        sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, header=None, engine=engine)
    except Exception:
        try:                        # 엔진 추정이 틀렸을 수 있다 — pandas 기본값으로 한 번 더
            sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, header=None)
        except Exception:
            return []
    out: list[list[list[str]]] = []
    for df in sheets.values():
        rows = [["" if (c is None or str(c) == "nan" or str(c) == "NaT") else _squash(str(c))
                 for c in row] for row in df.itertuples(index=False)]
        rows = [r for r in rows if any(r)]
        if rows:
            out.append(rows)
    return out


# --- 구분자 텍스트 ----------------------------------------------------------
def text_tables(text: str) -> list[list[list[str]]]:
    """CSV/TSV — 따옴표 안의 구분자를 지키려면 csv 모듈을 쓴다."""
    import csv
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    head = "\n".join(lines[:20])
    delim = "\t" if head.count("\t") >= head.count(",") and "\t" in head else ","
    rows = [[_squash(c) for c in r] for r in csv.reader(lines, delimiter=delim)]
    rows = [r for r in rows if any(r)]
    return [rows] if rows else []


# --- 진입점 ----------------------------------------------------------------
@dataclass
class Sheet:
    """파일 하나에서 뽑아낸 표들 + 카드사 판별에 쓸 원문."""

    kind: str
    tables: list[list[list[str]]] = field(default_factory=list)
    text: str = ""                      # 카드사·청구월 판별용 (파일명 포함)
    raw: str = ""                       # 디코딩한 원문 (엑셀이면 빈 문자열)

    @property
    def rows(self) -> list[list[str]]:
        """모든 표를 위에서부터 이어붙인 행 목록."""
        return [r for t in self.tables for r in t]


def read(filename: str, data: bytes) -> Sheet:
    kind = sniff(data, filename)
    raw = ""
    if kind in ("xlsx", "xls"):
        found = excel_tables(data, kind)
        text = "\n".join(" ".join(r) for t in found for r in t[:40])
    else:
        raw = decode(data)
        found = html_tables(raw) if kind == "html" else text_tables(raw)
        # HTML 은 표 밖 제목(“2026년9월 예정 …”)에 청구월이 있어 원문을 함께 넘긴다.
        text = raw if kind == "html" else "\n".join(" ".join(r) for t in found for r in t[:40])
    return Sheet(kind=kind, tables=found, text=f"{filename}\n{text}", raw=raw)
