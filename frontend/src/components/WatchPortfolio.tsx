"use client";

import { useEffect, useState } from "react";
import { api, Watchlist, Portfolio } from "@/lib/api";

const RED = "#c92a2a";
const BLUE = "#1971c2";

function won(v: number | null | undefined): string {
  if (v == null) return "—";
  return Math.round(v).toLocaleString("ko-KR");
}
function pctStyle(v: number | null | undefined): React.CSSProperties {
  if (v == null) return { color: "#bbb" };
  return { color: v > 0 ? RED : v < 0 ? BLUE : "#666", fontWeight: 700 };
}
function pct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}
function verdictColor(v?: string | null) {
  return v === "매수" ? RED : v === "매도" ? BLUE : "#888";
}

type EditRow = { ticker: string; qty: string; avg: string };

export function WatchPortfolio() {
  const [wl, setWl] = useState<Watchlist | null>(null);
  const [pf, setPf] = useState<Portfolio | null>(null);
  const [newTicker, setNewTicker] = useState("");
  const [rows, setRows] = useState<EditRow[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let alive = true;
    api.watchlist().then((r) => alive && setWl(r)).catch(() => {});
    api.portfolioDiag().then((r) => {
      if (!alive) return;
      setPf(r);
      setRows(r.holdings.map((h) => ({ ticker: h.ticker, qty: String(h.qty), avg: String(h.avg) })));
    }).catch(() => {});
    return () => { alive = false; };
  }, []);

  const addWatch = () => {
    const t = newTicker.trim();
    if (!t) return;
    setNewTicker("");
    api.watchlistAdd(t).then(setWl).catch(() => {});
  };
  const removeWatch = (t: string) => api.watchlistRemove(t).then(setWl).catch(() => {});

  const savePortfolio = () => {
    setSaving(true);
    const holdings = rows
      .filter((r) => r.ticker.trim())
      .map((r) => ({ ticker: r.ticker.trim(), qty: Number(r.qty) || 0, avg: Number(r.avg) || 0 }));
    api.portfolioSave(holdings)
      .then((r) => { setPf(r); setRows(r.holdings.map((h) => ({ ticker: h.ticker, qty: String(h.qty), avg: String(h.avg) }))); })
      .catch(() => {})
      .finally(() => setSaving(false));
  };

  const s = pf?.summary;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {/* ── 관심종목 ─────────────────────────── */}
      <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
        <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
          <span className="text-sm font-semibold">관심종목.xlsx</span>
        </div>
        <div className="flex gap-2 border-b border-[#e5e5e5] bg-[#f5f7f5] px-3 py-2">
          <input
            value={newTicker}
            onChange={(e) => setNewTicker(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addWatch()}
            placeholder="종목코드 (예: 005930)"
            className="min-w-0 flex-1 rounded border border-[#cdcdcd] px-2 py-1 text-xs outline-none focus:border-[#217346]"
          />
          <button onClick={addWatch} className="shrink-0 rounded bg-[#217346] px-3 py-1 text-xs font-semibold text-white hover:bg-[#1b5e3a]">추가</button>
        </div>
        {!wl || wl.rows.length === 0 ? (
          <div className="px-3 py-10 text-center text-xs text-[#aaa]">관심종목을 추가하면 현재가·매매신호·목표가를 추적합니다.</div>
        ) : (
          <table className="w-full text-[12px]">
            <thead className="text-left text-[10px] uppercase tracking-wide text-[#999]">
              <tr className="border-b border-[#eee]">
                <th className="px-3 py-1.5">종목</th>
                <th className="px-3 py-1.5 text-right">현재가</th>
                <th className="px-3 py-1.5 text-center">신호</th>
                <th className="px-3 py-1.5 text-right">목표가↑</th>
                <th className="px-3 py-1.5"></th>
              </tr>
            </thead>
            <tbody>
              {wl.rows.map((r) => (
                <tr key={r.ticker} className="border-t border-[#f2f2f2]">
                  <td className="px-3 py-1.5">
                    <span className="font-semibold text-[#333]">{r.name ?? r.ticker}</span>
                    <span className="ml-1 text-[10px] text-[#aaa]">{r.ticker}</span>
                  </td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-[#333]">
                    {won(r.close)} <span className="text-[10px]" style={pctStyle(r.chg_pct)}>{pct(r.chg_pct)}</span>
                  </td>
                  <td className="px-3 py-1.5 text-center">
                    {r.verdict ? <span className="rounded px-1.5 py-0.5 text-[10px] font-bold text-white" style={{ background: verdictColor(r.verdict) }}>{r.verdict}</span> : "—"}
                  </td>
                  <td className="px-3 py-1.5 text-right tabular-nums" style={pctStyle(r.upside_pct)}>{pct(r.upside_pct)}</td>
                  <td className="px-3 py-1.5 text-right">
                    <button onClick={() => removeWatch(r.ticker)} className="text-[#bbb] hover:text-rose-500" aria-label="삭제">✕</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ── 포트폴리오 진단 ─────────────────────── */}
      <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
        <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
          <span className="text-sm font-semibold">포트폴리오 진단.xlsx</span>
          {s && s.count > 0 && (
            <span className="text-xs text-white/90">
              평가 {won(s.total_value)} · <span style={{ color: s.total_pnl >= 0 ? "#ffd0d0" : "#cfe0ff" }}>{pct(s.total_pnl_pct)}</span>
            </span>
          )}
        </div>

        {/* 편집 테이블 */}
        <div className="border-b border-[#e5e5e5]">
          <table className="w-full text-[12px]">
            <thead className="text-left text-[10px] uppercase tracking-wide text-[#999]">
              <tr className="border-b border-[#eee] bg-[#f5f7f5]">
                <th className="px-2 py-1.5">종목코드</th>
                <th className="px-2 py-1.5">수량</th>
                <th className="px-2 py-1.5">평단가</th>
                <th className="px-2 py-1.5"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-t border-[#f5f5f5]">
                  <td className="px-2 py-1">
                    <input value={r.ticker} onChange={(e) => setRows((p) => p.map((x, j) => j === i ? { ...x, ticker: e.target.value } : x))}
                      placeholder="005930" className="w-24 rounded border border-[#e0e0e0] px-1.5 py-0.5 text-xs outline-none focus:border-[#217346]" />
                  </td>
                  <td className="px-2 py-1">
                    <input value={r.qty} onChange={(e) => setRows((p) => p.map((x, j) => j === i ? { ...x, qty: e.target.value } : x))}
                      inputMode="numeric" placeholder="10" className="w-20 rounded border border-[#e0e0e0] px-1.5 py-0.5 text-right text-xs outline-none focus:border-[#217346]" />
                  </td>
                  <td className="px-2 py-1">
                    <input value={r.avg} onChange={(e) => setRows((p) => p.map((x, j) => j === i ? { ...x, avg: e.target.value } : x))}
                      inputMode="numeric" placeholder="70000" className="w-24 rounded border border-[#e0e0e0] px-1.5 py-0.5 text-right text-xs outline-none focus:border-[#217346]" />
                  </td>
                  <td className="px-2 py-1 text-right">
                    <button onClick={() => setRows((p) => p.filter((_, j) => j !== i))} className="text-[#bbb] hover:text-rose-500">✕</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex gap-2 px-2 py-2">
            <button onClick={() => setRows((p) => [...p, { ticker: "", qty: "", avg: "" }])}
              className="rounded border border-[#cdcdcd] bg-white px-2.5 py-1 text-xs text-[#217346] hover:bg-[#eef6f0]">+ 종목 추가</button>
            <button onClick={savePortfolio} disabled={saving}
              className="rounded bg-[#217346] px-3 py-1 text-xs font-semibold text-white hover:bg-[#1b5e3a] disabled:opacity-50">
              {saving ? "저장 중…" : "저장 · 진단"}
            </button>
          </div>
        </div>

        {/* 진단 결과 */}
        {s && s.count > 0 && (
          <div className="p-3">
            <div className="mb-2 grid grid-cols-3 gap-2 text-center">
              <div className="rounded bg-[#fafafa] px-2 py-1.5">
                <div className="text-[10px] text-[#888]">평가금액</div>
                <div className="text-xs font-bold tabular-nums text-[#333]">{won(s.total_value)}</div>
              </div>
              <div className="rounded bg-[#fafafa] px-2 py-1.5">
                <div className="text-[10px] text-[#888]">손익</div>
                <div className="text-xs font-bold tabular-nums" style={pctStyle(s.total_pnl)}>{won(s.total_pnl)}</div>
              </div>
              <div className="rounded bg-[#fafafa] px-2 py-1.5">
                <div className="text-[10px] text-[#888]">수익률</div>
                <div className="text-xs font-bold tabular-nums" style={pctStyle(s.total_pnl_pct)}>{pct(s.total_pnl_pct)}</div>
              </div>
            </div>
            {pf!.diagnosis.length > 0 && (
              <ul className="mb-2 flex flex-col gap-1 rounded border border-[#f0e6c9] bg-[#fdfaf0] p-2 text-[11px] text-[#8a6d1a]">
                {pf!.diagnosis.map((v, i) => <li key={i}>• {v}</li>)}
              </ul>
            )}
            <table className="w-full text-[11px]">
              <thead className="text-left text-[9px] uppercase tracking-wide text-[#999]">
                <tr className="border-b border-[#eee]">
                  <th className="px-2 py-1">종목</th>
                  <th className="px-2 py-1 text-right">비중</th>
                  <th className="px-2 py-1 text-right">손익%</th>
                  <th className="px-2 py-1 text-center">신호</th>
                </tr>
              </thead>
              <tbody>
                {pf!.holdings.map((h) => (
                  <tr key={h.ticker} className="border-t border-[#f5f5f5]">
                    <td className="px-2 py-1 text-[#333]">{h.name ?? h.ticker}</td>
                    <td className="px-2 py-1 text-right tabular-nums text-[#666]">{h.weight != null ? `${h.weight}%` : "—"}</td>
                    <td className="px-2 py-1 text-right tabular-nums" style={pctStyle(h.pnl_pct)}>{pct(h.pnl_pct)}</td>
                    <td className="px-2 py-1 text-center">
                      {h.verdict ? <span style={{ color: verdictColor(h.verdict), fontWeight: 700 }}>{h.verdict}</span> : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {s.sectors.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-[#888]">
                {s.sectors.slice(0, 5).map((se) => <span key={se.sector}>{se.sector} <b className="text-[#555]">{se.weight}%</b></span>)}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
