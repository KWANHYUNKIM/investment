"""관심종목 + 보유(포트폴리오) 영속화 및 진단.

로컬 단일 사용자용이라 파일 하나(``data/watchlist.json``)에 관심종목 티커 목록과 보유
종목(수량·평단)을 저장한다. 조회 시 현재가·매매신호·목표주가 상승여력을 얹어 준다.
보유는 손익·비중·집중도까지 진단한다.
"""
from __future__ import annotations

import threading

from app.core.jsonstore import read_json, user_path, write_json
from app.data.infra import store
from app.data.market import signals as signals_mod
from app.data.market import target_price as tp_mod

_lock = threading.Lock()



def _path(user: str) -> str:
    return user_path("watchlist", user)


def _load(user: str) -> dict:
    # 저장소만 갈아 끼운다 — 아래의 시세 붙이기·진단 로직은 어느 쪽인지 모른다.
    from app.db import stores
    if stores.enabled():
        return stores.watchlist_load(user)
    return read_json(_path(user), {"watch": [], "holdings": []})


def _save(user: str, d: dict) -> None:
    from app.db import stores
    if stores.enabled():
        stores.watchlist_save(user, d)
        return
    write_json(_path(user), d)


# --- 시세/메타 조회 (보드 1회 쿼리 캐시) -------------------------------------
def _quote_map() -> dict:
    q = store.latest_quotes(market="KR")
    out: dict = {}
    if q is None or q.empty:
        return out
    secmap = store.sector_map()  # 실제 업종(WICS) — securities.sector는 시장명이라 부적합
    for r in q.to_dict("records"):
        prev = r.get("prev_close")
        close = r.get("close")
        chg = None
        try:
            if prev:
                chg = round((float(close) - float(prev)) / float(prev) * 100, 2)
        except (TypeError, ValueError):
            chg = None
        out[r["ticker"]] = {"name": r.get("name"), "sector": secmap.get(r["ticker"]) or r.get("sector"),
                            "close": float(close) if close is not None else None, "chg_pct": chg}
    return out


def _enrich(ticker: str, qm: dict) -> dict:
    meta = qm.get(ticker, {})
    row = {"ticker": ticker, "name": meta.get("name"), "sector": meta.get("sector"),
           "close": meta.get("close"), "chg_pct": meta.get("chg_pct"),
           "verdict": None, "score": None, "target": None, "upside_pct": None}
    try:
        s = signals_mod.signals(ticker)
        row["verdict"] = s.get("verdict")
        row["score"] = s.get("score")
    except Exception:
        pass
    try:
        t = tp_mod.target_price(ticker)
        row["target"] = t.get("base")
        row["upside_pct"] = t.get("base_upside_pct")
    except Exception:
        pass
    return row


# --- 관심종목 --------------------------------------------------------------
def get_watch(user: str) -> dict:
    with _lock:
        d = _load(user)
    qm = _quote_map()
    rows = [_enrich(t, qm) for t in d["watch"]]
    return {"tickers": d["watch"], "rows": rows}


def add_watch(user: str, ticker: str) -> dict:
    with _lock:
        d = _load(user)
        if ticker not in d["watch"]:
            d["watch"].append(ticker)
            _save(user, d)
    return get_watch(user)


def remove_watch(user: str, ticker: str) -> dict:
    with _lock:
        d = _load(user)
        d["watch"] = [t for t in d["watch"] if t != ticker]
        _save(user, d)
    return get_watch(user)


# --- 보유(포트폴리오) -------------------------------------------------------
def set_holdings(user: str, holdings: list[dict]) -> dict:
    """holdings = [{ticker, qty, avg}] 전체 교체."""
    clean = []
    for h in holdings or []:
        t = str(h.get("ticker", "")).strip()
        if not t:
            continue
        try:
            qty = float(h.get("qty") or 0)
            avg = float(h.get("avg") or 0)
        except (TypeError, ValueError):
            continue
        clean.append({"ticker": t, "qty": qty, "avg": avg})
    with _lock:
        d = _load(user)
        d["holdings"] = clean
        _save(user, d)
    return diagnose(user)


def diagnose(user: str) -> dict:
    with _lock:
        d = _load(user)
    holdings = d["holdings"]
    qm = _quote_map()

    rows = []
    total_val = 0.0
    total_cost = 0.0
    sector_val: dict[str, float] = {}
    for h in holdings:
        t = h["ticker"]
        enr = _enrich(t, qm)
        close = enr["close"]
        qty, avg = h["qty"], h["avg"]
        val = (close or 0) * qty
        cost = avg * qty
        pnl = val - cost
        pnl_pct = round((close - avg) / avg * 100, 2) if (close and avg) else None
        total_val += val
        total_cost += cost
        sec = enr.get("sector") or "기타"
        sector_val[sec] = sector_val.get(sec, 0.0) + val
        rows.append({**enr, "qty": qty, "avg": avg, "value": round(val),
                     "cost": round(cost), "pnl": round(pnl), "pnl_pct": pnl_pct})

    # 비중·집중도
    for r in rows:
        r["weight"] = round(r["value"] / total_val * 100, 1) if total_val else None
    rows.sort(key=lambda r: -(r["value"] or 0))
    max_weight = max((r["weight"] or 0 for r in rows), default=0)
    sectors = sorted(
        ({"sector": k, "weight": round(v / total_val * 100, 1)} for k, v in sector_val.items()),
        key=lambda x: -x["weight"],
    ) if total_val else []

    total_pnl = total_val - total_cost
    # 진단 코멘트
    diag: list[str] = []
    if not rows:
        diag.append("보유 종목을 입력하면 손익·집중도·신호를 진단합니다.")
    else:
        if max_weight >= 40:
            top = rows[0]
            diag.append(f"'{top['name'] or top['ticker']}' 비중이 {max_weight}%로 과도하게 집중돼 있습니다(분산 권장).")
        if sectors and sectors[0]["weight"] >= 50:
            diag.append(f"'{sectors[0]['sector']}' 업종에 {sectors[0]['weight']}% 편중.")
        sells = [r for r in rows if r.get("verdict") == "매도"]
        if sells:
            diag.append("기술적 '매도' 신호 종목: " + ", ".join((r["name"] or r["ticker"]) for r in sells) + ".")
        losers = [r for r in rows if (r.get("pnl_pct") or 0) <= -15]
        if losers:
            diag.append("−15% 이상 손실 종목 점검 필요: " + ", ".join((r["name"] or r["ticker"]) for r in losers) + ".")
        if not diag:
            diag.append("특이 리스크 신호는 없습니다. 목표가·신호를 주기적으로 점검하세요.")

    return {
        "holdings": rows,
        "summary": {
            "total_value": round(total_val),
            "total_cost": round(total_cost),
            "total_pnl": round(total_pnl),
            "total_pnl_pct": round(total_pnl / total_cost * 100, 2) if total_cost else None,
            "max_weight": max_weight,
            "sectors": sectors,
            "count": len(rows),
        },
        "diagnosis": diag,
    }
