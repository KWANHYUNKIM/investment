"""한국 경제 흐름 — 돈이 부동산·국채(안전자산)로 가는지 (키 없는 fdr + RSS).

국토부 실거래·한국은행 ECOS 같은 정밀 수치는 API 키가 필요하므로, 키 없이 바로
읽을 수 있는 대용 신호로 국내 자금 흐름을 그린다:

  1. 부동산 자금   — 리츠/부동산 ETF 바스켓의 가격·등락·수익률(1주/1개월/3개월).
                     오르면 부동산 자산으로 자금이 유입되는 신호.
  2. 국채·채권 자금 — 국고채/종합채권 ETF. 오르면 안전자산(채권)으로 자금 이동.
  3. 뉴스 동향     — 부동산 거래/집값·대출규제·국채/통안채 발행·리츠 분위기.

시세는 FinanceDataReader(키 불필요), 뉴스는 Google News RSS(moneyflow 패턴 재사용).
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import FinanceDataReader as fdr

from app.data import macro, moneyflow

_lock = threading.Lock()
_cache: dict = {"ts": 0.0, "data": None}
TTL = 120.0  # 2분 (시세 폴링 + 스케줄러 워밍 여지)

# (key, 라벨, 종목코드, 그룹)  그룹: real_estate 부동산 / bond 국채·채권
_BASKET: tuple[tuple[str, str, str, str], ...] = (
    ("re_tiger", "TIGER 리츠부동산인프라", "329200", "real_estate"),
    ("re_macquarie", "맥쿼리인프라", "088980", "real_estate"),
    ("re_sk", "SK리츠", "395400", "real_estate"),
    ("re_lotte", "롯데리츠", "330590", "real_estate"),
    ("re_samsungfn", "삼성FN리츠", "448730", "real_estate"),
    ("re_esr", "ESR켄달스퀘어리츠", "365550", "real_estate"),
    ("re_kodex", "KODEX 한국부동산리츠인프라", "476800", "real_estate"),
    ("bd_kgb3", "KODEX 국고채3년", "114260", "bond"),
    ("bd_kgb10", "KOSEF 국고채10년", "148070", "bond"),
    ("bd_agg", "KODEX 종합채권(AA-이상)", "273130", "bond"),
)

# 부동산·국채로 가는 돈의 '이야기'를 읽는 뉴스 카테고리 (모두 국내 RSS).
_NEWS: list[tuple[str, str, str, list]] = [
    ("re_trade", "부동산 거래·집값", "🏠", [
        ("부동산 거래량 거래액 아파트 매매", "ko", "KR", "KR:ko"),
        ("집값 주택 매매 시장 자금", "ko", "KR", "KR:ko"),
    ]),
    ("mortgage", "대출·규제·유동성", "🏦", [
        ("주택담보대출 가계대출 DSR 규제", "ko", "KR", "KR:ko"),
        ("부동산 대출 규제 금리 유동성", "ko", "KR", "KR:ko"),
    ]),
    ("sovereign", "국채·통안채 발행", "📜", [
        ("국고채 발행 통안증권 국채 입찰", "ko", "KR", "KR:ko"),
        ("국채 금리 채권 시장 발행 물량", "ko", "KR", "KR:ko"),
    ]),
    ("reits", "리츠·부동산펀드", "🏢", [
        ("리츠 REITs 부동산펀드 배당 상장", "ko", "KR", "KR:ko"),
    ]),
]


def _quote(spec: tuple[str, str, str, str]) -> dict | None:
    key, label, code, group = spec
    try:
        df = fdr.DataReader(code)
        if df is None or df.empty or "Close" not in df.columns:
            return None
        s = df["Close"].dropna()
        if len(s) < 2:
            return None
        c = s.to_numpy(dtype="float64")
        last, prev = float(c[-1]), float(c[-2])

        def ret(k: int) -> float | None:
            return round((last / c[-1 - k] - 1.0) * 100.0, 2) if (len(c) > k and c[-1 - k] > 0) else None

        win = c[-252:]
        hi = float(win.max())
        return {
            "key": key,
            "label": label,
            "code": code,
            "group": group,
            "close": round(last, 2),
            "change_pct": round((last - prev) / prev * 100.0, 2) if prev else None,
            "ret_1w": ret(5),
            "ret_1m": ret(21),
            "ret_3m": ret(63),
            "pct_from_high": round((last / hi - 1.0) * 100.0, 2) if hi > 0 else None,
            "date": str(s.index[-1])[:10],
        }
    except Exception:
        return None


def _basket() -> list[dict]:
    with ThreadPoolExecutor(max_workers=8) as ex:
        return [q for q in ex.map(_quote, _BASKET) if q]


def _news_cat(cat) -> dict:
    key, label, icon, queries = cat
    pool = moneyflow._pool(queries)
    pos = sum(1 for a in pool if macro._lean(a["title"]) == "긍정")
    neg = sum(1 for a in pool if macro._lean(a["title"]) == "부정")
    lean = "긍정" if pos > neg else "부정" if neg > pos else "중립"
    return {
        "key": key, "label": label, "icon": icon,
        "lean": lean, "pos": pos, "neg": neg, "count": len(pool),
        "headlines": moneyflow._headlines(pool, 5), "digest": moneyflow._digest(pool, 3),
    }


def _avg(items: list[dict], k: str) -> float | None:
    vals = [i[k] for i in items if i.get(k) is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def _verdict(re_items: list[dict], bd_items: list[dict]) -> dict:
    """리츠/채권 ETF 1개월 수익률 평균으로 자금 유입/이탈 방향 판정."""
    re_1m, bd_1m = _avg(re_items, "ret_1m"), _avg(bd_items, "ret_1m")

    def dir_of(v: float | None, thr: float) -> str:
        if v is None:
            return "중립"
        return "유입" if v > thr else "이탈" if v < -thr else "중립"

    re_dir, bd_dir = dir_of(re_1m, 0.5), dir_of(bd_1m, 0.3)
    bits = []
    if re_dir != "중립":
        bits.append(f"부동산(리츠) 자금 {re_dir}(최근 1개월 {re_1m:+.1f}%)")
    else:
        bits.append("부동산(리츠) 자금 보합")
    if bd_dir != "중립":
        bits.append(f"국채·채권 자금 {bd_dir}({bd_1m:+.1f}%)")
    else:
        bits.append("국채·채권 자금 보합")
    narrative = " · ".join(bits) + "."
    return {
        "real_estate_dir": re_dir,
        "bond_dir": bd_dir,
        "real_estate_1m": re_1m,
        "bond_1m": bd_1m,
        "narrative": narrative,
    }


def snapshot(force: bool = False) -> dict:
    with _lock:
        if not force and _cache["data"] and (time.time() - _cache["ts"] < TTL):
            return _cache["data"]

    basket = _basket()
    re_items = [b for b in basket if b["group"] == "real_estate"]
    bd_items = [b for b in basket if b["group"] == "bond"]

    with ThreadPoolExecutor(max_workers=4) as ex:
        cats = list(ex.map(_news_cat, _NEWS))

    dates = [b["date"] for b in basket if b.get("date")]
    data = {
        "as_of": max(dates) if dates else None,
        "verdict": _verdict(re_items, bd_items),
        "real_estate": re_items,
        "bonds": bd_items,
        "news": cats,
        "note": "키 없는 대용 신호(ETF 시세·뉴스). 부동산 실거래 거래액·M2·국고채금리·"
                "통안증권 발행 등 정확한 수치는 data.go.kr·한국은행 ECOS 무료 키 연동 시 추가됩니다.",
    }
    with _lock:
        _cache["ts"] = time.time()
        _cache["data"] = data
    return data
