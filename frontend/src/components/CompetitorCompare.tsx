"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api, PeerCompare, PeerGlobal, PeerNews, UEProduct } from "@/lib/api";

const GREEN = "#217346";

// 경쟁군 색 팔레트 — 기준 제품은 항상 브랜드 그린(팔레트[0]).
// 주가선·변동성 막대·뉴스 칩이 같은 회사면 같은 색을 쓰도록 티커→색 매핑.
const PALETTE = ["#217346", "#2563eb", "#d97706", "#dc2626", "#7c3aed", "#0891b2", "#db2777", "#65a30d"];

function pct(v: number | null | undefined, d = 1): string {
  return v == null ? "—" : `${(v * 100).toFixed(d)}%`;
}
function won(v: number | null | undefined): string {
  return v == null ? "—" : `${Math.round(v).toLocaleString("ko-KR")}원`;
}
// 시가총액(USD) 축약: $262B / $1.5B / $340M
function usd(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${Math.round(v).toLocaleString("en-US")}`;
}
function ago(ts: number | null): string {
  if (!ts) return "";
  const s = Date.now() / 1000 - ts;
  if (s < 3600) return `${Math.max(1, Math.floor(s / 60))}분 전`;
  if (s < 86400) return `${Math.floor(s / 3600)}시간 전`;
  return `${Math.floor(s / 86400)}일 전`;
}

// 원자재 방향 칩(원가 관점: up=악재 빨강, down=호재 파랑)
function DirChip({ dir, chg }: { dir?: string | null; chg?: number | null }) {
  if (!dir || chg == null) return null;
  const up = dir === "up";
  const flat = dir === "flat";
  const color = flat ? "#868e96" : up ? "#c92a2a" : "#1971c2";
  const arrow = flat ? "→" : up ? "▲" : "▼";
  return (
    <span style={{ color }} className="whitespace-nowrap text-[10px] font-semibold">
      {arrow}{chg > 0 ? "+" : ""}{(chg * 100).toFixed(0)}%
    </span>
  );
}

export function CompetitorCompare() {
  const [products, setProducts] = useState<UEProduct[]>([]);
  const [sel, setSel] = useState<string>("");
  const [sectorFilter, setSectorFilter] = useState<string>("전체");
  const [data, setData] = useState<PeerCompare | null>(null);
  const [news, setNews] = useState<PeerNews | null>(null);
  const [glob, setGlob] = useState<PeerGlobal | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [newsLoading, setNewsLoading] = useState(false);
  const [globLoading, setGlobLoading] = useState(false);

  // 제품 목록 로드 → 기준 제품 자동선택(원가모델이 실측인 첫 제품)
  useEffect(() => {
    let alive = true;
    api.unitEconomicsProducts()
      .then((r) => {
        if (!alive) return;
        setProducts(r.products);
        if (r.products.length) setSel(r.products[0].id);
      })
      .catch((e) => alive && setErr(e?.message ?? "제품 목록 실패"));
    return () => { alive = false; };
  }, []);

  // 원가 + 주가 변동성
  useEffect(() => {
    if (!sel) return;
    let alive = true;
    setLoading(true);
    setErr("");
    api.peerCompare(sel)
      .then((r) => alive && setData(r))
      .catch((e) => alive && setErr(e?.message ?? "비교 실패"))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [sel]);

  // 경쟁사 뉴스 (별도 스피너)
  useEffect(() => {
    if (!sel) return;
    let alive = true;
    setNewsLoading(true);
    setNews(null);
    api.peerNews(sel)
      .then((r) => alive && setNews(r))
      .catch(() => {})
      .finally(() => alive && setNewsLoading(false));
    return () => { alive = false; };
  }, [sel]);

  // 글로벌 시장 규모 (별도 스피너)
  useEffect(() => {
    if (!sel) return;
    let alive = true;
    setGlobLoading(true);
    setGlob(null);
    api.peerGlobal(sel)
      .then((r) => alive && setGlob(r))
      .catch(() => {})
      .finally(() => alive && setGlobLoading(false));
    return () => { alive = false; };
  }, [sel]);

  // 티커 → 색 (기준 제품이 맨 앞이라 그린)
  const colorByTicker = useMemo(() => {
    const m: Record<string, string> = {};
    let i = 0;
    for (const p of data?.peers ?? []) {
      if (!(p.ticker in m)) m[p.ticker] = PALETTE[i++ % PALETTE.length];
    }
    return m;
  }, [data]);

  // 주가 오버레이용 데이터 재구성
  const priceRows = useMemo(() => {
    if (!data) return [];
    const { dates, series } = data.price;
    return dates.map((d, i) => {
      const row: Record<string, number | string | null> = { date: d };
      for (const tk of Object.keys(series)) row[tk] = series[tk][i];
      return row;
    });
  }, [data]);

  // 업종 필터 + 그룹핑 (원가분해와 동일 패턴)
  const sectors = Array.from(new Set(products.map((p) => p.sector)));
  const visible = sectorFilter === "전체" ? products : products.filter((p) => p.sector === sectorFilter);
  const grouped: [string, UEProduct[]][] = [];
  for (const p of visible) {
    let g = grouped.find((x) => x[0] === p.sector);
    if (!g) { g = [p.sector, []]; grouped.push(g); }
    g[1].push(p);
  }

  const peers = data?.peers ?? [];
  const priceTickers = data ? Object.keys(data.price.series) : [];
  const maxVol = Math.max(0.0001, ...peers.map((p) => p.annual_vol ?? 0));

  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      {/* 헤더 + 제품 선택 */}
      <div className="flex flex-wrap items-center justify-between gap-2 bg-[#217346] px-4 py-2 text-white">
        <span className="text-sm font-semibold">
          경쟁사 비교.xlsx — 원가·주가 변동성·뉴스 한눈에
          {data && (
            <span className="ml-2 text-[11px] font-normal text-white/70">
              {data.sector} · 경쟁 {peers.length}곳 · 기준 {data.as_of}
            </span>
          )}
        </span>
        <div className="flex items-center gap-1.5">
          <select
            value={sectorFilter}
            onChange={(e) => {
              const sec = e.target.value;
              setSectorFilter(sec);
              const first = products.find((p) => sec === "전체" || p.sector === sec);
              if (first && sec !== "전체") setSel(first.id);
            }}
            className="rounded border border-white/30 bg-white/10 px-2 py-1 text-xs text-white outline-none [&>option]:text-black"
          >
            <option key="all" value="전체">🗂 전체 업종</option>
            {sectors.filter(Boolean).map((sec) => (
              <option key={sec} value={sec}>{sec}</option>
            ))}
          </select>
          <select
            value={sel}
            onChange={(e) => setSel(e.target.value)}
            className="max-w-[240px] rounded border border-white/30 bg-white/10 px-2 py-1 text-xs text-white outline-none [&>optgroup]:text-black [&>option]:text-black"
          >
            {grouped.map(([sec, ps]) => (
              <optgroup key={sec || "기타"} label={sec || "기타"}>
                {ps.map((p) => (
                  <option key={p.id} value={p.id}>{p.company} · {p.product}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>
      </div>

      {err && !data ? (
        <div className="py-20 text-center text-sm text-rose-600">{err}</div>
      ) : !data ? (
        <div className="flex flex-col items-center gap-3 py-24 text-sm text-[#888]">
          <span className="h-7 w-7 animate-spin rounded-full border-2 border-[#d0d0d0] border-t-[#217346]" />
          경쟁사 비교 계산 중…
        </div>
      ) : peers.length <= 1 ? (
        <div className="py-20 text-center text-sm text-[#888]">
          이 제품과 같은 업종({data.sector})으로 비교할 경쟁 제품이 없습니다.
        </div>
      ) : (
        <div className="max-h-[calc(100vh-150px)] space-y-6 overflow-auto p-4">
          {loading && <div className="text-xs text-[#888]">갱신 중…</div>}

          {/* ① 원가 구조 비교 ─────────────────────────────────────── */}
          <section>
            <SectionTitle no="1" title="원가 구조 비교" hint="출고가(=회사 인식 매출) 100% 기준. DART 손익계산서 실측 원가율·판관비율·영업이익률." />
            <div className="space-y-2">
              {peers.map((p) => {
                const cogs = p.cogs_ratio ?? 0;
                const sga = p.sga_ratio ?? 0;
                const op = p.op_margin ?? 0;
                const total = cogs + sga + Math.max(op, 0) || 1;
                const seg = (v: number) => `${(Math.max(v, 0) / total) * 100}%`;
                return (
                  <div key={p.id} className={`rounded border p-2.5 ${p.is_base ? "border-[#217346] bg-[#f2f8f4]" : "border-[#e5e5e5] bg-white"}`}>
                    <div className="mb-1.5 flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5 text-[13px]">
                        <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: colorByTicker[p.ticker] }} />
                        <span className="font-semibold text-[#333]">{p.company}</span>
                        <span className="text-[#888]">{p.product}</span>
                        {p.is_base && <span className="rounded bg-[#217346] px-1 text-[10px] font-bold text-white">기준</span>}
                        <span className="rounded bg-[#eef1ef] px-1 text-[10px] text-[#667]">{p.basis_source}</span>
                      </div>
                      <div className="flex items-center gap-3 text-[11px] text-[#555]">
                        <span>소비자가 <b className="text-[#333]">{won(p.retail_price)}</b></span>
                        <span>개당이익 <b style={{ color: (p.profit_per_unit ?? 0) >= 0 ? GREEN : "#c92a2a" }}>{won(p.profit_per_unit)}</b></span>
                      </div>
                    </div>
                    {/* 스택 막대: 원가 / 판관 / 영업이익 */}
                    <div className="flex h-5 w-full overflow-hidden rounded bg-[#f0f0f0] text-[10px] font-semibold text-white">
                      <div className="flex items-center justify-center" style={{ width: seg(cogs), background: "#40916c" }} title={`원가율 ${pct(cogs)}`}>
                        {cogs > 0.12 && `원가 ${pct(cogs, 0)}`}
                      </div>
                      <div className="flex items-center justify-center" style={{ width: seg(sga), background: "#f4a259" }} title={`판관비율 ${pct(sga)}`}>
                        {sga > 0.1 && `판관 ${pct(sga, 0)}`}
                      </div>
                      <div className="flex items-center justify-center" style={{ width: seg(op), background: "#1b4332" }} title={`영업이익률 ${pct(op)}`}>
                        {op > 0.08 && `이익 ${pct(op, 0)}`}
                      </div>
                      {op < 0 && <div className="flex items-center px-1 text-[#c92a2a]">영업적자 {pct(op, 0)}</div>}
                    </div>
                    {/* 핵심 원자재(오르내림) */}
                    {p.top_materials.length > 0 && (
                      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-[#667]">
                        <span className="text-[#999]">주요 원자재:</span>
                        {p.top_materials.map((m, i) => (
                          <span key={i} className="inline-flex items-center gap-1">
                            {m.item}{m.commodity ? `(${m.commodity})` : ""} <DirChip dir={m.direction} chg={m.chg_1y} />
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>

          {/* ② 주가 변동성 ────────────────────────────────────────── */}
          <section>
            <SectionTitle no="2" title="주가 변동성" hint={`최근 ${data.window_days}거래일. 시작=100 리베이스로 종목을 한 축에서 비교.`} />
            <div className="rounded border border-[#e5e5e5] p-2">
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={priceRows} margin={{ top: 8, right: 12, bottom: 4, left: -12 }}>
                  <CartesianGrid stroke="#f0f0f0" vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#999" }} minTickGap={48}
                    tickFormatter={(d: string) => d.slice(5)} />
                  <YAxis tick={{ fontSize: 10, fill: "#999" }} domain={["dataMin - 3", "dataMax + 3"]}
                    tickFormatter={(v: number) => v.toFixed(0)} width={40} />
                  <Tooltip
                    contentStyle={{ fontSize: 12, borderRadius: 6, border: "1px solid #ddd" }}
                    formatter={(v, name) => [v == null ? "—" : Number(v).toFixed(1), data.price.meta[String(name)]?.company ?? String(name)]}
                    labelStyle={{ color: "#666" }}
                  />
                  {priceTickers.map((tk) => (
                    <Line key={tk} type="monotone" dataKey={tk} stroke={colorByTicker[tk] ?? "#999"}
                      strokeWidth={data.price.meta[tk]?.is_base ? 2.6 : 1.4}
                      dot={false} connectNulls isAnimationActive={false} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
              {/* 변동성·수익률 랭킹 */}
              <div className="mt-2 space-y-1 border-t border-[#f0f0f0] pt-2">
                {[...peers].filter((p, i, a) => a.findIndex((x) => x.ticker === p.ticker) === i)
                  .sort((a, b) => (b.annual_vol ?? 0) - (a.annual_vol ?? 0))
                  .map((p) => (
                    <div key={p.ticker} className="flex items-center gap-2 text-[11px]">
                      <span className="w-20 shrink-0 truncate text-[#444]">{p.company}</span>
                      <div className="h-3 flex-1 rounded bg-[#f2f2f2]">
                        <div className="h-3 rounded" style={{ width: `${((p.annual_vol ?? 0) / maxVol) * 100}%`, background: colorByTicker[p.ticker] }} />
                      </div>
                      <span className="w-24 shrink-0 text-right text-[#666]">
                        변동성 <b className="text-[#333]">{pct(p.annual_vol, 0)}</b>
                      </span>
                      <span className="w-20 shrink-0 text-right" style={{ color: (p.ret_pct ?? 0) >= 0 ? "#c92a2a" : "#1971c2" }}>
                        {p.ret_pct == null ? "—" : `${p.ret_pct > 0 ? "+" : ""}${p.ret_pct}%`}
                      </span>
                    </div>
                  ))}
                <div className="pt-0.5 text-[10px] text-[#aaa]">막대=연율 변동성(높을수록 출렁임) · 우측=기간 수익률(빨강 상승/파랑 하락)</div>
              </div>
            </div>
          </section>

          {/* ③ 글로벌 시장 규모 ───────────────────────────────────── */}
          <section>
            <SectionTitle no="3" title="글로벌 시장 규모 비교" hint="같은 제품군의 국내 경쟁사 + 글로벌 리더를 시가총액(USD)으로. '리더만큼 크면 몇 배 여력'." />
            {globLoading ? (
              <div className="flex items-center gap-2 py-6 text-xs text-[#888]">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-[#e0e0e0] border-t-[#217346]" />
                시가총액 집계 중…
              </div>
            ) : !glob || glob.members.length === 0 ? (
              <div className="py-6 text-center text-xs text-[#999]">글로벌 비교 데이터가 없습니다.</div>
            ) : (
              <GlobalPanel g={glob} />
            )}
          </section>

          {/* ④ 경쟁사 뉴스 ────────────────────────────────────────── */}
          <section>
            <SectionTitle no="4" title="경쟁사 뉴스 취합" hint="경쟁군 회사들의 최신 뉴스를 한데 모아 최신순으로. 회사 색으로 구분." />
            {newsLoading ? (
              <div className="flex items-center gap-2 py-6 text-xs text-[#888]">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-[#e0e0e0] border-t-[#217346]" />
                뉴스 수집 중…
              </div>
            ) : !news || news.items.length === 0 ? (
              <div className="py-6 text-center text-xs text-[#999]">수집된 뉴스가 없습니다.</div>
            ) : (
              <div className="divide-y divide-[#f2f2f2] rounded border border-[#e5e5e5]">
                {news.items.slice(0, 40).map((it, i) => (
                  <a key={i} href={it.link ?? "#"} target="_blank" rel="noopener noreferrer"
                    className="flex items-start gap-2 px-3 py-2 hover:bg-[#f7faf8]">
                    <span className="mt-0.5 inline-block h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: colorByTicker[it.ticker] ?? "#bbb" }} />
                    <span className="min-w-0 flex-1">
                      <span className="text-[13px] leading-snug text-[#222]">{it.title}</span>
                      <span className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[11px] text-[#999]">
                        <span className="font-semibold" style={{ color: colorByTicker[it.ticker] ?? "#666" }}>{it.company}</span>
                        {it.scope === "global" && <span className="rounded bg-[#eef2ff] px-1 text-[10px] text-[#4560c0]">글로벌</span>}
                        <span>{it.source}</span>
                        <span>· {ago(it.ts)}</span>
                      </span>
                    </span>
                  </a>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

function GlobalPanel({ g }: { g: PeerGlobal }) {
  const maxCap = Math.max(1, ...g.members.map((m) => m.market_cap_usd ?? 0));
  return (
    <div className="rounded border border-[#e5e5e5] p-3">
      {/* 여력 콜아웃 */}
      {g.headroom_x && g.base && g.leader ? (
        <div className="mb-3 rounded bg-[#f2f8f4] px-3 py-2 text-[13px] text-[#245]">
          <b className="text-[#217346]">{g.base.name}</b>이(가) 리더 <b>{g.leader.name}</b>만큼 커지려면{" "}
          <b className="text-[#c0392b]">{g.headroom_x}배</b> 여력{" "}
          <span className="text-[#888]">({usd(g.base.market_cap_usd)} → {usd(g.leader.market_cap_usd)})</span>
        </div>
      ) : null}

      {/* 시가총액 막대 */}
      <div className="space-y-1">
        {g.members.map((m) => {
          const cap = m.market_cap_usd;
          const w = cap ? Math.max(1.5, (cap / maxCap) * 100) : 0;
          const color = m.is_base ? "#217346" : m.market === "KR" ? "#74c69d" : "#2563eb";
          return (
            <div key={`${m.market}-${m.code}`} className={`flex items-center gap-2 rounded px-1 py-0.5 text-[12px] ${m.is_base ? "bg-[#f2f8f4]" : ""}`}>
              <span className="flex w-40 shrink-0 items-center gap-1 truncate">
                {m.market === "GLOBAL"
                  ? <span className="rounded bg-[#eef2ff] px-1 text-[9px] font-bold text-[#4560c0]">{m.country}</span>
                  : <span className="rounded bg-[#eef7f0] px-1 text-[9px] font-bold text-[#217346]">KR</span>}
                <span className={`truncate ${m.is_base ? "font-bold text-[#217346]" : "text-[#333]"}`}>{m.name}</span>
                {m.is_leader && <span title="시총 1위">👑</span>}
                {m.is_base && <span className="rounded bg-[#217346] px-1 text-[9px] font-bold text-white">기준</span>}
              </span>
              <div className="h-4 flex-1 rounded bg-[#f4f4f4]">
                {cap ? <div className="h-4 rounded" style={{ width: `${w}%`, background: color }} /> : null}
              </div>
              <span className="w-16 shrink-0 text-right font-semibold text-[#333]">{usd(cap)}</span>
              <span className="w-14 shrink-0 text-right text-[10px]" style={{ color: (m.op_margin ?? 0) >= 0 ? "#217346" : "#c92a2a" }}>
                {m.op_margin == null ? "" : `이익 ${m.op_margin.toFixed(0)}%`}
              </span>
            </div>
          );
        })}
      </div>

      {/* 데이터 소스 안내 */}
      {!g.foreign_enabled && (
        <div className="mt-2 rounded bg-[#fff7ed] px-2 py-1.5 text-[11px] text-[#9a6b2f]">
          ⚠ 글로벌 리더 시가총액이 아직 비어 있습니다 — Finnhub API 키를 <code className="rounded bg-[#f3e6d0] px-1 font-mono">backend/.env</code>에 넣고 서버를 재시작하면 코카콜라 등 해외 시총이 채워집니다.
        </div>
      )}
      {g.foreign_enabled && g.foreign_missing > 0 && (
        <div className="mt-2 text-[11px] text-[#aaa]">글로벌 {g.foreign_missing}곳은 아직 갱신 대기 중(Finnhub 일 1회 갱신).</div>
      )}
    </div>
  );
}

function SectionTitle({ no, title, hint }: { no: string; title: string; hint: string }) {
  return (
    <div className="mb-2">
      <div className="flex items-center gap-2">
        <span className="flex h-5 w-5 items-center justify-center rounded bg-[#217346] text-[11px] font-bold text-white">{no}</span>
        <span className="text-sm font-bold text-[#217346]">{title}</span>
      </div>
      <div className="mt-0.5 pl-7 text-[11px] text-[#999]">{hint}</div>
    </div>
  );
}
