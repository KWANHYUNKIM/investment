"""DART 사업보고서 자동 파싱으로 원가모델을 대량 생성해 costmodels_auto.json 에 적재.

사용:
    python -m scripts.build_costmodels --limit 40
    python -m scripts.build_costmodels --tickers 010140,000880,001040

store(DuckDB) 없이 DART corpCode.xml 에서 종목명을 얻어 실행하므로, 앱 서버가
DB를 물고 있어도 병렬로 돌릴 수 있다. 수작업 PRODUCTS에 있는 종목은 건너뛴다.
"""
from __future__ import annotations

import argparse
import io
import time
import zipfile
from xml.etree import ElementTree as ET

import requests

from app.core.config import get_settings
from app.data.fundamentals import auto_costmodel as ac
from app.data.fundamentals import unit_economics as ue


def listed_names() -> dict[str, str]:
    """{ticker: corp_name} — 상장(stock_code 보유) 기업만."""
    key = get_settings().dart_api_key
    r = requests.get("https://opendart.fss.or.kr/api/corpCode.xml",
                     params={"crtfc_key": key}, timeout=60)
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    root = ET.fromstring(zf.read(zf.namelist()[0]))
    out = {}
    for el in root.iter("list"):
        stock = (el.findtext("stock_code") or "").strip()
        name = (el.findtext("corp_name") or "").strip()
        if stock and name:
            out[stock] = name
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--tickers", type=str, default="")
    args = ap.parse_args()

    curated = {p["ticker"] for p in ue.PRODUCTS.values()}
    names = listed_names()
    print(f"상장사 {len(names)}개 · 수작업 커버 {len(curated)}개")

    if args.tickers:
        want = [t.strip() for t in args.tickers.split(",") if t.strip()]
        targets = {t: names.get(t, t) for t in want}
    else:
        targets = {t: n for t, n in names.items() if t not in curated}
        targets = dict(list(targets.items())[: args.limit])

    print(f"자동 생성 대상 {len(targets)}개 시작…")
    ok = 0
    mapped = 0
    for i, (tk, nm) in enumerate(targets.items(), 1):
        t0 = time.time()
        try:
            m = ac.build(tk, nm)
        except Exception as e:
            print(f"  [{i}/{len(targets)}] {tk} {nm} ERR {type(e).__name__}")
            continue
        if not m:
            print(f"  [{i}/{len(targets)}] {tk} {nm} -> None")
            continue
        # 병합 저장(개별)
        existing = ac.load_auto()
        existing[f"{tk}:auto"] = m
        ac._auto_path().write_text(
            __import__("json").dumps(existing, ensure_ascii=False, indent=1), encoding="utf-8")
        ok += 1
        has = sum(1 for x in m["material_mix"] if x["commodity"])
        mapped += 1 if has else 0
        top = ", ".join(f"{x['item'][:10]}:{x['commodity']}" for x in m["material_mix"] if x["commodity"])[:60]
        print(f"  [{i}/{len(targets)}] {tk} {nm} cogs={m['default_ratios']['cogs']} "
              f"매핑{has}종 [{top}] ({time.time()-t0:.1f}s)")

    print(f"\n완료: {ok}개 생성, 그중 원재료 매핑 성공 {mapped}개 → {ac._auto_path()}")


if __name__ == "__main__":
    main()
