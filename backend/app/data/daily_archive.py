"""Persistent daily report archive (데일리 리포트 — 하루하루 저장).

The market report used to be computed on demand and kept only in a 10-minute
cache, so each day's report vanished. This module builds the *full* daily report
and writes it to one JSON file per trading day under ``data/daily_reports/`` so
the history accumulates and any past day can be read back.

Each day's snapshot captures, for every stock:
  - the price move (왜 올랐는지 / 떨어졌는지 — direction),
  - who was buying / selling and an estimated *why* per investor type
    (외국인 / 개인 / 기관) — see ``insight``,
and, on top of the per-stock news story, a market-wide **macro** layer (금리 ·
환율 · 유가 · 미국 증시 …) for the "전체 영향을 받는 뉴스" — see ``macro``.

To stay within news rate limits the deep news layer runs only on the day's most
significant names (most-traded ∪ top movers, ``settings.report_deep_n``); every
other stock is still archived with its price + investor-flow + signal-based why.
"""
from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core.config import get_settings
from app.data import crossasset, foreign_view, insight, macro, market_report, news, rates, store

_lock = threading.Lock()


# --------------------------------------------------------------------------- #
# Per-stock builders
# --------------------------------------------------------------------------- #
def _num(v) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def _slim(r: dict) -> dict:
    return {
        "ticker": r["ticker"],
        "name": r.get("name"),
        "sector": r.get("sector"),
        "close": r.get("close"),
        "change": r.get("change"),
        "change_pct": r.get("change_pct"),
        "volume": r.get("volume"),
    }


def _direction(chg) -> str:
    if chg is None:
        return "보합"
    return "상승" if chg > 0 else "하락" if chg < 0 else "보합"


def _deep_stock(row: dict) -> dict | None:
    """Full per-stock card: live investor flow + news + why (themes)."""
    ins = market_report._stock_insight(row)  # investors + news + foreign_ratio
    if ins is None:
        return None
    titles = [a.get("title", "") for a in ins.get("news", [])]
    chg = row.get("change_pct")
    up = (chg or 0) >= 0
    themes = insight._themes(titles, insight._POS_THEMES if up else insight._NEG_THEMES)
    ins["why"] = {"direction": _direction(chg), "themes": themes}
    ins["depth"] = "deep"
    return ins


def _bulk_stock(row: dict, flow: dict | None) -> dict:
    """Lighter per-stock card for the long tail: price + DB flow + signal why.

    No live news fetch — investor reasons come purely from the structural signals
    (valuation, momentum, foreign-ratio move) so it stays cheap at ~2,800 stocks.
    """
    chg = row.get("change_pct")
    # _num() may return None for NaN even when the raw value isn't None, so guard
    # on the cleaned numbers (not the raw flow values) to avoid None - float.
    fr = _num(flow.get("foreign_ratio")) if flow else None
    fr_prev = _num(flow.get("foreign_ratio_prev")) if flow else None
    fr_delta = (fr - fr_prev) if (fr is not None and fr_prev is not None) else None
    sig = {
        "individual": _num(flow.get("individual")) if flow else None,
        "foreign": _num(flow.get("foreigner")) if flow else None,
        "organ": _num(flow.get("organ")) if flow else None,
        "foreign_ratio": fr,
        "foreign_ratio_delta": fr_delta,
        "change_pct": chg,
        "ret_1m": row.get("ret_1m"),
        "pct_from_high": row.get("pct_from_high"),
        "per": row.get("per"),
        "pbr": row.get("pbr"),
        "roe": row.get("roe"),
        "div_yield": row.get("div_yield"),
    }
    investors = insight.build(sig, []) if flow else []
    return {
        "ticker": row["ticker"],
        "name": row.get("name"),
        "sector": row.get("sector"),
        "close": row.get("close"),
        "change": row.get("change"),
        "change_pct": chg,
        "volume": row.get("volume"),
        "foreign_ratio": sig["foreign_ratio"],
        "foreign_ratio_delta": round(sig["foreign_ratio_delta"], 2) if sig["foreign_ratio_delta"] is not None else None,
        "investors": investors,
        "news": [],
        "news_global": [],
        "why": {"direction": _direction(chg), "themes": []},
        "depth": "bulk",
    }


# --------------------------------------------------------------------------- #
# Day builder
# --------------------------------------------------------------------------- #
def build(date_override: str | None = None) -> dict:
    """Assemble the full daily report for the latest data day."""
    settings = get_settings()
    deep_n = settings.report_deep_n

    rows = store.screen_table_prices()
    valid = [r for r in rows if r.get("change_pct") is not None]
    date = date_override or (rows[0]["date"] if rows else store.max_price_date())

    gainers = sorted(valid, key=lambda r: r["change_pct"], reverse=True)
    losers = sorted(valid, key=lambda r: r["change_pct"])
    most_traded = sorted([r for r in valid if r.get("volume")], key=lambda r: r["volume"], reverse=True)

    # Deep targets: most-traded ∪ top gainers ∪ top losers, deduped, capped.
    # Interleave so the deep set spans heavy-volume large caps AND the day's
    # sharp movers (다양한 회사), not just one slice.
    deep_targets: list[dict] = []
    seen: set[str] = set()
    for r in most_traded + gainers[:40] + losers[:40]:
        tk = r["ticker"]
        if tk not in seen:
            seen.add(tk)
            deep_targets.append(r)
        if len(deep_targets) >= deep_n:
            break

    deep_by_ticker: dict[str, dict] = {}
    if deep_targets:
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = {ex.submit(_deep_stock, r): r for r in deep_targets}
            for fut in as_completed(futs):
                try:
                    res = fut.result()
                except Exception:
                    res = None
                if res:
                    deep_by_ticker[res["ticker"]] = res

    # Bulk layer for every remaining stock, using accumulated DB investor flow.
    flow_map = store.latest_investor_flow_map()
    stocks: list[dict] = []
    for r in valid:
        tk = r["ticker"]
        stocks.append(deep_by_ticker[tk] if tk in deep_by_ticker else _bulk_stock(r, flow_map.get(tk)))
    # Most significant first (deep names, then by absolute move).
    stocks.sort(key=lambda s: (s.get("depth") != "deep", -abs(s.get("change_pct") or 0)))

    # 시장 전체 투자자별 매매 동향(일단위) — 누가 매입/매도했나.
    try:
        investor_trend = store.market_investor_daily(as_of=date, days=10)
    except Exception:
        investor_trend = []

    macro_data = macro.market_macro()
    try:
        rates_data = rates.rate_calendar()
    except Exception:
        rates_data = None
    try:
        fview_data = foreign_view.foreign_view()
    except Exception:
        fview_data = None
    try:
        cross_data = crossasset.cross_asset()
    except Exception:
        cross_data = None

    up = sum(1 for r in valid if r["change_pct"] > 0)
    down = sum(1 for r in valid if r["change_pct"] < 0)
    flat = len(valid) - up - down

    # Market-level summary, incl. who was net buying among the deep names.
    parts: list[str] = []
    if date:
        parts.append(f"{date} 기준, 상승 {up:,}종목 · 하락 {down:,}종목 · 보합 {flat:,}종목.")
    if gainers and losers:
        parts.append(
            f"최고 상승 {gainers[0]['name']}({gainers[0]['change_pct']:+.2f}%), "
            f"최대 하락 {losers[0]['name']}({losers[0]['change_pct']:+.2f}%)."
        )

    def _net(key: str) -> tuple[int, int]:
        buy = sell = 0
        for s in deep_by_ticker.values():
            for iv in s.get("investors", []):
                if iv.get("key") == key and iv.get("qty"):
                    if iv["qty"] > 0:
                        buy += 1
                    elif iv["qty"] < 0:
                        sell += 1
        return buy, sell

    if deep_by_ticker:
        fb, fs = _net("foreign")
        ib, is_ = _net("individual")
        ob, os_ = _net("organ")

        def _word(b, s):
            return "순매수 우위" if b > s else "순매도 우위" if s > b else "혼조"

        parts.append(
            f"거래·등락 상위 {len(deep_by_ticker)}종목 기준 "
            f"외국인 {_word(fb, fs)}, 기관 {_word(ob, os_)}, 개인 {_word(ib, is_)}였습니다."
        )
    # 시장 전체 투자자별 순매수 금액(당일) 한 줄 요약 — 누가 주도했나.
    if investor_trend:
        td = investor_trend[0]

        def _amt(v: float | None) -> str:
            if v is None:
                return "—"
            return f"+{v:,.0f}억" if v >= 0 else f"{v:,.0f}억"

        parts.append(
            f"투자자별 순매수(금액): 외국인 {_amt(td.get('foreign'))} · "
            f"기관 {_amt(td.get('organ'))} · 개인 {_amt(td.get('individual'))}."
        )
    if macro_data.get("summary"):
        parts.append(macro_data["summary"])
    if rates_data and rates_data.get("summary"):
        parts.append(rates_data["summary"])
    if fview_data and fview_data.get("summary"):
        parts.append(fview_data["summary"])
    if cross_data and cross_data.get("flow", {}).get("summary"):
        parts.append(cross_data["flow"]["summary"])

    generated_at = time.strftime("%Y-%m-%d %H:%M:%S")
    # 데이터별 '최근 언제 들어왔나'(기준/갱신 시점) — 화면에 모두 표시.
    data_freshness = {
        "report_generated": generated_at,          # 이 리포트를 조립(뉴스·매크로 수집)한 시각
        "price_date": date,                        # 시세(가격) 최신 거래일
        "investor_date": investor_trend[0]["date"] if investor_trend else None,  # 투자자 수급 최근 확정 거래일
        "cross_asset_as_of": (cross_data or {}).get("as_of"),  # 크로스에셋 시세 기준 시각
        "macro_pool": macro_data.get("pool_size"),  # 매크로/뉴스 취합 건수(생성 시각 기준)
    }

    return {
        "date": date,
        "generated_at": generated_at,
        "scope": {"total": len(valid), "deep": len(deep_by_ticker), "deep_n": deep_n},
        "market": {
            "breadth": {"up": up, "down": down, "flat": flat, "total": len(valid)},
            "summary": " ".join(p for p in parts if p),
            "data_freshness": data_freshness,
            "investor_trend": investor_trend,
            "macro": macro_data,
            "rates": rates_data,
            "foreign_view": fview_data,
            "cross_asset": cross_data,
        },
        "movers": {
            "gainers": [_slim(r) for r in gainers[:12]],
            "losers": [_slim(r) for r in losers[:12]],
            "most_traded": [_slim(r) for r in most_traded[:12]],
        },
        "stocks": stocks,
    }


# --------------------------------------------------------------------------- #
# JSON persistence (one file per trading day)
# --------------------------------------------------------------------------- #
def _path(date: str) -> str:
    return str(get_settings().reports_dir / f"{date}.json")


def exists(date: str) -> bool:
    return os.path.exists(_path(date))


def save(data: dict) -> str:
    """Write the day's report atomically (temp file → replace)."""
    date = data.get("date")
    if not date:
        raise ValueError("daily report has no date")
    path = _path(date)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)
    return path


def load(date: str) -> dict | None:
    path = _path(date)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def list_dates() -> list[str]:
    """Archived report dates, newest first."""
    d = get_settings().reports_dir
    if not d.exists():
        return []
    dates = [p.stem for p in d.glob("*.json")]
    dates.sort(reverse=True)
    return dates


def snapshot(force: bool = False) -> dict:
    """Build today's report and persist it (skip if already saved unless forced).

    Serialised so the scheduler and a manual trigger can't double-build.
    """
    with _lock:
        date = store.max_price_date()
        if date and exists(date) and not force:
            return {"status": "exists", "date": date, "path": _path(date)}
        data = build(date_override=date)
        path = save(data)
        return {
            "status": "saved",
            "date": data["date"],
            "path": path,
            "total": data["scope"]["total"],
            "deep": data["scope"]["deep"],
        }
