"""배당주·공모주 추천 (계속 바뀌므로 주기적 갱신).

- 배당주 추천: 배당·실적(dividends) 고배당 랭킹 + 재무(PBR·ROE·시총·외국인·실적개선)로 점수화·등급·
  추천 이유·안정성·배당주기를 붙여 정리. '얼마 사면 월 얼마' 매수 가이드 포함.
- 공모주 청약일정: 38커뮤니케이션(38.co.kr) 청약일정 + 종목 상세(수요예측 경쟁률·의무보유확약·상장일·
  공모금액·시장)까지 스크래핑(캐시 30분). 확정공모가·경쟁률은 수요예측 후 확정.
"""
from __future__ import annotations

import datetime as _dt
import html
import re
import threading
import time
import urllib.request

from app.data.infra import store
from app.data.market import dividends

_lock = threading.Lock()
_ipo_cache: dict = {"ts": 0.0, "data": None}
IPO_TTL = 1800.0
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_DIV_TAX = 0.154


def _num(v):
    try:
        v = float(v)
        return None if v != v else v
    except (TypeError, ValueError):
        return None


# --- 배당주 추천 (점수화) --------------------------------------------------
def _financials_map() -> dict:
    fins = store.financials_latest()
    out = {}
    if fins is not None and not fins.empty:
        for r in fins.to_dict("records"):
            out[r.get("ticker")] = {"op_yoy": _num(r.get("op_yoy")), "op_margin": _num(r.get("op_margin"))}
    return out


def _score(dy, per, pbr, roe, mcap, fratio, op_yoy, is_reit):
    s = 0.0
    reasons = []
    # 배당 매력 (35)
    if dy:
        s += min(35, dy / 7 * 35)
        reasons.append(f"배당수익률 {dy}% 고배당" if dy >= 6 else (f"배당수익률 {dy}% 양호" if dy >= 4 else f"배당 {dy}%"))
    # 저평가 (PER 15 + PBR 10)
    if per and per > 0:
        s += 15 if per <= 6 else max(0, 15 * (1 - (per - 6) / 14))
        if per <= 10:
            reasons.append(f"PER {round(per, 1)}배 저평가")
    if pbr and pbr > 0:
        s += 10 if pbr <= 1 else max(0, 10 * (1 - (pbr - 1) / 2))
        if pbr <= 1:
            reasons.append(f"PBR {round(pbr, 2)} 순자산 이하")
    # 수익성 (ROE 15 + 실적개선 5)
    if roe is not None:
        s += max(0, min(15, roe / 15 * 15))
        if roe >= 10:
            reasons.append(f"ROE {round(roe, 1)}% 수익성 양호")
        elif roe < 0:
            reasons.append(f"ROE {round(roe, 1)}% 적자 주의")
    if op_yoy is not None and op_yoy > 0:
        s += 5
        reasons.append(f"영업이익 전년比 +{round(op_yoy)}% 개선")
    # 규모·외국인 (시총 15 + 외국인 5)
    if mcap:
        s += min(15, 15 if mcap >= 1e12 else max(3, 15 * (mcap / 1e12)))
        reasons.append("대형주(안정)" if mcap >= 1e12 else ("중형주" if mcap >= 3e11 else "중소형주(변동성 주의)"))
    if fratio:
        s += min(5, fratio / 40 * 5)
        if fratio >= 20:
            reasons.append(f"외국인 {round(fratio)}% 보유")
    if is_reit:
        reasons.append("리츠 — 정기 배당 성향")

    score = round(min(100, s))
    grade = "A" if score >= 75 else "B" if score >= 60 else "C" if score >= 45 else "D"
    if roe is not None and roe < 0:
        stability = "낮음"
    elif roe and roe >= 8 and (op_yoy is None or op_yoy >= 0) and mcap and mcap >= 3e11:
        stability = "높음"
    else:
        stability = "중간"
    cycle = "분기·반기 배당 많음(리츠)" if is_reit else "연 1회(결산) 배당이 흔함"
    return score, grade, reasons, stability, cycle


def dividend_picks(top: int = 12) -> dict:
    base = dividends.board().get("dividends", [])
    rich = store.fundamentals_rich_map()
    fin = _financials_map()

    rows = []
    for r in base:
        dy = r.get("div_yield") or 0
        if dy < 2 or dy > 15:
            continue
        t = r["ticker"]
        f = rich.get(t, {})
        pbr = _num(f.get("pbr"))
        mcap = _num(f.get("market_cap"))
        fratio = _num(f.get("foreign_ratio"))
        roe = _num(r.get("roe"))
        per = _num(r.get("per"))
        op_yoy = (fin.get(t) or {}).get("op_yoy")
        sector = r.get("sector") or ""
        is_reit = ("리츠" in (r.get("name") or "")) or ("부동산" in sector)
        score, grade, reasons, stability, cycle = _score(dy, per, pbr, roe, mcap, fratio, op_yoy, is_reit)
        monthly = round(10_000_000 * dy / 100 * (1 - _DIV_TAX) / 12)
        rows.append({
            "ticker": t, "name": r.get("name"), "sector": sector, "close": r.get("close"),
            "div_yield": round(dy, 2), "per": round(per, 1) if per else None,
            "pbr": round(pbr, 2) if pbr else None, "roe": round(roe, 1) if roe is not None else None,
            "market_cap": round(mcap) if mcap else None, "foreign_ratio": round(fratio, 1) if fratio else None,
            "op_yoy": round(op_yoy, 1) if op_yoy is not None else None,
            "score": score, "grade": grade, "reasons": reasons, "stability": stability, "cycle": cycle,
            "monthly_per_10m": monthly,
            "naver_url": f"https://finance.naver.com/item/main.naver?code={t}",
        })

    rows.sort(key=lambda x: -x["score"])
    return {
        "generated_at": dividends.board().get("generated_at"),
        "picks": rows[:top],
        "guide": [
            "① 배당수익률만 보지 마세요 — 배당은 실적이 나쁘면 삭감됩니다. ROE·영업이익·배당성향을 함께 확인.",
            "② PER·PBR이 낮으면 주가가 싸다는 뜻이라 배당수익률이 상대적으로 높게 잡히기도 합니다(저평가 vs 부실 구분).",
            "③ '점수'는 배당(35)+저평가(25)+수익성(20)+규모·외국인(20)을 합산한 참고 지표입니다(A≥75·B≥60·C≥45).",
            "④ 배당락일 전에 보유해야 그 회차 배당을 받습니다. 리츠·커버드콜은 분기/월 배당이 많습니다.",
            "⑤ 배당소득세 15.4%, 연 금융소득 2천만 초과 시 종합과세 — ISA·연금계좌 활용이 절세에 유리.",
            "⑥ 한 종목에 몰빵하지 말고 업종을 분산하세요(은행·통신·리츠·정유 등).",
        ],
        "note": "고배당 상위(유동성 필터+배당 2~15% 밴드)를 재무 점수로 재정렬. 배당수익률·재무는 최근 스냅샷이라 계속 변합니다. "
                "점수는 참고용이며 투자 판단·손실 책임은 본인에게 있습니다.",
    }


# --- 공모주 청약일정 + 상세 -----------------------------------------------
def _parse_range(s: str):
    m = re.match(r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})\s*~\s*(?:(\d{4})[.\-])?(\d{1,2})[.\-](\d{1,2})", s)
    if not m:
        m2 = re.match(r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})", s)
        if not m2:
            return None, None
        try:
            d = _dt.date(int(m2.group(1)), int(m2.group(2)), int(m2.group(3)))
            return d, d
        except ValueError:
            return None, None
    try:
        start = _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        y2 = int(m.group(4)) if m.group(4) else int(m.group(1))
        end = _dt.date(y2, int(m.group(5)), int(m.group(6)))
        return start, end
    except ValueError:
        return None, None


def _cells(htmltext: str) -> list[str]:
    out = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).replace("&nbsp;", "").strip()
           for c in re.split(r"</td>", htmltext)]
    return [c for c in out if c]


def _ipo_detail(no: str) -> dict:
    try:
        req = urllib.request.Request(f"http://www.38.co.kr/html/fund/index.htm?o=v&no={no}", headers=_UA)
        det = urllib.request.urlopen(req, timeout=8).read().decode("euc-kr", "ignore")
    except Exception:
        return {}
    cells = _cells(det)

    def nxt(label: str) -> str:
        for i, c in enumerate(cells):
            cc = c.replace(" ", "")
            if cc == label or (label in cc and len(c) <= 22):
                return cells[i + 1].strip() if i + 1 < len(cells) else ""
        return ""

    market = nxt("시장구분")
    shares = nxt("총공모주식수")
    amount = nxt("공모금액")                       # 예: "24,840 (백만원)"
    listing = nxt("상장일") or nxt("신규상장일")
    lm = re.search(r"(20\d\d[.\-]\d{1,2}[.\-]\d{1,2})", listing)
    listing_date = lm.group(1) if lm else ""
    # 공모금액(백만원) → 원
    amt_won = None
    am = re.search(r"([\d,]+)", amount)
    if am and "백만" in amount:
        amt_won = int(am.group(1).replace(",", "")) * 1_000_000
    # 태그 제거한 평문에서 경쟁률·확약 추출(태그 속성 숫자 오인 방지)
    flat = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", det))
    dc = re.search(r"([0-9][0-9,]*\.?[0-9]*)\s*:\s*1", flat)
    demand = dc.group(0).replace(" ", "") if dc else ""
    lk = re.search(r"의무보유확약[^0-9%]*([0-9]+\.?[0-9]*)\s*%", flat)
    lockup = f"{lk.group(1)}%" if lk else ""
    if not demand:                     # 수요예측 전이면 경쟁률·확약 모두 미정
        lockup = ""
    return {
        "market": market, "shares": shares, "offer_amount_text": amount, "offer_amount_won": amt_won,
        "listing_date": listing_date, "demand_competition": demand, "lockup": lockup,
        "detail_url": f"http://www.38.co.kr/html/fund/index.htm?o=v&no={no}",
    }


def _fetch_ipo(limit: int) -> dict:
    url = "http://www.38.co.kr/html/fund/index.htm?o=k"
    try:
        req = urllib.request.Request(url, headers=_UA)
        txt = urllib.request.urlopen(req, timeout=15).read().decode("euc-kr", "ignore")
    except Exception as e:
        return {"items": [], "source": "38커뮤니케이션 (38.co.kr)", "error": f"{type(e).__name__}",
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "note": "공모주 일정 소스에 일시적으로 접속하지 못했습니다. 잠시 후 새로고침하세요."}

    today = _dt.date.today()
    items = []
    for chunk in re.split(r"<tr", txt):
        if "o=v&amp;no=" not in chunk and "o=v&no=" not in chunk:
            continue
        mno = re.search(r"o=v&(?:amp;)?no=(\d+)", chunk)
        mnm = re.search(r"o=v&(?:amp;)?no=\d+[^>]*>\s*([^<]+?)\s*</a>", chunk)
        cells = _cells(chunk)
        if not mno or len(cells) < 4:
            continue
        name = html.unescape(mnm.group(1)) if mnm else html.unescape(cells[0].split(">")[-1]).strip()
        sub = cells[1]
        if not re.search(r"20\d\d", sub):
            continue
        confirmed = cells[2] if len(cells) > 2 else "-"
        band = cells[3] if len(cells) > 3 else ""
        under = html.unescape(cells[4]) if len(cells) > 4 else ""
        start, end = _parse_range(sub)
        status = ("예정" if today < start else ("청약중" if today <= end else "마감")) if (start and end) else ""
        items.append({
            "no": mno.group(1), "name": name, "subscribe": sub, "status": status,
            "price_confirmed": confirmed if confirmed and confirmed != "-" else None,
            "price_band": band, "underwriter": under,
            "_start": start.isoformat() if start else "9999",
        })

    order = {"청약중": 0, "예정": 1, "": 2, "마감": 3}
    items.sort(key=lambda x: (order.get(x["status"], 2), x["_start"]))
    upcoming = [x for x in items if x["status"] in ("청약중", "예정")]
    recent_closed = [x for x in items if x["status"] == "마감"][:4]
    merged = (upcoming + recent_closed)[:limit]

    # 상세 보강 (청약중·예정 위주, 최대 12건)
    enriched = 0
    for x in merged:
        if x["status"] in ("청약중", "예정") and enriched < 12:
            x.update(_ipo_detail(x["no"]))
            enriched += 1
        else:
            x["detail_url"] = f"http://www.38.co.kr/html/fund/index.htm?o=v&no={x['no']}"
        x.pop("_start", None)

    return {
        "items": merged,
        "upcoming_count": len(upcoming),
        "source": "38커뮤니케이션 (38.co.kr)",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "guide": [
            "① 청약하려면 해당 '주간사(증권사)' 계좌가 필요합니다. 여러 종목은 각 주간사별로 계좌를 미리 만들어 두세요.",
            "② 청약 증거금은 보통 청약금액의 50%. 배정 후 미배정분은 환불됩니다.",
            "③ 균등배정(최소 청약하면 누구나 비슷하게)+비례배정(많이 넣을수록 더). 소액이면 여러 증권사 균등 청약이 유리.",
            "④ 수요예측 경쟁률↑·의무보유확약 비율↑·공모가 밴드 상단 확정이면 흥행 신호(상장일 강세 가능성).",
            "⑤ 인기 공모주는 배정 주수가 매우 적습니다(수 주). '따상'은 드무니 목표 수익률을 정해 분할 매도.",
            "⑥ 상장일 변동성이 큽니다. 여유자금으로, 손실 가능성도 감안하세요.",
        ],
        "note": "공모주 청약일정은 수시로 바뀝니다. 확정공모가·경쟁률은 기관 수요예측 후 결정됩니다. "
                "상세(경쟁률·의무보유확약·상장일)는 38커뮤니케이션 상세페이지 기준이며, 파싱 실패 시 일부 값이 비어 있을 수 있습니다.",
    }


def ipo_schedule(limit: int = 20) -> dict:
    with _lock:
        if _ipo_cache["data"] and (time.time() - _ipo_cache["ts"] < IPO_TTL):
            return _ipo_cache["data"]
    out = _fetch_ipo(limit)
    with _lock:
        if out.get("items") or not _ipo_cache["data"]:
            _ipo_cache["ts"] = time.time()
            _ipo_cache["data"] = out
    return out
