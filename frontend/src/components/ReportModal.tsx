"use client";

import { useEffect, useState } from "react";
import { api, Holder, ReportResponse } from "@/lib/api";
import { won, toneClass, arrow, manShares, tone, UP, DOWN } from "@/lib/format";
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

  // Close on Escape.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const p = rep?.price ?? {};
  const f = rep?.flow ?? {};
  const up = (p.change_pct ?? 0) > 0;
  const down = (p.change_pct ?? 0) < 0;
  const accent = up ? UP : down ? DOWN : "#94a3b8";

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="my-6 w-full max-w-2xl overflow-hidden rounded-2xl bg-white text-[#1f1f1f] shadow-2xl ring-1 ring-slate-900/10"
        onClick={(e) => e.stopPropagation()}
      >
        {/* tone accent strip */}
        <div className="h-1" style={{ background: accent }} />

        {/* header */}
        <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-6 pb-4 pt-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-[#3a7d2c]">
              <span>장마감 리포트</span>
              {p.date && <span className="font-normal normal-case tracking-normal text-slate-400">· {p.date}</span>}
            </div>
            <div className="mt-1 flex items-center gap-2">
              <h2 className="truncate text-xl font-bold text-slate-900">{rep?.name ?? stock.name}</h2>
              <span className="shrink-0 rounded-md bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-500">
                {stock.ticker}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="닫기"
            className="-mr-1 shrink-0 rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
          >
            ✕
          </button>
        </div>

        {loading ? (
          <div className="flex flex-col items-center gap-3 py-20 text-sm text-slate-400">
            <span className="h-6 w-6 animate-spin rounded-full border-2 border-slate-200 border-t-[#3a7d2c]" />
            리포트 생성 중…
          </div>
        ) : !rep ? (
          <div className="py-20 text-center text-sm text-rose-500">리포트를 불러오지 못했습니다.</div>
        ) : (
          <div className="space-y-6 px-6 py-5">
            {/* price hero */}
            {p.close != null && (
              <div
                className="flex items-end justify-between gap-4 rounded-xl border px-5 py-4"
                style={{
                  borderColor: `${accent}33`,
                  background: `${accent}0d`,
                }}
              >
                <div>
                  <div className="text-[11px] font-medium text-slate-500">종가</div>
                  <div className="mt-0.5 text-3xl font-bold leading-none tabular-nums text-slate-900">
                    {won(p.close)}
                    <span className="ml-1 text-base font-normal text-slate-400">원</span>
                  </div>
                </div>
                <div className={`text-right text-lg font-bold tabular-nums ${toneClass(p.change_pct)}`}>
                  <div className="flex items-center justify-end gap-1">
                    <span className="text-sm">{arrow(p.change)}</span>
                    {p.change != null ? won(Math.abs(p.change)) : ""}
                  </div>
                  <div className="text-sm">
                    {p.change_pct != null ? `${p.change_pct > 0 ? "+" : ""}${p.change_pct}%` : "—"}
                  </div>
                </div>
              </div>
            )}

            {/* summary */}
            <div className="rounded-xl border-l-[3px] border-[#3a7d2c] bg-[#f6faf4] py-3 pl-4 pr-4 text-[15px] leading-relaxed text-slate-700">
              {rep.summary || "데이터가 부족하여 요약을 생성하지 못했습니다."}
            </div>

            {/* investor flow */}
            <Section
              title="투자자별 매매동향"
              meta={f.date}
              badges={
                <>
                  {rep.lead_buyer && (
                    <Badge color={UP}>매수주도 {rep.lead_buyer}</Badge>
                  )}
                  {rep.lead_seller && (
                    <Badge color={DOWN}>매도주도 {rep.lead_seller}</Badge>
                  )}
                </>
              }
            >
              <div className="space-y-2">
                <FlowBar label="개인" v={f.individual} max={flowMax(f)} />
                <FlowBar label="외국인" v={f.foreign} max={flowMax(f)} />
                <FlowBar label="기관" v={f.organ} max={flowMax(f)} />
              </div>
              {f.foreign_ratio != null && (
                <div className="mt-2.5 border-t border-slate-100 pt-2 text-right text-xs text-slate-500">
                  외국인 보유율 <b className="text-slate-700">{f.foreign_ratio}%</b>
                </div>
              )}
            </Section>

            {/* major holders (DART 5%+) */}
            {holders.length > 0 && (
              <Section title="대량보유 주주" meta="5%+ · DART 공시">
                <div className="flex flex-wrap gap-1.5">
                  {holders.map((h, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600"
                    >
                      {h.name}
                      {h.ratio != null && <b className="text-[#3a7d2c]">{h.ratio}%</b>}
                    </span>
                  ))}
                </div>
              </Section>
            )}

            {/* news */}
            {rep.news.length > 0 && (
              <Section title="관련 주요 뉴스">
                <ul className="space-y-0.5">
                  {rep.news.map((a, i) => (
                    <li key={i}>
                      <a
                        href={a.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="-mx-2 flex items-start gap-2 rounded-lg px-2 py-1.5 text-sm text-slate-700 transition hover:bg-slate-50 hover:text-[#1155cc]"
                      >
                        <span className="mt-0.5 text-[#3a7d2c]">›</span>
                        <span className="flex-1">
                          {a.title}
                          <span className="ml-1.5 text-xs text-slate-400">{a.source}</span>
                        </span>
                      </a>
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            <p className="border-t border-slate-100 pt-3 text-[11px] leading-relaxed text-slate-400">{rep.note}</p>
          </div>
        )}
      </div>
    </div>
  );
}

/** Largest absolute net-buy across the three investor groups — bar scale. */
function flowMax(f: ReportResponse["flow"]): number {
  return Math.max(1, Math.abs(f?.individual ?? 0), Math.abs(f?.foreign ?? 0), Math.abs(f?.organ ?? 0));
}

function Section({
  title,
  meta,
  badges,
  children,
}: {
  title: string;
  meta?: string | null;
  badges?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-2.5 flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-bold text-slate-800">{title}</h3>
        {meta && <span className="text-xs font-normal text-slate-400">{meta}</span>}
        {badges && <span className="ml-auto flex gap-1.5">{badges}</span>}
      </div>
      {children}
    </div>
  );
}

function Badge({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <span
      className="rounded px-1.5 py-0.5 text-[11px] font-semibold"
      style={{ color, background: `${color}14` }}
    >
      {children}
    </span>
  );
}

/** A horizontal magnitude bar for one investor group's net-buy. */
function FlowBar({ label, v, max }: { label: string; v: number | null | undefined; max: number }) {
  const has = v != null && v !== 0;
  const sells = (v ?? 0) < 0;
  const color = tone(v ?? null);
  const width = has ? `${Math.max(4, (Math.abs(v as number) / max) * 100)}%` : "0%";
  return (
    <div className="flex items-center gap-3">
      <span className="w-12 shrink-0 text-xs font-medium text-slate-500">{label}</span>
      <div className="relative h-6 flex-1 overflow-hidden rounded-md bg-slate-100">
        <div className="absolute inset-y-0 left-0 rounded-md transition-all" style={{ width, background: color, opacity: 0.85 }} />
      </div>
      <span className={`w-20 shrink-0 text-right text-sm font-bold tabular-nums ${toneClass(v ?? null)}`}>
        {manShares(v ?? null)}
      </span>
      <span className="w-9 shrink-0 text-[10px] text-slate-400">{!has ? "" : sells ? "순매도" : "순매수"}</span>
    </div>
  );
}
