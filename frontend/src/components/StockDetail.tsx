"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  ComposedChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";
import { api, OHLC, DartFinancials, DartStatement } from "@/lib/api";
import { Spinner, Empty } from "./ui";
import { won, UP, DOWN, toneClass, arrow } from "@/lib/format";

type Row = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  range: [number, number];
};

const PERIODS: { k: string; days: number }[] = [
  { k: "1개월", days: 21 },
  { k: "3개월", days: 63 },
  { k: "6개월", days: 126 },
  { k: "1년", days: 252 },
  { k: "전체", days: 0 },
];

// Draws one candle (wick + body) using the bar slot the chart assigned to the
// [low, high] range. Red when close ≥ open, blue otherwise (KR convention).
function Candle(props: {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  payload?: Row;
}) {
  const { x = 0, y = 0, width = 0, height = 0, payload } = props;
  if (!payload || height <= 0) return null;
  const { open, high, low, close } = payload;
  const span = high - low || 1;
  const up = close >= open;
  const color = up ? UP : DOWN;
  const yOf = (v: number) => y + ((high - v) / span) * height;
  const bodyTop = yOf(Math.max(open, close));
  const bodyH = Math.max(1, Math.abs(yOf(open) - yOf(close)));
  const cx = x + width / 2;
  const bw = Math.max(1.5, Math.min(width * 0.7, 10));
  return (
    <g>
      <line x1={cx} x2={cx} y1={y} y2={y + height} stroke={color} strokeWidth={1} />
      <rect x={cx - bw / 2} y={bodyTop} width={bw} height={bodyH} fill={color} />
    </g>
  );
}

export function StockDetail({
  ticker,
  name,
  sector,
  onClose,
}: {
  ticker: string;
  name: string | null;
  sector: string | null;
  onClose: () => void;
}) {
  const [data, setData] = useState<OHLC | null>(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState(2); // default 6개월
  const [fin, setFin] = useState<DartFinancials | null>(null);
  const [finLoading, setFinLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .ohlc({ ticker })
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [ticker]);

  useEffect(() => {
    setFinLoading(true);
    setFin(null);
    api
      .dartFinancials(ticker)
      .then(setFin)
      .catch(() => setFin(null))
      .finally(() => setFinLoading(false));
  }, [ticker]);

  const rows: Row[] = useMemo(() => {
    if (!data) return [];
    const r: Row[] = [];
    for (let i = 0; i < data.dates.length; i++) {
      const o = data.open[i], h = data.high[i], l = data.low[i], c = data.close[i], v = data.volume[i];
      if (o == null || h == null || l == null || c == null) continue;
      r.push({ date: data.dates[i], open: o, high: h, low: l, close: c, volume: v ?? 0, range: [l, h] });
    }
    return r;
  }, [data]);

  const view = useMemo(() => {
    const days = PERIODS[period].days;
    return days > 0 ? rows.slice(-days) : rows;
  }, [rows, period]);

  const last = view.at(-1);
  const first = view[0];
  const change = last && first ? last.close - view.at(-2)!.close : null;
  const changePct =
    last && view.length > 1 ? ((last.close - view.at(-2)!.close) / view.at(-2)!.close) * 100 : null;
  const periodPct = last && first ? ((last.close - first.open) / first.open) * 100 : null;

  const yDomain = useMemo(() => {
    if (view.length === 0) return [0, 1];
    let lo = Infinity, hi = -Infinity;
    for (const r of view) {
      lo = Math.min(lo, r.low);
      hi = Math.max(hi, r.high);
    }
    const pad = (hi - lo) * 0.05 || 1;
    return [Math.floor(lo - pad), Math.ceil(hi + pad)];
  }, [view]);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4 backdrop-blur-sm">
      <div className="my-6 w-full max-w-5xl overflow-hidden rounded-xl border border-[#d0d0d0] bg-white text-[#1f1f1f] shadow">
        {/* header — Excel green title bar */}
        <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-sm text-white">
          <span className="truncate font-semibold">{name ?? ticker} — 차트.xlsx</span>
          <button
            onClick={onClose}
            className="shrink-0 px-1 text-white/80 transition hover:text-white"
            aria-label="닫기"
          >
            ✕
          </button>
        </div>
        {/* header */}
        <div className="flex items-start justify-between border-b border-[#e0e0e0] p-5">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-[#1f1f1f]">{name ?? ticker}</h2>
              <span className="rounded bg-[#f3f2f1] px-2 py-0.5 text-xs text-[#555]">{ticker}</span>
              {sector && <span className="rounded bg-[#f3f2f1] px-2 py-0.5 text-xs text-[#555]">{sector}</span>}
            </div>
            {last && (
              <div className="mt-2 flex items-baseline gap-3">
                <span className="text-3xl font-bold tabular-nums text-[#1f1f1f]">{won(last.close)}</span>
                <span className="text-sm text-[#888]">원</span>
                <span className={`text-sm font-semibold tabular-nums ${toneClass(change)}`}>
                  {arrow(change)} {change != null ? won(Math.abs(change)) : "—"} (
                  {changePct != null ? `${changePct > 0 ? "+" : ""}${changePct.toFixed(2)}%` : "—"})
                </span>
              </div>
            )}
          </div>
        </div>

        {/* period tabs */}
        <div className="flex gap-1 px-5 pt-4">
          {PERIODS.map((p, i) => (
            <button
              key={p.k}
              onClick={() => setPeriod(i)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
                period === i ? "bg-[#217346] text-white" : "text-[#555] hover:bg-[#eef6f0]"
              }`}
            >
              {p.k}
            </button>
          ))}
          {periodPct != null && (
            <span className={`ml-auto self-center text-xs font-semibold ${toneClass(periodPct)}`}>
              기간 {periodPct > 0 ? "+" : ""}
              {periodPct.toFixed(2)}%
            </span>
          )}
        </div>

        {/* charts */}
        <div className="p-5">
          {loading ? (
            <div className="flex h-72 items-center justify-center text-[#888]">
              <Spinner />
            </div>
          ) : view.length === 0 ? (
            <Empty>가격 데이터가 없습니다.</Empty>
          ) : (
            <>
              {last && (
                <div className="mb-3 grid grid-cols-4 gap-2 text-xs">
                  <Info label="시가" value={won(last.open)} />
                  <Info label="고가" value={won(last.high)} cls="text-[#c92a2a]" />
                  <Info label="저가" value={won(last.low)} cls="text-[#1971c2]" />
                  <Info label="거래량" value={last.volume.toLocaleString("ko-KR")} />
                </div>
              )}
              <div className="h-96 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={view} margin={{ top: 6, right: 8, bottom: 0, left: 8 }}>
                    <CartesianGrid stroke="#e0e0e0" vertical={false} />
                    <XAxis dataKey="date" tick={{ fill: "#666", fontSize: 10 }} minTickGap={56} />
                    <YAxis
                      orientation="right"
                      domain={yDomain}
                      tick={{ fill: "#666", fontSize: 10 }}
                      tickFormatter={(v) => won(v)}
                      width={56}
                    />
                    <Tooltip content={<CandleTip />} />
                    <Bar dataKey="range" shape={<Candle />} isAnimationActive={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-2 h-24 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={view} margin={{ top: 0, right: 8, bottom: 0, left: 8 }}>
                    <XAxis dataKey="date" hide />
                    <YAxis orientation="right" tick={{ fill: "#666", fontSize: 9 }} width={56} tickFormatter={(v) => (v >= 1e6 ? `${(v / 1e6).toFixed(0)}M` : v >= 1e3 ? `${(v / 1e3).toFixed(0)}K` : `${v}`)} />
                    <Tooltip
                      contentStyle={{ background: "#ffffff", border: "1px solid #d0d0d0", borderRadius: 4, fontSize: 11, color: "#1f1f1f" }}
                      labelStyle={{ color: "#666" }}
                      formatter={(v) => [Number(v).toLocaleString("ko-KR"), "거래량"]}
                    />
                    <Bar dataKey="volume" fill="#9aa0a6" isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </>
          )}

          {/* DART 전체 재무제표 (전 계정·연도별) */}
          <Financials fin={fin} loading={finLoading} />
        </div>
      </div>
    </div>
  );
}

// 원 단위 금액 → 조/억 (음수 보존). 표가 빽빽하므로 축약.
function won2(v: number | null | undefined): string {
  if (v == null) return "—";
  const neg = v < 0;
  const a = Math.abs(v);
  let s: string;
  if (a >= 1e12) s = `${(a / 1e12).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}조`;
  else if (a >= 1e8) s = `${(a / 1e8).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}억`;
  else if (a >= 1e4) s = `${(a / 1e4).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}만`;
  else s = Math.round(a).toLocaleString("ko-KR");
  return neg ? `-${s}` : s;
}

// 합병 실사처럼 한눈에 보는 핵심 계정 — 강조 표시.
const KEY_ACCOUNTS = new Set([
  "자산총계", "부채총계", "자본총계", "유동자산", "비유동자산", "유동부채", "비유동부채",
  "현금및현금성자산", "이익잉여금(결손금)", "이익잉여금",
  "매출액", "수익(매출액)", "매출원가", "매출총이익", "판매비와관리비", "영업이익", "영업이익(손실)",
  "법인세비용차감전순이익", "당기순이익", "당기순이익(손실)",
  "영업활동 현금흐름", "영업활동현금흐름", "투자활동 현금흐름", "투자활동현금흐름",
  "재무활동 현금흐름", "재무활동현금흐름",
]);

function Financials({ fin, loading }: { fin: DartFinancials | null; loading: boolean }) {
  const statements = fin?.statements ?? [];
  const years = fin?.years ?? [];
  const [sj, setSj] = useState<string>("");

  const active = statements.find((s) => s.sj_div === sj) ?? statements[0];

  return (
    <div className="mt-5 overflow-hidden rounded-lg border border-[#e0e0e0]">
      <div className="flex flex-wrap items-center gap-2 border-b border-[#e0e0e0] bg-[#a9d08e] px-3 py-1.5">
        <span className="text-sm font-bold text-[#244d1a]"> 재무제표 (DART 전자공시 · 전 계정)</span>
        {years.length > 0 && <span className="text-xs text-[#2d5016]/80">{years[years.length - 1]}~{years[0]} · {years.length}개년</span>}
      </div>

      {loading ? (
        <div className="py-10 text-center text-sm text-[#888]">DART 재무제표 불러오는 중… <span className="text-[#aaa]">(최초 수초)</span></div>
      ) : statements.length === 0 ? (
        <div className="py-10 text-center text-sm text-[#999]">
          {fin && fin.available === false ? "DART 연동이 비활성화되어 있습니다." : "DART 재무제표가 없습니다."}
        </div>
      ) : (
        <>
          {/* statement tabs */}
          <div className="flex flex-wrap gap-1 border-b border-[#e0e0e0] bg-[#f3f2f1] px-2 py-1.5">
            {statements.map((s) => (
              <button
                key={s.sj_div}
                onClick={() => setSj(s.sj_div)}
                className={`rounded px-2.5 py-1 text-xs font-semibold transition ${
                  active?.sj_div === s.sj_div ? "bg-[#217346] text-white" : "text-[#555] hover:bg-[#e6efe8]"
                }`}
              >
                {s.label} <span className="opacity-70">({s.accounts.length})</span>
              </button>
            ))}
          </div>
          {active && <StatementTable st={active} years={years} />}
          <p className="border-t border-[#eee] px-3 py-1.5 text-[11px] text-[#999]">
            출처: 금융감독원 전자공시(DART) 단일회사 전체 재무제표 · 연결 우선(없으면 별도) · 금액 단위 원. 계정명은 보고서 원문 그대로라 연도별로 표기가 달라질 수 있습니다.
          </p>
        </>
      )}
    </div>
  );
}

function StatementTable({ st, years }: { st: DartStatement; years: string[] }) {
  return (
    <div className="max-h-[460px] overflow-auto">
      <table className="w-full border-collapse text-[12.5px]">
        <thead className="sticky top-0 z-10">
          <tr className="bg-[#f0f0f0] text-xs text-[#444]">
            <th className="sticky left-0 z-20 min-w-[200px] border border-[#e0e0e0] bg-[#f0f0f0] px-2 py-1.5 text-left font-semibold">
              계정 (원)
            </th>
            {years.map((y) => (
              <th key={y} className="min-w-[78px] border border-[#e0e0e0] px-2 py-1.5 text-right font-semibold tabular-nums">
                {y}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {st.accounts.map((a) => {
            const key = KEY_ACCOUNTS.has(a.account_nm);
            return (
              <tr key={a.account_nm} className="hover:bg-[#fff7e6]">
                <th
                  className={`sticky left-0 z-10 border border-[#e0e0e0] px-2 py-1 text-left font-medium ${
                    key ? "bg-[#eef6f0] font-bold text-[#1b5e3a]" : "bg-[#fafafa] text-[#444]"
                  }`}
                >
                  {a.account_nm}
                </th>
                {years.map((y) => {
                  const v = a.by_year[y] ?? null;
                  return (
                    <td
                      key={y}
                      className={`border border-[#eee] px-2 py-1 text-right tabular-nums ${
                        v == null ? "text-[#ccc]" : v < 0 ? "text-[#1971c2]" : "text-[#1f1f1f]"
                      } ${key ? "font-semibold" : ""}`}
                    >
                      {won2(v)}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Info({ label, value, cls = "text-[#1f1f1f]" }: { label: string; value: string; cls?: string }) {
  return (
    <div className="rounded-lg border border-[#e0e0e0] bg-[#fafafa] px-3 py-2">
      <div className="text-[10px] text-[#888]">{label}</div>
      <div className={`mt-0.5 font-semibold tabular-nums ${cls}`}>{value}</div>
    </div>
  );
}

function CandleTip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  const up = r.close >= r.open;
  return (
    <div className="rounded-md border border-[#d0d0d0] bg-white p-2.5 text-xs shadow-sm">
      <div className="mb-1 text-[#666]">{r.date}</div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 tabular-nums">
        <span className="text-[#555]">시 {won(r.open)}</span>
        <span className="text-[#555]">고 {won(r.high)}</span>
        <span className="text-[#555]">저 {won(r.low)}</span>
        <span className={up ? "text-[#c92a2a]" : "text-[#1971c2]"}>종 {won(r.close)}</span>
      </div>
    </div>
  );
}
