"use client";

import { useEffect, useState } from "react";
import { api, WealthPlan as WP, LoanSim } from "@/lib/api";

const GREEN = "#2f9e44";
const RED = "#c92a2a";

function eok(v: number | null | undefined): string {
  if (v == null) return "—";
  const a = Math.abs(v);
  if (a >= 1e8) return `${(v / 1e8).toFixed(a % 1e8 === 0 ? 0 : 2)}억`;
  if (a >= 1e4) return `${Math.round(v / 1e4).toLocaleString("ko-KR")}만`;
  return `${Math.round(v).toLocaleString("ko-KR")}`;
}
function won(v: number | null | undefined): string {
  return v == null ? "—" : `${Math.round(v).toLocaleString("ko-KR")}원`;
}
function num(s: string): number { return Number((s || "").replace(/,/g, "")) || 0; }

const catColor: Record<string, string> = {
  "청년지원": "#2f9e44", "세제혜택·노후": "#217346", "세제혜택·투자": "#217346",
  "주택·청약": "#1971c2", "안전저축": "#7a5f10", "투자": "#c92a2a", "주거대출": "#8a6d1a",
};

export function WealthPlan() {
  const [d, setD] = useState<WP | null>(null);
  const [f, setF] = useState({
    age: "", married: false, homeless: true, has_child: false,
    annual_income: "", monthly_income: "", monthly_saving: "", current_assets: "",
    goal_amount: "", goal_years: "5",
  });
  const [busy, setBusy] = useState(false);
  const [lf, setLf] = useState({ amount: "20000000", rate: "6", years: "5", ret: "8" });
  const [ls, setLs] = useState<LoanSim | null>(null);
  const [lbusy, setLbusy] = useState(false);
  const runLoan = () => {
    setLbusy(true);
    api.wealthLoanSim(num(lf.amount), Number(lf.rate) || 0, Number(lf.years) || 5, Number(lf.ret) || 0)
      .then(setLs).finally(() => setLbusy(false));
  };

  const fill = (p: WP) => {
    setD(p);
    const pr = p.profile as Record<string, unknown>;
    setF((s) => ({
      ...s,
      age: pr.age != null ? String(pr.age) : s.age,
      married: Boolean(pr.married ?? s.married),
      homeless: Boolean(pr.homeless ?? s.homeless),
      has_child: Boolean(pr.has_child ?? s.has_child),
      annual_income: pr.annual_income != null ? String(pr.annual_income) : s.annual_income,
      monthly_income: pr.monthly_income != null ? String(pr.monthly_income) : s.monthly_income,
      monthly_saving: pr.monthly_saving != null ? String(pr.monthly_saving) : s.monthly_saving,
      current_assets: pr.current_assets != null ? String(pr.current_assets) : s.current_assets,
      goal_amount: pr.goal_amount != null ? String(pr.goal_amount) : s.goal_amount,
      goal_years: pr.goal_years != null ? String(pr.goal_years) : s.goal_years,
    }));
  };

  useEffect(() => { api.wealthPlan().then(fill).catch(() => {}); }, []);

  const save = () => {
    setBusy(true);
    api.wealthSaveProfile({
      age: num(f.age), married: f.married, homeless: f.homeless, has_child: f.has_child,
      annual_income: num(f.annual_income), monthly_income: num(f.monthly_income),
      monthly_saving: num(f.monthly_saving), current_assets: num(f.current_assets),
      goal_amount: num(f.goal_amount), goal_years: num(f.goal_years) || 5,
    }).then(fill).finally(() => setBusy(false));
  };

  const inp = "mt-0.5 block w-full rounded border border-[#cdcdcd] px-2 py-1 text-right text-sm tabular-nums outline-none focus:border-[#217346]";
  const gaugePos = d && d.required_monthly > 0
    ? Math.max(0, Math.min(100, (d.capacity_monthly / d.required_monthly) * 100)) : 0;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {/* ── 좌: 프로필/목표 입력 ─────────────────── */}
      <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
        <div className="bg-[#217346] px-4 py-2 text-sm font-semibold text-white">내 정보·목표</div>
        <div className="grid grid-cols-2 gap-3 p-4">
          <label className="text-xs text-[#555]">나이(만)
            <input value={f.age} onChange={(e) => setF({ ...f, age: e.target.value })} inputMode="numeric" placeholder="30" className={inp} />
          </label>
          <div className="flex items-end gap-3 text-xs text-[#555]">
            <label className="flex items-center gap-1"><input type="checkbox" checked={f.married} onChange={(e) => setF({ ...f, married: e.target.checked })} />결혼</label>
            <label className="flex items-center gap-1"><input type="checkbox" checked={f.homeless} onChange={(e) => setF({ ...f, homeless: e.target.checked })} />무주택</label>
            <label className="flex items-center gap-1"><input type="checkbox" checked={f.has_child} onChange={(e) => setF({ ...f, has_child: e.target.checked })} />자녀</label>
          </div>
          <label className="text-xs text-[#555]">연봉(원)
            <input value={f.annual_income} onChange={(e) => setF({ ...f, annual_income: e.target.value })} inputMode="numeric" placeholder="40000000" className={inp} />
          </label>
          <label className="text-xs text-[#555]">월 실수령(원)
            <input value={f.monthly_income} onChange={(e) => setF({ ...f, monthly_income: e.target.value })} inputMode="numeric" placeholder="3000000" className={inp} />
          </label>
          <label className="text-xs text-[#555]">월 저축 여력(원)
            <input value={f.monthly_saving} onChange={(e) => setF({ ...f, monthly_saving: e.target.value })} inputMode="numeric" placeholder="1000000" className={inp} />
          </label>
          <label className="text-xs text-[#555]">현재 자산(원)
            <input value={f.current_assets} onChange={(e) => setF({ ...f, current_assets: e.target.value })} inputMode="numeric" placeholder="10000000" className={inp} />
          </label>
          <label className="text-xs text-[#555]">목표 금액(원)
            <input value={f.goal_amount} onChange={(e) => setF({ ...f, goal_amount: e.target.value })} inputMode="numeric" placeholder="100000000" className={inp} />
            {num(f.goal_amount) > 0 && <span className="mt-0.5 block text-right text-[10px] text-[#217346]">= {eok(num(f.goal_amount))}원</span>}
          </label>
          <label className="text-xs text-[#555]">목표 기간(년)
            <input value={f.goal_years} onChange={(e) => setF({ ...f, goal_years: e.target.value })} inputMode="numeric" placeholder="5" className={inp} />
          </label>
        </div>
        <div className="border-t border-[#eee] px-4 py-2 text-right">
          <button onClick={save} disabled={busy} className="rounded bg-[#217346] px-4 py-1.5 text-xs font-semibold text-white hover:bg-[#1b5e3a] disabled:opacity-50">
            {busy ? "계산 중…" : "계획 계산"}
          </button>
        </div>
        <div className="px-4 pb-3 text-[10px] leading-relaxed text-[#aaa]">
          월수입·저축여력·현재자산은 가계부/소득·성장/포트폴리오에서 자동으로 채워집니다(수정 가능).
        </div>
      </div>

      {/* ── 우: 달성 계획 ─────────────────────────── */}
      <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
        <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
          <span className="text-sm font-semibold">달성 계획</span>
          {d && d.goal.amount > 0 && <span className="text-xs text-white/90">목표 {eok(d.goal.amount)}원 · {d.goal.years}년</span>}
        </div>
        {!d ? (
          <div className="py-16 text-center text-sm text-[#888]">불러오는 중…</div>
        ) : d.goal.amount <= 0 ? (
          <div className="px-4 py-10 text-center text-sm text-[#999]">목표 금액과 기간을 입력하고 "계획 계산"을 누르세요.</div>
        ) : (
          <div className="p-4">
            <div className="mb-2 grid grid-cols-3 gap-2 text-center">
              <div className="rounded bg-[#fafafa] px-2 py-2"><div className="text-[10px] text-[#888]">필요 월저축</div><div className="text-sm font-bold tabular-nums text-[#333]">{won(d.required_monthly)}</div></div>
              <div className="rounded bg-[#fafafa] px-2 py-2"><div className="text-[10px] text-[#888]">현재 여력</div><div className="text-sm font-bold tabular-nums" style={{ color: d.feasible ? GREEN : RED }}>{won(d.capacity_monthly)}</div></div>
              <div className="rounded bg-[#fafafa] px-2 py-2"><div className="text-[10px] text-[#888]">예상 달성</div><div className="text-sm font-bold tabular-nums text-[#333]">{d.reach_years ? `${d.reach_years}년` : "미달"}</div></div>
            </div>
            <div className="mb-1 h-2.5 w-full overflow-hidden rounded-full bg-[#eee]">
              <div className="h-full rounded-full" style={{ width: `${gaugePos}%`, background: d.feasible ? GREEN : "#e0a34e" }} />
            </div>
            <div className="mb-3 text-center text-[11px]" style={{ color: d.feasible ? GREEN : RED }}>
              {d.feasible ? `목표 기간 내 달성 가능 (연 ${Math.round(d.assumed_return * 100)}% 가정)` : `월 ${d.shortfall.toLocaleString("ko-KR")}원 부족`}
            </div>

            {/* 추천 배분 */}
            {d.allocation.length > 0 && (
              <div className="mb-3">
                <div className="mb-1 text-xs font-semibold text-[#555]">월 저축 추천 배분</div>
                <div className="flex flex-col gap-1">
                  {d.allocation.map((a, i) => (
                    <div key={i} className="flex items-center justify-between rounded bg-[#f5f7f5] px-2 py-1 text-[11px]">
                      <span className="font-semibold text-[#245]">{a.name}</span>
                      <span className="tabular-nums font-bold text-[#217346]">{won(a.monthly)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 로드맵 */}
            <ul className="flex flex-col gap-1 rounded border border-[#f0e6c9] bg-[#fdfaf0] p-2 text-[11px] leading-relaxed text-[#7a5f10]">
              {d.steps.map((s, i) => <li key={i}>✔ {s}</li>)}
            </ul>
          </div>
        )}
      </div>

      {/* ── 위험도별 시나리오 비교 ─────────────────── */}
      {d && d.goal.amount > 0 && d.scenarios?.length > 0 && (
        <div className="lg:col-span-2 overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
          <div className="bg-[#217346] px-4 py-2 text-sm font-semibold text-white">
            위험도별 시나리오 — 모았을 때 얼마 · 목표 도달 · 안전성
          </div>
          <div className="grid grid-cols-1 gap-2 p-3 sm:grid-cols-3">
            {d.scenarios.map((s) => {
              const color = s.key === "safe" ? "#1971c2" : s.key === "balanced" ? "#217346" : "#c92a2a";
              return (
                <div key={s.key} className={`relative rounded-lg border p-3 ${s.recommended ? "border-[#217346] bg-[#f2f8f4]" : "border-[#e5e5e5] bg-white"}`}>
                  {s.recommended && <span className="absolute right-2 top-2 rounded bg-[#217346] px-1.5 py-0.5 text-[9px] font-bold text-white">추천</span>}
                  <div className="text-sm font-bold" style={{ color }}>{s.name}</div>
                  <div className="text-[10px] text-[#888]">{s.desc}</div>
                  <div className="mt-2 flex items-baseline justify-between">
                    <span className="text-[10px] text-[#888]">기대수익률</span>
                    <span className="text-sm font-bold tabular-nums" style={{ color }}>연 {Math.round(s.return_mid * 100)}%</span>
                  </div>
                  <div className="mt-1 border-t border-[#eee] pt-1">
                    <div className="text-[10px] text-[#888]">{d.goal.years}년 뒤 예상</div>
                    <div className="text-sm font-bold tabular-nums text-[#1f1f1f]">{eok(s.balance_at_goal_years)}원</div>
                    <div className="text-[9px] text-[#aaa]">범위 {eok(s.balance_low)}~{eok(s.balance_high)}원</div>
                  </div>
                  <div className="mt-1 border-t border-[#eee] pt-1">
                    <div className="text-[10px] text-[#888]">목표 도달</div>
                    <div className="text-sm font-bold tabular-nums text-[#1f1f1f]">{s.reach_years ? `${s.reach_years}년` : "50년+"}</div>
                    {s.time_saved_vs_safe != null && s.time_saved_vs_safe > 0 && (
                      <div className="text-[10px] font-semibold text-[#c92a2a]">안전형보다 {s.time_saved_vs_safe}년 단축</div>
                    )}
                  </div>
                  <div className="mt-1 flex items-center justify-between border-t border-[#eee] pt-1 text-[10px]">
                    <span className="text-[#888]">위험도</span>
                    <span className="font-semibold" style={{ color }}>{s.risk}</span>
                  </div>
                  <div className="text-[9px] leading-relaxed text-[#999]">{s.safety}</div>
                </div>
              );
            })}
          </div>
          <div className="px-3 pb-3 text-[10px] text-[#bbb]">
            수익률은 가정치입니다. 공격형은 더 빨리 모을 수 있지만 원금 손실 위험이 있어, 목표 기간이 짧을수록 안전형이 유리합니다.
          </div>
        </div>
      )}

      {/* ── 대출 레버리지 시뮬레이터 ─────────────────── */}
      <div className="lg:col-span-2 overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
        <div className="bg-[#217346] px-4 py-2 text-sm font-semibold text-white">대출 레버리지 시뮬 (대출받아 투자 시)</div>
        <div className="flex flex-wrap items-end gap-2 border-b border-[#eee] p-3 text-xs text-[#555]">
          <label>대출금액(원)
            <input value={lf.amount} onChange={(e) => setLf({ ...lf, amount: e.target.value })} inputMode="numeric" className={`${inp} w-32`} />
          </label>
          <label>대출금리(%)
            <input value={lf.rate} onChange={(e) => setLf({ ...lf, rate: e.target.value })} inputMode="decimal" className={`${inp} w-20`} />
          </label>
          <label>기간(년)
            <input value={lf.years} onChange={(e) => setLf({ ...lf, years: e.target.value })} inputMode="numeric" className={`${inp} w-16`} />
          </label>
          <label>기대수익률(%)
            <input value={lf.ret} onChange={(e) => setLf({ ...lf, ret: e.target.value })} inputMode="decimal" className={`${inp} w-20`} />
          </label>
          <button onClick={runLoan} disabled={lbusy} className="rounded bg-[#217346] px-3 py-1.5 font-semibold text-white hover:bg-[#1b5e3a] disabled:opacity-50">계산</button>
        </div>
        {ls && (
          <div className="p-3">
            <div className="mb-2 grid grid-cols-2 gap-2 text-center sm:grid-cols-4">
              <div className="rounded bg-[#fafafa] px-2 py-1.5"><div className="text-[10px] text-[#888]">월 상환액</div><div className="text-xs font-bold tabular-nums text-[#333]">{won(ls.monthly_payment)}</div></div>
              <div className="rounded bg-[#fafafa] px-2 py-1.5"><div className="text-[10px] text-[#888]">총 이자</div><div className="text-xs font-bold tabular-nums" style={{ color: RED }}>{won(ls.total_interest)}</div></div>
              <div className="rounded bg-[#fafafa] px-2 py-1.5"><div className="text-[10px] text-[#888]">투자 예상가치</div><div className="text-xs font-bold tabular-nums text-[#333]">{eok(ls.invest_value)}원</div></div>
              <div className="rounded bg-[#fafafa] px-2 py-1.5"><div className="text-[10px] text-[#888]">순손익</div><div className="text-xs font-bold tabular-nums" style={{ color: ls.net_profit >= 0 ? GREEN : RED }}>{ls.net_profit >= 0 ? "+" : ""}{eok(ls.net_profit)}원</div></div>
            </div>
            <div className="mb-2 rounded px-2 py-1.5 text-[11px]" style={{ background: ls.worthwhile ? "#f2f8f4" : "#fdf3f3", color: ls.worthwhile ? "#245" : "#a33" }}>
              손익분기 수익률 <b>{ls.breakeven_return}%</b> — {ls.verdict}
            </div>
            {/* 수익률별 결과 */}
            <div className="grid grid-cols-3 gap-2">
              {ls.scenarios.map((s) => (
                <div key={s.name} className="rounded border border-[#eee] p-2 text-center text-[11px]">
                  <div className="font-semibold text-[#555]">{s.name} (연 {s.return}%)</div>
                  <div className="tabular-nums font-bold" style={{ color: s.net_profit >= 0 ? GREEN : RED }}>{s.net_profit >= 0 ? "+" : ""}{eok(s.net_profit)}원</div>
                </div>
              ))}
            </div>
            <div className="mt-2 rounded bg-[#fff8f0] px-2 py-1.5 text-[10px] leading-relaxed text-[#a33]">{ls.warning}</div>
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-[#888]">
              {ls.loans.map((l) => <span key={l.name}>{l.name} <b className="text-[#555]">~{l.rate}%</b></span>)}
            </div>
          </div>
        )}
      </div>

      {/* ── 하단: 자격 상품 ─────────────────────────── */}
      {d && (
        <div className="lg:col-span-2 overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
          <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
            <span className="text-sm font-semibold">맞춤 재테크 상품</span>
            <span className="text-xs text-white/90">자격 {d.eligible_count}개 / 전체 {d.products.length}개</span>
          </div>
          <div className="grid grid-cols-1 gap-2 p-3 sm:grid-cols-2 lg:grid-cols-3">
            {[...d.products].sort((a, b) => Number(b.eligible) - Number(a.eligible) || a.priority - b.priority).map((p) => (
              <div key={p.name} className={`rounded-lg border p-3 ${p.eligible ? "border-[#cfe3d6] bg-[#f7faf8]" : "border-[#eee] bg-[#fafafa] opacity-70"}`}>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold text-[#1f1f1f]">{p.name}</span>
                  {p.eligible
                    ? <span className="rounded bg-[#2f9e44] px-1.5 py-0.5 text-[10px] font-bold text-white">자격 O</span>
                    : <span className="rounded bg-[#bbb] px-1.5 py-0.5 text-[10px] font-bold text-white">해당X</span>}
                </div>
                <div className="mt-0.5 text-[10px] font-semibold" style={{ color: catColor[p.category] || "#666" }}>{p.category}</div>
                <div className="mt-1 text-[11px] leading-relaxed text-[#444]">{p.benefit}</div>
                {p.example && (
                  <div className="mt-1 rounded bg-[#eef4f0] px-2 py-1 text-[10px] font-semibold leading-relaxed text-[#1f4d2b]">
                    💰 {p.example}
                  </div>
                )}
                <div className="mt-1 text-[10px] text-[#999]">조건: {p.cond}</div>
                {p.eligible && p.link && (
                  <a href={p.link} target="_blank" rel="noreferrer" className="mt-1 inline-block text-[10px] text-[#1971c2] hover:underline">공식 안내 →</a>
                )}
              </div>
            ))}
          </div>
          <div className="px-3 pb-3 text-[10px] leading-relaxed text-[#bbb]">{d.note}</div>
        </div>
      )}
    </div>
  );
}
