"use client";

import { useEffect, useRef, useState } from "react";
import { api, GlobalMoneyFlow as MF, MoneyCategory, MoneyKrDay } from "@/lib/api";

const RED = "#c92a2a";
const BLUE = "#1971c2";

function eok(v: number | null | undefined): string {
  if (v == null) return "—";
  const s = Math.abs(v) >= 10000 ? `${(Math.abs(v) / 10000).toFixed(2)}조` : `${Math.round(Math.abs(v)).toLocaleString("ko-KR")}억`;
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${s}`;
}
function flowStyle(v: number | null | undefined): React.CSSProperties {
  if (v == null) return { color: "#bbb" };
  return { color: v > 0 ? RED : v < 0 ? BLUE : "#666", fontWeight: 700 };
}
// 완화=초록(돈 푼다), 긴축=빨강(조인다)
function liqColor(t?: string) {
  return t === "완화" ? "#2f9e44" : t === "긴축" ? "#c92a2a" : "#666";
}
function dirColor(d?: string) {
  return d === "우호" || d === "유입" ? RED : d === "경계" || d === "이탈" ? BLUE : "#666";
}

export function MoneyFlow() {
  const [d, setD] = useState<MF | null>(null);
  const [live, setLive] = useState(false);
  const [err, setErr] = useState("");
  const [at, setAt] = useState("");
  const first = useRef(true);

  useEffect(() => {
    let alive = true;
    const load = () =>
      api
        .moneyFlow()
        .then((r) => {
          if (!alive) return;
          setD(r);
          setLive(true);
          setAt(new Date().toLocaleTimeString("ko-KR", { hour12: false }));
        })
        .catch((e) => { if (alive && first.current) setErr(e?.message ?? "자금 흐름을 불러오지 못했습니다."); })
        .finally(() => { first.current = false; });
    load();
    const id = setInterval(load, 60000); // 60초마다 실시간 갱신
    return () => { alive = false; clearInterval(id); };
  }, []);

  if (err && !d) return <Sheet right={null}><div className="py-20 text-center text-sm text-rose-600">{err}</div></Sheet>;
  if (!d) return <Sheet right={null}><div className="flex flex-col items-center gap-3 py-24 text-sm text-[#888]"><span className="h-7 w-7 animate-spin rounded-full border-2 border-[#d0d0d0] border-t-[#217346]" />글로벌 자금 흐름 취합 중…</div></Sheet>;

  const v = d.verdict;
  const liq = d.liquidity;
  const liqGauge = Math.max(0, Math.min(100, 50 + ((liq.ease - liq.tight) / Math.max(1, liq.ease + liq.tight)) * 50));

  return (
    <Sheet
      right={
        <span className="flex items-center gap-1.5 text-xs font-bold" style={{ color: live ? "#a5f3c0" : "#ddd" }}>
          <span className={`inline-block h-2 w-2 rounded-full ${live ? "animate-pulse" : ""}`} style={{ background: live ? "#7ee2a0" : "#bbb" }} />
          LIVE {at && <span className="font-normal text-white/70">갱신 {at}</span>}
        </span>
      }
    >
      <div className="space-y-5 bg-[#fafafa] p-4">
        {/* ── 종합 판정 ─────────────────────────── */}
        <section className="rounded border border-[#d0d0d0] bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center gap-2">
            <Badge label="글로벌 유동성" value={v.liquidity_label} color={liqColor(v.liquidity)} />
            <Badge label="외국 자본(한국)" value={v.foreign_kr} color={dirColor(v.foreign_kr)} />
            <Badge label="위험선호" value={v.risk} color={v.risk.includes("Risk-on") ? RED : v.risk.includes("Risk-off") ? BLUE : "#666"} />
            <span className="ml-auto text-xs text-[#999]">기준 {d.as_of?.slice(5)}</span>
          </div>
          <p className="mt-2 text-sm leading-relaxed text-[#333]">{v.narrative}</p>
        </section>

        {/* ── 실측 지표 (하드데이터) ─────────────── */}
        {d.indicators?.length > 0 && (
          <Block title="실측 지표 (하드데이터 · 무료 공개 소스)" color="#ffd8a8" fg="#8a4b00">
            <div className="grid gap-px bg-[#eee] sm:grid-cols-2 lg:grid-cols-4">
              {d.indicators.map((ind) => {
                const danger = ind.signal.includes("공포") || ind.signal.includes("긴축");
                const col = danger ? BLUE : ind.signal.includes("탐욕") || ind.signal.includes("완화") ? RED : "#666";
                return (
                  <div key={ind.key} className="bg-white p-3" title={ind.desc}>
                    <div className="text-[11px] text-[#888]">{ind.label}</div>
                    <div className="mt-0.5 flex items-baseline gap-1.5">
                      <span className="text-xl font-bold tabular-nums text-[#1f1f1f]">{ind.value}<span className="text-[11px] font-normal text-[#999]">{ind.unit}</span></span>
                      {ind.change != null && (
                        <span className="text-[11px] font-bold tabular-nums" style={{ color: ind.change > 0 ? RED : ind.change < 0 ? BLUE : "#999" }}>
                          {ind.change > 0 ? "▲" : ind.change < 0 ? "▼" : ""}{Math.abs(ind.change)}
                        </span>
                      )}
                    </div>
                    <div className="mt-0.5 inline-block rounded px-1.5 py-0.5 text-[10px] font-bold text-white" style={{ background: col }}>{ind.signal}</div>
                    <div className="mt-1 text-[10px] leading-snug text-[#999]">{ind.desc}</div>
                  </div>
                );
              })}
            </div>
          </Block>
        )}

        {/* ── 유동성: 돈을 푸나 조이나 ─────────────── */}
        <Block title="글로벌 유동성 — 세계가 돈을 푸나 / 조이나" color="#b2f2bb" fg="#2b5a2b">
          <div className="px-3 py-3">
            <div className="mb-1 flex items-center justify-between text-xs text-[#888]">
              <span style={{ color: "#c92a2a" }}>긴축(조인다) {liq.tight}</span>
              <span className="font-bold" style={{ color: liqColor(liq.tone) }}>{liq.regime}</span>
              <span style={{ color: "#2f9e44" }}>완화(푼다) {liq.ease}</span>
            </div>
            <div className="relative h-3 w-full overflow-hidden rounded-full border border-[#e0e0e0] bg-gradient-to-r from-[#c92a2a] via-[#e9e9e9] to-[#2f9e44]">
              <div className="absolute top-[-3px] h-[18px] w-[3px] rounded bg-[#1f1f1f]" style={{ left: `calc(${liqGauge}% - 1.5px)` }} />
            </div>
          </div>
          {liq.digest.length > 0 && (
            <div className="border-t border-[#eee] bg-[#f4fbf4] px-3 py-2">
              <div className="mb-1 text-[11px] font-bold text-[#2b8a3e]">대표 내용 (여러 매체 취합)</div>
              <ul className="space-y-0.5">{liq.digest.map((x, i) => <li key={i} className="flex gap-1.5 text-[12px] leading-snug text-[#555]"><span className="text-[#69db7c]">·</span><span>{x}</span></li>)}</ul>
            </div>
          )}
          <NewsList items={liq.headlines} dot="#69db7c" />
        </Block>

        {/* ── 지역별 중앙은행 스탠스 ─────────────── */}
        {d.regions?.length > 0 && (
          <Block title="지역별 중앙은행 — 누가 돈을 푸나 / 조이나" color="#c3e9c8" fg="#2b5a2b">
            <div className="grid gap-px bg-[#eee] sm:grid-cols-2 lg:grid-cols-5">
              {d.regions.map((r) => {
                const col = r.stance === "완화" ? "#2f9e44" : r.stance === "긴축" ? "#c92a2a" : "#666";
                const top = r.headlines[0];
                return (
                  <div key={r.region} className="bg-white p-3">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[13px] font-bold text-[#1f1f1f]">{r.label}</span>
                      <span className="ml-auto rounded px-1.5 py-0.5 text-[10px] font-bold text-white" style={{ background: col }}>{r.stance}</span>
                    </div>
                    <div className="mt-0.5 text-[10px] text-[#999]">완화 {r.ease} · 긴축 {r.tight} · {r.count}건</div>
                    {top && (
                      <a href={top.link || "#"} target="_blank" rel="noopener noreferrer" className="mt-1 block text-[11.5px] leading-snug text-[#555] hover:text-[#1155cc] hover:underline">{top.title}</a>
                    )}
                  </div>
                );
              })}
            </div>
          </Block>
        )}

        {/* ── 금리 결정 일정 ─────────────── */}
        {d.rate_schedule?.length > 0 && (
          <Block title="금리 결정 일정 — 다음 발표 (D-day)" color="#a5d8ff" fg="#1a3a5e">
            <div className="grid gap-2 p-3 sm:grid-cols-2 lg:grid-cols-4">
              {d.rate_schedule.map((m) => {
                const soon = m.d_day != null && m.d_day <= 14;
                return (
                  <div key={m.key} className="rounded border border-[#dbe7f3] bg-[#f7fbff] px-2.5 py-2">
                    <div className="flex items-center gap-1 text-xs font-bold text-[#1f5132]"><span>{m.name}</span></div>
                    <div className="mt-1 flex items-baseline gap-1.5">
                      <span className="text-base font-bold tabular-nums text-[#1f1f1f]">{m.next_label ?? "—"}</span>
                      {m.d_day != null && <span className="rounded px-1.5 py-0.5 text-[11px] font-bold" style={{ background: soon ? RED : "#dbe7f3", color: soon ? "#fff" : "#1a3a5e" }}>D-{m.d_day}</span>}
                    </div>
                    {m.next_date && <div className="mt-0.5 text-[10px] text-[#999]">{m.next_date}</div>}
                  </div>
                );
              })}
            </div>
          </Block>
        )}

        {/* ── 한국 자금: 외국인 vs 국내 ─────────────── */}
        <Block title="한국 자금 — 외국인 vs 국내(개인+기관) 순매수 + 원/달러" color="#a5d8ff" fg="#1a3a5e">
          <div className="flex flex-wrap items-center gap-3 border-b border-[#eee] bg-[#f3f9ff] px-3 py-2 text-[13px]">
            <span>외국인 최근 <b style={{ color: dirColor(d.kr_capital.foreign_direction) }}>{d.kr_capital.foreign_direction}</b></span>
            {d.kr_capital.latest && (
              <span className="text-[#555]">외국인 <span style={flowStyle(d.kr_capital.latest.foreign)}>{eok(d.kr_capital.latest.foreign)}</span> · 국내 <span style={flowStyle(d.kr_capital.latest.domestic)}>{eok(d.kr_capital.latest.domestic)}</span> <span className="text-[#999]">({d.kr_capital.latest.date})</span></span>
            )}
            {d.usdkrw?.value != null && (
              <span className="ml-auto text-[#555]">원/달러 <b>₩{d.usdkrw.value.toLocaleString("ko-KR")}</b> <span style={flowStyle(d.usdkrw.change_pct != null ? -d.usdkrw.change_pct : null)}>{d.usdkrw.change_pct != null ? `${d.usdkrw.change_pct > 0 ? "+" : ""}${d.usdkrw.change_pct}%` : ""}</span></span>
            )}
          </div>
          <table className="w-full border-collapse text-[13px]">
            <thead><tr className="bg-[#eaf3ff] text-xs text-[#1a3a5e]"><Th>일자</Th><Th right>외국인</Th><Th right>국내(개인+기관)</Th></tr></thead>
            <tbody>
              {d.kr_capital.series.map((r: MoneyKrDay) => (
                <tr key={r.date} className="hover:bg-[#f3f9ff]">
                  <td className="border border-[#eee] px-2 py-1.5 font-medium text-[#1f1f1f]">{r.date}</td>
                  <td className="border border-[#eee] px-2 py-1.5 text-right tabular-nums" style={flowStyle(r.foreign)}>{eok(r.foreign)}</td>
                  <td className="border border-[#eee] px-2 py-1.5 text-right tabular-nums" style={flowStyle(r.domestic)}>{eok(r.domestic)}</td>
                </tr>
              ))}
              {d.kr_capital.series.length === 0 && <tr><td colSpan={3} className="px-3 py-3 text-center text-sm text-[#999]">수급 데이터 누적 중…</td></tr>}
            </tbody>
          </table>
        </Block>

        {/* ── 크로스에셋: 현금이 어디로 ─────────────── */}
        {d.cross_asset?.verdict && (
          <Block title="크로스에셋 — 현금이 어디로 흐르나 (Risk-on/off)" color="#ffe08a" fg="#7a5b00">
            <div className="flex flex-wrap items-center gap-3 px-3 py-2.5 text-sm">
              <span className="rounded-full px-3 py-1 text-sm font-bold text-white" style={{ background: d.cross_asset.tone === "긍정" ? RED : d.cross_asset.tone === "부정" ? BLUE : "#666" }}>{d.cross_asset.verdict}</span>
              <span className="text-[#444]">{d.cross_asset.desc}</span>
              {d.cross_asset.metrics && (
                <span className="ml-auto text-[13px] text-[#999]">증시 {fmt(d.cross_asset.metrics.equities)} · 코인 {fmt(d.cross_asset.metrics.crypto)} · 금 {fmt(d.cross_asset.metrics.gold)} · 원/달러 {fmt(d.cross_asset.metrics.usdkrw)}</span>
              )}
            </div>
          </Block>
        )}

        {/* ── 자산군별 자금 흐름 뉴스 ─────────────── */}
        <Block title="자산군별 자금 흐름 (정책·외국인·부동산·채권·현금·원자재·외환·펀드)" color="#d0bfff" fg="#3d2c66">
          <div className="grid gap-px bg-[#eee] sm:grid-cols-2 xl:grid-cols-4">
            {d.categories.map((c) => <CategoryCard key={c.key} c={c} />)}
          </div>
        </Block>

        <p className="px-1 text-center text-[11px] leading-relaxed text-[#999]">
          유동성·자금 방향은 뉴스 키워드(완화/긴축·우호/경계) 집계와 수급·환율·크로스에셋을 조합한 <b className="text-[#666]">규칙 기반 유추</b>이며, 투자 권유가 아닙니다. 60초마다 실시간 갱신 + 백그라운드 상시 크롤링.
        </p>
      </div>
    </Sheet>
  );
}

function fmt(v: number | null | undefined): string {
  return v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;
}

function CategoryCard({ c }: { c: MoneyCategory }) {
  const col = dirColor(c.direction);
  const top = c.headlines[0];
  return (
    <div className="bg-white p-3">
      <div className="flex items-center gap-1.5">
        <span className="text-[13px] font-bold text-[#1f1f1f]">{c.label}</span>
        <span className="ml-auto rounded px-1.5 py-0.5 text-[10px] font-bold text-white" style={{ background: col }}>{c.direction}</span>
      </div>
      <div className="mt-0.5 text-[10px] text-[#999]"> {c.count}건 · 우호 {c.pos} · 경계 {c.neg}</div>
      {top && (
        <a href={top.link || "#"} target="_blank" rel="noopener noreferrer" className="mt-1 block text-[12px] leading-snug text-[#555] hover:text-[#1155cc] hover:underline">
          {top.title}<span className="ml-1 text-[11px] text-[#aaa]">· {top.source}</span>
        </a>
      )}
    </div>
  );
}

function NewsList({ items, dot }: { items: { title: string; link: string; source: string }[]; dot: string }) {
  return (
    <ul className="divide-y divide-[#f0f0f0]">
      {items.map((a, i) => (
        <li key={i}>
          <a href={a.link || "#"} target="_blank" rel="noopener noreferrer" className="flex items-start gap-2 px-3 py-1.5 text-sm text-[#333] hover:bg-[#f7fdf7]">
            <span className="mt-0.5" style={{ color: dot }}>›</span>
            <span className="flex-1">{a.title}<span className="ml-1.5 text-xs text-[#999]">{a.source}</span></span>
          </a>
        </li>
      ))}
    </ul>
  );
}

function Badge({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5" style={{ borderColor: `${color}44`, background: `${color}0d` }}>
      <span className="text-[11px] text-[#888]">{label}</span>
      <b className="text-sm" style={{ color }}>{value}</b>
    </span>
  );
}

// 엑셀 톤: 모든 블록 헤더를 연초록 배경 + 진초록 글씨로 통일(색 prop은 무시).
function Block({ title, children }: { title: string; color?: string; fg?: string; children: React.ReactNode }) {
  return (
    <section className="overflow-hidden rounded border border-[#d0d0d0] bg-white shadow-sm">
      <div className="border-b border-[#d0d0d0] bg-[#e8efe8] px-3 py-1.5 text-sm font-bold text-[#1f5132]">{title}</div>
      {children}
    </section>
  );
}

function Th({ children, right }: { children?: React.ReactNode; right?: boolean }) {
  return <th className={`border border-[#d0d0d0] px-2 py-1.5 font-semibold ${right ? "text-right" : "text-left"}`}>{children}</th>;
}

function Sheet({ right, children }: { right: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
        <span className="flex items-center gap-2 text-sm font-semibold">글로벌 자금 흐름.xlsx</span>
        {right}
      </div>
      {children}
    </div>
  );
}
