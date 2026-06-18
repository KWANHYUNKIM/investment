"""클릭한 지수/자산의 '장 마감' 상세 (how the session closed) — Excel drill-in.

크로스에셋 표에서 S&P500·나스닥·코스피·금·비트코인 등을 클릭하면, 그 자산이 오늘
장을 어떻게 끝냈는지(시/고/저/종가·등락·거래량)와 최근 시세(엑셀 표), 52주 고저,
그리고 가능한 지수는 구성종목 목록까지 펼쳐 보여준다. 시세 FinanceDataReader.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import FinanceDataReader as fdr

from app.data.crossasset import _ASSETS

# key -> 자산 메타 (crossasset 정의 재사용).
_META = {a[0]: {"label": a[1], "symbol": a[2], "group": a[3], "kind": a[4], "unit": a[5]} for a in _ASSETS}

# 구성종목(전체 보드)을 받을 수 있는 지수만. (StockListing 미지원/무가격은 제외)
_LISTING_BOARD = {"sp500": "S&P500", "nasdaq": "NASDAQ", "shanghai": "SSE"}

_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}
TTL = 300.0  # 5분
_listing_lock = threading.Lock()
_listing_cache: dict[str, tuple[float, list]] = {}
LISTING_TTL = 3600.0  # 1시간 (구성종목 목록은 거의 안 변함)


def _num(v) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def _history(df, n: int = 30) -> list[dict]:
    df = df.dropna(subset=["Close"]).copy()
    df["__chg"] = df["Close"].pct_change() * 100.0
    tail = df.tail(n)
    out: list[dict] = []
    for idx, row in tail.iterrows():
        out.append(
            {
                "date": str(idx)[:10],
                "open": _num(row.get("Open")),
                "high": _num(row.get("High")),
                "low": _num(row.get("Low")),
                "close": _num(row.get("Close")),
                "change_pct": round(c, 2) if (c := _num(row.get("__chg"))) is not None else None,
                "volume": _num(row.get("Volume")),
            }
        )
    return out


def _constituents(board: str) -> list[dict]:
    with _listing_lock:
        hit = _listing_cache.get(board)
        if hit and (time.time() - hit[0] < LISTING_TTL):
            return hit[1]
    rows: list[dict] = []
    try:
        df = fdr.StockListing(board)
        sector_col = "Sector" if "Sector" in df.columns else ("Industry" if "Industry" in df.columns else None)
        for r in df.itertuples(index=False):
            rows.append(
                {
                    "symbol": str(getattr(r, "Symbol", "") or ""),
                    "name": getattr(r, "Name", None),
                    "sector": getattr(r, sector_col) if sector_col else None,
                }
            )
    except Exception:
        rows = []
    with _listing_lock:
        _listing_cache[board] = (time.time(), rows)
    return rows


# --------------------------------------------------------------------------- #
# Constituent quotes — fill the 전종목분석-style grid lazily, batch by batch.
# --------------------------------------------------------------------------- #
_quote_lock = threading.Lock()
_quote_cache: dict[str, tuple[float, dict]] = {}
QUOTE_TTL = 600.0  # 10분


def _ret(c, n: int) -> float | None:
    if len(c) <= n:
        return None
    base = float(c.iloc[-1 - n])
    return round((float(c.iloc[-1]) / base - 1.0) * 100.0, 2) if base else None


def _quote_one(symbol: str) -> dict:
    with _quote_lock:
        hit = _quote_cache.get(symbol)
        if hit and (time.time() - hit[0] < QUOTE_TTL):
            return hit[1]
    out = {"symbol": symbol, "close": None, "change": None, "change_pct": None,
           "ret_1w": None, "ret_1m": None, "ret_3m": None, "ret_12m": None}
    try:
        df = fdr.DataReader(symbol).dropna(subset=["Close"])
        if not df.empty:
            c = df["Close"]
            last = float(c.iloc[-1])
            prev = float(c.iloc[-2]) if len(c) > 1 else last
            out.update(
                close=round(last, 2),
                change=round(last - prev, 2),
                change_pct=round((last - prev) / prev * 100.0, 2) if prev else None,
                ret_1w=_ret(c, 5),
                ret_1m=_ret(c, 22),
                ret_3m=_ret(c, 63),
                ret_12m=_ret(c, 252),
            )
    except Exception:
        pass
    with _quote_lock:
        _quote_cache[symbol] = (time.time(), out)
    return out


def constituent_quotes(symbols: list[str]) -> list[dict]:
    """Batch quote (close/change/returns) for up to ~60 constituent symbols."""
    symbols = [s for s in symbols if s][:60]
    if not symbols:
        return []
    with ThreadPoolExecutor(max_workers=10) as ex:
        return list(ex.map(_quote_one, symbols))


def asset_detail(key: str) -> dict | None:
    """장 마감 OHLC + 최근 시세 + 52주 고저 (+ 구성종목). cached ~5분."""
    meta = _META.get(key)
    if not meta:
        return None
    with _lock:
        hit = _cache.get(key)
        if hit and (time.time() - hit[0] < TTL):
            return hit[1]

    try:
        df = fdr.DataReader(meta["symbol"]).dropna(subset=["Close"])
    except Exception:
        df = None

    if df is None or df.empty:
        return None

    history = _history(df, 30)
    last = history[-1] if history else {}
    prev_close = history[-2]["close"] if len(history) > 1 else None
    change = (last.get("close") - prev_close) if (last.get("close") is not None and prev_close is not None) else None

    win = df.tail(252)
    hi52 = _num(win["High"].max()) if "High" in win.columns else None
    lo52 = _num(win["Low"].min()) if "Low" in win.columns else None

    constituents: list[dict] = []
    total_constituents = 0
    board = _LISTING_BOARD.get(key)
    if board:
        all_c = _constituents(board)
        total_constituents = len(all_c)
        constituents = all_c[:500]

    session = {
        "date": last.get("date"),
        "open": last.get("open"),
        "high": last.get("high"),
        "low": last.get("low"),
        "close": last.get("close"),
        "change": round(change, 4) if change is not None else None,
        "change_pct": last.get("change_pct"),
        "volume": last.get("volume"),
        "high_52w": hi52,
        "low_52w": lo52,
        "prev_close": prev_close,
    }
    data = {
        "key": key,
        "label": meta["label"],
        "symbol": meta["symbol"],
        "group": meta["group"],
        "unit": meta["unit"],
        "session": session,
        "history": history,
        "constituents": constituents,
        "total_constituents": total_constituents,
    }
    with _lock:
        _cache[key] = (time.time(), data)
    return data
