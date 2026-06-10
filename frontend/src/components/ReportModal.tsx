"use client";

import { useEffect, useState } from "react";
import { api, Holder, ReportResponse } from "@/lib/api";
import { won, toneClass, arrow, manShares } from "@/lib/format";
import type { PickedStock } from "./NewsPanel";

export function ReportModal({ stock, onClose }: { stock: PickedStock; onClose: () => void }) {
  const [rep, setRep] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [holders, setHolders] = useState<Holder[]>([]);

  useEffect(() => {
    setLoading(true);
    api
      .report(stock.ticker, stock.name ?? undefined)
      .then(setRep)
      .catch(() => setRep(null))
      .finally(() => setLoading(false));
    api
      .holders(stock.ticker)
      .then((d) => setHolders(d.holders))
      .catch(() => setHolders([]));
  }, [stock.ticker, stock.name]);

  const p = rep?.price ?? {};
  const f = rep?.flow ?? {};

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4">
      <div className="my-6 w-full max-w-2xl rounded-xl border border-slate-300 bg-white text-[#1f1f1f] shadow-2xl">
        {/* header */}
        <div className="flex items-start justify-between border-b border-slate-200 bg-[#f7faf7] px-5 py-3.5">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-base font-bold">📋 장마감 리포트</span>
              <span className="rounded bg-slate-200 px-1.5 py-0.5 text-xs text-slate-600">{stock.ticker}</span>
            </div>
            <div className="mt-0.5 text-sm text-slate-600">
              {rep?.name ?? stock.name} {p.date && <span className="text-slate-400">· {p.date}</span>}
            </div>
          </div>
          <button onClick={onClose} className="rounded p-1.5 text-slate-400 hover:bg-slate-200 hover:text-slate-700">✕</button>
        </div>

        {loading ? (
          <div className="py-16 text-center text-sm text-slate-400">리포트 생성 중…</div>
        ) : !rep ? (
          <div className="py-16 text-center text-sm text-rose-500">리포트를 불러오지 못했습니다.</div>
        ) : (
          <div className="space-y-5 px-5 py-4">
            {/* price headline */}
            {p.close != null && (
              <div className="flex items-baseline gap-3">
                <span className="text-3xl font-bold tabular-nums">{won(p.close)}<span className="ml-1 text-base font-normal text-slate-400">원</span></span>
                <span className={`text-lg font-semibold tabular-nums ${toneClass(p.change_pct)}`}>
                  {arrow(p.change)} {p.change != null ? won(Math.abs(p.change)) : ""} ({p.change_pct != null ? `${p.change_pct > 0 ? "+" : ""}${p.change_pct}%` : "—"})
                </span>
              </div>
            )}

            {/* summary */}
            <div className="rounded-lg border border-slate-200 bg-[#fbfdfb] p-4 text-[15px] leading-relaxed text-slate-800">
              {rep.summary || "데이터가 부족하여 요약을 생성하지 못했습니다."}
            </div>

            {/* investor flow */}
            <div>
              <div className="mb-2 flex items-center gap-2 text-sm font-bold text-[#244d1a]">
                투자자별 매매동향
                {f.date && <span className="text-xs font-normal text-slate-400">{f.date}</span>}
                {rep.lead_seller && (
                  <span className="rounded bg-[#e7f0fb] px-1.5 py-0.5 text-[11px] font-semibold text-[#1971c2]">매도주도 {rep.lead_seller}</span>
                )}
                {rep.lead_buyer && (
                  <span className="rounded bg-[#fdeaea] px-1.5 py-0.5 text-[11px] font-semibold text-[#c92a2a]">매수주도 {rep.lead_buyer}</span>
                )}
              </div>
              <div className="grid grid-cols-3 gap-2">
                <FlowBox label="개인" v={f.individual} />
                <FlowBox label="외국인" v={f.foreign} />
                <FlowBox label="기관" v={f.organ} />
              </div>
              {f.foreign_ratio != null && (
                <div className="mt-1.5 text-right text-xs text-slate-500">외국인 보유율 {f.foreign_ratio}%</div>
              )}
            </div>

            {/* major holders (DART 5%+) */}
            {holders.length > 0 && (
              <div>
                <div className="mb-2 text-sm font-bold text-[#244d1a]">대량보유 주주 (5%+ · DART 공시)</div>
                <div className="flex flex-wrap gap-1.5">
                  {holders.map((h, i) => (
                    <span key={i} className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-700">
                      {h.name} <b className="text-[#244d1a]">{h.ratio != null ? `${h.ratio}%` : ""}</b>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* news */}
            {rep.news.length > 0 && (
              <div>
                <div className="mb-2 text-sm font-bold text-[#244d1a]">관련 주요 뉴스</div>
                <ul className="space-y-1.5">
                  {rep.news.map((a, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-sm">
                      <span className="mt-1 text-slate-300">•</span>
                      <a href={a.link} target="_blank" rel="noopener noreferrer" className="text-slate-700 hover:text-[#1155cc] hover:underline">
                        {a.title}
                        <span className="ml-1.5 text-xs text-slate-400">{a.source}</span>
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <p className="border-t border-slate-100 pt-3 text-[11px] leading-relaxed text-slate-400">{rep.note}</p>
          </div>
        )}
      </div>
    </div>
  );
}

function FlowBox({ label, v }: { label: string; v: number | null | undefined }) {
  const sells = v != null && v < 0;
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-center">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`mt-0.5 text-base font-bold tabular-nums ${toneClass(v ?? null)}`}>{manShares(v ?? null)}</div>
      <div className="text-[10px] text-slate-400">{v == null ? "" : sells ? "순매도" : "순매수"}</div>
    </div>
  );
}
