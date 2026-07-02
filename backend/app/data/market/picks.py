"""배당주·공모주 추천 (계속 바뀌므로 주기적 갱신).

- 배당주 추천: 기존 배당·실적(dividends) 고배당 랭킹을 재사용, 합리적 배당 밴드(2~15%)로
  추려 재테크 로드맵 맥락(월 배당 소득)으로 정리.
- 공모주 청약일정: 38커뮤니케이션(38.co.kr) 공모청약 일정 페이지를 스크래핑(캐시 30분).
  확정공모가·경쟁률은 수요예측 후 결정되므로 밴드/일정 위주로 제공.
"""
from __future__ import annotations

import datetime as _dt
import html
import re
import threading
import time
import urllib.request

from app.data.market import dividends

_lock = threading.Lock()
_ipo_cache: dict = {"ts": 0.0, "data": None}
IPO_TTL = 1800.0
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


# --- 배당주 추천 -----------------------------------------------------------
def dividend_picks(top: int = 12) -> dict:
    b = dividends.board()
    picks = []
    for r in b.get("dividends", []):
        dy = r.get("div_yield") or 0
        if dy < 2 or dy > 15:              # 저배당·이상치(특별배당·구주가) 제외
            continue
        # 참고: 1천만원 투자 시 세후 월 배당
        monthly = round(10_000_000 * dy / 100 * (1 - 0.154) / 12)
        picks.append({**r, "monthly_per_10m": monthly})
        if len(picks) >= top:
            break
    return {
        "generated_at": b.get("generated_at"),
        "picks": picks,
        "note": "고배당 상위(유동성 필터+배당 2~15% 밴드). 배당수익률=최근 재무 스냅샷 기준이라 주가·실적에 따라 "
                "계속 변합니다. 배당은 삭감될 수 있으니 배당성향·이익 안정성·연속 배당 이력을 확인하세요. 투자 판단·손실 책임은 본인에게 있습니다.",
    }


# --- 공모주 청약일정 -------------------------------------------------------
def _parse_range(s: str):
    """'2026.08.11~08.12' → (start_date, end_date) 또는 (None, None)."""
    m = re.match(r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})\s*~\s*(?:(\d{4})[.\-])?(\d{1,2})[.\-](\d{1,2})", s)
    if not m:
        m2 = re.match(r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})", s)
        if not m2:
            return None, None
        y, mo, d = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        try:
            return _dt.date(y, mo, d), _dt.date(y, mo, d)
        except ValueError:
            return None, None
    y1, mo1, d1 = int(m.group(1)), int(m.group(2)), int(m.group(3))
    y2 = int(m.group(4)) if m.group(4) else y1
    mo2, d2 = int(m.group(5)), int(m.group(6))
    try:
        return _dt.date(y1, mo1, d1), _dt.date(y2, mo2, d2)
    except ValueError:
        return None, None


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
        nm = re.search(r"o=v&(?:amp;)?no=\d+[^>]*>\s*([^<]+?)\s*</a>", chunk)
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).replace("&nbsp;", "").strip()
                 for c in re.split(r"</td>", chunk)]
        cells = [c for c in cells if c]
        if len(cells) < 4:
            continue
        name = html.unescape(nm.group(1)) if nm else html.unescape(cells[0].split(">")[-1]).strip()
        sub = cells[1]
        confirmed = cells[2] if len(cells) > 2 else "-"
        band = cells[3] if len(cells) > 3 else ""
        under = html.unescape(cells[4]) if len(cells) > 4 else ""
        if not re.search(r"20\d\d", sub):
            continue
        start, end = _parse_range(sub)
        if start and end:
            status = "예정" if today < start else ("청약중" if today <= end else "마감")
        else:
            status = ""
        items.append({
            "name": name, "subscribe": sub, "status": status,
            "price_confirmed": confirmed if confirmed and confirmed != "-" else None,
            "price_band": band, "underwriter": under,
            "_start": start.isoformat() if start else "",
            "_end": end.isoformat() if end else "",
        })

    # 청약중 → 예정 → 마감 순, 각 그룹 내 시작일 오름차순
    order = {"청약중": 0, "예정": 1, "": 2, "마감": 3}
    items.sort(key=lambda x: (order.get(x["status"], 2), x["_start"] or "9999"))
    # 마감 이미 지난 건 최근 것 위주로 소수만
    upcoming = [x for x in items if x["status"] in ("청약중", "예정")]
    recent_closed = [x for x in items if x["status"] == "마감"][:5]
    merged = upcoming + recent_closed
    for x in merged:
        x.pop("_start", None)
        x.pop("_end", None)
    return {
        "items": merged[:limit],
        "upcoming_count": len(upcoming),
        "source": "38커뮤니케이션 (38.co.kr)",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": "공모주 청약일정은 수시로 바뀝니다. 확정공모가·청약경쟁률은 기관 수요예측 후 결정됩니다. "
                "청약하려면 해당 주간사(증권사) 계좌가 필요하며, 인기 종목은 배정 주수가 매우 적습니다. 상장일 손실 위험도 있습니다.",
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
