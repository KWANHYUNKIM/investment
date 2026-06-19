"use client";

import { useEffect, useState, ReactNode } from "react";
import {
  api,
  DailyArchive,
  MoverRow,
  ArchiveStock,
  InvestorDriver,
  InvestorDay,
  MacroDriver,
  BrokerHouse,
  RateLayer,
  ForeignView as ForeignViewType,
  CrossAssetLayer,
  CrossAsset,
} from "@/lib/api";
import { won, manShares } from "@/lib/format";
import { AssetDetailModal } from "./AssetDetailModal";

// KR convention: red = up / buy, blue = down / sell.
const RED = "#c92a2a";
const BLUE = "#1971c2";

// Conditional-format heatmap for a percent move (mirrors the 전종목 grid).
function retStyle(v: number | null | undefined): React.CSSProperties {
  if (v == null) return { color: "#bbb" };
  const a = Math.min(Math.abs(v) / 40, 1) * 0.62;
  if (v > 0) return { backgroundColor: `rgba(224,49,49,${a})`, color: a > 0.4 ? "#fff" : RED };
  if (v < 0) return { backgroundColor: `rgba(28,126,214,${a})`, color: a > 0.4 ? "#fff" : BLUE };
  return { color: "#666" };
}

export function MarketReport() {
  const [dates, setDates] = useState<string[]>([]);
  const [selected, setSelected] = useState(""); // "" = latest archived
  const [data, setData] = useState<DailyArchive | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    api
      .dailyArchiveDates()
      .then((r) => setDates(r.dates))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    setErr("");
    api
      .dailyArchive(selected || undefined)
      .then(setData)
      .catch((e) => setErr(e?.message ?? "리포트를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, [selected]);

  if (loading)
    return (
      <Sheet title="데일리리포트.xlsx">
        <div className="flex flex-col items-center gap-3 py-24 text-sm text-[#888]">
          <span className="h-7 w-7 animate-spin rounded-full border-2 border-[#d0d0d0] border-t-[#217346]" />
          데일리 리포트 불러오는 중… <span className="text-[#aaa]">(미저장 시 즉석 생성 ~20초)</span>
        </div>
      </Sheet>
    );
  if (err)
    return (
      <Sheet title="데일리리포트.xlsx">
        <div className="py-20 text-center text-sm text-rose-600">{err}</div>
      </Sheet>
    );
  if (!data) return null;

  const b = data.market.breadth;
  const total = Math.max(1, b.total);
  const macro = data.market.macro;
  const deepStocks = data.stocks.filter((s) => s.depth === "deep");
  const dateOptions = dates.length ? dates : data.date ? [data.date] : [];
  // 최신(오늘) 날짜만 실시간; 과거 날짜는 그날 마감값(아카이브)으로 고정.
  const latestDate = dates[0];
  const isLatest = !selected || (latestDate ? selected === latestDate : selected === data.date);

  return (
    <Sheet
      title="데일리리포트.xlsx"
      right={
        <div className="flex items-center gap-2">
          <span className="text-xs text-white/80">리포트 날짜</span>
          <select
            value={selected || data.date || ""}
            onChange={(e) => setSelected(e.target.value)}
            className="rounded border border-white/30 bg-white/15 px-2 py-0.5 text-xs font-semibold text-white outline-none [&>option]:text-[#1f1f1f]"
          >
            {dateOptions.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </div>
      }
    >
      {/* toolbar / scope */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-[#d0d0d0] bg-[#f3f2f1] px-3 py-1.5 text-xs text-[#555]">
        <span>
          기준일 <b className="text-[#217346]">{data.date}</b>
        </span>
        <span>
          전체 <b className="text-[#1f1f1f]">{data.scope.total.toLocaleString("ko-KR")}</b>종목 · 심층{" "}
          <b className="text-[#1f1f1f]">{data.scope.deep}</b>종목
        </span>
        {data.generated_at && <span className="text-[#999]">생성 {data.generated_at}</span>}
      </div>

      {/* 데이터 신선도 — 각 데이터가 언제 들어왔는지 모두 표시 */}
      <FreshnessBar data={data} />

      {/* formula-bar style summary */}
      {data.market.summary && (
        <div className="flex items-start gap-2 border-b border-[#d0d0d0] bg-white px-3 py-2 text-sm">
          <span className="mt-0.5 shrink-0 italic text-[#999]">fx</span>
          <p className="leading-relaxed text-[#333]">{data.market.summary}</p>
        </div>
      )}

      <div className="space-y-5 bg-[#fafafa] p-4">
        {/* ── breadth band ─────────────────────────────────── */}
        <Block label="시장 요약" color="#d9d9d9" fg="#333">
          <div className="flex flex-wrap items-end gap-6 px-3 py-3">
            <BreadthStat label="상승" value={b.up} color={RED} />
            <BreadthStat label="하락" value={b.down} color={BLUE} />
            <BreadthStat label="보합" value={b.flat} color="#888" />
            <div className="text-right">
              <div className="text-[11px] uppercase tracking-wide text-[#888]">전체</div>
              <div className="text-xl font-bold tabular-nums text-[#1f1f1f]">{b.total.toLocaleString("ko-KR")}</div>
            </div>
            <div className="ml-auto flex h-3 w-full max-w-md overflow-hidden rounded-sm border border-[#d0d0d0]">
              <div style={{ width: `${(b.up / total) * 100}%`, background: RED }} />
              <div style={{ width: `${(b.flat / total) * 100}%`, background: "#c9c9c9" }} />
              <div style={{ width: `${(b.down / total) * 100}%`, background: BLUE }} />
            </div>
          </div>
        </Block>

        {/* ── 투자자별 매매 동향 (일단위) — 누가 매입/매도했나 ─ */}
        <InvestorTrendBlock trend={data.market.investor_trend ?? []} reportDate={data.date} />

        {/* ── 크로스에셋 자금 흐름 (미국·글로벌 증시 · 금 · 비트코인) · 최신일만 실시간 ─ */}
        <CrossAssetBlock ca={data.market.cross_asset ?? null} live={isLatest} reportDate={data.date} />

        {/* ── global finance macro layer (전 세계 돈 관련 빅데이터) ─ */}
        {macro && macro.drivers.length > 0 && (
          <Block
            label={`글로벌 금융 빅데이터 · 전 세계 매크로${
              macro.pool_size ? ` (${macro.pool_size.toLocaleString("ko-KR")}건 취합)` : ""
            }`}
            color="#9dc3e6"
            fg="#1a3a5e"
          >
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-[#eaf1f8] text-xs text-[#555]">
                  <Th w="16%">이슈</Th>
                  <Th w="8%" center>방향</Th>
                  <Th w="7%" center>건수</Th>
                  <Th w="23%">주요 지역</Th>
                  <Th w="46%">대표 헤드라인 · 대표 내용 (여러 매체 취합)</Th>
                </tr>
              </thead>
              <tbody>
                {macro.drivers.map((d) => (
                  <MacroRow key={d.theme} d={d} />
                ))}
              </tbody>
            </table>

            {/* 지역별 글로벌 금융 뉴스 (모든 나라) */}
            {macro.by_region && macro.by_region.length > 0 && (
              <div className="border-t border-[#d0d0d0]">
                <div className="bg-[#f3f2f1] px-3 py-1 text-xs font-bold text-[#555]">지역별 글로벌 금융 뉴스</div>
                <div className="grid sm:grid-cols-2 xl:grid-cols-3">
                  {macro.by_region.map((r) => (
                    <div key={r.region} className="border-b border-r border-[#eee]">
                      <div className="flex items-baseline gap-1.5 bg-[#fafafa] px-3 py-1 text-xs font-bold text-[#1a3a5e]">
                        {r.region}
                        <span className="font-normal text-[#999]">{r.count}건</span>
                      </div>
                      <NewsList items={r.news.slice(0, 5)} dot="#9dc3e6" />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Block>
        )}

        {/* ── 외국인이 보는 한국 증시 + 금리 발표 일정 ─────────── */}
        <div className="grid gap-4 lg:grid-cols-2">
          {data.market.foreign_view && <ForeignViewBlock fv={data.market.foreign_view} />}
          {data.market.rates && <RatesBlock rates={data.market.rates} />}
        </div>

        {/* ── main sheet: per-stock investor reasons ────────── */}
        <Block label="거래·등락 상위 종목 · 투자자별 매매 이유" color="#a9d08e" fg="#244d1a">
          {deepStocks.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-[#888]">분석할 종목 데이터가 없습니다.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="border-collapse text-[13px]" style={{ minWidth: 1180 }}>
                {/* group header band */}
                <thead>
                  <tr>
                    <GroupTh w={36} bg="#e9e9e9" fg="#888" />
                    <GroupTh span={2} bg="#a9d08e" fg="#244d1a">종목정보</GroupTh>
                    <GroupTh span={2} bg="#d9d9d9" fg="#333">시세</GroupTh>
                    <GroupTh span={2} bg="#f4b084" fg="#7a3a0c">외국인</GroupTh>
                    <GroupTh span={2} bg="#9dc3e6" fg="#1a3a5e">개인</GroupTh>
                    <GroupTh span={2} bg="#c6e0b4" fg="#2d5016">기관</GroupTh>
                  </tr>
                  <tr className="bg-[#f0f0f0] text-xs text-[#444]">
                    <ColTh w={36} center>#</ColTh>
                    <ColTh w={150}>종목명</ColTh>
                    <ColTh w={70} center>코드</ColTh>
                    <ColTh w={92} right>현재가</ColTh>
                    <ColTh w={76} center>등락%</ColTh>
                    <ColTh w={96} center>외국인 매매</ColTh>
                    <ColTh w={210}>추정 사유</ColTh>
                    <ColTh w={96} center>개인 매매</ColTh>
                    <ColTh w={210}>추정 사유</ColTh>
                    <ColTh w={96} center>기관 매매</ColTh>
                    <ColTh w={210}>추정 사유</ColTh>
                  </tr>
                </thead>
                <tbody>
                  {deepStocks.map((s, i) => (
                    <StockRow key={s.ticker} s={s} n={i + 2} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Block>

        {/* ── 거래원 (어느 증권사 창구가 매매했는지) ────────────── */}
        <BrokerSheet stocks={deepStocks} />

        {/* ── 해외 뉴스 (종목별 글로벌 헤드라인) ───────────────── */}
        <GlobalNewsSheet stocks={deepStocks} />

        {/* ── movers ────────────────────────────────────────── */}
        <div className="grid gap-4 lg:grid-cols-2">
          <MoverSheet title="상승 상위" color="#f4b084" fg="#7a3a0c" rows={data.movers.gainers} />
          <MoverSheet title="하락 상위" color="#9dc3e6" fg="#1a3a5e" rows={data.movers.losers} />
        </div>
        <MoverSheet title="거래량 상위" color="#d9d9d9" fg="#333" rows={data.movers.most_traded} showVol />

        <p className="px-1 text-center text-xs leading-relaxed text-[#999]">
          매매 이유는 수급(네이버) · 가격 모멘텀 · 밸류에이션 · 뉴스 키워드를 조합한 <b className="text-[#666]">규칙 기반 추정</b>이며, 투자 권유가 아닙니다.
          리포트는 매 거래일 JSON으로 저장되어 과거 날짜를 다시 볼 수 있습니다.
        </p>
      </div>
    </Sheet>
  );
}

/* 데이터 신선도 바 — 각 데이터가 '언제 들어왔는지'(기준/갱신 시점) 한눈에. */
function FreshnessChip({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded border border-[#d8d8d8] bg-white px-2 py-0.5">
      <span className="text-[#888]">{label}</span>
      <b className="text-[#217346]">{value}</b>
      {sub && <span className="text-[#aaa]">{sub}</span>}
    </span>
  );
}
function FreshnessBar({ data }: { data: DailyArchive }) {
  const f = data.market.data_freshness;
  const ca = data.market.cross_asset;
  // data_freshness가 없는(기능 도입 이전) 과거 아카이브도 가진 정보로 최대한 표시.
  const priceDate = f?.price_date ?? data.date ?? "—";
  const investorDate = f?.investor_date ?? data.market.investor_trend?.[0]?.date ?? null;
  const caAsOf = f?.cross_asset_as_of ?? ca?.as_of ?? null;
  const gen = f?.report_generated ?? data.generated_at ?? null;
  return (
    <div className="flex flex-wrap items-center gap-1.5 border-b border-[#d0d0d0] bg-[#eef6f0] px-3 py-1.5 text-[11px] text-[#555]">
      <span className="font-bold text-[#217346]">최근 데이터</span>
      <FreshnessChip label="시세(가격)" value={priceDate} sub="장 마감 종가" />
      <FreshnessChip label="투자자 수급" value={investorDate ?? "—"} sub="마감후 집계·1일 지연" />
      {caAsOf && <FreshnessChip label="크로스에셋" value={caAsOf.slice(5)} sub="시세 기준" />}
      <FreshnessChip label="뉴스·매크로" value={gen ? gen.slice(5) : "—"} sub={f?.macro_pool ? `${f.macro_pool.toLocaleString("ko-KR")}건` : "리포트 생성시"} />
      {gen && <FreshnessChip label="리포트 생성" value={gen.slice(5)} />}
    </div>
  );
}

/* ── worksheet frame ──────────────────────────────────────── */
function Sheet({ title, right, children }: { title: string; right?: ReactNode; children: ReactNode }) {
  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
        <span className="flex items-center gap-2 text-sm font-semibold">
          {title}
        </span>
        {right}
      </div>
      {children}
    </div>
  );
}

/* a labelled spreadsheet block with a coloured group-header strip */
function Block({ label, color, fg, children }: { label: string; color: string; fg: string; children: ReactNode }) {
  return (
    <section className="overflow-hidden rounded border border-[#d0d0d0] bg-white shadow-sm">
      <div className="border-b border-[#d0d0d0] bg-[#e8efe8] px-3 py-1.5 text-sm font-bold text-[#1f5132]">
        {label}
      </div>
      {children}
    </section>
  );
}

function BreadthStat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-[#888]">{label}</div>
      <div className="text-xl font-bold tabular-nums" style={{ color }}>
        {value.toLocaleString("ko-KR")}
      </div>
    </div>
  );
}

/* 투자자별 매매 동향 (일단위) — 시장 전체 순매수 금액(억원). 빨강=순매수, 파랑=순매도. */
function eok(v: number | null | undefined): string {
  if (v == null) return "—";
  const s = Math.abs(v) >= 10000 ? `${(Math.abs(v) / 10000).toFixed(2)}조` : `${Math.abs(v).toLocaleString("ko-KR")}억`;
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${s}`;
}
function flowStyle(v: number | null | undefined): React.CSSProperties {
  if (v == null) return { color: "#bbb" };
  return { color: v > 0 ? RED : v < 0 ? BLUE : "#666", fontWeight: 700 };
}
// 현재(최근 거래일) 한 주체의 매매현황 타일.
function InvestorTile({ label, amt, qty }: { label: string; amt: number | null; qty: number | null }) {
  const buy = (amt ?? 0) > 0;
  const sell = (amt ?? 0) < 0;
  const color = buy ? RED : sell ? BLUE : "#888";
  const action = amt == null ? "데이터 없음" : buy ? "순매수" : sell ? "순매도" : "보합";
  return (
    <div className="flex flex-col items-center rounded border px-3 py-3" style={{ borderColor: `${color}33`, background: `${color}0d` }}>
      <div className="text-sm font-bold text-[#3d2c66]">{label}</div>
      <div className="mt-1 rounded-full px-2.5 py-0.5 text-xs font-bold text-white" style={{ background: color }}>{action}</div>
      <div className="mt-1.5 text-xl font-bold tabular-nums" style={{ color }}>{eok(amt)}</div>
      {qty != null && <div className="text-[11px] tabular-nums text-[#999]">{manShares(qty)}주</div>}
    </div>
  );
}
function InvestorTrendBlock({ trend, reportDate }: { trend: InvestorDay[]; reportDate?: string | null }) {
  if (!trend || trend.length === 0) return null;
  // 가장 최근 확정 거래일 = 현재 매매현황(수급은 마감 후 집계라 보통 1일 지연).
  const top = trend[0];
  const lag = reportDate && top.date !== reportDate;
  const led = (["foreign", "individual", "organ"] as const)
    .map((k) => ({ k, v: top[k] ?? 0, label: k === "foreign" ? "외국인" : k === "individual" ? "개인" : "기관" }))
    .filter((x) => x.v > 0)
    .sort((a, b) => b.v - a.v)[0];
  return (
    <Block label="투자자별 매매현황 (현재 · 일단위)" color="#b4a7d6" fg="#3d2c66">
      {/* 현재(최근 거래일) 매매현황 — 누가 매입/매도했나, 크게 */}
      <div className="border-b border-[#eee] bg-[#f6f3fb] px-3 py-3">
        <div className="mb-2 flex flex-wrap items-center gap-2 text-[13px] text-[#3d2c66]">
          <span className="rounded bg-[#3d2c66] px-2 py-0.5 text-xs font-bold text-white">현재 매매현황</span>
          <b>{top.date}</b> 기준 (집계 {top.stocks.toLocaleString("ko-KR")}종목)
          {led && <span>· <b>{led.label}</b> 순매수 주도</span>}
          {lag && <span className="text-[11px] text-[#999]">· 수급은 장 마감 후 집계 → 가장 최근 확정 거래일 기준 ({reportDate} 당일분은 마감 후 반영)</span>}
        </div>
        <div className="grid grid-cols-3 gap-2">
          <InvestorTile label="외국인" amt={top.foreign} qty={top.foreign_qty} />
          <InvestorTile label="개인" amt={top.individual} qty={top.individual_qty} />
          <InvestorTile label="기관" amt={top.organ} qty={top.organ_qty} />
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="bg-[#ece7f6] text-[11px] text-[#3d2c66]">
              <th colSpan={5} className="border border-[#d0d0d0] px-2 py-1 text-left font-bold"> 일별 추이 (순매수 금액, 억원)</th>
            </tr>
            <tr className="bg-[#ece7f6] text-xs text-[#3d2c66]">
              <Th w="22%">일자</Th>
              <Th w="22%" right>외국인</Th>
              <Th w="22%" right>개인</Th>
              <Th w="22%" right>기관</Th>
              <Th w="12%" center>집계종목</Th>
            </tr>
          </thead>
          <tbody>
            {trend.map((d) => (
              <tr key={d.date} className="hover:bg-[#faf8ff]">
                <td className="border border-[#eee] px-2 py-1.5 font-medium text-[#1f1f1f]">{d.date}</td>
                <td className="border border-[#eee] px-2 py-1.5 text-right tabular-nums" style={flowStyle(d.foreign)}>{eok(d.foreign)}</td>
                <td className="border border-[#eee] px-2 py-1.5 text-right tabular-nums" style={flowStyle(d.individual)}>{eok(d.individual)}</td>
                <td className="border border-[#eee] px-2 py-1.5 text-right tabular-nums" style={flowStyle(d.organ)}>{eok(d.organ)}</td>
                <td className="border border-[#eee] px-2 py-1.5 text-center tabular-nums text-[#888]">{d.stocks.toLocaleString("ko-KR")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="px-3 py-1.5 text-[11px] leading-relaxed text-[#999]">
        종목별 누적 수급(네이버)을 그날 종가와 곱해 시장 전체 <b>순매수 금액</b>으로 집계(개인/외국인/기관). 빨강=순매수(매입) · 파랑=순매도. <b>투자자별 매매(매수·매도)는 장 마감 후 집계되어 보통 1거래일 지연</b>되므로, 당일 가격은 있어도 그날 수급은 다음 날 확정됩니다 — 위 "현재 매매현황"은 가장 최근 확정 거래일 기준입니다. (KRX 기관 세부주체는 비공개 구간)
      </p>
    </Block>
  );
}

function Th({ children, w, center, right }: { children?: ReactNode; w?: string; center?: boolean; right?: boolean }) {
  return (
    <th
      style={{ width: w }}
      className={`border border-[#d0d0d0] px-2 py-1.5 font-semibold ${center ? "text-center" : right ? "text-right" : "text-left"}`}
    >
      {children}
    </th>
  );
}

function GroupTh({
  children,
  span = 1,
  w,
  bg,
  fg,
}: {
  children?: ReactNode;
  span?: number;
  w?: number;
  bg: string;
  fg: string;
}) {
  return (
    <th
      colSpan={span}
      style={{ width: w, background: bg, color: fg }}
      className="border border-white px-2 py-1 text-center text-xs font-bold"
    >
      {children}
    </th>
  );
}

function ColTh({ children, w, center, right }: { children?: ReactNode; w: number; center?: boolean; right?: boolean }) {
  return (
    <th
      style={{ width: w }}
      className={`border border-[#d6d6d6] px-2 py-1.5 font-semibold ${center ? "text-center" : right ? "text-right" : "text-left"}`}
    >
      {children}
    </th>
  );
}

/* region flags for the global finance feed */
const REGION_FLAG: Record<string, string> = {
  한국: "",
  미국: "",
  유럽: "",
  중국: "",
  일본: "",
  글로벌: "",
};

/* format a cross-asset value by its unit */
function assetValue(a: CrossAsset): string {
  if (a.value == null) return "—";
  const v = a.value;
  if (a.unit === "pct") return `${v.toFixed(2)}%`;
  if (a.unit === "usd") return `$${v.toLocaleString("en-US", { maximumFractionDigits: v >= 100 ? 0 : 2 })}`;
  if (a.unit === "krw") return `₩${v.toLocaleString("ko-KR", { maximumFractionDigits: 1 })}`;
  return v.toLocaleString("en-US", { maximumFractionDigits: 2 }); // pt
}

/* 크로스에셋 자금 흐름 — 어느 판으로 현금이 흐르는지 한눈에 (실시간 폴링) */
const EMPTY_CA: CrossAssetLayer = {
  groups: [],
  count: 0,
  flow: { verdict: "불러오는 중…", tone: "중립", score: 0, desc: "실시간 시세를 불러오는 중입니다.", metrics: { equities: null, crypto: null, gold: null, usdkrw: null }, summary: "" },
};
function CrossAssetBlock({
  ca: initial,
  live: allowLive,
  reportDate,
}: {
  ca: CrossAssetLayer | null;
  live: boolean;
  reportDate?: string | null;
}) {
  const [ca, setCa] = useState<CrossAssetLayer>(initial ?? EMPTY_CA);
  const [live, setLive] = useState(false);
  const [picked, setPicked] = useState<string | null>(null); // asset key for the drill-in modal

  useEffect(() => {
    // 과거 날짜: 그날 마감값(아카이브)으로 고정 — 실시간 폴링하지 않는다.
    if (!allowLive) {
      setCa(initial ?? EMPTY_CA);
      setLive(false);
      return;
    }
    // 최신(오늘) 날짜만 실시간 갱신.
    let alive = true;
    const load = () =>
      api
        .crossAsset()
        .then((d) => {
          if (alive) {
            setCa(d);
            setLive(true);
          }
        })
        .catch(() => {});
    load(); // refresh immediately on mount …
    const id = setInterval(load, 30000); // … then live every 30초
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [allowLive, initial]);

  // 과거 날짜인데 그 일자의 크로스에셋 스냅샷이 저장돼 있지 않은 경우.
  if (!allowLive && !initial) {
    return (
      <Block label="크로스에셋 자금 흐름 · 미국/글로벌 증시 · 금 · 비트코인" color="#ffe08a" fg="#7a5b00">
        <div className="px-3 py-4 text-sm text-[#999]">
          {reportDate} 일자에는 크로스에셋 데이터가 저장되어 있지 않습니다. (해당 기능 도입 이전 날짜)
        </div>
      </Block>
    );
  }

  const flow = ca.flow;
  const tone = flow.tone === "긍정" ? RED : flow.tone === "부정" ? BLUE : "#666";
  return (
    <Block label="크로스에셋 자금 흐름 · 미국/글로벌 증시 · 금 · 비트코인" color="#ffe08a" fg="#7a5b00">
      {/* money-flow verdict banner */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-[#eee] bg-[#fffaf0] px-3 py-2">
        <span className="rounded-full px-3 py-1 text-sm font-bold text-white" style={{ background: tone }}>
          {flow.verdict}
        </span>
        {allowLive ? (
          <span className="flex items-center gap-1 text-[11px] font-bold" style={{ color: live ? "#2f9e44" : "#aaa" }}>
            <span className={`inline-block h-1.5 w-1.5 rounded-full ${live ? "animate-pulse" : ""}`} style={{ background: live ? "#2f9e44" : "#bbb" }} />
            {live ? "LIVE" : "…"}
            {ca.as_of && <span className="font-normal text-[#999]">{ca.as_of.slice(11)}</span>}
          </span>
        ) : (
          <span className="flex items-center gap-1 rounded bg-[#f0ead6] px-1.5 py-0.5 text-[11px] font-bold text-[#7a5b00]">
            {reportDate} 마감값 (아카이브)
          </span>
        )}
        <span className="text-[15px] text-[#444]">{flow.desc}</span>
        <span className="ml-auto text-[13px] text-[#999]">
          글로벌 증시 {fmtSigned(flow.metrics.equities)} · 암호화폐 {fmtSigned(flow.metrics.crypto)} · 금 {fmtSigned(flow.metrics.gold)} · 원/달러 {fmtSigned(flow.metrics.usdkrw)}
        </span>
      </div>
      <div className="grid sm:grid-cols-2 xl:grid-cols-4">
        {ca.groups.map((g) => (
          <div key={g.group} className="border-b border-r border-[#eee]">
            <div className="bg-[#fafafa] px-3 py-1.5 text-sm font-bold text-[#7a5b00]">{g.group}</div>
            <table className="w-full border-collapse text-[15px]">
              <tbody>
                {g.assets.map((a) => (
                  <tr
                    key={a.key}
                    onClick={() => setPicked(a.key)}
                    className="cursor-pointer hover:bg-[#fff7e6]"
                    title="클릭하면 장 마감 상세가 열립니다"
                  >
                    <td className="border-t border-[#f0f0f0] px-3 py-2 font-medium text-[#1155cc] hover:underline">{a.label}</td>
                    <td className="border-t border-[#f0f0f0] px-2 py-2 text-right tabular-nums text-[#1f1f1f]">
                      {assetValue(a)}
                    </td>
                    <td
                      className="border-t border-[#f0f0f0] px-2 py-2 text-right font-bold tabular-nums"
                      style={retStyle(a.change_pct)}
                    >
                      {a.change_pct != null ? `${a.change_pct > 0 ? "+" : ""}${a.change_pct}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
      <p className="px-3 py-1.5 text-[12px] text-[#999]">
        종목을 클릭하면 그 장이 어떻게 끝났는지(장 마감 OHLC·최근 시세·구성종목) 엑셀로 열립니다. 금리(국채 10년)·원/달러 상승은 위험회피(현금·안전자산 선호), 증시·비트코인 상승은 위험선호 신호로 읽습니다. 시세 FinanceDataReader{allowLive ? " · 30초마다 실시간 갱신(해외장은 지연 시세)." : ` · ${reportDate} 장 마감 기준 저장값(과거 날짜는 실시간 갱신하지 않습니다).`}
      </p>
      {picked && (
        <AssetDetailModal
          assetKey={picked}
          onClose={() => setPicked(null)}
          asOf={allowLive ? undefined : reportDate ?? undefined}
        />
      )}
    </Block>
  );
}

function fmtSigned(v: number | null): string {
  if (v == null) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;
}

/* small reusable digest bullet list (대표 내용 — 여러 매체 취합) */
function DigestList({ lines, color = "#9dc3e6" }: { lines: string[]; color?: string }) {
  if (!lines || lines.length === 0) return null;
  return (
    <ul className="space-y-0.5">
      {lines.map((line, i) => (
        <li key={i} className="flex gap-1.5 text-[12px] leading-snug text-[#555]">
          <span style={{ color }}>·</span>
          <span>{line}</span>
        </li>
      ))}
    </ul>
  );
}

/* 외국인이 보는 한국 증시 — 외신(영문) 시각 + 대표 내용 */
function ForeignViewBlock({ fv }: { fv: ForeignViewType }) {
  const tone = fv.lean === "긍정" ? RED : fv.lean === "부정" ? BLUE : "#666";
  return (
    <Block label="외국인이 보는 한국 증시 (외신 시각)" color="#f4b084" fg="#7a3a0c">
      <div className="space-y-2 px-3 py-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className="rounded-full px-2.5 py-0.5 text-xs font-bold text-white"
            style={{ background: tone }}
          >
            {fv.lean}
          </span>
          <span className="text-xs text-[#888]">
            긍정 {fv.pos} · 부정 {fv.neg} · 영문 보도 {fv.pool_size}건
          </span>
        </div>
        {fv.summary && <p className="text-[13px] leading-relaxed text-[#444]">{fv.summary}</p>}
        {fv.headlines.length > 0 && (
          <NewsList items={fv.headlines.slice(0, 5).map((h) => ({ title: h.title ?? "", link: h.link ?? "#", source: h.source ?? "" }))} dot="#f4b084" />
        )}
        {fv.digest.length > 0 && (
          <div className="border-t border-[#eee] pt-2">
            <div className="mb-1 text-[11px] font-bold text-[#7a3a0c]">대표 내용 (여러 매체 취합)</div>
            <DigestList lines={fv.digest} color="#f4b084" />
          </div>
        )}
      </div>
    </Block>
  );
}

/* 금리 발표 일정 + 인상 시기 전망 */
function RatesBlock({ rates }: { rates: RateLayer }) {
  return (
    <Block label="금리 발표 일정 · 인상 시기 전망" color="#9dc3e6" fg="#1a3a5e">
      <div className="space-y-2.5 px-3 py-2.5">
        <div className="grid grid-cols-2 gap-2">
          {rates.schedule.map((m) => {
            const soon = m.d_day != null && m.d_day <= 7;
            return (
              <div
                key={m.key}
                className="rounded border border-[#dbe7f3] bg-[#f7fbff] px-2.5 py-2"
              >
                <div className="flex items-center gap-1 text-xs font-bold text-[#1a3a5e]">
                  <span>{m.flag}</span>
                  <span>{m.name}</span>
                </div>
                <div className="mt-1 flex items-baseline gap-1.5">
                  <span className="text-lg font-bold tabular-nums text-[#1f1f1f]">{m.next_label ?? "—"}</span>
                  {m.d_day != null && (
                    <span
                      className="rounded px-1.5 py-0.5 text-[11px] font-bold"
                      style={{ background: soon ? RED : "#dbe7f3", color: soon ? "#fff" : "#1a3a5e" }}
                    >
                      D-{m.d_day}
                    </span>
                  )}
                </div>
                <div className="mt-0.5 text-[11px] text-[#999]">
                  다음 발표일{m.next_date ? ` · ${m.next_date}` : ""} · 2026 {m.remaining_2026}회 남음
                </div>
              </div>
            );
          })}
        </div>
        {rates.digest.length > 0 && (
          <div className="border-t border-[#eee] pt-2">
            <div className="mb-1 text-[11px] font-bold text-[#1a3a5e]">금리 시기 전망 (대표 내용)</div>
            <DigestList lines={rates.digest} color="#9dc3e6" />
          </div>
        )}
        {rates.outlook.length > 0 && (
          <NewsList items={rates.outlook.slice(0, 4).map((h) => ({ title: h.title ?? "", link: h.link ?? "#", source: h.source ?? "" }))} dot="#9dc3e6" />
        )}
      </div>
    </Block>
  );
}

/* macro driver row */
function MacroRow({ d }: { d: MacroDriver }) {
  const color = d.direction === "긍정" ? RED : d.direction === "부정" ? BLUE : "#666";
  const regions = Object.entries(d.regions ?? {}).sort((a, b) => b[1] - a[1]);
  const top = d.headlines[0];
  return (
    <tr className="border-b border-[#eee] hover:bg-[#fff7e6]">
      <td className="border border-[#eee] px-2 py-1.5 font-semibold text-[#1f1f1f]">{d.theme}</td>
      <td className="border border-[#eee] px-2 py-1.5 text-center font-bold" style={{ color }}>
        {d.direction}
      </td>
      <td className="border border-[#eee] px-2 py-1.5 text-center tabular-nums text-[#555]">{d.count}</td>
      <td className="border border-[#eee] px-2 py-1.5">
        <div className="flex flex-wrap gap-1">
          {regions.slice(0, 5).map(([reg, n]) => (
            <span key={reg} className="rounded bg-[#eaf1f8] px-1.5 py-0.5 text-[11px] text-[#1a3a5e]">
              {reg} {n}
            </span>
          ))}
        </div>
      </td>
      <td className="border border-[#eee] px-2 py-1.5 align-top text-[#555]">
        {top ? (
          <a href={top.link ?? "#"} target="_blank" rel="noopener noreferrer" className="font-medium hover:text-[#1155cc] hover:underline">
            {top.region && <span className="mr-1 text-[11px] text-[#999]">[{top.region}]</span>}
            {top.title}
            {top.source && <span className="ml-1 text-xs text-[#999]">· {top.source}</span>}
          </a>
        ) : (
          "—"
        )}
        {d.digest && d.digest.length > 0 && (
          <ul className="mt-1 space-y-0.5 border-l-2 border-[#dbe7f3] pl-2">
            {d.digest.map((line, i) => (
              <li key={i} className="flex gap-1 text-[12px] leading-snug text-[#666]">
                <span className="text-[#9dc3e6]">·</span>
                <span>{line}</span>
              </li>
            ))}
          </ul>
        )}
      </td>
    </tr>
  );
}

/* shared news list (used by the macro 국내/해외 columns) */
function NewsList({ items, dot }: { items: { title: string; link: string; source: string }[]; dot: string }) {
  return (
    <ul className="divide-y divide-[#eee]">
      {items.map((a, i) => (
        <li key={i}>
          <a
            href={a.link}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-start gap-2 px-3 py-1.5 text-sm text-[#333] hover:bg-[#fff7e6]"
          >
            <span className="mt-0.5" style={{ color: dot }}>›</span>
            <span className="flex-1">
              {a.title}
              <span className="ml-1.5 text-xs text-[#999]">{a.source}</span>
            </span>
          </a>
        </li>
      ))}
    </ul>
  );
}

/* 거래원 sheet — which brokerage houses (창구) drove each stock's trade.
   외국계 창구 매수/매도는 외국인 수급의 대용 지표로 읽힌다. */
function HouseTags({ houses }: { houses: BrokerHouse[] }) {
  if (!houses || houses.length === 0) return <span className="text-xs text-[#bbb]">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {houses.map((h, i) => (
        <span
          key={i}
          className={`rounded px-1.5 py-0.5 text-[11px] ${
            h.foreign ? "bg-[#fde7e9] font-semibold text-[#c92a2a]" : "bg-[#f0f0f0] text-[#555]"
          }`}
          title={h.volume != null ? `${h.volume.toLocaleString("ko-KR")}주` : undefined}
        >
          {h.foreign && " "}
          {h.name}
          {h.volume != null && <span className="ml-1 tabular-nums text-[#999]">{manShares(h.volume)}</span>}
        </span>
      ))}
    </div>
  );
}

function BrokerSheet({ stocks }: { stocks: ArchiveStock[] }) {
  const rows = stocks.filter((s) => s.brokers && (s.brokers.buy.length > 0 || s.brokers.sell.length > 0));
  if (rows.length === 0) return null;
  return (
    <Block label="거래원 · 매매 상위 증권사 창구 (외국계 추정 · 20분 지연)" color="#c6e0b4" fg="#2d5016">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px]" style={{ minWidth: 900 }}>
          <thead>
            <tr className="bg-[#eaf3e3] text-xs text-[#2d5016]">
              <Th w="16%">종목</Th>
              <Th w="34%">매수 상위 창구</Th>
              <Th w="34%">매도 상위 창구</Th>
              <Th w="16%" center>외국계 추정</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => {
              const fn = s.brokers!.foreign?.net ?? null;
              const fColor = fn == null ? "#888" : fn > 0 ? RED : fn < 0 ? BLUE : "#888";
              return (
                <tr key={s.ticker} className="hover:bg-[#fff7e6]">
                  <td className="border border-[#eee] px-2 py-1.5 align-top">
                    <span className="font-medium text-[#1f1f1f]">{s.name}</span>
                    <span className="ml-1 font-mono text-[11px] text-[#999]">{s.ticker}</span>
                  </td>
                  <td className="border border-[#eee] px-2 py-1.5 align-top">
                    <HouseTags houses={s.brokers!.buy} />
                  </td>
                  <td className="border border-[#eee] px-2 py-1.5 align-top">
                    <HouseTags houses={s.brokers!.sell} />
                  </td>
                  <td className="border border-[#eee] px-2 py-1.5 text-center align-top font-bold tabular-nums" style={{ color: fColor }}>
                    {fn == null
                      ? "—"
                      : `${fn > 0 ? "순매수" : fn < 0 ? "순매도" : "보합"} ${manShares(Math.abs(fn)).replace("+", "")}주`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="px-3 py-1.5 text-[11px] text-[#999]">
         표시는 외국계 창구(모간스탠리·제이피모간·골드만삭스 등). 당일 매매 상위 5개 회원사 기준 추정치이며, 기관 세부주체(연기금·투신 등)는 KRX 비공개 구간으로 제공되지 않습니다.
      </p>
    </Block>
  );
}

/* per-stock global (English) headlines — the 해외 뉴스 sheet */
function GlobalNewsSheet({ stocks }: { stocks: ArchiveStock[] }) {
  const rows = stocks.flatMap((s) =>
    (s.news_global ?? []).map((n) => ({ name: s.name, ticker: s.ticker, ...n })),
  );
  if (rows.length === 0) return null;
  return (
    <Block label="해외 뉴스 · 종목별 글로벌 헤드라인 (Google News EN)" color="#f4b084" fg="#7a3a0c">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="bg-[#fbe7d6] text-xs text-[#7a3a0c]">
              <Th w="16%">종목</Th>
              <Th w="9%" center>코드</Th>
              <Th w="60%">헤드라인 (EN)</Th>
              <Th w="15%">출처</Th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 60).map((r, i) => (
              <tr key={i} className="hover:bg-[#fff7e6]">
                <td className="border border-[#eee] px-2 py-1.5 font-medium text-[#1f1f1f]">{r.name}</td>
                <td className="border border-[#eee] px-2 py-1.5 text-center font-mono text-xs text-[#888]">{r.ticker}</td>
                <td className="border border-[#eee] px-2 py-1.5">
                  <a
                    href={r.link ?? "#"}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[#1155cc] hover:underline"
                  >
                    {r.title}
                  </a>
                </td>
                <td className="border border-[#eee] px-2 py-1.5 text-xs text-[#888]">{r.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Block>
  );
}

/* one stock row in the main investor-reason sheet */
function StockRow({ s, n }: { s: ArchiveStock; n: number }) {
  const find = (k: string) => s.investors.find((iv) => iv.key === k);
  return (
    <tr className="hover:bg-[#fff7e6]">
      <td className="border border-[#e6e6e6] bg-[#f0f0f0] px-1 text-center text-xs text-[#999]">{n}</td>
      <td className="border border-[#e6e6e6] px-2 py-1.5 font-medium text-[#1155cc]">{s.name}</td>
      <td className="border border-[#e6e6e6] px-2 py-1.5 text-center font-mono text-xs text-[#555]">{s.ticker}</td>
      <td className="border border-[#e6e6e6] px-2 py-1.5 text-right tabular-nums text-[#1f1f1f]">{won(s.close)}</td>
      <td className="border border-[#e6e6e6] px-2 py-1.5 text-center font-bold tabular-nums" style={retStyle(s.change_pct)}>
        {s.change_pct != null ? `${s.change_pct > 0 ? "+" : ""}${s.change_pct}%` : "—"}
      </td>
      <InvestorCells iv={find("foreign")} />
      <InvestorCells iv={find("individual")} />
      <InvestorCells iv={find("organ")} />
    </tr>
  );
}

function InvestorCells({ iv }: { iv?: InvestorDriver }) {
  const buy = iv?.action === "순매수";
  const sell = iv?.action === "순매도";
  const color = buy ? RED : sell ? BLUE : "#888";
  return (
    <>
      <td className="border border-[#e6e6e6] px-2 py-1.5 text-center align-top">
        {iv && iv.action !== "데이터 없음" ? (
          <div className="leading-tight">
            <div className="font-bold" style={{ color }}>
              {iv.action}
            </div>
            {iv.qty != null && iv.qty !== 0 && (
              <div className="tabular-nums text-xs" style={{ color }}>
                {manShares(iv.qty)}주
              </div>
            )}
          </div>
        ) : (
          <span className="text-xs text-[#bbb]">—</span>
        )}
      </td>
      <td className="border border-[#e6e6e6] px-2 py-1.5 align-top text-xs leading-relaxed text-[#444]">
        {iv && iv.reasons.length > 0 ? iv.reasons.join(" · ") : <span className="text-[#bbb]">—</span>}
      </td>
    </>
  );
}

/* compact mover mini-sheet */
function MoverSheet({
  title,
  color,
  fg,
  rows,
  showVol,
}: {
  title: string;
  color: string;
  fg: string;
  rows: MoverRow[];
  showVol?: boolean;
}) {
  return (
    <Block label={title} color={color} fg={fg}>
      <table className="w-full border-collapse text-[13px]">
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.ticker} className="hover:bg-[#fff7e6]">
              <td className="border border-[#eee] bg-[#f0f0f0] px-1 text-center text-xs text-[#999]" style={{ width: 30 }}>
                {i + 1}
              </td>
              <td className="border border-[#eee] px-2 py-1.5">
                <span className="text-[#1f1f1f]">{r.name}</span>
                <span className="ml-1.5 font-mono text-[11px] text-[#999]">{r.ticker}</span>
              </td>
              <td className="border border-[#eee] px-2 py-1.5 text-right tabular-nums text-[#333]">{won(r.close)}</td>
              {showVol ? (
                <td className="border border-[#eee] px-2 py-1.5 text-right tabular-nums text-[#555]">
                  {r.volume != null ? r.volume.toLocaleString("ko-KR") : "—"}
                </td>
              ) : (
                <td
                  className="border border-[#eee] px-2 py-1.5 text-right font-bold tabular-nums"
                  style={retStyle(r.change_pct)}
                >
                  {r.change_pct != null ? `${r.change_pct > 0 ? "+" : ""}${r.change_pct}%` : "—"}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </Block>
  );
}
