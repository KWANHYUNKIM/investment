"""개장 예측 기록·채점 아카이브 (prediction log + next-session scoring).

매 세션 개장 예측을 하나의 JSON으로 저장하고(``data/premarket/``), 다음 거래일의
실제 개장 갭(코스피/코스닥 시가 - 전일 종가)이 나오면 그 예측을 채점한다:
예측 방향(강세/중립/약세)이 실제 개장 방향과 맞았는지(적중/실패)와 그 이유를 기록.
스케줄러가 이 두 가지(기록·채점)를 계속 반복 호출해 적중률이 누적된다.

- 예측 파일 키 = ``based_on`` = 예측 시점의 최신 코스피 종가 날짜(D0).
  → 그 예측은 "D0 다음 거래일 개장"을 맞히는 것. D0당 예측 1개, 실제 1개로 1:1.
- 채점: KS11에 D0보다 뒤 날짜(D1) 바가 생기면 실제 개장 갭 = (Open[D1]-Close[D0])/Close[D0].
"""
from __future__ import annotations

import json
import os
import threading
import time

import FinanceDataReader as fdr

from app.core.config import get_settings
from app.data.market import premarket

_lock = threading.Lock()

# 중립 판정 임계치: 개장 갭 절대값이 이보다 작으면 '중립(보합)'으로 본다.
_FLAT = 0.15


def _path(based_on: str) -> str:
    return str(get_settings().premarket_dir / f"{based_on}.json")


def exists(based_on: str) -> bool:
    return os.path.exists(_path(based_on))


def _save(rec: dict) -> str:
    path = _path(rec["based_on"])
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)
    return path


def load(based_on: str) -> dict | None:
    path = _path(based_on)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def list_dates() -> list[str]:
    d = get_settings().premarket_dir
    if not d.exists():
        return []
    return sorted((p.stem for p in d.glob("*.json")), reverse=True)


# --------------------------------------------------------------------------- #
# KOSPI/KOSDAQ 일봉 (시가/종가) — 실제 개장 갭 채점용
# --------------------------------------------------------------------------- #
def _daily(sym: str):
    df = fdr.DataReader(sym)
    if df is None or df.empty or "Close" not in df.columns:
        return None
    return df.dropna(subset=["Close"]).tail(90)


def _bars() -> dict:
    """{'kospi': [(date, open, close)...], 'kosdaq': [...]} 최근치."""
    out: dict = {}
    for key, sym in (("kospi", "KS11"), ("kosdaq", "KQ11")):
        df = _daily(sym)
        if df is None:
            continue
        rows = []
        for d, row in df.iterrows():
            o = row.get("Open")
            c = row.get("Close")
            try:
                rows.append((str(d)[:10], float(o) if o == o else None, float(c)))
            except (TypeError, ValueError):
                continue
        out[key] = rows
    return out


def _open_gap(rows: list, based_on: str):
    """based_on(D0) 다음 거래일(D1)의 개장 갭(%) + D1 날짜. 아직 없으면 None."""
    idx = next((i for i, r in enumerate(rows) if r[0] == based_on), None)
    if idx is None or idx + 1 >= len(rows):
        return None, None
    d1, o1, _c1 = rows[idx + 1]
    _d0, _o0, c0 = rows[idx]
    if o1 is None or not c0:
        return None, d1
    return round((o1 - c0) / c0 * 100.0, 2), d1


def _dir(pct: float | None) -> str:
    if pct is None:
        return "중립"
    return "강세" if pct > _FLAT else "약세" if pct < -_FLAT else "중립"


# --------------------------------------------------------------------------- #
# 기록 (record) — 예측 저장
# --------------------------------------------------------------------------- #
def record(force: bool = False) -> dict:
    """오늘 예측을 저장. based_on = 최신 코스피 종가 날짜. 이미 있으면 skip."""
    with _lock:
        rows = _bars().get("kospi") or []
        if not rows:
            return {"status": "no-index"}
        based_on = rows[-1][0]
        if exists(based_on) and not force:
            return {"status": "exists", "based_on": based_on}

        fc = premarket.forecast()
        rec = {
            "based_on": based_on,               # 이 종가 다음 개장을 예측
            "made_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "prediction": {
                "bias": fc["bias"],
                "weighted_pct": fc["weighted_pct"],
                "gauge": fc["gauge"],
                "expected_gap": fc["expected_gap"],
                "adr_avg": fc.get("adr_avg"),
                "drivers": fc.get("drivers", []),
                "ai_one_liner": (fc.get("ai") or {}).get("one_liner") if fc.get("ai") else None,
            },
            "signals": [
                {"label": s["label"], "impact_pct": s["impact_pct"]} for s in fc.get("signals", [])
            ],
            "graded": False,
            "actual": None,
        }
        _save(rec)
        return {"status": "saved", "based_on": based_on, "bias": fc["bias"]}


# --------------------------------------------------------------------------- #
# 채점 (grade) — 실제 개장과 대조 + 이유
# --------------------------------------------------------------------------- #
def _reason(pred: dict, kospi_gap: float, hit: bool) -> str:
    p_bias = pred["bias"]
    a_dir = _dir(kospi_gap)
    if hit:
        return (
            f"예측 {p_bias} → 실제 코스피 개장 {kospi_gap:+.2f}%({a_dir})로 방향 일치. "
            f"간밤 신호(가중 {pred['weighted_pct']:+.2f}%)가 개장에 그대로 반영됨."
        )
    # 실패 원인 추정
    if p_bias != "중립" and a_dir == "중립":
        cause = "간밤 신호는 뚜렷했지만 개장은 보합권 — 국내 수급/관망이 글로벌 신호를 상쇄"
    elif (p_bias == "강세" and a_dir == "약세") or (p_bias == "약세" and a_dir == "강세"):
        cause = "간밤 글로벌 방향과 반대로 개장 — 장중/전일 국내 이슈나 환율·수급이 우세"
    else:
        cause = "예측은 방향을 잡았으나 실제 개장 강도가 예상과 달라 판정 기준을 벗어남"
    return f"예측 {p_bias} → 실제 코스피 {kospi_gap:+.2f}%({a_dir})로 빗나감. {cause}."


def grade_all() -> dict:
    """미채점 예측 중 다음 세션 바가 나온 것들을 채점한다."""
    with _lock:
        bars = _bars()
        kospi = bars.get("kospi") or []
        kosdaq = bars.get("kosdaq") or []
        if not kospi:
            return {"status": "no-index", "graded": 0}

        graded = 0
        for based_on in list_dates():
            rec = load(based_on)
            if not rec or rec.get("graded"):
                continue
            kospi_gap, d1 = _open_gap(kospi, based_on)
            if kospi_gap is None:
                continue  # 다음 세션 개장 아직 없음
            kosdaq_gap, _ = _open_gap(kosdaq, based_on)

            p_bias = rec["prediction"]["bias"]
            a_dir = _dir(kospi_gap)
            hit = (p_bias == a_dir)
            rec["actual"] = {
                "open_date": d1,
                "kospi_gap": kospi_gap,
                "kosdaq_gap": kosdaq_gap,
                "direction": a_dir,
            }
            rec["hit"] = hit
            rec["reason"] = _reason(rec["prediction"], kospi_gap, hit)
            rec["graded"] = True
            rec["graded_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _save(rec)
            graded += 1
        return {"status": "ok", "graded": graded}


# --------------------------------------------------------------------------- #
# 조회 (history + accuracy)
# --------------------------------------------------------------------------- #
def accuracy() -> dict:
    dates = list_dates()
    total = 0
    hits = 0
    recent: list[bool] = []
    for based_on in dates:
        rec = load(based_on)
        if not rec or not rec.get("graded"):
            continue
        total += 1
        if rec.get("hit"):
            hits += 1
        if len(recent) < 10:
            recent.append(bool(rec.get("hit")))
    return {
        "total": total,
        "hits": hits,
        "rate": round(hits / total * 100.0, 1) if total else None,
        "recent10_hits": sum(1 for r in recent if r),
        "recent10_total": len(recent),
        "pending": len(dates) - total,
    }


def history(limit: int = 60) -> dict:
    records = []
    for based_on in list_dates()[:limit]:
        rec = load(based_on)
        if rec:
            records.append(rec)
    return {"accuracy": accuracy(), "records": records}
