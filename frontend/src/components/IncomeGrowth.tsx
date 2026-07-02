"use client";

import { useEffect, useState } from "react";
import { api, IncomeOverview, SalaryHistory, SideList, RaiseSim } from "@/lib/api";

const RED = "#c92a2a";
const BLUE = "#1971c2";
const GREEN = "#2f9e44";

function won(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${Math.round(v).toLocaleString("ko-KR")}원`;
}
function eok(v: number | null | undefined): string {
  if (v == null) return "—";
  const a = Math.abs(v);
  if (a >= 1e8) return `${(v / 1e8).toFixed(2)}억`;
  if (a >= 1e4) return `${Math.round(v / 1e4).toLocaleString("ko-KR")}만`;
  return `${Math.round(v).toLocaleString("ko-KR")}`;
}
function num(s: string): number { return Number((s || "").replace(/,/g, "")) || 0; }

type Item = { label: string; amount: string };

function ItemRows({ items, setItems, color }: { items: Item[]; setItems: (v: Item[]) => void; color: string }) {
  return (
    <div className="flex flex-col gap-1">
      {items.map((it, i) => (
        <div key={i} className="flex gap-1">
          <input value={it.label} onChange={(e) => setItems(items.map((x, j) => j === i ? { ...x, label: e.target.value } : x))}
            className="min-w-0 flex-1 rounded border border-[#e0e0e0] px-1.5 py-0.5 text-xs outline-none focus:border-[#217346]" />
          <input value={it.amount} onChange={(e) => setItems(items.map((x, j) => j === i ? { ...x, amount: e.target.value } : x))}
            inputMode="numeric" placeholder="0" className="w-28 rounded border border-[#e0e0e0] px-1.5 py-0.5 text-right text-xs outline-none focus:border-[#217346]"
            style={{ color }} />
          <button onClick={() => setItems(items.filter((_, j) => j !== i))} className="px-1 text-[#ccc] hover:text-rose-500">✕</button>
        </div>
      ))}
      <button onClick={() => setItems([...items, { label: "", amount: "" }])}
        className="self-start rounded border border-[#cdcdcd] px-2 py-0.5 text-[10px] text-[#217346] hover:bg-[#eef6f0]">+ 항목</button>
    </div>
  );
}
const DEF_EARN: Item[] = [{ label: "기본급", amount: "" }, { label: "식대/수당", amount: "" }, { label: "상여", amount: "" }];
const DEF_DED: Item[] = [
  { label: "국민연금", amount: "" }, { label: "건강보험", amount: "" }, { label: "고용보험", amount: "" },
  { label: "소득세", amount: "" }, { label: "지방소득세", amount: "" },
];

export function IncomeGrowth() {
  const [ov, setOv] = useState<IncomeOverview | null>(null);
  const [earn, setEarn] = useState<Item[]>(DEF_EARN);
  const [ded, setDed] = useState<Item[]>(DEF_DED);
  const [hist, setHist] = useState<SalaryHistory[]>([]);
  const [side, setSide] = useState<SideList | null>(null);
  const [sim, setSim] = useState<RaiseSim | null>(null);
  const [rp, setRp] = useState("5");      // 인상률 %
  const [yrs, setYrs] = useState(5);
  const [ir, setIr] = useState(0.5);
  const [ret, setRet] = useState(6);
  const [ns, setNs] = useState({ date: new Date().toISOString().slice(0, 10), source: "", amount: "" });
  const [busy, setBusy] = useState("");

  const load = () => {
    api.incomeOverview().then(setOv).catch(() => {});
    api.incomeSalaryGet().then((r) => {
      if (r.salary) {
        setEarn(r.salary.earnings.length ? r.salary.earnings.map((e) => ({ label: e.label, amount: String(e.amount) })) : DEF_EARN);
        setDed(r.salary.deductions.length ? r.salary.deductions.map((e) => ({ label: e.label, amount: String(e.amount) })) : DEF_DED);
      }
      setHist(r.history || []);
    }).catch(() => {});
    api.incomeSideList().then(setSide).catch(() => {});
  };
  useEffect(load, []);

  const grossPrev = earn.reduce((a, x) => a + num(x.amount), 0);
  const dedPrev = ded.reduce((a, x) => a + num(x.amount), 0);
  const netPrev = grossPrev - dedPrev;

  const saveSalary = () => {
    setBusy("sal");
    api.incomeSalarySet(
      earn.map((x) => ({ label: x.label, amount: num(x.amount) })),
      ded.map((x) => ({ label: x.label, amount: num(x.amount) })),
    ).then(() => load()).finally(() => setBusy(""));
  };
  const runSim = () => {
    setBusy("sim");
    api.incomeRaiseSim({ raise_pct: num(rp), years: yrs, invest_ratio: ir, annual_return: ret })
      .then(setSim).finally(() => setBusy(""));
  };
  const addSide = () => {
    if (!num(ns.amount)) return;
    setBusy("side");
    api.incomeSideAdd([{ date: ns.date, source: ns.source || "부업", amount: num(ns.amount) }])
      .then(() => { setNs({ ...ns, source: "", amount: "" }); load(); }).finally(() => setBusy(""));
  };
  const delSide = (id: number) => api.incomeSideDelete(id).then(() => load()).catch(() => {});

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {/* ── 좌: 종합 + 인상 시뮬 ─────────────────── */}
      <div className="flex flex-col gap-4">
        {/* 종합 대시보드 */}
        <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
          <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
            <span className="text-sm font-semibold">소득 종합.xlsx</span>
            {ov && <span className="text-xs text-white/90">월 총소득 {won(ov.total_month_income)}</span>}
          </div>
          {ov && (
            <div className="p-3">
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded bg-[#fafafa] px-2 py-2">
                  <div className="text-[10px] text-[#888]">급여(실수령/월)</div>
                  <div className="text-sm font-bold tabular-nums text-[#333]">{won(ov.salary?.net)}</div>
                </div>
                <div className="rounded bg-[#fafafa] px-2 py-2">
                  <div className="text-[10px] text-[#888]">부업(이번달)</div>
                  <div className="text-sm font-bold tabular-nums" style={{ color: GREEN }}>{won(ov.side.this_month)}</div>
                </div>
                <div className="rounded bg-[#fafafa] px-2 py-2">
                  <div className="text-[10px] text-[#888]">주식 평가손익</div>
                  <div className="text-sm font-bold tabular-nums" style={{ color: (ov.investment.pnl || 0) >= 0 ? RED : BLUE }}>{won(ov.investment.pnl)}</div>
                </div>
              </div>
              <div className="mt-2 flex flex-wrap justify-between gap-2 text-[11px] text-[#666]">
                <span>연 환산(급여×12+부업누적) <b className="text-[#333]">{eok(ov.annual_est)}원</b></span>
                <span>부업 누적 <b className="text-[#333]">{won(ov.side.total)}</b> · 주식 평가액 <b className="text-[#333]">{won(ov.investment.value)}</b></span>
              </div>
              {ov.tips.length > 0 && (
                <ul className="mt-3 flex flex-col gap-1 rounded border border-[#f0e6c9] bg-[#fdfaf0] p-2 text-[11px] leading-relaxed text-[#7a5f10]">
                  {ov.tips.map((t, i) => <li key={i}>💡 {t}</li>)}
                </ul>
              )}
            </div>
          )}
        </div>

        {/* 급여 인상 시뮬 */}
        <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
          <div className="bg-[#217346] px-4 py-2 text-sm font-semibold text-white">급여 인상 시뮬레이터</div>
          <div className="p-3">
            <div className="flex flex-wrap items-end gap-2 text-xs text-[#555]">
              <label>인상률(%)
                <input value={rp} onChange={(e) => setRp(e.target.value)} inputMode="numeric"
                  className="mt-0.5 block w-20 rounded border border-[#cdcdcd] px-2 py-1 text-right outline-none focus:border-[#217346]" />
              </label>
              <label>기간
                <select value={yrs} onChange={(e) => setYrs(Number(e.target.value))} className="mt-0.5 block rounded border border-[#cdcdcd] px-1 py-1">
                  {[3, 5, 10, 20].map((n) => <option key={n} value={n}>{n}년</option>)}
                </select>
              </label>
              <label>인상분 투자
                <select value={ir} onChange={(e) => setIr(Number(e.target.value))} className="mt-0.5 block rounded border border-[#cdcdcd] px-1 py-1">
                  {[0.3, 0.5, 0.7, 1].map((n) => <option key={n} value={n}>{Math.round(n * 100)}%</option>)}
                </select>
              </label>
              <label>수익률
                <select value={ret} onChange={(e) => setRet(Number(e.target.value))} className="mt-0.5 block rounded border border-[#cdcdcd] px-1 py-1">
                  {[4, 6, 8, 10].map((n) => <option key={n} value={n}>연 {n}%</option>)}
                </select>
              </label>
              <button onClick={runSim} disabled={busy === "sim"}
                className="rounded bg-[#217346] px-3 py-1.5 font-semibold text-white hover:bg-[#1b5e3a] disabled:opacity-50">계산</button>
            </div>
            {sim && (
              <div className="mt-3">
                <div className="grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="rounded bg-[#fafafa] px-2 py-1.5"><div className="text-[10px] text-[#888]">새 실수령/월</div><div className="font-bold tabular-nums text-[#333]">{won(sim.new_net)}</div></div>
                  <div className="rounded bg-[#fafafa] px-2 py-1.5"><div className="text-[10px] text-[#888]">월 증가</div><div className="font-bold tabular-nums" style={{ color: RED }}>+{won(sim.monthly_increase)}</div></div>
                  <div className="rounded bg-[#fafafa] px-2 py-1.5"><div className="text-[10px] text-[#888]">연 증가</div><div className="font-bold tabular-nums" style={{ color: RED }}>+{won(sim.annual_increase)}</div></div>
                </div>
                <div className="mt-2 rounded border border-[#cfe3d6] bg-[#f2f8f4] p-2 text-[12px] text-[#245]">
                  인상분 중 매월 <b>{won(sim.invest_monthly)}</b>씩 연 {sim.annual_return}%로 <b>{sim.years}년</b> 투자하면 →{" "}
                  <b style={{ color: GREEN }}>{won(sim.future_value)}</b>
                  <span className="text-[#888]"> (원금 {won(sim.contributed)} + 투자수익 {won(sim.investment_gain)})</span>
                </div>
                <div className="mt-1 text-[10px] text-[#bbb]">{sim.note}</div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── 우: 급여 상세 + 부업 ─────────────────── */}
      <div className="flex flex-col gap-4">
        {/* 급여 상세 */}
        <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
          <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
            <span className="text-sm font-semibold">급여 상세.xlsx</span>
            <span className="text-xs text-white/90">실수령 {won(netPrev)} · 연 {eok(netPrev * 12)}</span>
          </div>
          <div className="grid grid-cols-2 gap-3 p-3">
            <div>
              <div className="mb-1 text-xs font-semibold text-[#c92a2a]">지급 항목</div>
              <ItemRows items={earn} setItems={setEarn} color="#c92a2a" />
              <div className="mt-1 text-right text-[11px] text-[#666]">지급계 <b>{won(grossPrev)}</b></div>
            </div>
            <div>
              <div className="mb-1 text-xs font-semibold text-[#1971c2]">공제 항목</div>
              <ItemRows items={ded} setItems={setDed} color="#1971c2" />
              <div className="mt-1 text-right text-[11px] text-[#666]">공제계 <b>{won(dedPrev)}</b></div>
            </div>
          </div>
          <div className="flex items-center justify-between border-t border-[#eee] px-3 py-2">
            <span className="text-sm">실수령액 <b className="tabular-nums text-[#217346]">{won(netPrev)}</b></span>
            <button onClick={saveSalary} disabled={busy === "sal"}
              className="rounded bg-[#217346] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#1b5e3a] disabled:opacity-50">
              {busy === "sal" ? "저장 중…" : "저장"}
            </button>
          </div>
          {hist.length > 1 && (
            <div className="border-t border-[#eee] px-3 py-2">
              <div className="mb-1 text-[10px] font-semibold text-[#888]">급여 인상 이력</div>
              <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-[#555]">
                {hist.slice(-6).map((h, i) => (
                  <span key={i}>{h.date.slice(2)} <b className="tabular-nums text-[#333]">{won(h.net)}</b></span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 부업 소득 */}
        <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
          <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
            <span className="text-sm font-semibold">부업 소득.xlsx</span>
            {side && <span className="text-xs text-white/90">누적 {won(side.total)} · 이번달 {won(side.month_total)}</span>}
          </div>
          <div className="flex flex-wrap gap-1 border-b border-[#eee] bg-[#f5f7f5] p-2">
            <input type="date" value={ns.date} onChange={(e) => setNs({ ...ns, date: e.target.value })}
              className="rounded border border-[#cdcdcd] px-1.5 py-1 text-xs outline-none focus:border-[#217346]" />
            <input value={ns.source} onChange={(e) => setNs({ ...ns, source: e.target.value })} placeholder="출처(예: 블로그, 배달)"
              className="min-w-0 flex-1 rounded border border-[#cdcdcd] px-2 py-1 text-xs outline-none focus:border-[#217346]" />
            <input value={ns.amount} onChange={(e) => setNs({ ...ns, amount: e.target.value })} inputMode="numeric" placeholder="금액"
              onKeyDown={(e) => e.key === "Enter" && addSide()}
              className="w-24 rounded border border-[#cdcdcd] px-2 py-1 text-right text-xs outline-none focus:border-[#217346]" />
            <button onClick={addSide} disabled={busy === "side"}
              className="rounded bg-[#217346] px-3 py-1 text-xs font-semibold text-white hover:bg-[#1b5e3a] disabled:opacity-50">추가</button>
          </div>
          {!side || side.rows.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-[#aaa]">부업 소득을 기록하면 얼마 벌었는지 누적됩니다.</div>
          ) : (
            <>
              {side.sources.length > 0 && (
                <div className="flex flex-wrap gap-x-3 gap-y-1 border-b border-[#f2f2f2] px-3 py-1.5 text-[10px] text-[#888]">
                  {side.sources.slice(0, 6).map((s) => <span key={s.source}>{s.source} <b className="text-[#555]">{won(s.amount)}</b></span>)}
                </div>
              )}
              <div className="max-h-56 overflow-auto">
                <table className="w-full text-[11px]">
                  <tbody>
                    {side.rows.map((r) => (
                      <tr key={r.id} className="border-t border-[#f5f5f5]">
                        <td className="whitespace-nowrap px-2 py-1 text-[#999]">{r.date.slice(5)}</td>
                        <td className="px-2 py-1 text-[#333]">{r.source}</td>
                        <td className="px-2 py-1 text-right tabular-nums font-semibold" style={{ color: GREEN }}>{won(r.amount)}</td>
                        <td className="px-1 py-1 text-right"><button onClick={() => delSide(r.id)} className="text-[#ccc] hover:text-rose-500">✕</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
