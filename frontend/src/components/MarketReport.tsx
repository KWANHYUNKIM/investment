"use client";

import { useEffect, useState } from "react";
import { api, MarketReport as MR, MoverRow, StockInsight, InvestorDriver } from "@/lib/api";
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
    return <div className="py-20 text-center text-sm text-slate-400">데일리 리포트 생성 중… (최초 약 10~20초)</div>;
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

      {/* 핵심: 종목별 투자자 매매 이유 분석 */}
      <section>
        <div className="mb-3 flex items-baseline justify-between">
          <h3 className="text-base font-bold text-white">🔍 거래 상위 종목 — 투자자별 매매 이유 분석</h3>
          <span className="text-xs text-slate-500">수급·밸류에이션·뉴스 기반 추정</span>
        </div>
        {data.insights.length === 0 ? (
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-8 text-center text-sm text-slate-500">
            분석할 종목 데이터가 없습니다.
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {data.insights.map((s) => (
              <InsightCard key={s.ticker} s={s} />
            ))}
          </div>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <MoverTable title="상승 상위" rows={data.gainers} />
        <MoverTable title="하락 상위" rows={data.losers} />
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
        매매 이유는 수급(네이버) · 가격 모멘텀 · 밸류에이션 · 뉴스 키워드를 조합한 <b>규칙 기반 추정</b>이며, 투자 권유가 아닙니다. · 10분마다 갱신
      </p>
    </div>
  );
}

function InsightCard({ s }: { s: StockInsight }) {
  const frd = s.foreign_ratio_delta;
  return (
    <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60">
      <div className="flex items-baseline justify-between border-b border-slate-800 px-4 py-3">
        <div className="min-w-0">
          <span className="font-bold text-white">{s.name}</span>
          <span className="ml-1.5 text-[11px] text-slate-500">{s.ticker}</span>
          {s.sector && <span className="ml-2 text-[11px] text-slate-500">{s.sector}</span>}
        </div>
        <div className="shrink-0 text-right">
          <div className="tabular-nums text-slate-200">{won(s.close)}원</div>
          <div className={`text-xs font-semibold tabular-nums ${toneClass(s.change_pct)}`}>
            {s.change_pct != null ? `${s.change_pct > 0 ? "+" : ""}${s.change_pct}%` : "—"}
          </div>
        </div>
      </div>

      {s.foreign_ratio != null && (
        <div className="border-b border-slate-800/60 px-4 py-1.5 text-[11px] text-slate-400">
          외국인 보유율 {s.foreign_ratio.toFixed(1)}%
          {frd != null && frd !== 0 && (
            <span className={frd > 0 ? "ml-1 text-[#ff8787]" : "ml-1 text-[#74c0fc]"}>
              ({frd > 0 ? "+" : ""}
              {frd.toFixed(2)}%p)
            </span>
          )}
        </div>
      )}

      <div className="divide-y divide-slate-800/60">
        {s.investors.map((iv) => (
          <DriverRow key={iv.key} iv={iv} />
        ))}
      </div>

      {s.news.length > 0 && (
        <div className="border-t border-slate-800 bg-slate-950/40 px-4 py-2.5">
          <div className="mb-1 text-[11px] font-semibold text-slate-500">종목 뉴스</div>
          <ul className="space-y-1">
            {s.news.map((a, i) => (
              <li key={i} className="truncate text-xs">
                <a href={a.link ?? "#"} target="_blank" rel="noopener noreferrer" className="text-slate-400 hover:text-sky-400 hover:underline">
                  {a.title}
                  {a.source && <span className="ml-1 text-slate-600">· {a.source}</span>}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function DriverRow({ iv }: { iv: InvestorDriver }) {
  const buy = iv.action === "순매수";
  const sell = iv.action === "순매도";
  const badge = buy
    ? "bg-[#3a1f1f] text-[#ff8787]"
    : sell
      ? "bg-[#1f2a3a] text-[#74c0fc]"
      : "bg-slate-800 text-slate-400";
  return (
    <div className="px-4 py-2.5">
      <div className="flex items-center gap-2">
        <span className="w-10 shrink-0 text-sm font-semibold text-slate-200">{iv.type}</span>
        <span className={`rounded px-1.5 py-0.5 text-[11px] font-semibold ${badge}`}>{iv.action}</span>
        {iv.qty != null && iv.qty !== 0 && (
          <span className={`text-xs tabular-nums ${toneClass(iv.qty)}`}>{manShares(iv.qty)}주</span>
        )}
      </div>
      {iv.reasons.length > 0 && (
        <ul className="mt-1.5 space-y-0.5 pl-12">
          {iv.reasons.map((r, i) => (
            <li key={i} className="flex items-start gap-1.5 text-xs text-slate-400">
              <span className="mt-1 text-slate-600">›</span>
              <span>{r}</span>
            </li>
          ))}
        </ul>
      )}
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
