"""관리자용 블로그 글 생성기.

대시보드 분석을 블로그에 바로 붙여넣을 수 있는 글(마크다운 + HTML)로 변환한다.
섹션(제목/문단/표/목록/인용) 구조를 한 번 만들고 마크다운·HTML 두 형식으로 렌더한다.
네이버/티스토리 등은 HTML 붙여넣기가 깔끔하고, 마크다운 지원 에디터엔 마크다운을 쓴다.

콘텐츠: 배당 종목 분석 / 데일리 시황 / 위기 배당주 / 배당왕·귀족·ETF / 직접 작성.
"""
from __future__ import annotations

import base64
import html
import io
import re
import time

from app.data.market import dividend_detail, crisis_survivors, dividend_etf, dividend_royalty
from app.data.infra import store


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
            out.append(str(b[1]))
        elif t == "quote":
            out.append(f"> {b[1]}")
        elif t == "ul":
            out.extend(f"- {x}" for x in b[1])
        elif t == "table":
            headers, rows = b[1], b[2]
            out.append("| " + " | ".join(headers) + " |")
            out.append("| " + " | ".join(["---"] * len(headers)) + " |")
            out.extend("| " + " | ".join(str(c) for c in r) + " |" for r in rows)
        elif t == "img":
            out.append(f"![{b[2]}]({b[1]})")
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
        elif t == "img":
            out.append(f'<img src="{b[1]}" alt="{e(b[2])}" style="max-width:100%;border-radius:8px;" />')
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


def _chart_data_uri(ticker: str, up: bool, days: int = 40) -> str | None:
    """종목의 최근 주가 라인차트 PNG를 base64 data URI 로. (블로그 임베드용)"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from datetime import datetime, timedelta

        start = (datetime.now() - timedelta(days=days * 2)).strftime("%Y-%m-%d")
        wide = store.load_prices(tickers=[ticker], market="KR", start=start, field="close")
        if wide is None or wide.empty or ticker not in wide.columns:
            return None
        ser = wide[ticker].dropna().tail(days)
        if len(ser) < 3:
            return None
        color = "#c0392b" if up else "#1971c2"
        fig, ax = plt.subplots(figsize=(5.2, 2.2), dpi=110)
        ax.plot(ser.index, ser.values, color=color, linewidth=2)
        ax.fill_between(ser.index, ser.values, ser.min(), color=color, alpha=0.08)
        ax.margins(x=0.01)
        ax.grid(True, axis="y", alpha=0.25, linewidth=0.5)
        for sp in ("top", "right", "left"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(labelsize=7, length=0)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        last = ser.values[-1]
        ax.annotate(f"{last:,.0f}", (ser.index[-1], last), textcoords="offset points",
                    xytext=(4, 0), fontsize=8, color=color, fontweight="bold", va="center")
        fig.tight_layout(pad=0.4)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


# 증시/종목 관련 뉴스인지 판별하는 키워드 — 동명이의(예: 제지회사 '모나리자' vs 그림
# '모나리자')로 인한 잘못된 원인 귀속을 막는다. 거짓 원인은 절대 넣지 않는다.
_STOCK_KW = (
    "주가", "급등", "급락", "상한가", "하한가", "특징주", "종목", "증시", "코스피", "코스닥",
    "신고가", "신저가", "강세", "약세", "상승", "하락", "매수", "매도", "목표주가", "실적",
    "수주", "계약", "공시", "인수", "합병", "유상증자", "무상증자", "배당", "거래량", "시총",
    "어닝", "분기", "영업이익", "적자", "흑자", "리포트", "증권", "투자", "테마", "관련주",
    "해운주", "조선주", "방산", "바이오", "2차전지", "반도체", "%", "％",
)


def _is_stock_relevant(article: dict, name: str) -> bool:
    """기사 제목/관련보도에 증시·종목 맥락이 있으면 True. 동명이의 오귀속 방지."""
    hay = (article.get("title") or "")
    hay += " " + " ".join(article.get("cluster") or [])
    if name and name not in hay:
        # 회사명이 아예 없으면 관련성 낮음(구글뉴스는 보통 이름으로 검색됨)
        pass
    return any(k in hay for k in _STOCK_KW)


def _relevant_news(news: list[dict], name: str) -> list[dict]:
    return [a for a in (news or []) if _is_stock_relevant(a, name)]


def _mover_blocks(it: dict, real_move: bool) -> list:
    """핫 종목 1개 → 제목 + 차트 + (검증된) 뉴스 발췌 블록.

    real_move=True 면 실제 등락률 기준(급등/급락). False 면 데이터가 평평한 상태라
    등락률을 단정하지 않고 거래대금 기준으로만 표기한다(거짓 표기 방지).
    """
    name = it.get("name") or it.get("ticker")
    chg = it.get("change_pct") or 0
    up = chg >= 0
    sign = "+" if chg >= 0 else ""
    val = it.get("value") or 0
    val_txt = f"{val/1e8:,.0f}억" if val >= 1e8 else f"{round(val):,}원"
    close_txt = f"{round(it.get('close') or 0):,}원"
    if real_move and abs(chg) >= 0.01:
        head = f"{name}  {sign}{chg}%  (종가 {close_txt})"
    else:
        head = f"{name}  거래대금 {val_txt}  (종가 {close_txt})"
    blocks: list = [("h3", head)]
    uri = _chart_data_uri(it.get("ticker"), up)
    if uri:
        blocks.append(("img", uri, f"{name} 최근 주가"))

    rel = _relevant_news(it.get("news") or [], name)
    if rel:
        top = rel[0]
        cause = f"📰 {top.get('title','')}"
        if top.get("source"):
            cause += f" — {top['source']}"
        blocks.append(("p", cause))
        extra = [f"{a['title']}" + (f" — {a['source']}" if a.get("source") else "")
                 for a in rel[1:4] if a.get("title")]
        if extra:
            blocks.append(("ul", extra))
    else:
        # 관련 뉴스가 확인 안 되면 원인을 지어내지 않고 정직하게 표기
        blocks.append(("p", "관련 증시 뉴스가 뚜렷하게 확인되지 않았습니다. (거래는 활발)"))
    return blocks


def _headline_text(h) -> str | None:
    if isinstance(h, dict):
        t = h.get("title") or h.get("headline")
        return (t + (f" — {h['source']}" if h.get("source") else "")) if t else None
    if isinstance(h, str):
        return h
    return None


def _market_issue_blocks() -> list:
    """하루 전체 이슈 — 시장 분위기 + 주도 테마 + 시장 전체 주요 뉴스.

    livepulse(실시간 시황 취합)의 검증된 분위기·드라이버·뉴스만 쓴다. 지어내지 않는다.
    """
    from app.data.news import livepulse
    try:
        p = livepulse.pulse()
    except Exception:
        return []
    blocks: list = []
    pulse = p.get("pulse") or {}
    drivers = [d for d in (p.get("drivers") or []) if d.get("direction") != "중립"][:5] or (p.get("drivers") or [])[:4]
    flow = p.get("flow") or []

    # 시장 분위기 한 줄
    if pulse.get("narrative"):
        blocks.append(("h2", "🗞️ 오늘 시장 분위기"))
        blocks.append(("quote", pulse["narrative"]))

    # 하루를 끌고 간 핵심 이슈(테마)
    if drivers:
        blocks.append(("h2", "🎯 오늘의 핵심 이슈"))
        for d in drivers:
            theme = d.get("theme", "이슈")
            direction = d.get("direction")
            cnt = d.get("count")
            head = theme + (f"  ({direction}" if direction else "  (") + (f" · {cnt}건)" if cnt else ")")
            blocks.append(("h3", head))
            # digest 는 헤드라인들이 뭉친 형태라 지저분 → 깔끔한 헤드라인 목록만 사용
            hl = [t for t in (_headline_text(h) for h in (d.get("headlines") or [])[:4]) if t]
            if hl:
                blocks.append(("ul", hl))

    # 시장 전체 주요 뉴스(최신 헤드라인)
    top_news = []
    for a in flow[:8]:
        t = a.get("title")
        if t:
            top_news.append(t + (f" — {a['source']}" if a.get("source") else "") + (f" ({a['ago']})" if a.get("ago") else ""))
    if top_news:
        blocks.append(("h2", "📰 오늘의 주요 뉴스"))
        blocks.append(("ul", top_news))
    return blocks


def _sector_blocks(snap: dict) -> list:
    """업종별 등락 — 오른/내린 업종과 대표 종목(주도 테마 파악)."""
    up = snap.get("sectors_up") or []
    down = snap.get("sectors_down") or []
    if not up and not down:
        return []

    def _row(s):
        leaders = ", ".join(l.get("name", "") for l in (s.get("leaders") or [])[:3])
        return [s.get("sector"), f"{s.get('avg_change_pct'):+.2f}%", str(s.get("count", "")), leaders]
    blocks: list = [("h2", "🏭 업종별 등락 (오늘 주도 업종)")]
    if up:
        blocks.append(("h3", "오른 업종"))
        blocks.append(("table", ["업종", "평균등락", "종목수", "대표 종목"], [_row(s) for s in up[:5]]))
    if down:
        blocks.append(("h3", "내린 업종"))
        blocks.append(("table", ["업종", "평균등락", "종목수", "대표 종목"], [_row(s) for s in down[:5]]))
    return blocks


def daily_report() -> dict:
    from app.data.market import market_movers
    snap = market_movers.snapshot()
    blocks: list = []
    today = time.strftime("%Y년 %m월 %d일")
    thr = snap.get("threshold") or 5.0
    gainers = (snap.get("gainers") or [])[:4]
    losers = (snap.get("losers") or [])[:4]

    # 실제 등락이 있는 날인지(데이터 기준). 거짓으로 '급등/급락'이라 부르지 않기 위함.
    real_move = any(abs(x.get("change_pct") or 0) >= thr for x in gainers + losers)
    breadth = snap.get("breadth") or {}
    ai = snap.get("ai")

    if real_move:
        title = f"{today} 오늘의 급등락 종목 총정리"
        blocks.append(("h2", f"{today} 오늘의 급등락 — 가장 크게 움직인 종목과 그 이유"))
        intro = "오늘 시장에서 가장 크게 움직인 종목들을 관련 뉴스와 함께 정리했습니다."
        if breadth:
            intro += f" (상승 {breadth.get('advancers','—')} · 하락 {breadth.get('decliners','—')} 종목)"
        gain_head, lose_head = "🔥 급등 종목", "❄️ 급락 종목"
    else:
        title = f"{today} 거래 상위 종목·이슈 정리"
        blocks.append(("h2", f"{today} 오늘 거래가 활발했던 종목과 이슈"))
        intro = ("※ 아직 장중 시세가 반영되지 않아 등락률을 단정하지 않고, 거래대금(거래가 "
                 "몰린 정도) 기준으로 정리했습니다. 등락률은 장 마감 데이터가 들어오면 갱신됩니다.")
        gain_head, lose_head = "💹 거래대금 상위 (관심 집중)", None

    blocks.append(("p", intro))
    if ai and isinstance(ai, dict) and ai.get("summary"):
        blocks.append(("quote", ai["summary"]))

    # ── 하루 전체 이슈: 시장 분위기 + 핵심 테마 + 주요 뉴스 + 업종 등락 ──
    blocks.extend(_market_issue_blocks())
    blocks.extend(_sector_blocks(snap))

    # ── 개별 종목: 급등락/거래 상위 + 종목별 원인 뉴스 ──
    if gainers:
        blocks.append(("h2", gain_head))
        for it in gainers:
            blocks.extend(_mover_blocks(it, real_move))
    if losers and lose_head:
        blocks.append(("h2", lose_head))
        for it in losers:
            blocks.extend(_mover_blocks(it, real_move))

    blocks.append(("hr",))
    blocks.append(("p", "※ 원인으로 제시한 뉴스는 증시 관련성으로 선별했으나 상관관계일 뿐 "
                        "인과를 보장하지 않습니다. 수치·인용은 실제 데이터·기사 기준이며, "
                        "확인되지 않은 원인은 임의로 넣지 않습니다. 투자 판단의 책임은 본인에게 있습니다."))
    tags = (["오늘의증시", "급등주", "급락주", "시황"] if real_move
            else ["오늘의증시", "거래상위", "관심종목", "시황"])
    tags += [g.get("name") for g in gainers[:2] if g.get("name")]
    return _pack(title, blocks, tags)


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


# ── 하루 증시 보고서 (자동 발행용) ────────────────────────────────────────
def _amt_eok(v) -> str:
    """억 단위 순매수 금액 → '+1.2조' / '-3,400억'."""
    if v is None:
        return "—"
    sign = "+" if v >= 0 else "−"
    a = abs(v)
    return f"{sign}{a/10000:,.2f}조" if a >= 10000 else f"{sign}{a:,.0f}억"


def _breadth_blocks(rep: dict) -> list:
    """장 마감 상태 — 상승/하락 종목 수와 투자자별 순매수(누가 샀나)."""
    m = rep.get("market") or {}
    b = m.get("breadth") or {}
    blocks: list = []
    total = b.get("total")
    if total:
        rows = [["상승", f"{b.get('up', 0):,}종목"],
                ["하락", f"{b.get('down', 0):,}종목"],
                ["보합", f"{b.get('flat', 0):,}종목"]]
        blocks.append(("h2", "📊 오늘 시장 한눈에"))
        blocks.append(("table", ["구분", "종목 수"], rows))

    trend = m.get("investor_trend") or []
    if trend:
        td = trend[0]
        blocks.append(("h3", f"투자자별 순매수 ({td.get('date', '')})"))
        blocks.append(("table", ["외국인", "기관", "개인"],
                       [[_amt_eok(td.get("foreign")), _amt_eok(td.get("organ")),
                         _amt_eok(td.get("individual"))]]))
        # 방향이 갈리면 그 자체가 오늘의 이야기다.
        f, o, i = td.get("foreign"), td.get("organ"), td.get("individual")
        if f is not None and i is not None:
            if f > 0 and i < 0:
                blocks.append(("p", "외국인이 사고 개인이 판 날입니다. 외국인 수급이 들어온 업종을 보면 "
                                    "오늘 시장이 무엇을 좋게 봤는지 드러납니다."))
            elif f < 0 and i > 0:
                blocks.append(("p", "외국인이 팔고 개인이 받은 날입니다. 개인 매수로 버틴 장은 "
                                    "이튿날 수급이 이어지는지가 관건입니다."))
    return blocks


def _macro_blocks(rep: dict) -> list:
    """매크로·금리·환율·글로벌 — 각 모듈이 이미 만든 요약문만 인용한다(지어내지 않음)."""
    m = rep.get("market") or {}
    items: list[str] = []
    for key, label in (("macro", "거시"), ("rates", "금리"),
                       ("foreign_view", "외국인 시각"), ("cross_asset", "크로스에셋")):
        d = m.get(key) or {}
        s = d.get("summary") or ((d.get("flow") or {}).get("summary") if key == "cross_asset" else None)
        if s:
            items.append(f"[{label}] {s}")
    if not items:
        return []
    return [("h2", "🌍 매크로·환율·글로벌"), ("ul", items)]


def _tomorrow_blocks(rep: dict) -> list:
    """내일 관전포인트 — 공시된 일정(금리 캘린더)이 있을 때만. 전망은 만들지 않는다."""
    rates = ((rep.get("market") or {}).get("rates") or {})
    ev = rates.get("upcoming") or rates.get("events") or []
    out: list[str] = []
    for e in ev[:5]:
        if isinstance(e, dict):
            t = e.get("title") or e.get("name") or e.get("event")
            d = e.get("date") or e.get("when")
            if t:
                out.append(f"{d} · {t}" if d else str(t))
        elif isinstance(e, str):
            out.append(e)
    if not out:
        return []
    return [("h2", "📅 내일 이후 일정"), ("ul", out)]


def market_wrap(date: str | None = None) -> dict:
    """**오늘 하루 증시 보고서** — 블로그에 그대로 올릴 원고.

    구성: 한 줄 요약 → 시장 한눈에(등락·수급) → 시장 분위기·핵심 이슈 → 업종 →
    급등락 종목과 이유(차트 포함) → 매크로 → 일정 → 면책.

    데이터는 이미 만들어 둔 것들을 모아 쓴다. 새로 계산하지도, 없는 걸 지어내지도 않는다.
      · ``daily_archive``  그날 저장된 리포트(등락폭·투자자 수급·매크로 요약)
      · ``livepulse``      시장 분위기·핵심 이슈·뉴스
      · ``market_movers``  급등락 종목과 원인 뉴스, 업종별 등락
    """
    from app.data.market import market_movers
    from app.data.reports import daily_archive

    # ``snapshot()`` 은 리포트가 아니라 **저장 상태**({"status": "exists", ...})를 준다.
    # 본문이 필요하므로 날짜를 정한 뒤 ``load()`` 로 읽는다(없으면 한 번 만들고 다시 읽기).
    rep: dict = {}
    try:
        d0 = date or (daily_archive.list_dates() or [None])[0]
        rep = (daily_archive.load(d0) if d0 else None) or {}
        if not rep:
            got = daily_archive.snapshot()
            rep = daily_archive.load(got.get("date")) or {}
    except Exception:
        rep = {}
    d = rep.get("date") or date or time.strftime("%Y-%m-%d")
    try:
        y, mth, dd = d.split("-")
        today_ko = f"{y}년 {int(mth)}월 {int(dd)}일"
    except Exception:
        today_ko = time.strftime("%Y년 %m월 %d일")

    try:
        snap = market_movers.snapshot()
    except Exception:
        snap = {}

    blocks: list = [("h2", f"{today_ko} 증시 리포트")]
    summary = ((rep.get("market") or {}).get("summary") or "").strip()
    if summary:
        blocks.append(("quote", summary))
        # 요약문의 '최고 상승/최대 하락'에 ±100% 넘는 값이 섞이는 날이 있다(신규상장·거래재개·
        # 액면변경). 자동 발행이라 그대로 나가면 오해를 부르므로 한 줄 덧붙인다.
        if re.search(r"[+-]\s?\d{3,}(?:\.\d+)?%", summary):
            blocks.append(("p", "※ 등락률이 세 자리로 찍힌 종목은 신규상장·거래재개·액면변경처럼 "
                                "기준가가 바뀐 경우일 수 있어 일반 등락과 같이 보기 어렵습니다."))

    blocks.extend(_breadth_blocks(rep))
    blocks.extend(_market_issue_blocks())          # 분위기 + 핵심 이슈 + 주요 뉴스
    blocks.extend(_sector_blocks(snap))

    thr = snap.get("threshold") or 5.0
    gainers = (snap.get("gainers") or [])[:4]
    losers = (snap.get("losers") or [])[:4]
    real_move = any(abs(x.get("change_pct") or 0) >= thr for x in gainers + losers)
    if gainers:
        blocks.append(("h2", "🔥 오늘 많이 오른 종목" if real_move else "💹 거래가 몰린 종목"))
        for it in gainers:
            blocks.extend(_mover_blocks(it, real_move))
    if losers and real_move:
        blocks.append(("h2", "❄️ 오늘 많이 내린 종목"))
        for it in losers:
            blocks.extend(_mover_blocks(it, real_move))

    blocks.extend(_macro_blocks(rep))
    blocks.extend(_tomorrow_blocks(rep))

    blocks.append(("hr",))
    fresh = ((rep.get("market") or {}).get("data_freshness") or {})
    if fresh.get("price_date"):
        blocks.append(("p", f"※ 시세 기준일 {fresh['price_date']}"
                            + (f" · 수급 기준일 {fresh['investor_date']}" if fresh.get("investor_date") else "")
                            + f" · 작성 {time.strftime('%Y-%m-%d %H:%M')}"))
    blocks.append(("p", "※ 원인으로 제시한 뉴스는 증시 관련성으로 선별했으나 상관관계일 뿐 "
                        "인과를 보장하지 않습니다. 수치는 공시·시세 데이터 기준이며, 확인되지 않은 "
                        "내용은 넣지 않았습니다. 투자 판단과 그 결과는 본인 책임입니다."))

    post = _pack(f"{today_ko} 증시 리포트 — 오늘의 이슈와 급등락 정리", blocks,
                 ["오늘의증시", "증시리포트", "시황", "급등주", "수급"])
    post["date"] = d
    return post


def publish_market_wrap(date: str | None = None, force: bool = False) -> dict:
    """보고서를 만들어 ``data/blog_posts/`` 에 저장한다(같은 날 재생성은 갱신).

    자동 발행(스케줄러·스크립트)과 관리자 버튼이 같은 경로를 쓴다.
    """
    from app.data.admin import blog_archive
    d = date or time.strftime("%Y-%m-%d")
    if not force:
        got = blog_archive.load(d, "market-wrap")
        if got:
            return {**got, "reused": True}
    post = market_wrap(date)
    saved = blog_archive.save(post, kind="market-wrap", date=post.get("date") or d)
    return {**saved, "reused": False}


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
    "market-wrap": lambda p: market_wrap(p.get("date") or None),
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
