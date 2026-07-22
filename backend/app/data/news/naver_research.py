"""애널리스트 리포트 목록 취합 (Tier 1) — 네이버 리서치 '사실+링크'만.

저작권 경계: 리포트 **원문(분석 프로즈)은 취득·저장·복제하지 않는다**. 여기서 모으는 것은
공개 목록의 **사실 메타데이터**(제목·증권사·작성일·원문 링크)뿐이다. 화면에는 링크만 걸어
사용자가 원문을 직접 보게 한다. 목표주가·투자의견 컨센서스 '수치'는 목록에 없어(각 PDF 내부)
Tier 2에서 별도 소스로 다룬다.

개인용·비상업 전제. 과도한 크롤링을 피하려 10분 캐시 + 회사 단위 온디맨드 호출만 한다.
"""
from __future__ import annotations

import re
import threading
import time
from urllib.parse import quote

import requests

_BASE = "https://finance.naver.com/research/company_list.naver"
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
_TTL = 600  # 10분
_cache: dict[str, dict] = {}
_lock = threading.Lock()


def _fetch(company: str, ticker: str) -> str:
    kw = quote(company.encode("euc-kr"))
    url = f"{_BASE}?searchType=keyword&keyword={kw}&itemName=&itemCode={ticker}"
    r = requests.get(url, headers=_UA, timeout=15)
    r.encoding = "euc-kr"
    return r.text


def _parse(html: str, company: str, limit: int) -> list[dict]:
    """목록 표에서 이 회사의 행만 → [{title, broker, date, url}]."""
    out: list[dict] = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        tds = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip()
               for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(tds) < 5 or not re.search(r"\d{2}\.\d{2}\.\d{2}", " ".join(tds)):
            continue
        if tds[0].strip() != company:              # 종목명 정확 일치만
            continue
        pdf = re.search(r'href="([^"]*\.pdf[^"]*)"', row)
        out.append({
            "title": tds[1][:120],                 # 제목(사실 메타데이터)
            "broker": tds[2],
            "date": _norm_date(tds[4]),
            "url": pdf.group(1) if pdf else None,   # 원문 PDF 링크(복제 아님)
        })
        if len(out) >= limit:
            break
    return out


def _norm_date(s: str) -> str:
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{2})", s or "")
    return f"20{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else (s or "")


_WISE = "https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx"
_consensus_cache: dict[str, dict] = {}


def _opinion_label(score: float) -> str:
    """네이버 투자의견 4점 척도(4=적극매수 … 1=매도)."""
    if score >= 3.5:
        return "적극매수"
    if score >= 3.0:
        return "매수"
    if score >= 2.0:
        return "중립"
    return "매도"


def _norm_opinion(op: str) -> str:
    """제공처 투자의견 문자열 → 매수/중립/매도 3분류(사실 라벨)."""
    o = (op or "").strip().lower()
    if any(k in o for k in ("strongbuy", "strong buy", "적극")):
        return "적극매수"
    if any(k in o for k in ("buy", "overweight", "outperform", "매수")):
        return "매수"
    if any(k in o for k in ("hold", "neutral", "marketperform", "중립", "보유")):
        return "중립"
    if any(k in o for k in ("sell", "reduce", "underweight", "매도")):
        return "매도"
    return "기타"


def _bucket(label: str) -> str:
    if label in ("적극매수", "매수"):
        return "buy"
    if label == "중립":
        return "hold"
    if label == "매도":
        return "sell"
    return "other"


def consensus(ticker: str) -> dict | None:
    """(Tier2) 애널리스트 컨센서스 — WISEfn(네이버 종목분석).

    반환 사실 수치: 투자의견(4점)·목표주가·EPS·PER·추정기관수·기준일
      + 투자의견 분포(매수/중립/매도) + 제공처별(증권사·목표가·의견). 원문 복제 아님.
    """
    now = time.time()
    with _lock:
        c = _consensus_cache.get(ticker)
        if c and now - c["ts"] < _TTL:
            return c["data"]
    try:
        r = requests.get(f"{_WISE}?cmp_cd={ticker}", headers={**_UA, "Referer": "https://finance.naver.com/"}, timeout=15)
        html = r.text
        flat = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    except Exception:
        return None
    # 요약 행: "… 추정기관수 <투자의견> <목표주가> <EPS> <PER> <추정기관수>"
    m = re.search(r"추정기관수\s+([0-9.]+)\s+([0-9,]+)\s+([0-9,]+)\s+([0-9.]+)\s+([0-9]+)", flat)
    if not m:
        return None
    opinion = float(m.group(1))
    dm = re.search(r"기준:([0-9.]+)", flat)

    # 제공처별 투자의견·목표가 표 → 분포 + 증권사별
    providers: list[dict] = []
    dist = {"buy": 0, "hold": 0, "sell": 0, "other": 0}
    i = html.find("제공처별 투자의견")
    if i >= 0:
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html[i:i + 9000], re.S):
            tds = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip()
                   for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
            if len(tds) < 6 or not re.search(r"\d{2}/\d{2}/\d{2}", tds[1] if len(tds) > 1 else ""):
                continue
            label = _norm_opinion(tds[5])
            dist[_bucket(label)] += 1
            tgt = re.sub(r"[^\d]", "", tds[2])
            providers.append({
                "broker": tds[0],
                "date": "20" + tds[1].replace("/", "-"),
                "target": int(tgt) if tgt else None,
                "opinion": label,
            })

    data = {
        "opinion_score": opinion,
        "opinion_label": _opinion_label(opinion),
        "target_price": int(m.group(2).replace(",", "")),
        "eps": int(m.group(3).replace(",", "")),
        "per": float(m.group(4)),
        "n_institutions": int(m.group(5)),
        "as_of": dm.group(1).replace(".", "-") if dm else None,
        "opinion_dist": {"buy": dist["buy"], "hold": dist["hold"], "sell": dist["sell"]},
        "providers": providers,
        "source": "네이버 종목분석 컨센서스(WISEfn) — 수치·의견 사실만",
    }
    with _lock:
        _consensus_cache[ticker] = {"ts": now, "data": data}
    return data


_pdf_cache: dict[str, int | None] = {}


def _pdf_target_price(url: str) -> int | None:
    """(Tier2-ㄴ) 리포트 PDF에서 '목표주가 …원' **숫자만** 추출(사실). 원문 저장 X.

    첫 1~2페이지만 읽고 목표주가 숫자만 취한 뒤 텍스트는 버린다.
    """
    if not url:
        return None
    if url in _pdf_cache:
        return _pdf_cache[url]
    val = None
    try:
        import io
        from pypdf import PdfReader
        b = requests.get(url, headers=_UA, timeout=20).content
        reader = PdfReader(io.BytesIO(b))
        txt = " ".join((reader.pages[i].extract_text() or "") for i in range(min(2, len(reader.pages))))
        m = re.search(r"목표주가[^0-9]{0,12}([0-9]{2,3},[0-9]{3})\s*원", txt)
        if m:
            v = int(m.group(1).replace(",", ""))
            if 100 <= v <= 100_000_000:
                val = v
    except Exception:
        val = None
    _pdf_cache[url] = val
    return val


def reports(company: str, ticker: str, limit: int = 15, extract_targets: int = 0) -> dict:
    """회사별 최근 애널리스트 리포트 취합(메타데이터+링크) + 컨센서스 + 리포트별 목표주가. 10분 캐시.

    - Tier1: 제목·증권사·날짜·원문 링크(사실+링크).
    - Tier2-ㄱ: `consensus`(WISEfn 투자의견·목표주가·추정기관수).
    - Tier2-ㄴ: 최근 `extract_targets`건 PDF에서 목표주가 숫자만 추출 → 증권사별 목표주가 분포.
    """
    key = f"{ticker}:{company}"
    now = time.time()
    with _lock:
        c = _cache.get(key)
        if c and now - c["ts"] < _TTL:
            return c["data"]
    try:
        items = _parse(_fetch(company, ticker), company, limit)
    except Exception as e:  # noqa: BLE001
        return {"ticker": ticker, "company": company, "n_reports": 0,
                "brokers": [], "latest_date": None, "reports": [], "consensus": None, "error": str(e)[:120]}

    # Tier2-ㄴ: 최근 몇 건만 PDF 목표주가 추출(과도한 다운로드 방지)
    for it in items[:extract_targets]:
        it["target_price"] = _pdf_target_price(it.get("url"))
    for it in items[extract_targets:]:
        it["target_price"] = None
    targets = [it["target_price"] for it in items if it.get("target_price")]

    brokers = sorted({r["broker"] for r in items if r["broker"]})
    data = {
        "ticker": ticker, "company": company,
        "n_reports": len(items),
        "brokers": brokers,
        "broker_count": len(brokers),
        "latest_date": items[0]["date"] if items else None,
        "reports": items,
        "consensus": consensus(ticker),                    # Tier2-ㄱ
        "target_sample": {                                 # Tier2-ㄴ 요약(추출된 것만)
            "n": len(targets),
            "avg": round(sum(targets) / len(targets)) if targets else None,
            "high": max(targets) if targets else None,
            "low": min(targets) if targets else None,
        },
        "source": "네이버 금융 리서치(목록 메타데이터·원문 링크) + 종목분석 컨센서스(수치)",
    }
    with _lock:
        _cache[key] = {"ts": now, "data": data}
    return data
