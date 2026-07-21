"""관리자용 블로그 글 생성기.

대시보드 분석을 블로그에 바로 붙여넣을 수 있는 글(마크다운 + HTML)로 변환한다.
섹션(제목/문단/표/목록/인용) 구조를 한 번 만들고 마크다운·HTML 두 형식으로 렌더한다.
네이버/티스토리 등은 HTML 붙여넣기가 깔끔하고, 마크다운 지원 에디터엔 마크다운을 쓴다.

콘텐츠: 배당 종목 분석 / 데일리 시황 / 위기 배당주 / 배당왕·귀족·ETF / 직접 작성.
"""
from __future__ import annotations

import html
import time

from app.data.market import dividend_detail, crisis_survivors, dividend_etf, dividend_royalty


# ── 문서 빌더 (섹션 → 마크다운/HTML) ──────────────────────────────────────
def _md(blocks: list) -> str:
    out = []
    for b in blocks:
        t = b[0]
        if t == "h2":
            out.append(f"## {b[1]}")
        elif t == "h3":
            out.append(f"### {b[1]}")
        elif t == "p":
            out.append(b[1])
        elif t == "quote":
            out.append(f"> {b[1]}")
        elif t == "ul":
            out.extend(f"- {x}" for x in b[1])
        elif t == "table":
            headers, rows = b[1], b[2]
            out.append("| " + " | ".join(headers) + " |")
            out.append("| " + " | ".join(["---"] * len(headers)) + " |")
            out.extend("| " + " | ".join(str(c) for c in r) + " |" for r in rows)
        elif t == "hr":
            out.append("---")
        out.append("")
    return "\n".join(out).strip() + "\n"


def _html(blocks: list) -> str:
    e = html.escape
    out = []
    for b in blocks:
        t = b[0]
        if t == "h2":
            out.append(f"<h2>{e(b[1])}</h2>")
        elif t == "h3":
            out.append(f"<h3>{e(b[1])}</h3>")
        elif t == "p":
            out.append(f"<p>{e(b[1])}</p>")
        elif t == "quote":
            out.append(f"<blockquote>{e(b[1])}</blockquote>")
        elif t == "ul":
            items = "".join(f"<li>{e(str(x))}</li>" for x in b[1])
            out.append(f"<ul>{items}</ul>")
        elif t == "table":
            headers, rows = b[1], b[2]
            th = "".join(f"<th>{e(str(h))}</th>" for h in headers)
            trs = "".join("<tr>" + "".join(f"<td>{e(str(c))}</td>" for c in r) + "</tr>" for r in rows)
            out.append(f'<table border="1" cellpadding="6" cellspacing="0"><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>')
        elif t == "hr":
            out.append("<hr>")
    return "\n".join(out)


def _pack(title: str, blocks: list, tags: list[str]) -> dict:
    return {
        "title": title,
        "markdown": _md(blocks),
        "html": _html(blocks),
        "tags": tags,
        "generated_at": time.strftime("%Y-%m-%d %H:%M"),
    }


def _fmt_money(v, cur: str) -> str:
    if v is None:
        return "—"
    return f"${v:,.2f}" if cur == "USD" else f"{round(v):,}원"


def _fmt_mag(v, unit: str) -> str:
    if v is None:
        return "—"
    if unit == "백만$":
        return f"${v/1000:,.1f}B" if abs(v) >= 1000 else f"${round(v):,}M"
    return f"{v/10000:,.1f}조" if abs(v) >= 10000 else f"{round(v):,}억"


# ── 콘텐츠별 생성기 ────────────────────────────────────────────────────────
def dividend_stock(ticker: str) -> dict:
    d = dividend_detail.detail(ticker)
    cur = d.get("currency", "KRW")
    name = d.get("name") or ticker
    dv = d.get("dividend") or {}
    cl = d.get("checklist") or {}
    blocks: list = []
    yld = dv.get("div_yield")
    blocks.append(("h2", f"{name} 배당 분석 — 배당률 {yld}% 짜리, 사도 될까?"))
    intro = f"{name}({d.get('ticker')})의 배당률은 {yld}%입니다. 주당배당금 {_fmt_money(dv.get('dps'), cur)} ÷ 현재가 {_fmt_money(d.get('close'), cur)} 기준입니다."
    if d.get("royalty"):
        intro += f" 이 종목은 {d['royalty'].get('tier_label','')}({d['royalty'].get('years')}년 연속 증액)입니다."
    blocks.append(("p", intro))

    if cl:
        blocks.append(("h3", "투자 전 체크리스트"))

        def _mrow(m, label):
            latest = (m or {}).get("latest")
            val = _fmt_mag(latest.get("value"), m.get("unit")) if latest else "—"
            return [label, val, (m or {}).get("trend") or "—"]
        rows = [
            _mrow(cl.get("revenue"), "매출(돈 버는가)"),
            _mrow(cl.get("net_income"), "순이익(남기는가)"),
            _mrow(cl.get("op_cash_flow"), "영업현금흐름(건강한가)"),
        ]
        dy = cl.get("div_years", {})
        dg = cl.get("div_growth", {})
        rows.append(["배당연수(신뢰)", f"{dy.get('value','—')}년 연속", "—"])
        rows.append(["배당성장률(주주친화)", f"{dg.get('cagr','—')}%/년", "—"])
        blocks.append(("table", ["항목", "최근값", "추세"], rows))

    cr = d.get("crises")
    if cr and cr.get("available"):
        blocks.append(("h3", "3대 경제위기 때 배당은?"))
        for c in cr.get("crises", []):
            vals = [f"{r['year']}년 {_fmt_money(r['dps'], cur)}({r['verdict'] or '-'})" for r in c["rows"] if r["dps"] is not None]
            if vals:
                blocks.append(("p", f"**{c['label']}**: " + ", ".join(vals) + f" → {c['summary']}"))
            else:
                blocks.append(("p", f"**{c['label']}**: {c['summary']}"))
        if cr.get("notes"):
            blocks.append(("quote", cr["notes"]))

    blocks.append(("hr",))
    blocks.append(("p", "※ 본 글은 대시보드 자동 분석이며 투자 권유가 아닙니다. 데이터: " + (d.get("note") or "")))
    return _pack(f"{name} 배당 분석 (배당률 {yld}%)", blocks, ["배당주", "배당투자", name])


def daily_report() -> dict:
    from app.data.market import market_movers
    snap = market_movers.snapshot()
    blocks: list = []
    today = time.strftime("%Y년 %m월 %d일")
    blocks.append(("h2", f"{today} 시황 브리핑 — 오늘의 급등락 원인"))
    gainers = (snap.get("gainers") or [])[:5]
    losers = (snap.get("losers") or [])[:5]
    if gainers:
        blocks.append(("h3", "급등 종목 TOP 5"))
        blocks.append(("table", ["종목", "등락률", "종가"],
                       [[g.get("name") or g.get("ticker"), f"+{g.get('change_pct')}%", f"{round(g.get('close') or 0):,}원"] for g in gainers]))
    if losers:
        blocks.append(("h3", "급락 종목 TOP 5"))
        blocks.append(("table", ["종목", "등락률", "종가"],
                       [[l.get("name") or l.get("ticker"), f"{l.get('change_pct')}%", f"{round(l.get('close') or 0):,}원"] for l in losers]))
    cause = snap.get("ai_cause") or snap.get("cause")
    if cause and isinstance(cause, dict) and cause.get("summary"):
        blocks.append(("h3", "오늘 시장 한줄 요약"))
        blocks.append(("quote", cause["summary"]))
    blocks.append(("hr",))
    blocks.append(("p", "※ 자동 생성 시황 리포트입니다. 투자 판단의 책임은 본인에게 있습니다."))
    return _pack(f"{today} 시황 브리핑", blocks, ["시황", "증시", "급등주", "급락주"])


def crisis_survivors_post() -> dict:
    b = crisis_survivors.board()
    blocks: list = []
    blocks.append(("h2", "위기를 이겨낸 우상향 배당주 — 2000·2008·2020을 견딘 기업들"))
    bench = b.get("benchmark")
    if bench:
        blocks.append(("p", f"S&P500은 {b.get('start','2000')[:4]}년 이후 {bench.get('multiple')}배(연 {bench.get('cagr')}%) 올랐습니다. 아래 배당주들은 위기마다 급락했지만 매번 회복하며 그 이상 우상향했고, 그동안 배당까지 계속 늘렸습니다."))
    rows = []
    for r in b.get("survivors", [])[:10]:
        dds = " / ".join(f"{c['label'].split(' ')[0]} {c['drawdown']}%" for c in r.get("crises", []) if c.get("drawdown") is not None)
        rows.append([r.get("name"), f"{r.get('multiple')}배", f"연 {r.get('cagr')}%", dds])
    blocks.append(("table", ["종목", "상승배수", "연평균", "위기별 최대낙폭"], rows))
    blocks.append(("p", "핵심: 좋은 배당주는 위기에 '급락'하지만 '망하지 않고' 회복하며, 그 와중에도 배당을 늘립니다. 그래서 장기 적립·재투자가 강력합니다."))
    blocks.append(("hr",))
    blocks.append(("p", "※ 주가: FinanceDataReader, 배당 지위: 배당왕/귀족 기록. 투자 권유 아님."))
    return _pack("위기를 이겨낸 우상향 배당주 TOP 10", blocks, ["배당주", "장기투자", "미국주식", "S&P500"])


def etf_post() -> dict:
    b = dividend_etf.board()
    blocks: list = []
    blocks.append(("h2", "배당 ETF 완전정리 — VIG·SCHD·DGRO부터 S&P500 적립까지"))
    blocks.append(("p", "배당 투자를 ETF 하나로 시작하는 법. 성향별로 정리했습니다."))
    for g in b.get("groups", []):
        blocks.append(("h3", f"{g['category']} (평균 배당 {g.get('avg_yield','—')}%)"))
        rows = [[e["ticker"], f"{e.get('yield','—')}%", f"{e.get('expense','—')}%", e.get("strategy", "")] for e in g.get("rows", [])]
        blocks.append(("table", ["ETF", "배당률", "보수", "전략"], rows))
    blocks.append(("hr",))
    blocks.append(("p", "※ 수익률·보수는 조사 시점 기준. 투자 권유 아님."))
    return _pack("배당 ETF 완전정리 (VIG·SCHD·DGRO·S&P500)", blocks, ["ETF", "배당ETF", "SCHD", "적립식투자"])


def royalty_post() -> dict:
    b = dividend_royalty.board()
    blocks: list = []
    blocks.append(("h2", "배당왕·배당귀족이란? 50년·25년 배당 늘린 기업들"))
    blocks.append(("p", "배당왕(Dividend Kings)은 50년 이상, 배당귀족(Aristocrats)은 25년 이상 매년 배당을 늘려온 기업입니다. 위기에도 배당을 늘렸다는 건 그만큼 사업이 튼튼하다는 증거죠."))
    for key, label in (("kings", "👑 배당왕 TOP (50년+)"), ("aristocrats", "🎖️ 배당귀족 TOP (25년+)")):
        g = b.get(key, {})
        rows = [[r["name"], r["ticker"], f"{r.get('years','—')}년", f"{r.get('yield','—')}%"] for r in g.get("rows", [])[:15]]
        blocks.append(("h3", label))
        blocks.append(("table", ["기업", "티커", "연속증액", "배당률"], rows))
    blocks.append(("hr",))
    blocks.append(("p", "※ 조사 시점 기준. 투자 권유 아님."))
    return _pack("배당왕·배당귀족 완전정리", blocks, ["배당왕", "배당귀족", "미국배당주"])


def custom(title: str, body_markdown: str) -> dict:
    """직접 작성 — 제목 + 마크다운 본문을 HTML로도 변환."""
    blocks = [("p", body_markdown)]  # 본문은 그대로 두되 HTML은 문단 처리
    # 마크다운 본문은 그대로 보존하고, HTML은 줄바꿈만 <br>로
    md = f"# {title}\n\n{body_markdown}\n" if title else body_markdown + "\n"
    html_body = "<br>\n".join(html.escape(line) for line in body_markdown.splitlines())
    return {
        "title": title or "제목 없음",
        "markdown": md,
        "html": (f"<h2>{html.escape(title)}</h2>\n" if title else "") + f"<p>{html_body}</p>",
        "tags": [],
        "generated_at": time.strftime("%Y-%m-%d %H:%M"),
    }


GENERATORS = {
    "dividend-stock": lambda p: dividend_stock(p.get("ticker", "")),
    "daily-report": lambda p: daily_report(),
    "crisis-survivors": lambda p: crisis_survivors_post(),
    "etf": lambda p: etf_post(),
    "royalty": lambda p: royalty_post(),
    "custom": lambda p: custom(p.get("title", ""), p.get("body", "")),
}


def generate(kind: str, params: dict) -> dict:
    gen = GENERATORS.get(kind)
    if not gen:
        raise ValueError(f"알 수 없는 콘텐츠 유형: {kind}")
    return gen(params or {})
