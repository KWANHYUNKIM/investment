"use client";

import { useEffect, useState } from "react";
import { api, MarketReport as MR, MoverRow, StockInsight, InvestorDriver } from "@/lib/api";
import { won, toneClass, manShares, UP, DOWN } from "@/lib/format";

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
    return (
      <div className="flex flex-col items-center gap-3 py-24 text-sm text-slate-400">
        <span className="h-7 w-7 animate-spin rounded-full border-2 border-slate-700 border-t-emerald-400" />
        데일리 리포트 생성 중… <span className="text-slate-500">(최초 약 10~20초)</span>
      </div>
    );
  if (err) return <div className="py-20 text-center text-sm text-rose-400">{err}</div>;
  if (!data) return null;

  const b = data.breadth;
  const total = Math.max(1, b.total);

  return (
    <div className="space-y-6 text-slate-200">
      {/* ── header ───────────────────────────────────────────── */}
      <header className="overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 to-slate-900/40 shadow-lg shadow-black/30">
        <div className="flex flex-wrap items-baseline justify-between gap-2 px-6 pt-5">
          <h2 className="flex items-center gap-2 text-lg font-bold text-white">
            <span className="text-emerald-400">●</span> 시장 데일리 리포트
          </h2>
          <span className="text-xs text-slate-500">{data.date} 기준 · 10분마다 갱신</span>
        </div>

        {/* breadth: numbers + proportion bar */}
        <div className="px-6 pt-4">
          <div className="flex items-end gap-6">
            <BreadthStat label="상승" value={b.up} color={UP} />
            <BreadthStat label="하락" value={b.down} color={DOWN} />
            <BreadthStat label="보합" value={b.flat} color="#94a3b8" />
            <div className="ml-auto text-right">
              <div className="text-[11px] uppercase tracking-wide text-slate-500">전체</div>
              <div className="text-xl font-bold tabular-nums text-slate-200">{b.total.toLocaleString("ko-KR")}</div>
            </div>
          </div>
          <div className="mt-3 flex h-2 overflow-hidden rounded-full bg-slate-800">
            <div style={{ width: `${(b.up / total) * 100}%`, background: UP }} />
            <div style={{ width: `${(b.flat / total) * 100}%`, background: "#475569" }} />
            <div style={{ width: `${(b.down / total) * 100}%`, background: DOWN }} />
          </div>
        </div>

        {data.summary && (
          <p className="mt-4 border-t border-slate-800 px-6 py-4 text-sm leading-relaxed text-slate-300">
            {data.summary}
          </p>
        )}
      </header>

      {/* ── insight cards ────────────────────────────────────── */}
      <section>
        <div className="mb-3 flex items-baseline justify-between">
          <h3 className="text-base font-bold text-white">거래 상위 종목 · 투자자별 매매 이유</h3>
          <span className="text-xs text-slate-500">수급 · 밸류에이션 · 뉴스 기반 추정</span>
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

      {/* ── movers ───────────────────────────────────────────── */}
      <div className="grid gap-4 lg:grid-cols-2">
        <MoverTable title="상승 상위" accent={UP} rows={data.gainers} />
        <MoverTable title="하락 상위" accent={DOWN} rows={data.losers} />
      </div>
      <MoverTable title="거래량 상위" accent="#94a3b8" rows={data.most_traded} showVol />

      {/* ── market news ──────────────────────────────────────── */}
      {data.news.length > 0 && (
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg shadow-black/20">
          <h3 className="mb-3 text-sm font-bold text-white">시장 주요 뉴스</h3>
          <ul className="space-y-0.5">
            {data.news.map((a, i) => (
              <li key={i}>
                <a
                  href={a.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="-mx-2 flex items-start gap-2 rounded-lg px-2 py-1.5 text-sm text-slate-300 transition hover:bg-slate-800/60 hover:text-sky-300"
                >
                  <span className="mt-0.5 text-emerald-400/70">›</span>
                  <span className="flex-1">
                    {a.title}
                    <span className="ml-1.5 text-xs text-slate-500">{a.source}</span>
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}

      <p className="text-center text-xs leading-relaxed text-slate-600">
        매매 이유는 수급(네이버) · 가격 모멘텀 · 밸류에이션 · 뉴스 키워드를 조합한 <b className="text-slate-500">규칙 기반 추정</b>이며, 투자 권유가 아닙니다.
      </p>
    </div>
  );
}

function BreadthStat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-xl font-bold tabular-nums" style={{ color }}>
        {value.toLocaleString("ko-KR")}
      </div>
    </div>
  );
}

function InsightCard({ s }: { s: StockInsight }) {
  const frd = s.foreign_ratio_delta;
  const up = (s.change_pct ?? 0) > 0;
  const down = (s.change_pct ?? 0) < 0;
  const accent = up ? UP : down ? DOWN : "#64748b";

  return (
    <section className="group relative overflow-hidden rounded-xl border border-slate-700/70 bg-slate-900 shadow-lg shadow-black/30">
      {/* left tone accent */}
      <span className="absolute inset-y-0 left-0 w-1" style={{ background: accent }} />

      {/* header */}
      <div className="flex items-start justify-between gap-3 px-4 py-3 pl-5">
        <div className="min-w-0">
          <div className="truncate font-bold text-white">{s.name}</div>
          <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-slate-500">
            <span className="font-mono">{s.ticker}</span>
            {s.sector && <span className="rounded bg-slate-800 px-1.5 py-0.5 text-slate-400">{s.sector}</span>}
            {s.foreign_ratio != null && (
              <span>
                외인 {s.foreign_ratio.toFixed(1)}%
                {frd != null && frd !== 0 && (
                  <span style={{ color: frd > 0 ? UP : DOWN }}>
                    {" "}
                    ({frd > 0 ? "+" : ""}
                    {frd.toFixed(2)}%p)
                  </span>
                )}
              </span>
            )}
          </div>
        </div>
        <div className="shrink-0 text-right">
          <div className="text-lg font-bold tabular-nums text-slate-100">{won(s.close)}원</div>
          <div
            className="mt-0.5 inline-block rounded px-1.5 py-0.5 text-xs font-bold tabular-nums"
            style={{ color: accent, background: `${accent}1f` }}
          >
            {s.change_pct != null ? `${s.change_pct > 0 ? "+" : ""}${s.change_pct}%` : "—"}
          </div>
        </div>
      </div>

      {/* investor rows */}
      <div className="space-y-1 px-3 pb-3">
        {s.investors.map((iv) => (
          <DriverRow key={iv.key} iv={iv} />
        ))}
      </div>

      {/* stock news */}
      {s.news.length > 0 && (
        <div className="border-t border-slate-800 bg-slate-950/50 px-4 py-2.5 pl-5">
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">종목 뉴스</div>
          <ul className="space-y-1">
            {s.news.map((a, i) => (
              <li key={i} className="truncate text-xs">
                <a
                  href={a.link ?? "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-slate-400 transition hover:text-sky-300 hover:underline"
                >
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
  const tint = buy ? `${UP}14` : sell ? `${DOWN}14` : "transparent";
  const badgeColor = buy ? UP : sell ? DOWN : "#94a3b8";

  return (
    <div className="rounded-lg px-2.5 py-2" style={{ background: tint }}>
      <div className="flex items-center gap-2">
        <span className="w-11 shrink-0 text-sm font-semibold text-slate-200">{iv.type}</span>
        <span
          className="rounded px-1.5 py-0.5 text-[11px] font-bold"
          style={{ color: badgeColor, background: `${badgeColor}26` }}
        >
          {iv.action}
        </span>
        {iv.qty != null && iv.qty !== 0 && (
          <span className={`text-xs font-semibold tabular-nums ${toneClass(iv.qty)}`}>{manShares(iv.qty)}주</span>
        )}
      </div>
      {iv.reasons.length > 0 && (
        <ul className="mt-1 space-y-0.5 pl-[3.25rem]">
          {iv.reasons.map((r, i) => (
            <li key={i} className="flex items-start gap-1.5 text-xs leading-relaxed text-slate-300">
              <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-slate-600" />
              <span>{r}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function MoverTable({
  title,
  rows,
  accent,
  showVol,
}: {
  title: string;
  rows: MoverRow[];
  accent: string;
  showVol?: boolean;
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60 shadow-lg shadow-black/20">
      <div className="flex items-center gap-2 border-b border-slate-800 px-4 py-2.5">
        <span className="h-3 w-1 rounded-full" style={{ background: accent }} />
        <span className="text-sm font-bold text-white">{title}</span>
      </div>
      <table className="w-full text-sm">
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.ticker} className="border-b border-slate-800/50 transition last:border-0 hover:bg-slate-800/40">
              <td className="w-8 py-2 pl-4 pr-1 text-right tabular-nums text-xs text-slate-600">{i + 1}</td>
              <td className="py-2 pr-2">
                <span className="text-slate-100">{r.name}</span>
                <span className="ml-1.5 font-mono text-[11px] text-slate-500">{r.ticker}</span>
              </td>
              <td className="py-2 pr-2 text-right tabular-nums text-slate-300">{won(r.close)}</td>
              {showVol ? (
                <td className="py-2 pr-4 text-right tabular-nums text-slate-400">
                  {r.volume != null ? r.volume.toLocaleString("ko-KR") : "—"}
                </td>
              ) : (
                <td className={`py-2 pr-4 text-right font-semibold tabular-nums ${toneClass(r.change_pct)}`}>
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
