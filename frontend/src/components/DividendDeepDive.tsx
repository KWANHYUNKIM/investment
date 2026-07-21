"use client";

import { useEffect, useMemo, useState } from "react";
import { api, DividendStock, DividendDetail, DDMetric, DDCrisis, RoyaltyRow } from "@/lib/api";

const GREEN = "#217346";
const RED = "#c0392b";

type Currency = "KRW" | "USD";

// 통화별 가격/배당 표기
function money(v: number | null | undefined, cur: Currency): string {
  if (v == null) return "—";
  if (cur === "USD") return `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  return `${Math.round(v).toLocaleString("ko-KR")}원`;
}
// 재무 규모(매출·순이익·현금흐름) — 단위(억원/백만$)에 맞춰 표기
function magnitude(v: number | null | undefined, unit: string): string {
  if (v == null) return "—";
  if (unit === "백만$") {
    const a = Math.abs(v);
    if (a >= 1000) return `$${(v / 1000).toLocaleString("en-US", { maximumFractionDigits: 1 })}B`;
    return `$${Math.round(v).toLocaleString("en-US")}M`;
  }
  // 억원
  const a = Math.abs(v);
  if (a >= 10000) return `${(v / 10000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}조`;
  return `${Math.round(v).toLocaleString("ko-KR")}억`;
}

const TREND_STYLE: Record<string, { c: string; label: string }> = {
  증가: { c: GREEN, label: "▲ 증가" },
  감소: { c: RED, label: "▼ 감소" },
  정체: { c: "#999", label: "→ 정체" },
};
const VERDICT_STYLE: Record<string, { c: string; bg: string }> = {
  증가: { c: "#137333", bg: "#e6f4ea" },
  유지: { c: "#555", bg: "#eef1ef" },
  삭감: { c: "#b06000", bg: "#fdf0e2" },
  중단: { c: "#c5221f", bg: "#fce8e6" },
};

function MetricCard({ title, m }: { title: string; m: DDMetric }) {
  const t = m.trend ? TREND_STYLE[m.trend] : null;
  const avail = m.available !== false;
  return (
    <div className="rounded-md border border-[#e5e5e5] bg-white p-3">
      <div className="flex items-baseline justify-between">
        <span className="text-[13px] font-bold text-[#333]">{title}</span>
        {avail && t && <span className="text-[11px] font-bold" style={{ color: t.c }}>{t.label}</span>}
      </div>
      <div className="mt-0.5 text-[11px] text-[#999]">{m.why}</div>
      {!avail ? (
        <div className="mt-3 rounded bg-[#f7f7f7] px-2 py-3 text-center text-[11px] text-[#aaa]">{m.note ?? "데이터 없음"}</div>
      ) : (
        <>
          <div className="mt-2 text-lg font-bold tabular-nums text-[#1f1f1f]">
            {m.latest ? magnitude(m.latest.value, m.unit) : "—"}
            {m.latest && <span className="ml-1 text-[10px] font-normal text-[#aaa]">{m.latest.year}</span>}
          </div>
          <div className="mt-2 flex items-end gap-1" style={{ height: 34 }}>
            {m.series.map((s) => {
              const max = Math.max(...m.series.map((x) => Math.abs(x.value)), 1);
              const h = Math.max(3, (Math.abs(s.value) / max) * 32);
              return (
                <div key={s.year} className="flex flex-1 flex-col items-center gap-0.5">
                  <div className="w-full rounded-sm" style={{ height: h, backgroundColor: s.value < 0 ? RED : GREEN, opacity: 0.35 + 0.65 * (h / 32) }} title={`${s.year}: ${magnitude(s.value, m.unit)}`} />
                  <span className="text-[8px] text-[#bbb]">{String(s.year).slice(2)}</span>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

function CrisisCard({ c, cur }: { c: DDCrisis; cur: Currency }) {
  const hasData = c.rows.some((r) => r.dps != null);
  return (
    <div className="rounded-md border border-[#e5e5e5] bg-white">
      <div className="border-b border-[#eee] bg-[#faf7f2] px-3 py-1.5 text-[12px] font-bold text-[#7a5c1e]">{c.label}</div>
      {!hasData ? (
        <div className="px-3 py-5 text-center text-[11px] text-[#aa9]">{c.summary}</div>
      ) : (
        <>
          <table className="w-full text-[12px]">
            <tbody>
              {c.rows.map((r) => {
                const vs = r.verdict ? VERDICT_STYLE[r.verdict] : null;
                return (
                  <tr key={r.year} className="border-t border-[#f4f4f4]">
                    <td className="px-3 py-1.5 text-[#888]">{r.year}</td>
                    <td className="px-3 py-1.5 text-right font-semibold tabular-nums text-[#222]">{r.dps != null ? money(r.dps, cur) : "—"}</td>
                    <td className="px-2 py-1.5 text-right">{vs && <span className="rounded px-1.5 py-0.5 text-[10px] font-bold" style={{ color: vs.c, backgroundColor: vs.bg }}>{r.verdict}</span>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="border-t border-[#f0f0f0] px-3 py-1.5 text-[10px] font-medium" style={{ color: c.summary.includes("삭감") ? "#b06000" : GREEN }}>{c.summary}</div>
        </>
      )}
    </div>
  );
}

type UsItem = { ticker: string; name: string; sector?: string; yield?: number | null };

export function DividendDeepDive() {
  const [market, setMarket] = useState<"KR" | "US">("KR");
  const [uni, setUni] = useState<DividendStock[]>([]);
  const [usUni, setUsUni] = useState<UsItem[]>([]);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [ticker, setTicker] = useState<string | null>(null);
  const [d, setD] = useState<DividendDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => { api.dividendUniverse().then((r) => setUni(r.stocks)).catch(() => {}); }, []);
  useEffect(() => {
    api.dividendRoyalty().then((r) => {
      const seen = new Set<string>();
      const list: UsItem[] = [];
      [...r.kings.rows, ...r.aristocrats.rows, ...r.monthly.rows].forEach((x: RoyaltyRow) => {
        if (seen.has(x.ticker)) return;
        seen.add(x.ticker);
        list.push({ ticker: x.ticker, name: x.name, sector: x.sector, yield: x.yield });
      });
      setUsUni(list);
    }).catch(() => {});
  }, []);

  const matches = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return [];
    if (market === "KR") {
      return uni.filter((x) => x.name.toLowerCase().includes(s) || x.ticker.includes(s)).slice(0, 12)
        .map((x) => ({ ticker: x.ticker, name: x.name, sector: x.sector ?? undefined, yield: x.div_yield, close: x.close }));
    }
    const list = usUni.filter((x) => x.name.toLowerCase().includes(s) || x.ticker.toLowerCase().includes(s)).slice(0, 12)
      .map((x) => ({ ticker: x.ticker, name: x.name, sector: x.sector, yield: x.yield, close: null as number | null }));
    // 목록에 없어도 티커 직접 조회 허용
    const up = q.trim().toUpperCase();
    if (/^[A-Z.]{1,6}$/.test(up) && !list.some((x) => x.ticker === up)) {
      list.unshift({ ticker: up, name: `${up} (직접 조회)`, sector: undefined, yield: null, close: null });
    }
    return list;
  }, [q, uni, usUni, market]);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true); setErr(""); setD(null);
    api.dividendDetail(ticker).then(setD).catch((e) => setErr(e?.message ?? "불러오기 실패")).finally(() => setLoading(false));
  }, [ticker]);

  const pick = (t: string, name: string) => { setQ(name); setOpen(false); setTicker(t); };
  const switchMarket = (m: "KR" | "US") => { setMarket(m); setQ(""); setTicker(null); setD(null); };

  const cur: Currency = d?.currency ?? "KRW";
  const dv = d?.dividend;
  const cl = d?.checklist;

  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
        <span className="text-sm font-semibold">배당 종목 진단 — 배당률 · 투자 전 체크리스트 · 3대 위기 배당</span>
      </div>

      <div className="p-4">
        {/* 시장 토글 + 검색 */}
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex overflow-hidden rounded border border-[#cdcdcd] text-[13px]">
            {(["KR", "US"] as const).map((m) => (
              <button key={m} onClick={() => switchMarket(m)}
                className={`px-3 py-1.5 font-semibold transition ${market === m ? "bg-[#217346] text-white" : "bg-white text-[#666] hover:bg-[#f2f2f2]"}`}>
                {m === "KR" ? "🇰🇷 한국" : "🇺🇸 미국"}
              </button>
            ))}
          </div>
          <div className="relative min-w-[240px] flex-1 max-w-md">
            <label className="text-xs text-[#555]">종목 검색 <span className="text-[10px] text-[#aaa]">{market === "KR" ? "(이름·종목코드)" : "(영문명·티커, 예: KO, JNJ, Realty)"}</span>
              <input value={q} onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)}
                placeholder={market === "KR" ? "예: 삼성전자, KT&G, 005930" : "예: Coca-Cola, KO, Realty Income"}
                className="mt-0.5 block w-full rounded border border-[#cdcdcd] px-2.5 py-1.5 text-sm outline-none focus:border-[#217346]" />
            </label>
            {open && matches.length > 0 && (
              <div className="absolute z-10 mt-1 max-h-64 w-full overflow-y-auto rounded border border-[#d0d0d0] bg-white shadow-lg">
                {matches.map((x) => (
                  <button key={x.ticker} onClick={() => pick(x.ticker, x.name)} className="grid w-full grid-cols-[1fr_auto] items-center gap-x-2 border-b border-[#f2f2f2] px-2.5 py-1.5 text-left text-[12px] hover:bg-[#f5faf7]">
                    <span className="truncate font-semibold text-[#1f1f1f]">{x.name} <span className="text-[9px] font-normal text-[#aaa]">{x.ticker}{x.sector ? ` · ${x.sector}` : ""}</span></span>
                    <span className="w-14 text-right font-bold tabular-nums" style={{ color: x.yield ? RED : "#bbb" }}>{x.yield ? `${x.yield}%` : ""}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {!ticker && <div className="mt-8 mb-4 text-center text-sm text-[#aaa]">종목을 검색해 배당 건전성을 진단하세요. {market === "US" && "미국은 SEC EDGAR 실데이터 기반입니다."}</div>}
        {loading && <div className="flex items-center gap-2 py-16 text-sm text-[#888]"><span className="h-5 w-5 animate-spin rounded-full border-2 border-[#d0d0d0] border-t-[#217346]" /> 진단 중…</div>}
        {err && <div className="py-10 text-center text-sm text-rose-600">{err}</div>}

        {d && dv && (
          <div className="mt-4 flex flex-col gap-5">
            {/* 배당률 히어로 */}
            <div className="flex flex-wrap items-center gap-x-8 gap-y-3 rounded-md border border-[#e5e5e5] bg-[#f8faf9] px-5 py-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-lg font-bold text-[#1f1f1f]">{d.name}</span>
                  <span className="text-xs font-normal text-[#aaa]">{d.ticker}{d.sector ? ` · ${d.sector}` : ""}</span>
                  {d.royalty && <span className="rounded bg-[#fff4d6] px-1.5 py-0.5 text-[10px] font-bold text-[#8a6d1a]">👑 {d.royalty.tier_label} {d.royalty.years}년</span>}
                </div>
                <div className="mt-0.5 text-xs text-[#888]">{dv.formula}</div>
              </div>
              <div className="flex items-end gap-1">
                <span className="text-4xl font-extrabold tabular-nums" style={{ color: RED }}>{dv.div_yield != null ? dv.div_yield : "—"}</span>
                <span className="mb-1 text-lg font-bold" style={{ color: RED }}>%</span>
              </div>
              <div className="flex gap-6 text-[13px]">
                <div><div className="text-[10px] text-[#999]">주당배당금{dv.dps_estimated ? "(추정)" : ""}</div><div className="font-bold tabular-nums text-[#217346]">{money(dv.dps, cur)}</div></div>
                <div><div className="text-[10px] text-[#999]">현재가</div><div className="font-bold tabular-nums text-[#333]">{money(d.close, cur)}</div></div>
              </div>
            </div>

            {/* 투자 전 체크리스트 */}
            {cl ? (
              <div>
                <div className="mb-2 border-l-4 border-[#217346] pl-2 text-sm font-bold text-[#217346]">배당 투자 전 체크리스트</div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  <MetricCard title="매출" m={cl.revenue} />
                  <MetricCard title="순이익" m={cl.net_income} />
                  <MetricCard title="영업현금흐름" m={cl.op_cash_flow} />
                  <div className="rounded-md border border-[#e5e5e5] bg-white p-3">
                    <span className="text-[13px] font-bold text-[#333]">배당연수</span>
                    <div className="mt-0.5 text-[11px] text-[#999]">{cl.div_years.why}</div>
                    <div className="mt-2 text-lg font-bold tabular-nums text-[#1f1f1f]">{cl.div_years.value}년<span className="ml-1 text-[10px] font-normal text-[#aaa]">연속 배당</span></div>
                    {cl.div_years.window && <div className="mt-1 text-[10px] text-[#bbb]">{cl.div_years.window[0]}~{cl.div_years.window[1]} 기준</div>}
                  </div>
                  <div className="rounded-md border border-[#e5e5e5] bg-white p-3">
                    <span className="text-[13px] font-bold text-[#333]">배당성장률</span>
                    <div className="mt-0.5 text-[11px] text-[#999]">{cl.div_growth.why}</div>
                    <div className="mt-2 text-lg font-bold tabular-nums" style={{ color: (cl.div_growth.cagr ?? 0) > 0 ? GREEN : (cl.div_growth.cagr ?? 0) < 0 ? RED : "#333" }}>
                      {cl.div_growth.cagr != null ? `${cl.div_growth.cagr > 0 ? "+" : ""}${cl.div_growth.cagr}%` : "—"}
                      <span className="ml-1 text-[10px] font-normal text-[#aaa]">연평균(CAGR)</span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-x-2 gap-y-0.5 text-[10px] text-[#999]">
                      {cl.div_growth.series.slice(-6).map((s) => <span key={s.year}>{String(s.year).slice(2)}: <b className="text-[#555]">{money(s.dps, cur)}</b></span>)}
                    </div>
                  </div>
                  {cl.roe.series.length > 0 && <MetricCard title="ROE (자기자본이익률)" m={{ ...cl.roe, why: "투입 자본 대비 얼마나 버는지" }} />}
                </div>
              </div>
            ) : (
              <div className="rounded-md border border-dashed border-[#ddd] bg-[#fafafa] px-4 py-5 text-center text-[12px] text-[#999]">{d.note}</div>
            )}

            {/* 3대 위기 배당 */}
            <div>
              <div className="mb-2 border-l-4 border-[#b06000] pl-2 text-sm font-bold text-[#b06000]">3대 경제위기 배당 방어력</div>
              {d.crises && d.crises.available ? (
                <>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                    {d.crises.crises.map((c) => <CrisisCard key={c.key} c={c} cur={cur} />)}
                  </div>
                  {(d.crises.notes || d.crises.sources?.length > 0) && (
                    <div className="mt-2 text-[10px] leading-relaxed text-[#bbb]">
                      {d.crises.notes && <div>※ {d.crises.notes}</div>}
                      {d.crises.sources?.length > 0 && <div>출처: {d.crises.sources.join(", ")}</div>}
                    </div>
                  )}
                </>
              ) : (
                <div className="rounded-md border border-dashed border-[#ddd] bg-[#fafafa] px-4 py-6 text-center text-[12px] text-[#999]">
                  이 종목은 아직 위기 배당 데이터가 없습니다.
                </div>
              )}
            </div>

            <div className="text-[10px] leading-relaxed text-[#bbb]">{d.note}</div>
          </div>
        )}
      </div>
    </div>
  );
}
