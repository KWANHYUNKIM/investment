"""Per-stock 거래원 (trading-member / 증권사 창구) buy·sell ranking.

Answers "어떤 창구가 사고팔았는지" for a ticker. KRX's investor-subtype data
(연기금 / 투신 / 금융투자 …) is login-walled/blocked here, and Naver's mobile
trend API only exposes the 개인 / 외국인 / 기관 *aggregate*. The one source that
still works without a key is Naver Finance's 거래원정보 table on
``finance.naver.com/item/frgn.naver`` (EUC-KR), which lists, for the day, the
top-5 매도 회원사 and top-5 매수 회원사 plus the 외국계 추정 net — i.e. *which
brokerage houses* drove the trade (외국계 창구 매수/매도 is the usual proxy for
foreign flow). Estimated from the 5 most-active members, 20-min delayed.
"""
from __future__ import annotations

import re
import threading
import time

import requests

_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
}
_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}
TTL = 600.0  # 10 min (source is 20-min delayed anyway)

# Foreign brokerage houses ("외국계 창구") — buying here usually proxies foreign
# demand. Matched as substrings against the 거래원 name.
_FOREIGN_HOUSES = (
    "모간스탠리", "모간", "제이피모간", "JP모간", "씨티", "CS", "크레디트스위스",
    "메릴린치", "BofA", "골드만삭스", "골드만", "UBS", "CLSA", "맥쿼리", "노무라",
    "다이와", "도이치", "HSBC", "BNP", "비엔피", "소시에테", "미즈호", "뉴엣지",
    "외국계",
)


def _is_foreign(name: str) -> bool:
    return any(h in name for h in _FOREIGN_HOUSES)


def _int(s: str) -> int | None:
    s = re.sub(r"[^\d-]", "", s or "")
    if not s or s == "-":
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _parse(html: str) -> dict:
    """Extract the 거래원정보 table → top sell/buy houses + 외국계 추정 net."""
    s = html.find("거래원정보")
    if s < 0:
        return {"sell": [], "buy": [], "foreign": None}
    end = html.find("</table>", s)
    block = html[s : end if end > 0 else s + 8000]

    sell: list[dict] = []
    buy: list[dict] = []
    foreign_sell = foreign_buy = None

    # Each data row: 매도 name | 매도 vol | 매수 name | 매수 vol, names optionally
    # wrapped in <span>. The 외국계추정합 row carries class="total".
    row_re = re.compile(r"<tr([^>]*)>(.*?)</tr>", re.S)
    cell_re = re.compile(
        r'<td[^>]*class="([^"]*)"[^>]*>\s*(?:<span[^>]*>)?\s*(.*?)\s*(?:</span>)?\s*</td>',
        re.S,
    )
    for rattr, rbody in row_re.findall(block):
        cells = cell_re.findall(rbody)
        if len(cells) < 4:
            continue
        # cells are (class, text) in column order: sell-name, sell-vol, buy-name, buy-vol
        texts = [re.sub(r"<[^>]+>", "", t).replace("&nbsp;", "").strip() for _, t in cells]
        sname, svol, bname, bvol = texts[0], texts[1], texts[2], texts[3]
        is_total = "total" in rattr
        if is_total:
            foreign_sell = _int(svol)
            foreign_buy = _int(bvol)
            continue
        if sname:
            sell.append({"name": sname, "volume": _int(svol), "foreign": _is_foreign(sname)})
        if bname:
            buy.append({"name": bname, "volume": _int(bvol), "foreign": _is_foreign(bname)})

    foreign = None
    if foreign_buy is not None or foreign_sell is not None:
        net = (foreign_buy or 0) - (foreign_sell or 0)
        foreign = {"buy": foreign_buy, "sell": foreign_sell, "net": net}
    return {"sell": sell[:5], "buy": buy[:5], "foreign": foreign}


def brokers(ticker: str) -> dict:
    """Top buy/sell 거래원 (증권사 창구) for a ticker (cached ~10 min).

    Returns ``{"sell": [{name, volume, foreign}], "buy": [...],
    "foreign": {buy, sell, net} | None}``. Empty lists when the source hasn't
    populated the day's table yet (e.g. pre-market).
    """
    with _lock:
        hit = _cache.get(ticker)
        if hit and (time.time() - hit[0] < TTL):
            return hit[1]

    url = f"https://finance.naver.com/item/frgn.naver?code={ticker}"
    out = {"sell": [], "buy": [], "foreign": None}
    try:
        r = requests.get(url, headers={**_UA, "Referer": f"https://finance.naver.com/item/main.naver?code={ticker}"}, timeout=12)
        r.raise_for_status()
        r.encoding = "euc-kr"
        out = _parse(r.text)
    except Exception:
        if _cache.get(ticker):
            return _cache[ticker][1]

    with _lock:
        _cache[ticker] = (time.time(), out)
    return out
