"""공시 파서 스모크 테스트 — 사업보고서에서 뽑아오는 값이 아직 멀쩡한가.

DART 문서 양식은 회사·연도마다 바뀐다. 그래서 파서는 "한 번 맞으면 끝"이 아니라
**주기적으로 확인해야 하는 것**이다. 이 스크립트는 대표 종목 몇 개를 실제로 파싱해
품질 규칙을 걸고, 깨지면 **0이 아닌 종료코드**를 돌려준다(자동화에서 실패 감지용).

검사 대상
  · ``report_notes``    「비용의 성격별 분류」(재료비·노무비·감가상각) + 감사보고서
  · ``report_business`` 「가격변동추이」(실매입·판매단가) + 「생산실적·가동률」
  · ``labor_cost``      「직원 등의 현황」(인원·급여)
  · ``statement_audit`` 재무제표 3종 정합(DuckDB 필요 — 서버가 물고 있으면 자동 건너뜀)

품질 규칙(과거에 실제로 터졌던 것들)
  - 품목명이 숫자('171,147')·단위('천배럴')·구분값('수입')이면 병합셀 파싱 실패다.
  - 1년 등락률이 ±200%를 넘으면 수량/금액 열이 섞인 것이다.
  - 성격별 비용 구성비 합이 100%에서 크게 벗어나면 표를 잘못 읽은 것이다.
  - 전 종목이 '계속기업 불확실성'이면 감사인 상용문구를 오탐한 것이다.

사용:
    python -m scripts.verify_parsers
    python -m scripts.verify_parsers --tickers 004370,005490 --json out.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time

# 업종이 서로 다른 대표 종목 — 표 양식이 제각각이라 회귀 검출에 유리하다.
DEFAULT = {
    "004370": "농심(음식료·조별)",
    "005490": "POSCO홀딩스(철강·지주)",
    "010950": "S-Oil(정유·연산품)",
    "005930": "삼성전자(전자·복수부문)",
    "006400": "삼성SDI(2차전지)",
}

_BAD_NAME = re.compile(r"^[\d,.\s%()-]+$|^(천|백만|억|만)?\s*(배럴|톤|상자|포|개|대|매|kg|MT)$"
                       r"|^(수입|국내|내수|수출|해외)$")


def _fail(msgs: list[str], tk: str, what: str):
    msgs.append(f"  ✗ {tk} {what}")


def check_notes(tk: str, problems: list[str]) -> dict:
    from app.data.fundamentals import report_notes as rn
    d = rn.notes(tk)
    cn = d.get("cost_nature")
    # available 은 '주석 또는 감사보고서 중 하나라도' 라서, 성격별 유무와 구분해 표시해야 한다.
    out = {"available": d["available"], "cost_nature": bool(cn),
           "opinion": None, "kam": 0, "breakdown": None}
    if cn:
        tot = sum(b["pct"] for b in cn["breakdown"])
        out["breakdown"] = {b["cat"]: b["pct"] for b in cn["breakdown"]}
        out["material_ratio"] = cn["material_ratio"]
        if not (95 <= tot <= 105):
            _fail(problems, tk, f"성격별 구성비 합 {tot:.1f}% (100%에서 이탈 — 표 오독 의심)")
        if cn["total_cost_eok"] <= 0:
            _fail(problems, tk, "성격별 총비용 0 이하 (단위 인식 실패 의심)")
    a = d.get("audit")
    if a:
        out["opinion"] = a.get("opinion")
        out["kam"] = a.get("n_kam") or len(a.get("kam") or [])
        out["going_concern"] = a.get("going_concern_doubt")
        for t in a.get("kam") or []:
            if len(t) > 40 or re.search(r"(표본추출|문서검사|하였습니다)", t):
                _fail(problems, tk, f"KAM 제목에 감사절차 문장 혼입: {t[:40]}")
    return out


def check_business(tk: str, problems: list[str]) -> dict:
    from app.data.fundamentals import report_business as rb
    d = rb.business(tk)
    out = {"available": d["available"], "price_blocks": [], "utilization": 0, "output": 0}
    for blk in d.get("price_trend", []):
        out["price_blocks"].append({"scope": blk["scope"], "n": len(blk["items"]),
                                    "sample": [i["name"] for i in blk["items"][:3]]})
        for it in blk["items"]:
            if _BAD_NAME.match(it["name"]):
                _fail(problems, tk, f"단가 품목명 이상('{it['name']}') — 병합셀 파싱 실패")
            if it.get("chg_1y") is not None and abs(it["chg_1y"]) > 2.0:
                _fail(problems, tk, f"단가 등락 이상 {it['name']} {it['chg_1y']*100:.0f}%")
    for blk in d.get("utilization", []):
        out["utilization"] += len(blk["items"])
        for it in blk["items"]:
            if _BAD_NAME.match(it["name"]):
                _fail(problems, tk, f"가동률 이름 이상('{it['name']}')")
            if not (0 < it["utilization_pct"] <= 200):
                _fail(problems, tk, f"가동률 범위 이상 {it['utilization_pct']}%")
    for blk in d.get("output_series", []):
        out["output"] += len(blk["items"])
        out["output_sample"] = [i["name"] for i in blk["items"][:3]]
        for it in blk["items"]:
            if _BAD_NAME.match(it["name"]):
                _fail(problems, tk, f"생산실적 이름 이상('{it['name']}')")
    return out


def check_labor(tk: str, problems: list[str]) -> dict:
    from app.data.fundamentals import labor_cost as lc
    ys = lc.labor_3y(tk)
    if not ys:
        return {"available": False}
    c = ys[0]
    out = {"available": True, "year": c["year"], "headcount": c["headcount"],
           "avg_salary": c["avg_salary"], "years": len(ys)}
    if c["headcount"] and c["avg_salary"]:
        # 1인평균급여가 1천만~5억 밖이면 총계행 중복(인원 2배) 등 집계 오류다.
        if not (1e7 <= c["avg_salary"] <= 5e8):
            _fail(problems, tk, f"1인평균급여 이상 {c['avg_salary']:,}원 (총계행 중복 의심)")
        d = c.get("avg_salary_disclosed")
        if d and abs(c["avg_salary"] - d) / d > 0.30:
            _fail(problems, tk, f"계산 평균급여와 공시값 30%↑ 괴리 ({c['avg_salary']:,} vs {d:,})")
    return out


def check_audit(tk: str, problems: list[str]) -> dict:
    from app.data.fundamentals import statement_audit as sa
    from app.data.fundamentals import report_notes as rn
    try:
        d = sa.audit(tk, rn.notes(tk))
    except Exception as e:
        return {"available": False, "reason": f"{type(e).__name__}"}
    if not d.get("available"):
        return {"available": False, "reason": "DB 미적재/잠금"}
    # 항등식(A1~A3)이 깨지면 계정 매핑 문제 — 파서 회귀 신호다.
    for c in d["checks"]:
        if c["code"] in ("A1", "A2", "A3") and c["status"] == "fail":
            _fail(problems, tk, f"{c['label']} 실패 — {c['detail']}")
    return {"available": True, "score": d["score"], "verdict": d["verdict"],
            "fails": [c["code"] for c in d["checks"] if c["status"] == "fail"]}


def main() -> int:
    ap = argparse.ArgumentParser(description="공시 파서 스모크 테스트")
    ap.add_argument("--tickers", default="", help="쉼표 구분(기본: 대표 5종목)")
    ap.add_argument("--json", default="", help="결과 JSON 저장 경로")
    ap.add_argument("--skip-audit", action="store_true", help="재무제표 감사 검사 생략(DB 잠금 시)")
    args = ap.parse_args()

    # PowerShell 이 네이티브 인자의 **선행 0을 잘라먹는다**(004370 → 4370).
    # 그대로 두면 전 소스가 비어 나오는데 경고는 0건이라 '정상'으로 오독된다 → 6자리로 복원.
    targets = ({t.strip().zfill(6): t.strip().zfill(6) for t in args.tickers.split(",") if t.strip()}
               if args.tickers else DEFAULT)
    problems: list[str] = []
    result: dict = {"checked_at": time.strftime("%Y-%m-%d %H:%M:%S"), "companies": {}}

    for tk, label in targets.items():
        t0 = time.time()
        row = {"label": label}
        row["notes"] = check_notes(tk, problems)
        row["business"] = check_business(tk, problems)
        row["labor"] = check_labor(tk, problems)
        row["audit"] = {"skipped": True} if args.skip_audit else check_audit(tk, problems)
        row["elapsed_sec"] = round(time.time() - t0, 1)
        result["companies"][tk] = row

        # 전 소스가 비면 '경고 0건 = 정상'으로 오독된다 → 이건 명백한 실패다.
        if not (row["notes"]["available"] or row["business"]["available"]
                or row["labor"].get("available")):
            _fail(problems, tk, "전 소스 미확보 — 종목코드 오류이거나 DART 접근 실패")

        n = row["notes"]
        b = row["business"]
        lb = row["labor"]
        au = row["audit"]
        print(f"[{tk}] {label}  ({row['elapsed_sec']}s)")
        print(f"   성격별: {'있음' if n['cost_nature'] else '없음'}"
              f"{'  재료비율 %.3f' % n['material_ratio'] if n.get('material_ratio') else ''}"
              f"   감사의견 {n.get('opinion') or '—'} · KAM {n.get('kam', 0)}건")
        pb = " / ".join(f"{x['scope']}{x['n']}개({','.join(x['sample'])})" for x in b["price_blocks"])
        print(f"   단가: {pb or '미공시'}   가동률 {b['utilization']}행   생산실적 {b['output']}행")
        if lb.get("available"):
            print(f"   인건비: {lb['headcount']:,}명 · 1인평균 {lb['avg_salary']:,}원 ({lb['years']}개년)")
        else:
            print("   인건비: 없음")
        if au.get("available"):
            print(f"   재무감사: {au['score']}점 · {au['verdict']}")
        elif not au.get("skipped"):
            print(f"   재무감사: 건너뜀({au.get('reason')})")

    result["problems"] = problems
    print("\n" + "=" * 60)
    if problems:
        print(f"품질 경고 {len(problems)}건:")
        for p in problems:
            print(p)
    else:
        print("품질 경고 없음 — 파서 정상")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        print(f"결과 저장 → {args.json}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
