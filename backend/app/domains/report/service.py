"""Business logic for the report domain.

Phase-2 deepening: the daily-report assembly (previously in
``app.data.reports.report``) now lives here — the domain owns its logic. The
service composes the report from the repository's data sources (price history,
investor flow, news) and builds the templated Korean summary itself. No LLM: it
states facts and frames news as *related background*, not proven causation.
"""
from __future__ import annotations

from .repository import ReportRepository

_FLOW_LABELS = {"individual": "개인", "foreign": "외국인", "organ": "기관"}
_NOTE = (
    "투자 주체는 유형(개인/외국인/기관)까지만 공개됩니다. 개별 기관·외국계 회사명은 "
    "5% 대량보유 공시(DART) 기준으로만 확인 가능합니다."
)


def _fmt_qty(v: int | None) -> str:
    if v is None:
        return "—"
    a = abs(v)
    if a >= 10000:
        return f"{a / 10000:,.0f}만주"
    return f"{a:,}주"


class ReportService:
    def __init__(self, repo: ReportRepository) -> None:
        self._repo = repo

    def daily_report(self, ticker: str, name: str | None) -> dict:
        name = name or ticker

        # --- price move (last two closes from the store) ---
        df = self._repo.ohlc(ticker)
        price: dict = {}
        if not df.empty and len(df) >= 2:
            last = df.iloc[-1]
            prev = df.iloc[-2]
            close = float(last["close"])
            pclose = float(prev["close"])
            change = close - pclose
            pct = (change / pclose * 100.0) if pclose else 0.0
            price = {
                "date": str(last["date"])[:10],
                "close": round(close),
                "change": round(change),
                "change_pct": round(pct, 2),
                "high": round(float(last["high"])),
                "low": round(float(last["low"])),
                "volume": round(float(last["volume"])) if last["volume"] == last["volume"] else None,
            }

        # --- investor flow (latest day) ---
        flow: dict = {}
        lead_seller = lead_buyer = None
        rows = self._repo.investor_flow(ticker)
        if rows:
            f = rows[0]
            flow = {
                "date": f["date"],
                "individual": f["individual"],
                "foreign": f["foreign"],
                "organ": f["organ"],
                "foreign_ratio": f["foreign_ratio"],
            }
            vals = {k: f[k] for k in _FLOW_LABELS if f.get(k) is not None}
            if vals:
                lead_seller = min(vals, key=lambda k: vals[k])
                lead_buyer = max(vals, key=lambda k: vals[k])

        # --- news (top headlines) ---
        arts: list[dict] = []
        try:
            nw = self._repo.news(name, limit=8)
            arts = (nw.get("domestic") or [])[:5]
        except Exception:
            pass

        # --- templated summary ---
        parts: list[str] = []
        if price:
            direction = "상승" if price["change_pct"] > 0 else "하락" if price["change_pct"] < 0 else "보합"
            sign = "+" if price["change"] > 0 else ""
            parts.append(
                f"{name}은(는) {price['date']} 종가 {price['close']:,}원으로 "
                f"전일 대비 {sign}{price['change']:,}원({sign}{price['change_pct']}%) {direction}했습니다."
            )
        if lead_seller and flow.get(lead_seller, 0) is not None and flow[lead_seller] < 0:
            parts.append(
                f"이날 매도는 {_FLOW_LABELS[lead_seller]}이(가) {_fmt_qty(flow[lead_seller])} 순매도하며 주도했고, "
                f"{_FLOW_LABELS[lead_buyer]}은(는) {_fmt_qty(flow[lead_buyer])} 순매수했습니다."
            )
        elif lead_buyer and flow.get(lead_buyer):
            parts.append(
                f"이날은 {_FLOW_LABELS[lead_buyer]}이(가) {_fmt_qty(flow[lead_buyer])} 순매수하며 매수세가 우위였습니다."
            )
        if arts:
            down = price.get("change_pct", 0) < 0
            parts.append("하락 관련 배경으로 볼 만한 주요 뉴스:" if down else "오늘의 주요 뉴스:")

        return {
            "ticker": ticker,
            "name": name,
            "price": price,
            "flow": flow,
            "lead_seller": _FLOW_LABELS.get(lead_seller) if lead_seller else None,
            "lead_buyer": _FLOW_LABELS.get(lead_buyer) if lead_buyer else None,
            "summary": " ".join(parts),
            "news": arts,
            "note": _NOTE,
        }

    def news_for(self, name: str, limit: int) -> dict:
        return self._repo.news(name, limit)
