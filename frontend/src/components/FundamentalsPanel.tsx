"use client";

import { useEffect, useState } from "react";
import { api, FundamentalsResponse, TargetPrice, TradeSignals } from "@/lib/api";
import type { PickedStock } from "./NewsPanel";

function verdictColor(v?: string | null) {
  return v === "매수" ? "#c92a2a" : v === "매도" ? "#1971c2" : "#666";
}
function scoreColor(v: number | null | undefined) {
  if (v == null) return "#999";
  return v > 0 ? "#c92a2a" : v < 0 ? "#1971c2" : "#888";
}

function won(v: number | null | undefined): string {
  if (v == null) return "—";
  return Math.round(v).toLocaleString("ko-KR");
}
function upCls(v: number | null | undefined): string {
  if (v == null) return "text-[#999]";
  return v > 0 ? "text-[#c92a2a]" : v < 0 ? "text-[#1971c2]" : "text-[#666]";
}
function upTxt(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

const ROWS: { key: string; label: string; suffix?: string }[] = [
  { key: "per", label: "PER", suffix: "배" },
  { key: "pbr", label: "PBR", suffix: "배" },
  { key: "roe", label: "ROE", suffix: "%" },
  { key: "debt_ratio", label: "부채비율", suffix: "%" },
  { key: "div_yield", label: "배당", suffix: "%" },
  { key: "foreign_ratio", label: "외인소진율", suffix: "%" },
];

export function FundamentalsPanel({ stock }: { stock: PickedStock | null }) {
  const [data, setData] = useState<FundamentalsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [tp, setTp] = useState<TargetPrice | null>(null);
  const [tpLoading, setTpLoading] = useState(false);
  const [sig, setSig] = useState<TradeSignals | null>(null);
  const [sigLoading, setSigLoading] = useState(false);

  useEffect(() => {
    if (!stock?.ticker) {
      setData(null);
      return;
    }
    let alive = true;
    setLoading(true);
    const load = () =>
      api
        .fundamentals(stock.ticker)
        .then((d) => alive && setData(d))
        .catch(() => alive && setData(null))
        .finally(() => alive && setLoading(false));
    load();
    const id = setInterval(load, 60000); // 변화 누적 반영
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [stock?.ticker]);

  useEffect(() => {
    if (!stock?.ticker) {
      setTp(null);
      return;
    }
    let alive = true;
    setTpLoading(true);
    setTp(null);
    api
      .targetPrice(stock.ticker)
      .then((d) => alive && setTp(d))
      .catch(() => alive && setTp(null))
      .finally(() => alive && setTpLoading(false));
    return () => { alive = false; };
  }, [stock?.ticker]);

  useEffect(() => {
    if (!stock?.ticker) {
      setSig(null);
      return;
    }
    let alive = true;
    setSigLoading(true);
    setSig(null);
    api
      .signals(stock.ticker)
      .then((d) => alive && setSig(d))
      .catch(() => alive && setSig(null))
      .finally(() => alive && setSigLoading(false));
    return () => { alive = false; };
  }, [stock?.ticker]);

  if (!stock) return null;
  const lt = data?.latest;
  const ch = data?.change;

  return (
    <div className="shrink-0 border-b border-[#d0d0d0] bg-white">
      <div className="flex items-center justify-between border-b border-[#e6e6e6] bg-[#f0f4f0] px-3 py-1.5">
        <span className="text-xs font-bold text-[#244d1a]">펀더멘털 {ch ? "· 변화(Δ)" : ""}</span>
        {lt?.date && <span className="text-[10px] text-[#aaa]">{lt.date}</span>}
      </div>
      {loading && !data ? (
        <div className="py-3 text-center text-xs text-[#999]">불러오는 중…</div>
      ) : !lt ? (
        <div className="px-3 py-3 text-xs text-[#bbb]">펀더멘털 데이터가 아직 없습니다(크롤링 대기).</div>
      ) : (
        <div className="grid grid-cols-3 gap-px bg-[#eee] p-px text-center">
          {ROWS.map((r) => {
            const v = lt[r.key as keyof typeof lt] as number | null;
            const d = ch?.[r.key] ?? null;
            return (
              <div key={r.key} className="bg-white px-1 py-2">
                <div className="text-[10px] text-[#888]">{r.label}</div>
                <div className="text-xs font-bold tabular-nums text-[#333]">
                  {v == null ? "—" : `${v}${r.suffix ?? ""}`}
                </div>
                {d != null && d !== 0 && (
                  <div className={`text-[9px] tabular-nums ${d > 0 ? "text-[#c92a2a]" : "text-[#1971c2]"}`}>
                    {d > 0 ? "▲" : "▼"}{Math.abs(d)}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* 목표주가 (밸류에이션 적정주가 + 강세/기준/약세) */}
      <div className="border-t border-[#e6e6e6]">
        <div className="flex items-center justify-between bg-[#f0f4f0] px-3 py-1.5">
          <span className="text-xs font-bold text-[#244d1a]">목표주가</span>
          {tp?.base != null && (
            <span className="text-[10px] text-[#666]">
              적정 <b>{won(tp.base)}</b> · <b className={upCls(tp.base_upside_pct)}>{upTxt(tp.base_upside_pct)}</b>
            </span>
          )}
        </div>
        {tpLoading && !tp ? (
          <div className="py-3 text-center text-xs text-[#999]">계산 중…</div>
        ) : !tp || tp.scenarios.length === 0 ? (
          <div className="px-3 py-3 text-[11px] leading-relaxed text-[#bbb]">
            {tp?.note ?? "목표주가를 계산할 수 없습니다."}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-3 gap-px bg-[#eee] p-px text-center">
              {tp.scenarios.map((s) => (
                <div key={s.name} className="bg-white px-1 py-2">
                  <div className="text-[10px] text-[#888]">{s.name}</div>
                  <div className="text-xs font-bold tabular-nums text-[#333]">
                    {s.target != null ? won(s.target) : "—"}
                  </div>
                  <div className={`text-[9px] font-semibold tabular-nums ${upCls(s.upside_pct)}`}>
                    {upTxt(s.upside_pct)}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-0.5 px-3 py-1.5 text-[9px] text-[#999]">
              <span>현재가 <b className="text-[#555]">{won(tp.close)}</b></span>
              {tp.fundamentals?.eps != null && <span>EPS <b className="text-[#555]">{won(tp.fundamentals.eps)}</b></span>}
              {tp.fundamentals?.bps != null && <span>BPS <b className="text-[#555]">{won(tp.fundamentals.bps)}</b></span>}
              {tp.target_per_used != null && <span>목표PER <b className="text-[#555]">{tp.target_per_used}</b></span>}
            </div>
            {tp.ai?.rationale && (
              <div className="border-t border-[#eee] bg-[#f7faf8] px-3 py-1.5 text-[10px] leading-relaxed text-[#456]">
                <b className="text-[#217346]">AI</b> {tp.ai.rationale}
              </div>
            )}
          </>
        )}
      </div>

      {/* 매매 신호 (기술적) + 손절/목표 */}
      <div className="border-t border-[#e6e6e6]">
        <div className="flex items-center justify-between bg-[#f0f4f0] px-3 py-1.5">
          <span className="text-xs font-bold text-[#244d1a]">매매 신호 (기술적)</span>
          {sig?.verdict && (
            <span className="rounded px-2 py-0.5 text-[10px] font-bold text-white" style={{ background: verdictColor(sig.verdict) }}>
              {sig.verdict}{sig.score != null ? ` ${sig.score > 0 ? "+" : ""}${sig.score}` : ""}
            </span>
          )}
        </div>
        {sigLoading && !sig ? (
          <div className="py-3 text-center text-xs text-[#999]">계산 중…</div>
        ) : !sig || !sig.verdict ? (
          <div className="px-3 py-3 text-[11px] leading-relaxed text-[#bbb]">{sig?.note ?? "가격 데이터가 부족합니다."}</div>
        ) : (
          <>
            {/* 핵심 지표 4칸 */}
            <div className="grid grid-cols-4 gap-px bg-[#eee] p-px text-center">
              <div className="bg-white px-1 py-1.5">
                <div className="text-[9px] text-[#888]">RSI</div>
                <div className="text-[11px] font-bold tabular-nums text-[#333]">{sig.rsi ?? "—"}</div>
              </div>
              <div className="bg-white px-1 py-1.5">
                <div className="text-[9px] text-[#888]">이평배열</div>
                <div className="text-[11px] font-bold" style={{ color: sig.ma_arrange === "정배열" ? "#c92a2a" : sig.ma_arrange === "역배열" ? "#1971c2" : "#666" }}>{sig.ma_arrange ?? "—"}</div>
              </div>
              <div className="bg-white px-1 py-1.5">
                <div className="text-[9px] text-[#888]">MACD</div>
                <div className="text-[11px] font-bold tabular-nums" style={{ color: scoreColor(sig.macd_hist) }}>{sig.macd_hist != null ? (sig.macd_hist > 0 ? "양(+)" : "음(−)") : "—"}</div>
              </div>
              <div className="bg-white px-1 py-1.5">
                <div className="text-[9px] text-[#888]">52주위치</div>
                <div className="text-[11px] font-bold tabular-nums text-[#333]">{sig.pos_52w != null ? `${sig.pos_52w}%` : "—"}</div>
              </div>
            </div>

            {/* 손절 / 목표 / 손익비 */}
            {sig.risk && (
              <div className="grid grid-cols-3 gap-px bg-[#eee] p-px text-center">
                <div className="bg-white px-1 py-1.5">
                  <div className="text-[9px] text-[#888]">손절(2·ATR)</div>
                  <div className="text-[11px] font-bold tabular-nums text-[#1971c2]">{sig.risk.stop_loss != null ? sig.risk.stop_loss.toLocaleString("ko-KR") : "—"}</div>
                </div>
                <div className="bg-white px-1 py-1.5">
                  <div className="text-[9px] text-[#888]">목표(3·ATR)</div>
                  <div className="text-[11px] font-bold tabular-nums text-[#c92a2a]">{sig.risk.target1 != null ? sig.risk.target1.toLocaleString("ko-KR") : "—"}</div>
                </div>
                <div className="bg-white px-1 py-1.5">
                  <div className="text-[9px] text-[#888]">손익비</div>
                  <div className="text-[11px] font-bold tabular-nums text-[#333]">{sig.risk.risk_reward != null ? `${sig.risk.risk_reward}:1` : "—"}</div>
                </div>
              </div>
            )}

            {/* 신호 목록 */}
            <div className="flex flex-col gap-0.5 px-3 py-2">
              {sig.signals.map((s, i) => (
                <div key={i} className="flex items-center gap-1.5 text-[10px]">
                  <span className="w-2 text-center font-bold" style={{ color: scoreColor(s.score) }}>
                    {s.score > 0 ? "▲" : s.score < 0 ? "▼" : "·"}
                  </span>
                  <span className="text-[#555]">{s.view}</span>
                </div>
              ))}
            </div>
            {sig.risk?.support != null && (
              <div className="px-3 pb-1.5 text-[9px] text-[#999]">
                지지 {sig.risk.support.toLocaleString("ko-KR")} · 저항 {sig.risk.resistance?.toLocaleString("ko-KR")} · ATR {sig.atr?.toLocaleString("ko-KR")}
              </div>
            )}
            {sig.backtest && sig.backtest.trades > 0 && (
              <div className="border-t border-[#eee] bg-[#fafafa] px-3 py-1.5 text-[10px] text-[#666]">
                <b>신호 백테스트</b>(골든/데드크로스): {sig.backtest.trades}회 · 승률{" "}
                <b>{sig.backtest.win_rate}%</b> · 전략{" "}
                <b className={scoreColor(sig.backtest.strat_return_pct)}>{sig.backtest.strat_return_pct != null ? `${sig.backtest.strat_return_pct > 0 ? "+" : ""}${sig.backtest.strat_return_pct}%` : "—"}</b>{" "}
                <span className="text-[#999]">(보유 {sig.backtest.bh_return_pct != null ? `${sig.backtest.bh_return_pct > 0 ? "+" : ""}${sig.backtest.bh_return_pct}%` : "—"})</span>
              </div>
            )}
            <div className="px-3 pb-2 text-[9px] leading-relaxed text-[#bbb]">{sig.note}</div>
          </>
        )}
      </div>
    </div>
  );
}
