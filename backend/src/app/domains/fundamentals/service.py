"""Business logic for the fundamentals domain.

Holds everything that is *decision*, not *I/O* or *transport*: cumulative
investor-flow sums, fundamentals Δ vs the previous snapshot (+ derived debt
ratio from the DART balance sheet), and grouping DART accounts into ordered
statements. Depends on the repository (DuckDB seam) and the legacy fetchers
(``financials`` / ``dart_financials`` / ``investor`` / ``dart`` / ``industry``)
— never on FastAPI.
"""
from __future__ import annotations

from app.core.errors import BadRequestError
from app.core.numeric import json_float as _f
from app.data.fundamentals import dart
from app.data.fundamentals import dart_financials
from app.data.fundamentals import financials
from app.data.intel import industry
from app.data.market import investor

from .repository import FundamentalsRepository

# DART statement (sj_div) display labels + report order. Domain-owned copies —
# intentionally not imported from the legacy ``app.api.data._common`` package.
_SJ_LABEL = {
    "BS": "재무상태표", "IS": "손익계산서", "CIS": "포괄손익계산서",
    "CF": "현금흐름표", "SCE": "자본변동표",
}
_SJ_ORDER = ["BS", "IS", "CIS", "CF", "SCE"]


class FundamentalsService:
    def __init__(self, repo: FundamentalsRepository) -> None:
        self._repo = repo

    def investor_flow(self, ticker: str, days: int) -> dict:
        hist = self._repo.investor_flow_history(ticker, days=days)
        rows = []
        cum = {"individual": 0.0, "foreigner": 0.0, "organ": 0.0}
        for r in hist.to_dict("records"):
            ind, frg, org = _f(r.get("individual")), _f(r.get("foreigner")), _f(r.get("organ"))
            cum["individual"] += ind or 0
            cum["foreigner"] += frg or 0
            cum["organ"] += org or 0
            rows.append(
                {
                    "date": str(r.get("date"))[:10],
                    "individual": ind,
                    "foreign": frg,
                    "organ": org,
                    "foreign_ratio": _f(r.get("foreign_ratio")),
                }
            )
        return {
            "ticker": ticker,
            "days_stored": len(rows),
            "cumulative": {"individual": cum["individual"], "foreign": cum["foreigner"], "organ": cum["organ"]},
            "rows": rows,
        }

    def fundamentals(self, ticker: str) -> dict:
        hist = self._repo.fundamentals_history(ticker)
        fields = ["per", "pbr", "eps", "bps", "roe", "div_yield", "market_cap", "foreign_ratio"]
        if hist.empty:
            return {"ticker": ticker, "latest": None, "prev": None, "change": None, "history": []}

        def clean(rec: dict) -> dict:
            out = {"date": str(rec.get("date"))[:10]}
            for f in fields:
                out[f] = _f(rec.get(f))
            return out

        recs = [clean(r) for r in hist.to_dict("records")]
        latest = recs[-1]
        prev = recs[-2] if len(recs) >= 2 else None
        change = None
        if prev:
            change = {
                f: round(latest[f] - prev[f], 2) if (latest[f] is not None and prev[f] is not None) else None
                for f in fields
            }
        # 부채비율(총부채/자기자본 %) — 위기 때 취약성. 펀더멘털 스냅샷엔 없으므로
        # DART 재무상태표 최신연도 부채총계/자본총계로 파생해 latest에 붙인다.
        bs = self._repo.dart_latest_bs(ticker)
        debt, equity = _f(bs.get("부채총계")), _f(bs.get("자본총계"))
        latest["debt_ratio"] = round(debt / equity * 100, 1) if (debt is not None and equity) else None
        return {"ticker": ticker, "latest": latest, "prev": prev, "change": change, "history": recs[-30:]}

    def financials(self, ticker: str) -> dict:
        df = self._repo.financials_series(ticker)
        if df.empty:
            financials.get(ticker)  # lazy scrape + persist on first view
            df = self._repo.financials_series(ticker)
        rows = [
            {
                "period": str(r.get("period")),
                "sales": _f(r.get("sales")),
                "op_profit": _f(r.get("op_profit")),
                "net_income": _f(r.get("net_income")),
                "op_margin": _f(r.get("op_margin")),
            }
            for r in df.to_dict("records")
        ]
        return {"ticker": ticker, "rows": rows}

    def financials_refresh(self, limit: int) -> dict:
        prof = self._repo.company_profiles()
        tickers = [str(t) for t in prof["ticker"].tolist()]
        if limit:
            tickers = tickers[:limit]
        n = financials.refresh_many(tickers)
        industry.invalidate()  # so 영업이익 합계가 즉시 반영
        return {"requested": len(tickers), "stored": n, "total": self._repo.financials_count()}

    def dart_financials(self, ticker: str) -> dict:
        df = self._repo.dart_financials(ticker)
        if df.empty:
            dart_financials.get(ticker)  # lazy fetch + persist
            df = self._repo.dart_financials(ticker)
        if df.empty:
            return {"ticker": ticker, "years": [], "statements": [], "available": dart.enabled()}

        years = sorted({int(y) for y in df["year"].tolist()}, reverse=True)
        by_sj: dict[str, dict] = {}
        for rec in df.to_dict("records"):
            sj = rec["sj_div"]
            acc = rec["account_nm"]
            st = by_sj.setdefault(sj, {})
            node = st.setdefault(acc, {"account_nm": acc, "ord": rec.get("ord") or 0, "by_year": {}})
            node["by_year"][str(int(rec["year"]))] = _f(rec.get("amount"))

        statements = []
        for sj in sorted(by_sj.keys(), key=lambda s: _SJ_ORDER.index(s) if s in _SJ_ORDER else 99):
            accounts = sorted(by_sj[sj].values(), key=lambda a: (a["ord"], a["account_nm"]))
            statements.append({"sj_div": sj, "label": _SJ_LABEL.get(sj, sj), "accounts": accounts})

        return {"ticker": ticker, "years": [str(y) for y in years], "statements": statements,
                "available": True}

    def dart_financials_refresh(self, limit: int, skip_existing: bool) -> dict:
        if not dart.enabled():
            raise BadRequestError("DART_API_KEY 미설정")
        prof = self._repo.company_profiles()
        tickers = [str(t) for t in prof["ticker"].tolist()]
        if limit:
            tickers = tickers[:limit]
        n = dart_financials.refresh_many(tickers, skip_existing=skip_existing)
        return {"requested": len(tickers), "stored": n, "total": self._repo.dart_financials_count()}

    def investors(self, ticker: str) -> dict:
        return {"ticker": ticker, "rows": investor.investors(ticker)}

    def holders(self, ticker: str) -> dict:
        return {"ticker": ticker, **dart.major_holders(ticker)}
