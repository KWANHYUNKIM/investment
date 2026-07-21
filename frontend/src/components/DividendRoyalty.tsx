"use client";

import { useEffect, useMemo, useState } from "react";
import { api, DividendRoyalty as DR, RoyaltyGroup, RoyaltyRow } from "@/lib/api";

const GREEN = "#217346";
const GOLD = "#b8860b";

function won(v: number | null | undefined): string {
  return v == null ? "—" : `${Math.round(v).toLocaleString("ko-KR")}원`;
}

// 배당왕/귀족 표
function RoyaltyTable({ group, accent, yearsLabel }: { group: RoyaltyGroup; accent: string; yearsLabel: string }) {
  if (!group.rows.length) {
    return <div className="px-4 py-8 text-center text-[12px] text-[#aaa]">목록 준비 중…</div>;
  }
  return (
    <div className="max-h-[420px] overflow-auto">
      <table className="w-full text-[12px]">
        <thead className="sticky top-0 bg-[#f5f5f5] text-left text-[10px] uppercase tracking-wide text-[#999]">
          <tr className="border-b border-[#eee]">
            <th className="px-3 py-1.5">종목</th>
            <th className="px-3 py-1.5">섹터</th>
            <th className="px-3 py-1.5 text-right">{yearsLabel}</th>
            <th className="px-3 py-1.5 text-right">배당수익률</th>
          </tr>
        </thead>
        <tbody>
          {group.rows.map((r) => (
            <tr key={r.ticker} className="border-t border-[#f2f2f2] hover:bg-[#faf9f4]">
              <td className="px-3 py-1.5">
                <span className="font-semibold text-[#333]">{r.name}</span>
                <span className="ml-1 text-[10px] text-[#aaa]">{r.ticker}</span>
              </td>
              <td className="px-3 py-1.5 text-[11px] text-[#888]">{r.sector ?? "—"}</td>
              <td className="px-3 py-1.5 text-right font-bold tabular-nums" style={{ color: accent }}>{r.years != null ? `${r.years}년` : "—"}</td>
              <td className="px-3 py-1.5 text-right tabular-nums text-[#c0392b]">{r.yield != null ? `${r.yield}%` : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DividendRoyalty() {
  const [d, setD] = useState<DR | null>(null);
  const [err, setErr] = useState("");
  const [tab, setTab] = useState<"kings" | "aristocrats" | "monthly">("kings");
  const [invest, setInvest] = useState("100000000"); // 1억

  useEffect(() => {
    api.dividendRoyalty().then(setD).catch((e) => setErr(e?.message ?? "불러오기 실패"));
  }, []);

  const num = (s: string) => Number(s.replace(/,/g, "")) || 0;
  // 월배당 포트 추정 (프론트에서 블렌드 수익률로 계산, 세후 15.4%)
  const port = useMemo(() => {
    if (!d) return null;
    const y = d.monthly.avg_yield ?? 0;
    const gross = num(invest) * y / 100;
    const net = gross * (1 - 0.154);
    return { y, monthlyGross: gross / 12, monthlyNet: net / 12, annualNet: net };
  }, [d, invest]);

  const TABS: { id: typeof tab; label: string; sub: string }[] = [
    { id: "kings", label: "👑 배당왕", sub: "50년+ 연속 증액" },
    { id: "aristocrats", label: "🎖️ 배당귀족", sub: "25년+ & S&P500" },
    { id: "monthly", label: "📅 월배당 포트", sub: "매월 배당 지급" },
  ];

  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
        <span className="text-sm font-semibold">배당 성장주 — 배당왕 · 배당귀족 · 월배당 포트</span>
        {d?.as_of && <span className="text-[10px] text-white/80">기준 {d.as_of}</span>}
      </div>

      {err ? (
        <div className="py-16 text-center text-sm text-rose-600">{err}</div>
      ) : !d ? (
        <div className="flex items-center gap-2 py-16 pl-4 text-sm text-[#888]">
          <span className="h-5 w-5 animate-spin rounded-full border-2 border-[#d0d0d0] border-t-[#217346]" /> 목록 불러오는 중…
        </div>
      ) : (
        <div className="p-4">
          {/* 탭 */}
          <div className="mb-3 flex gap-2">
            {TABS.map((t) => {
              const g = d[t.id];
              const active = tab === t.id;
              return (
                <button key={t.id} onClick={() => setTab(t.id)}
                  className={`flex-1 rounded-md border px-3 py-2 text-left transition ${active ? "border-[#217346] bg-[#eef6f0]" : "border-[#e2e2e2] bg-white hover:bg-[#f7f7f7]"}`}>
                  <div className="text-[13px] font-bold text-[#333]">{t.label}</div>
                  <div className="text-[10px] text-[#999]">{t.sub}</div>
                  <div className="mt-0.5 text-[11px] text-[#666]">{g.count}종목{g.avg_yield != null ? ` · 평균 ${g.avg_yield}%` : ""}</div>
                </button>
              );
            })}
          </div>

          {/* 설명 */}
          <div className="mb-2 rounded bg-[#f8faf9] px-3 py-1.5 text-[11px] text-[#666]">
            {tab === "kings" && "배당왕(Dividend Kings): 50년 이상 매년 배당을 늘려온 기업. 최고 수준의 배당 신뢰도."}
            {tab === "aristocrats" && "배당귀족(Dividend Aristocrats): 25년 이상 배당을 늘려왔고 S&P 500에 포함된 기업."}
            {tab === "monthly" && "월배당: 매월 배당을 지급하는 종목·ETF. 생활비형 현금흐름에 적합(대부분 REIT·BDC·인컴 ETF)."}
          </div>

          {tab === "kings" && <RoyaltyTable group={d.kings} accent={GOLD} yearsLabel="연속 증액" />}
          {tab === "aristocrats" && <RoyaltyTable group={d.aristocrats} accent={GREEN} yearsLabel="연속 증액" />}
          {tab === "monthly" && (
            <div className="flex flex-col gap-3">
              {/* 월배당 포트 시뮬레이터 */}
              <div className="rounded-md border border-[#e5e5e5] bg-[#f8faf9] p-3">
                <div className="text-[12px] font-bold text-[#217346]">월배당 포트폴리오 — 투자금별 월 배당 추정</div>
                <div className="mt-2 flex flex-wrap items-center gap-3">
                  <label className="text-[11px] text-[#555]">투자금(원)
                    <input value={Number(num(invest)).toLocaleString("ko-KR")} onChange={(e) => setInvest(e.target.value)}
                      className="ml-2 w-40 rounded border border-[#cdcdcd] px-2 py-1 text-right text-sm tabular-nums outline-none focus:border-[#217346]" />
                  </label>
                  {port && (
                    <div className="flex flex-wrap gap-x-6 gap-y-1 text-[12px]">
                      <span className="text-[#888]">블렌드 수익률 <b className="text-[#c0392b]">{port.y}%</b></span>
                      <span className="text-[#888]">월 배당(세전) <b className="tabular-nums text-[#217346]">{won(port.monthlyGross)}</b></span>
                      <span className="text-[#888]">월 배당(세후) <b className="tabular-nums text-[#217346]">{won(port.monthlyNet)}</b></span>
                    </div>
                  )}
                </div>
                <div className="mt-1 text-[10px] text-[#aaa]">동일가중·블렌드 배당수익률 기준 추정. 세후는 국내 배당소득세 15.4% 적용 근사값.</div>
              </div>
              {/* 월배당 종목 목록 */}
              {d.monthly.rows.length ? (
                <div className="max-h-[360px] overflow-auto rounded-md border border-[#e5e5e5]">
                  <table className="w-full text-[12px]">
                    <thead className="sticky top-0 bg-[#f5f5f5] text-left text-[10px] uppercase tracking-wide text-[#999]">
                      <tr className="border-b border-[#eee]">
                        <th className="px-3 py-1.5">종목</th>
                        <th className="px-3 py-1.5">유형</th>
                        <th className="px-3 py-1.5 text-right">배당수익률</th>
                        <th className="px-3 py-1.5 text-right">지급</th>
                      </tr>
                    </thead>
                    <tbody>
                      {d.monthly.rows.map((r: RoyaltyRow) => (
                        <tr key={r.ticker} className="border-t border-[#f2f2f2] hover:bg-[#faf9f4]">
                          <td className="px-3 py-1.5"><span className="font-semibold text-[#333]">{r.name}</span><span className="ml-1 text-[10px] text-[#aaa]">{r.ticker}</span></td>
                          <td className="px-3 py-1.5 text-[11px] text-[#888]">{r.type ?? "—"}</td>
                          <td className="px-3 py-1.5 text-right font-bold tabular-nums text-[#c0392b]">{r.yield != null ? `${r.yield}%` : "—"}</td>
                          <td className="px-3 py-1.5 text-right text-[10px] text-[#aaa]">{r.freq === "monthly" ? "매월" : r.freq ?? "매월"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="px-4 py-8 text-center text-[12px] text-[#aaa]">목록 준비 중…</div>
              )}
            </div>
          )}

          <div className="mt-3 text-[10px] leading-relaxed text-[#bbb]">{d.note}</div>
        </div>
      )}
    </div>
  );
}
