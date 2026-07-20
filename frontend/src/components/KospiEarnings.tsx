"use client";

import { useEffect, useMemo, useState } from "react";
import { api, KospiEarnings as KE, KospiEarningRow } from "@/lib/api";
import { Spinner } from "@/components/ui";

// 억원 단위 값 → 조/억 포맷
function eok(v: number | null): string {
  if (v == null) return "—";
  const a = Math.abs(v);
  if (a >= 10000) return `${(v / 10000).toFixed(1)}조`;
  return `${Math.round(v).toLocaleString("ko-KR")}억`;
}
function pct(v: number | null): string { return v == null ? "—" : `${v > 0 ? "+" : ""}${v}%`; }
function n2(v: number | null): string { return v == null ? "—" : v.toLocaleString("ko-KR"); }

type SortKey = "market_cap" | "sales" | "op_profit" | "net_income" | "op_margin" | "op_yoy" | "per" | "roe";
const COLS: { key: SortKey; label: string }[] = [
  { key: "market_cap", label: "시총" },
  { key: "sales", label: "매출" },
  { key: "op_profit", label: "영업이익" },
  { key: "net_income", label: "순이익" },
  { key: "op_margin", label: "영업이익률" },
  { key: "op_yoy", label: "전년比" },
  { key: "per", label: "PER" },
  { key: "roe", label: "ROE" },
];
const LIMIT = 400;

export function KospiEarnings() {
  const [d, setD] = useState<KE | null>(null);
  const [err, setErr] = useState(false);
  const [q, setQ] = useState("");
  const [sector, setSector] = useState("전체");
  const [sortKey, setSortKey] = useState<SortKey>("market_cap");
  const [onlyImproving, setOnlyImproving] = useState(false);

  useEffect(() => { api.kospiEarnings().then(setD).catch(() => setErr(true)); }, []);

  const sectors = useMemo(() => {
    if (!d) return [];
    return ["전체", ...Array.from(new Set(d.companies.map((c) => c.sector).filter(Boolean) as string[])).sort()];
  }, [d]);

  const rows = useMemo(() => {
    if (!d) return [];
    const term = q.trim();
    let list = d.companies.filter((c) =>
      (sector === "전체" || c.sector === sector) &&
      (!term || (c.name?.includes(term) || c.ticker.includes(term))) &&
      (!onlyImproving || (c.op_yoy ?? -1) > 0),
    );
    // 정렬: null 은 항상 뒤로, 내림차순
    list = list.slice().sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      return bv - av;
    });
    return list;
  }, [d, q, sector, sortKey, onlyImproving]);

  if (err) return null;
  if (!d) return <div className="flex items-center gap-2 py-8 text-sm text-[#888]"><Spinner /> 전체 실적 불러오는 중…</div>;

  const s = d.summary;
  const shown = rows.slice(0, LIMIT);

  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 bg-[#217346] px-4 py-2 text-white">
        <span className="text-sm font-semibold">전체 기업 실적 — 매출·영업이익·순이익 (DART {d.companies[0]?.period})</span>
        <span className="text-[10px] text-white/80">{d.count.toLocaleString("ko-KR")}개 · 흑자 {s.profitable_pct}% · 실적개선 {s.improving_pct}%</span>
      </div>

      {/* 컨트롤 */}
      <div className="flex flex-wrap items-center gap-2 border-b border-[#eee] px-3 py-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="종목명·코드 검색"
          className="w-40 rounded border border-[#cdcdcd] px-2 py-1 text-[12px] outline-none focus:border-[#217346]" />
        <select value={sector} onChange={(e) => setSector(e.target.value)}
          className="rounded border border-[#cdcdcd] px-2 py-1 text-[12px] outline-none focus:border-[#217346]">
          {sectors.map((sc) => <option key={sc} value={sc}>{sc}</option>)}
        </select>
        <label className="flex items-center gap-1 text-[12px] text-[#555]">
          <input type="checkbox" checked={onlyImproving} onChange={(e) => setOnlyImproving(e.target.checked)} />실적개선만
        </label>
        <span className="ml-auto text-[11px] text-[#888]">
          {rows.length.toLocaleString("ko-KR")}개{rows.length > LIMIT ? ` (상위 ${LIMIT} 표시 · 검색으로 좁히기)` : ""}
        </span>
      </div>

      {/* 테이블 */}
      <div className="max-h-[560px] overflow-auto">
        <table className="w-full min-w-[720px] text-[11px]">
          <thead className="sticky top-0 z-10 bg-[#f3f6f4]">
            <tr className="text-[#555]">
              <th className="px-2 py-1.5 text-left font-semibold">종목</th>
              {COLS.map((c) => (
                <th key={c.key} onClick={() => setSortKey(c.key)}
                  className={`cursor-pointer px-2 py-1.5 text-right font-semibold hover:text-[#217346] ${sortKey === c.key ? "text-[#217346]" : ""}`}>
                  {c.label}{sortKey === c.key ? " ▼" : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => <Row key={r.ticker} r={r} />)}
          </tbody>
        </table>
        {shown.length === 0 && <div className="py-8 text-center text-xs text-[#999]">조건에 맞는 기업이 없습니다.</div>}
      </div>
      <p className="px-3 py-2 text-[10px] leading-relaxed text-[#aaa]">{d.note}</p>
    </div>
  );
}

function Row({ r }: { r: KospiEarningRow }) {
  const marginColor = (r.op_margin ?? 0) >= 15 ? "#217346" : (r.op_margin ?? 0) < 0 ? "#c0392b" : "#555";
  const yoyColor = r.op_yoy == null ? "#bbb" : r.op_yoy >= 0 ? "#c0392b" : "#1c6fd6";
  return (
    <tr className="border-t border-[#f2f2f2] hover:bg-[#f7faf8]">
      <td className="px-2 py-1.5 text-left">
        <span className="font-semibold text-[#1f1f1f]">{r.name}</span>
        <span className="ml-1 text-[9px] text-[#aaa]">{r.sector ?? ""}</span>
      </td>
      <td className="px-2 py-1.5 text-right tabular-nums text-[#333]">{eok(r.market_cap)}</td>
      <td className="px-2 py-1.5 text-right tabular-nums text-[#333]">{eok(r.sales)}</td>
      <td className="px-2 py-1.5 text-right tabular-nums" style={{ color: (r.op_profit ?? 0) < 0 ? "#c0392b" : "#333" }}>{eok(r.op_profit)}</td>
      <td className="px-2 py-1.5 text-right tabular-nums" style={{ color: (r.net_income ?? 0) < 0 ? "#c0392b" : "#333" }}>{eok(r.net_income)}</td>
      <td className="px-2 py-1.5 text-right tabular-nums font-semibold" style={{ color: marginColor }}>{r.op_margin == null ? "—" : `${r.op_margin}%`}</td>
      <td className="px-2 py-1.5 text-right tabular-nums font-bold" style={{ color: yoyColor }}>{pct(r.op_yoy)}</td>
      <td className="px-2 py-1.5 text-right tabular-nums text-[#666]">{n2(r.per)}</td>
      <td className="px-2 py-1.5 text-right tabular-nums text-[#666]">{r.roe == null ? "—" : `${r.roe}%`}</td>
    </tr>
  );
}
