"""전 종목 재무제표 감사 리포트 — 야간 배치 결과에서 '이상 종목'을 뽑는다.

``data/company_costmodels.json`` (원가모델 야간 배치 산출)에는 종목마다
``audit_score``(재무제표 3종 정합·이익의 질 0~100), ``audit_opinion``(감사의견),
인건비·재료비 실측이 들어 있다. 이 스크립트는 그걸 읽어 **한 장짜리 리포트**로 만든다.
DuckDB 를 건드리지 않으므로 **서버가 떠 있어도 그대로 돌아간다**.

**업종 보정이 핵심이다.** 절대점수만 줄세우면 조선·건설·방산이 영구히 상위를 차지한다.
수주산업은 계약자산·미청구공사 때문에 매출채권과 발생액이 구조적으로 크기 때문이다.
그래서 같은 업종 안에서의 상대 위치(백분위)를 함께 낸다 — **동종 대비 유독 나쁜 회사**가
진짜 봐야 할 종목이다.

사용:
    python -m scripts.audit_report                 # 요약 + 하위 20
    python -m scripts.audit_report --top 40 --json data/audit_report.json
    python -m scripts.audit_report --sector 화학   # 특정 업종만
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
from collections import Counter, defaultdict

from app.core.config import get_settings


def load_batch() -> dict:
    p = pathlib.Path(get_settings().data_dir) / "company_costmodels.json"
    if not p.exists():
        print(f"배치 파일 없음: {p}\n  → ops\\win\\batch.ps1 costmodel 로 먼저 배치를 돌리세요.",
              file=sys.stderr)
        raise SystemExit(2)
    d = json.loads(p.read_text(encoding="utf-8"))
    return d


def main() -> int:
    ap = argparse.ArgumentParser(description="전 종목 재무제표 감사 리포트")
    ap.add_argument("--top", type=int, default=20, help="하위 N개 출력")
    ap.add_argument("--sector", default="", help="업종 필터")
    ap.add_argument("--json", default="", help="결과 JSON 저장 경로")
    ap.add_argument("--min-peers", type=int, default=4, help="업종 보정 최소 표본")
    args = ap.parse_args()

    d = load_batch()
    rows: dict = d.get("companies") or d.get("rows") or {}
    if args.sector:
        rows = {k: v for k, v in rows.items() if args.sector in (v.get("sector") or "")}

    print(f"배치 {d.get('built_at')} · {len(rows)}개사 · 오류 {d.get('n_errors')}개 "
          f"· {d.get('elapsed_sec')}s")

    # --- 커버리지 --------------------------------------------------------
    cov = Counter()
    for r in rows.values():
        c = r.get("coverage") or {}
        for k in ("financials_3y", "report_notes", "business", "labor", "statement_audit"):
            cov[(k, c.get(k))] += 1
    print("\n[데이터 커버리지]")
    label = {"financials_3y": "3개년 재무제표", "report_notes": "주석(성격별·감사보고서)",
             "business": "단가·생산실적(B3·B4)", "labor": "인건비(직원현황)",
             "statement_audit": "재무제표 3종 감사"}
    for k, ko in label.items():
        ok = sum(v for (kk, st), v in cov.items()
                 if kk == k and st in ("dart", "parsed", "ok"))
        print(f"   {ko:<24} {ok:>4} / {len(rows)}  ({ok/max(1,len(rows))*100:.0f}%)")

    ops = Counter(r.get("audit_opinion") for r in rows.values())
    print(f"\n[감사의견] " + ", ".join(f"{k or '미확보'} {v}" for k, v in ops.most_common()))
    bad_op = [(tk, r) for tk, r in rows.items()
              if r.get("audit_opinion") and r["audit_opinion"] != "적정"]
    if bad_op:
        print("   ⚠ 적정의견이 아닌 회사:")
        for tk, r in bad_op:
            print(f"      {tk} {r.get('company')} — {r['audit_opinion']}")

    # --- 업종 보정 --------------------------------------------------------
    scored = [(tk, r) for tk, r in rows.items() if r.get("audit_score") is not None]
    by_sector: dict[str, list] = defaultdict(list)
    for tk, r in scored:
        by_sector[r.get("sector") or "기타"].append(r["audit_score"])
    sector_med = {s: sorted(v)[len(v) // 2] for s, v in by_sector.items()}

    enriched = []
    for tk, r in scored:
        s = r.get("sector") or "기타"
        peers = by_sector[s]
        pct = (sum(1 for x in peers if x < r["audit_score"]) / len(peers) * 100) if peers else None
        enriched.append({
            "ticker": tk, "company": r.get("company"), "sector": s,
            "score": r["audit_score"], "verdict": r.get("audit_verdict"),
            "opinion": r.get("audit_opinion"),
            "sector_median": sector_med.get(s),
            "vs_sector": r["audit_score"] - sector_med.get(s, r["audit_score"]),
            "sector_pctile": round(pct, 0) if pct is not None else None,
            "peers": len(peers),
        })

    print("\n[업종 중앙값] (표본 %d개 이상)" % args.min_peers)
    for s, v in sorted(sector_med.items(), key=lambda x: x[1]):
        if len(by_sector[s]) >= args.min_peers:
            print(f"   {s:<14} {v:>3}점  (n={len(by_sector[s])})")

    low = sorted(enriched, key=lambda x: x["score"])[:args.top]
    print(f"\n[재무제표 신뢰도 하위 {len(low)}] — 절대점수 순")
    print("   %-5s %-14s %-10s %5s %6s %8s  %s" % ("코드", "회사", "업종", "점수", "업종중앙", "업종내%", "판정"))
    for e in low:
        print("   %-5s %-14s %-10s %5d %6s %7s%%  %s" % (
            e["ticker"], (e["company"] or "")[:14], (e["sector"] or "")[:10], e["score"],
            e["sector_median"], e["sector_pctile"], (e["verdict"] or "")[:34]))

    # 동종 대비 유독 나쁜 회사 — 업종 특성으로 설명되지 않는 쪽
    out_peers = [e for e in enriched if e["peers"] >= args.min_peers and e["vs_sector"] <= -20]
    out_peers.sort(key=lambda x: x["vs_sector"])
    print(f"\n[동종 대비 이례 — 업종 중앙값보다 20점 이상 낮음] {len(out_peers)}개")
    print("   업종 특성(수주산업 계약자산 등)으로 설명되지 않는 쪽이라 우선 확인 대상.")
    for e in out_peers[:args.top]:
        print("   %-5s %-14s %-10s %3d점 (업종 %s, %+d)  %s" % (
            e["ticker"], (e["company"] or "")[:14], (e["sector"] or "")[:10],
            e["score"], e["sector_median"], e["vs_sector"], (e["verdict"] or "")[:30]))

    # --- 재료비 실측 분포 --------------------------------------------------
    mr = sorted(r["material_ratio_of_cogs"] for r in rows.values()
                if r.get("material_ratio_of_cogs"))
    if mr:
        print(f"\n[재료비÷매출원가 실측] n={len(mr)}  최소 {mr[0]:.2f} · 중앙 {mr[len(mr)//2]:.2f} "
              f"· 최대 {mr[-1]:.2f}   (기존 가정값 0.80)")

    if args.json:
        payload = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "batch_built_at": d.get("built_at"), "n": len(rows),
                   "sector_median": sector_med, "companies": enriched,
                   "outliers_vs_sector": out_peers, "bad_opinion": [t for t, _ in bad_op]}
        pathlib.Path(args.json).write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n결과 저장 → {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
