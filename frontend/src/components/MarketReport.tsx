"use client";

import { useEffect, useState } from "react";
import { api, MarketReport as MR, MoverRow, FlowSeller } from "@/lib/api";
import { won, toneClass, manShares } from "@/lib/format";

export function MarketReport() {
  const [data, setData] = useState<MR | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    setLoading(true);
    api
      .marketReport()
      .then(setData)
      .catch((e) => setErr(e?.message ?? "리포트를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, []);

  if (loading)
    return <div className="py-20 text-center text-sm text-slate-400">데일리 리포트 생성 중… (최초 약 10초)</div>;
  if (err) return <div className="py-20 text-center text-sm text-rose-400">{err}</div>;
  if (!data) return null;

  const b = data.breadth;
  return (
    <div className="space-y-6 text-slate-200">
      <header className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-lg font-bold text-white">📊 시장 데일리 리포트</h2>
          <span className="text-sm text-slate-400">{data.date} 기준</span>
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-sm">
          <Pill label="상승" value={b.up} cls="bg-[#3a1f1f] text-[#ff8787]" />
          <Pill label="하락" value={b.down} cls="bg-[#1f2a3a] text-[#74c0fc]" />
          <Pill label="보합" value={b.flat} cls="bg-slate-800 text-slate-300" />
          <Pill label="전체" value={b.total} cls="bg-slate-800 text-slate-300" />
        </div>
        {data.summary && <p className="mt-3 text-sm leading-relaxed text-slate-300">{data.summary}</p>}
      </header>

      <div className="grid gap-6 lg:grid-cols-2">
        <MoverTable title="상승 상위" rows={data.gainers} />
        <MoverTable title="하락 상위" rows={data.losers} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <SellerTable title="외국인 순매도 상위" rows={data.foreign_sellers} field="foreign" />
        <SellerTable title="기관 순매도 상위" rows={data.organ_sellers} field="organ" />
      </div>

      <MoverTable title="거래량 상위" rows={data.most_traded} showVol />

      {data.news.length > 0 && (
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
          <h3 className="mb-3 text-sm font-bold text-white">시장 주요 뉴스</h3>
          <ul className="space-y-2">
            {data.news.map((a, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <span className="mt-1 text-slate-600">•</span>
                <a href={a.link} target="_blank" rel="noopener noreferrer" className="text-slate-300 hover:text-sky-400 hover:underline">
                  {a.title}
                  <span className="ml-1.5 text-xs text-slate-500">{a.source}</span>
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="text-center text-xs text-slate-600">
        가격 기반 집계 + 거래상위 종목 투자자 동향(네이버) + Google News · 10분마다 갱신
      </p>
    </div>
  );
}

function Pill({ label, value, cls }: { label: string; value: number; cls: string }) {
  return (
    <span className={`rounded-full px-3 py-1 text-sm font-semibold tabular-nums ${cls}`}>
      {label} {value.toLocaleString("ko-KR")}
    </span>
  );
}

function MoverTable({ title, rows, showVol }: { title: string; rows: MoverRow[]; showVol?: boolean }) {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60">
      <div className="border-b border-slate-800 px-4 py-2.5 text-sm font-bold text-white">{title}</div>
      <table className="w-full text-sm">
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.ticker} className="border-b border-slate-800/60 last:border-0">
              <td className="py-2 pl-4 pr-2 text-slate-500">{i + 1}</td>
              <td className="py-2 pr-2">
                <span className="text-slate-100">{r.name}</span>
                <span className="ml-1 text-[11px] text-slate-500">{r.ticker}</span>
              </td>
              <td className="py-2 pr-2 text-right tabular-nums text-slate-300">{won(r.close)}</td>
              {showVol ? (
                <td className="py-2 pr-4 text-right tabular-nums text-slate-400">
                  {r.volume != null ? r.volume.toLocaleString("ko-KR") : "—"}
                </td>
              ) : (
                <td className={`py-2 pr-4 text-right tabular-nums font-semibold ${toneClass(r.change_pct)}`}>
                  {r.change_pct != null ? `${r.change_pct > 0 ? "+" : ""}${r.change_pct}%` : "—"}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function SellerTable({ title, rows, field }: { title: string; rows: FlowSeller[]; field: "foreign" | "organ" }) {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60">
      <div className="border-b border-slate-800 px-4 py-2.5 text-sm font-bold text-white">{title}</div>
      {rows.length === 0 ? (
        <div className="px-4 py-6 text-center text-xs text-slate-500">데이터 없음</div>
      ) : (
        <table className="w-full text-sm">
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.ticker} className="border-b border-slate-800/60 last:border-0">
                <td className="py-2 pl-4 pr-2 text-slate-500">{i + 1}</td>
                <td className="py-2 pr-2">
                  <span className="text-slate-100">{r.name}</span>
                  <span className="ml-1 text-[11px] text-slate-500">{r.ticker}</span>
                </td>
                <td className={`py-2 pr-4 text-right tabular-nums font-semibold ${toneClass(r[field])}`}>
                  {manShares(r[field])}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
