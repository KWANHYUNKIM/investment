"use client";

import { useEffect, useRef, useState } from "react";
import { api, WealthPlan as WP, LoanSim, RealtySim, RealtyLoans, HoldingCatalogItem, HoldingsData, DividendSim, IpoSim, DividendPicks, IpoSchedule } from "@/lib/api";

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

// "4억", "3천만", "4억5000만", "40,000,000" 모두 원 단위 숫자로 파싱
function parseKMoney(raw: string): number {
  if (raw == null) return 0;
  let s = String(raw).replace(/[\s,]/g, "").replace(/원/g, "");
  if (s === "") return 0;
  if (/^\d+(\.\d+)?$/.test(s)) return Math.round(Number(s));
  let total = 0;
  const eokM = s.match(/(\d+(?:\.\d+)?)\s*억/); if (eokM) total += parseFloat(eokM[1]) * 1e8;
  const cmM = s.match(/(\d+(?:\.\d+)?)\s*천만/); if (cmM) total += parseFloat(cmM[1]) * 1e7;
  const rest = s.replace(/(\d+(?:\.\d+)?)\s*억/, "").replace(/(\d+(?:\.\d+)?)\s*천만/, "");
  const manM = rest.match(/(\d+(?:\.\d+)?)\s*만/); if (manM) total += parseFloat(manM[1]) * 1e4;
  const cheonM = rest.match(/(\d+(?:\.\d+)?)\s*천(?!만)/); if (cheonM) total += parseFloat(cheonM[1]) * 1e3;
  if (total === 0) { const n = s.replace(/[^\d.]/g, ""); return n ? Math.round(Number(n)) : 0; }
  return Math.round(total);
}
function fmtComma(digits: string): string {
  return digits ? Number(digits.replace(/,/g, "")).toLocaleString("ko-KR") : "";
}

const inpCls = "mt-0.5 block w-full rounded border border-[#cdcdcd] px-2 py-1 text-right text-sm tabular-nums outline-none focus:border-[#217346]";

// 금액 입력: 콤마 자동 + 한글(억/만) 인식 + 빠른 칩 + 읽기 표시
function MoneyField({ label, value, onChange, chips, placeholder, w }: {
  label: string; value: string; onChange: (v: string) => void;
  chips?: { label: string; value: number }[]; placeholder?: string; w?: string;
}) {
  const set = (raw: string) => {
    if (/[억만천]/.test(raw)) onChange(String(parseKMoney(raw)));
    else onChange(raw.replace(/[^\d]/g, ""));
  };
  const n = Number((value || "").replace(/,/g, "")) || 0;
  return (
    <label className="text-xs text-[#555]">{label}
      <input value={fmtComma(value)} onChange={(e) => set(e.target.value)} inputMode="numeric" placeholder={placeholder} className={`${inpCls} ${w || ""}`} />
      <div className="mt-0.5 flex items-center justify-between gap-1">
        <div className="flex flex-wrap gap-1">
          {chips?.map((c) => (
            <button key={c.label} type="button" onClick={() => onChange(String(c.value))}
              className="rounded bg-[#eef4f0] px-1.5 py-0.5 text-[10px] text-[#217346] hover:bg-[#d7e8dd]">{c.label}</button>
          ))}
        </div>
        <span className="shrink-0 text-[10px] font-semibold text-[#217346]">{n > 0 ? `= ${eok(n)}원` : ""}</span>
      </div>
    </label>
  );
}

// 슬라이더: 비율·기간·나이 드래그 입력
function Slider({ label, value, onChange, min, max, step, suffix }: {
  label: string; value: string; onChange: (v: string) => void;
  min: number; max: number; step: number; suffix: string;
}) {
  return (
    <label className="block text-xs text-[#555]">
      <span className="flex items-center justify-between">{label}<b className="tabular-nums text-[#217346]">{value || min}{suffix}</b></span>
      <input type="range" min={min} max={max} step={step} value={Number(value) || min}
        onChange={(e) => onChange(e.target.value)} className="mt-1 block w-full accent-[#217346]" />
    </label>
  );
}

const catColor: Record<string, string> = {
  "청년지원": "#2f9e44", "세제혜택·노후": "#217346", "세제혜택·투자": "#217346",
  "주택·청약": "#1971c2", "안전저축": "#7a5f10", "투자": "#c92a2a", "주거대출": "#8a6d1a",
};

const CHIP_INCOME = [{ label: "3천만", value: 30000000 }, { label: "4천만", value: 40000000 }, { label: "5천만", value: 50000000 }, { label: "7천만", value: 70000000 }];
const CHIP_MONTHLY = [{ label: "200만", value: 2000000 }, { label: "300만", value: 3000000 }, { label: "400만", value: 4000000 }, { label: "500만", value: 5000000 }];
const CHIP_SAVE = [{ label: "50만", value: 500000 }, { label: "100만", value: 1000000 }, { label: "200만", value: 2000000 }, { label: "300만", value: 3000000 }];
const CHIP_ASSETS = [{ label: "1천만", value: 10000000 }, { label: "5천만", value: 50000000 }, { label: "1억", value: 100000000 }, { label: "3억", value: 300000000 }];
const CHIP_GOAL = [{ label: "5천만", value: 50000000 }, { label: "1억", value: 100000000 }, { label: "3억", value: 300000000 }, { label: "5억", value: 500000000 }, { label: "10억", value: 1000000000 }];
const CHIP_PRICE = [{ label: "3억", value: 300000000 }, { label: "5억", value: 500000000 }, { label: "8억", value: 800000000 }, { label: "10억", value: 1000000000 }];
const CHIP_OWN = [{ label: "5천만", value: 50000000 }, { label: "1억", value: 100000000 }, { label: "2억", value: 200000000 }, { label: "3억", value: 300000000 }];
const CHIP_LOAN = [{ label: "1천만", value: 10000000 }, { label: "3천만", value: 30000000 }, { label: "5천만", value: 50000000 }, { label: "1억", value: 100000000 }];

// ── 배당주·공모주 추천 (실시간 갱신) ────────────────────────────────────
const gradeColor = (g: string) => (g === "A" ? "#2f9e44" : g === "B" ? "#1c7ed6" : g === "C" ? "#e8890c" : "#adb5bd");

function PicksBoard() {
  const [dp, setDp] = useState<DividendPicks | null>(null);
  const [ip, setIp] = useState<IpoSchedule | null>(null);
  const [busy, setBusy] = useState(false);
  const [openDiv, setOpenDiv] = useState<string | null>(null);
  const [openIpo, setOpenIpo] = useState<number | null>(null);
  const [showGuide, setShowGuide] = useState(false);

  const load = () => {
    setBusy(true);
    Promise.all([
      api.wealthDividendPicks(15).then(setDp).catch(() => {}),
      api.wealthIpoSchedule().then(setIp).catch(() => {}),
    ]).finally(() => setBusy(false));
  };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  const statusColor = (s: string) => (s === "청약중" ? "#c92a2a" : s === "예정" ? "#2f9e44" : "#aaa");
  const needFor = (mon: number, dy: number) => (dy > 0 ? Math.round((mon * 12) / (dy / 100 * (1 - 0.154))) : 0);

  return (
    <div className="lg:col-span-2 overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
        <span className="text-sm font-semibold">배당주·공모주 추천 (계속 바뀜 · 실시간 갱신)</span>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowGuide((v) => !v)} className="rounded bg-white/20 px-2 py-0.5 text-[11px] hover:bg-white/30">{showGuide ? "가이드 닫기" : "매수 가이드"}</button>
          <button onClick={load} disabled={busy} className="rounded bg-white/20 px-2 py-0.5 text-[11px] hover:bg-white/30 disabled:opacity-50">{busy ? "갱신 중…" : "↻ 새로고침"}</button>
        </div>
      </div>

      {showGuide && (dp || ip) && (
        <div className="grid grid-cols-1 gap-2 border-b border-[#eee] bg-[#fdfaf0] p-3 sm:grid-cols-2">
          <div>
            <div className="mb-1 text-xs font-bold text-[#7a5f10]">배당주 매수 가이드</div>
            <ul className="flex flex-col gap-0.5 text-[10px] leading-relaxed text-[#7a5f10]">{dp?.guide?.map((g, i) => <li key={i}>{g}</li>)}</ul>
          </div>
          <div>
            <div className="mb-1 text-xs font-bold text-[#7a5f10]">공모주 청약 가이드</div>
            <ul className="flex flex-col gap-0.5 text-[10px] leading-relaxed text-[#7a5f10]">{ip?.guide?.map((g, i) => <li key={i}>{g}</li>)}</ul>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 p-3 lg:grid-cols-2">
        {/* ── 배당주 추천 ── */}
        <div className="rounded-lg border border-[#e6ede8] bg-[#f8faf9] p-3">
          <div className="mb-2 flex items-baseline justify-between">
            <span className="text-sm font-bold text-[#217346]">고배당주 추천 TOP <span className="text-[10px] font-normal text-[#888]">(종목 클릭 = 상세)</span></span>
            <span className="text-[10px] text-[#888]">점수순 · 1천만당 세후 월배당</span>
          </div>
          {!dp ? <div className="py-6 text-center text-xs text-[#999]">불러오는 중…</div> : (
            <div className="overflow-hidden rounded border border-[#eee] bg-white">
              <div className="grid grid-cols-[auto_1fr_auto_auto] gap-x-2 bg-[#eef4f0] px-2 py-1 text-[10px] font-semibold text-[#555]">
                <span>등급</span><span>종목</span><span className="text-right">배당률</span><span className="text-right">1천만/월</span>
              </div>
              {dp.picks.map((p) => (
                <div key={p.ticker} className="border-t border-[#f0f0f0]">
                  <button onClick={() => setOpenDiv(openDiv === p.ticker ? null : p.ticker)} className="grid w-full grid-cols-[auto_1fr_auto_auto] items-center gap-x-2 px-2 py-1 text-left text-[11px] hover:bg-[#f5faf7]">
                    <span className="rounded px-1.5 py-0.5 text-[9px] font-bold text-white" style={{ background: gradeColor(p.grade) }}>{p.grade}{p.score}</span>
                    <span className="truncate font-semibold text-[#1f1f1f]">{p.name} <span className="text-[9px] font-normal text-[#aaa]">{p.sector}</span></span>
                    <span className="text-right font-bold tabular-nums text-[#c0392b]">{p.div_yield}%</span>
                    <span className="text-right tabular-nums text-[#217346]">{won(p.monthly_per_10m)}</span>
                  </button>
                  {openDiv === p.ticker && (
                    <div className="bg-[#f7faf8] px-2.5 py-2 text-[10px] leading-relaxed">
                      <div className="mb-1 flex flex-wrap gap-1">
                        {p.reasons.map((r, i) => <span key={i} className="rounded bg-[#eef4f0] px-1.5 py-0.5 text-[#245]">{r}</span>)}
                      </div>
                      <div className="grid grid-cols-3 gap-1 text-center text-[#555]">
                        <div className="rounded bg-white px-1 py-1">PER <b>{p.per ?? "—"}</b></div>
                        <div className="rounded bg-white px-1 py-1">PBR <b>{p.pbr ?? "—"}</b></div>
                        <div className="rounded bg-white px-1 py-1">ROE <b>{p.roe ?? "—"}%</b></div>
                        <div className="rounded bg-white px-1 py-1">시총 <b>{p.market_cap ? eok(p.market_cap) : "—"}</b></div>
                        <div className="rounded bg-white px-1 py-1">외국인 <b>{p.foreign_ratio != null ? `${p.foreign_ratio}%` : "—"}</b></div>
                        <div className="rounded bg-white px-1 py-1">안정성 <b style={{ color: p.stability === "높음" ? GREEN : p.stability === "낮음" ? RED : "#e8890c" }}>{p.stability}</b></div>
                      </div>
                      <div className="mt-1 text-[#666]">배당주기: {p.cycle} · 현재가 {won(p.close)}</div>
                      <div className="mt-1 rounded bg-[#eef4f0] px-2 py-1 text-[#245]">
                        월 50만 목표 → <b>{eok(needFor(500000, p.div_yield))}원</b> · 월 100만 → <b>{eok(needFor(1000000, p.div_yield))}원</b> 투자
                      </div>
                      <a href={p.naver_url} target="_blank" rel="noreferrer" className="mt-1 inline-block text-[10px] text-[#1971c2] hover:underline">네이버 증권에서 보기 →</a>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
          {dp?.note && <div className="mt-1.5 text-[9px] leading-relaxed text-[#bbb]">{dp.note}</div>}
        </div>

        {/* ── 공모주 청약일정 ── */}
        <div className="rounded-lg border border-[#e6ede8] bg-[#f8faf9] p-3">
          <div className="mb-2 flex items-baseline justify-between">
            <span className="text-sm font-bold text-[#c0392b]">공모주 청약일정 <span className="text-[10px] font-normal text-[#888]">(종목 클릭 = 상세)</span></span>
            {ip && <span className="text-[10px] text-[#888]">청약중·예정 {ip.upcoming_count}건</span>}
          </div>
          {!ip ? <div className="py-6 text-center text-xs text-[#999]">불러오는 중…</div> :
            ip.error || ip.items.length === 0 ? <div className="py-6 text-center text-xs text-[#999]">{ip.error ? "일정 소스 접속 실패 — 잠시 후 새로고침" : "표시할 공모 일정이 없습니다."}</div> : (
            <div className="flex flex-col gap-1">
              {ip.items.map((x, i) => (
                <div key={i} className="overflow-hidden rounded border border-[#eee] bg-white">
                  <button onClick={() => setOpenIpo(openIpo === i ? null : i)} className="w-full px-1.5 py-1 text-left hover:bg-[#fafcfb]">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        {x.status && <span className="rounded px-1.5 py-0.5 text-[9px] font-bold text-white" style={{ background: statusColor(x.status) }}>{x.status}</span>}
                        <span className="text-xs font-semibold text-[#1f1f1f]">{x.name}</span>
                      </div>
                      <span className="text-[10px] tabular-nums text-[#555]">{x.subscribe}</span>
                    </div>
                    <div className="mt-0.5 flex items-center justify-between text-[10px] text-[#888]">
                      <span>공모가 {x.price_confirmed ? <b className="text-[#217346]">{x.price_confirmed}원(확정)</b> : `${x.price_band}원(밴드)`}</span>
                      <span className="truncate pl-2">{x.underwriter}</span>
                    </div>
                  </button>
                  {openIpo === i && (
                    <div className="border-t border-[#f0f0f0] bg-[#f7faf8] px-2.5 py-2 text-[10px] leading-relaxed text-[#555]">
                      <div className="grid grid-cols-2 gap-1">
                        <div className="rounded bg-white px-2 py-1">시장 <b>{x.market || "—"}</b></div>
                        <div className="rounded bg-white px-2 py-1">상장예정일 <b>{x.listing_date || "미정"}</b></div>
                        <div className="rounded bg-white px-2 py-1">공모금액 <b>{x.offer_amount_won ? eok(x.offer_amount_won) + "원" : (x.offer_amount_text || "—")}</b></div>
                        <div className="rounded bg-white px-2 py-1">총공모주식수 <b>{x.shares || "—"}</b></div>
                        <div className="rounded bg-white px-2 py-1">수요예측 경쟁률 <b style={{ color: x.demand_competition ? RED : "#aaa" }}>{x.demand_competition || "수요예측 전"}</b></div>
                        <div className="rounded bg-white px-2 py-1">의무보유확약 <b>{x.lockup || "미정"}</b></div>
                      </div>
                      <div className="mt-1 text-[#666]">주간사(청약 계좌 필요): <b>{x.underwriter}</b></div>
                      {x.detail_url && <a href={x.detail_url} target="_blank" rel="noreferrer" className="mt-1 inline-block text-[10px] text-[#1971c2] hover:underline">38커뮤니케이션 상세 →</a>}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
          {ip?.note && <div className="mt-1.5 text-[9px] leading-relaxed text-[#bbb]">{ip.note}</div>}
        </div>
      </div>
    </div>
  );
}

// ── 배당주·공모주로 소득 만들기 (가이드 + 계산기) ────────────────────────
function IncomeBuilder() {
  const [dv, setDv] = useState({ invest: "100000000", yield: "5", years: "10", growth: "3", reinvest: true });
  const [ds, setDs] = useState<DividendSim | null>(null);
  const [io, setIo] = useState({ price: "30000", shares: "10", sub: "5000000" });
  const [is, setIs] = useState<IpoSim | null>(null);

  useEffect(() => {
    const t = setTimeout(() => {
      api.wealthDividendSim({ invest: num(dv.invest), yield_pct: Number(dv.yield) || 0, years: Number(dv.years) || 10, growth_pct: Number(dv.growth) || 0, reinvest: dv.reinvest }).then(setDs).catch(() => {});
    }, 400);
    return () => clearTimeout(t);
  }, [dv]);
  useEffect(() => {
    const t = setTimeout(() => {
      api.wealthIpoSim({ offer_price: num(io.price), alloc_shares: Number(io.shares) || 0, subscribe_amount: num(io.sub) }).then(setIs).catch(() => {});
    }, 400);
    return () => clearTimeout(t);
  }, [io]);

  return (
    <div className="lg:col-span-2 overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="bg-[#217346] px-4 py-2 text-sm font-semibold text-white">배당주·공모주로 소득 만들기 (방법 + 계산기)</div>
      <div className="grid grid-cols-1 gap-3 p-3 lg:grid-cols-2">
        {/* ── 배당주 ── */}
        <div className="rounded-lg border border-[#e6ede8] bg-[#f8faf9] p-3">
          <div className="mb-2 text-sm font-bold text-[#217346]">① 배당주 — 보유만 해도 나오는 현금흐름</div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-2">
            <MoneyField label="투자금" value={dv.invest} onChange={(v) => setDv({ ...dv, invest: v })} chips={CHIP_ASSETS} />
            <Slider label="배당수익률" value={dv.yield} onChange={(v) => setDv({ ...dv, yield: v })} min={1} max={10} step={0.1} suffix="%" />
            <Slider label="기간" value={dv.years} onChange={(v) => setDv({ ...dv, years: v })} min={1} max={40} step={1} suffix="년" />
            <Slider label="배당성장" value={dv.growth} onChange={(v) => setDv({ ...dv, growth: v })} min={0} max={10} step={0.5} suffix="%" />
          </div>
          <label className="mt-1 flex items-center gap-1 text-xs text-[#555]">
            <input type="checkbox" checked={dv.reinvest} onChange={(e) => setDv({ ...dv, reinvest: e.target.checked })} />세후 배당 재투자(복리)
          </label>
          {ds && (
            <>
              <div className="mt-2 grid grid-cols-2 gap-2 text-center">
                <div className="rounded bg-white px-2 py-1.5"><div className="text-[10px] text-[#888]">월 배당(세후)</div><div className="text-sm font-bold tabular-nums text-[#217346]">{won(ds.monthly_net)}</div></div>
                <div className="rounded bg-white px-2 py-1.5"><div className="text-[10px] text-[#888]">연 배당(세후)</div><div className="text-sm font-bold tabular-nums text-[#217346]">{eok(ds.annual_net)}원</div></div>
                <div className="rounded bg-white px-2 py-1.5"><div className="text-[10px] text-[#888]">{ds.years}년 후 평가액</div><div className="text-sm font-bold tabular-nums text-[#333]">{eok(ds.final_value)}원</div></div>
                <div className="rounded bg-white px-2 py-1.5"><div className="text-[10px] text-[#888]">누적 배당(세후)</div><div className="text-sm font-bold tabular-nums text-[#2f9e44]">+{eok(ds.total_dividends_net)}원</div></div>
              </div>
              <div className="mt-2 rounded bg-[#eef4f0] p-2 text-[11px] text-[#245]">
                <div className="mb-0.5 font-semibold">월 목표 소득에 필요한 투자금 (배당 {ds.yield_pct}% · 세후)</div>
                <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                  {ds.targets.map((t) => <span key={t.monthly}>월 {eok(t.monthly)}원 → <b>{eok(t.invest)}원</b></span>)}
                </div>
              </div>
              <div className="mt-2 flex flex-col gap-0.5">
                {ds.examples.map((e) => (
                  <div key={e.name} className="flex items-baseline justify-between text-[10px]"><span className="font-semibold text-[#444]">{e.name}</span><span className="text-[#888]">수익률 {e.yield} · {e.note}</span></div>
                ))}
              </div>
              <ul className="mt-2 flex flex-col gap-0.5 rounded border border-[#f0e6c9] bg-[#fdfaf0] p-2 text-[10px] leading-relaxed text-[#7a5f10]">
                {ds.guide.map((g, i) => <li key={i}>{g}</li>)}
              </ul>
            </>
          )}
        </div>

        {/* ── 공모주 ── */}
        <div className="rounded-lg border border-[#e6ede8] bg-[#f8faf9] p-3">
          <div className="mb-2 text-sm font-bold text-[#c0392b]">② 공모주(IPO) — 상장 첫날 차익</div>
          <div className="grid grid-cols-3 gap-x-3 gap-y-2">
            <MoneyField label="공모가" value={io.price} onChange={(v) => setIo({ ...io, price: v })} />
            <label className="text-xs text-[#555]">배정 주수
              <input value={io.shares} onChange={(e) => setIo({ ...io, shares: e.target.value.replace(/[^\d]/g, "") })} inputMode="numeric" placeholder="10" className={inpCls} />
            </label>
            <MoneyField label="청약금액" value={io.sub} onChange={(v) => setIo({ ...io, sub: v })} />
          </div>
          {is && (
            <>
              <div className="mt-2 grid grid-cols-2 gap-2 text-center">
                <div className="rounded bg-white px-2 py-1.5"><div className="text-[10px] text-[#888]">배정 원가</div><div className="text-sm font-bold tabular-nums text-[#333]">{eok(is.cost)}원</div></div>
                <div className="rounded bg-white px-2 py-1.5"><div className="text-[10px] text-[#888]">청약 증거금(약 50%)</div><div className="text-sm font-bold tabular-nums text-[#333]">{eok(is.margin_estimate)}원</div></div>
              </div>
              <div className="mt-2">
                <div className="mb-1 text-[11px] font-semibold text-[#555]">상장일 상승률별 예상 수익</div>
                <div className="grid grid-cols-5 gap-1">
                  {is.scenarios.map((s) => (
                    <div key={s.gain_pct} className="rounded border border-[#eee] bg-white p-1 text-center text-[10px]">
                      <div className="font-semibold text-[#555]">+{s.gain_pct}%{s.gain_pct === 160 ? " 따상" : ""}</div>
                      <div className="tabular-nums font-bold" style={{ color: s.profit > 0 ? GREEN : "#888" }}>{s.profit > 0 ? "+" : ""}{eok(s.profit)}</div>
                    </div>
                  ))}
                </div>
              </div>
              <ul className="mt-2 flex flex-col gap-0.5 rounded border border-[#f0e6c9] bg-[#fdfaf0] p-2 text-[10px] leading-relaxed text-[#7a5f10]">
                {is.guide.map((g, i) => <li key={i}>{g}</li>)}
              </ul>
              <div className="mt-1 text-[9px] leading-relaxed text-[#bbb]">{is.note}</div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── 내 저축·상품: 지금 하고 있는 것 저장 + 혜택 + 몇 년 뒤 예상 ───────────
function MyHoldings() {
  const [cat, setCat] = useState<HoldingCatalogItem[]>([]);
  const [rows, setRows] = useState<{ name: string; monthly: string; current: string }[]>([]);
  const [horizon, setHorizon] = useState("10");
  const [proj, setProj] = useState<HoldingsData["projection"] | null>(null);
  const [pick, setPick] = useState("");
  const [busy, setBusy] = useState(false);
  const loaded = useRef(false);

  useEffect(() => {
    api.wealthHoldings().then((d) => {
      setCat(d.catalog);
      setRows(d.holdings.map((h) => ({ name: h.name, monthly: h.monthly ? String(h.monthly) : "", current: h.current ? String(h.current) : "" })));
      setHorizon(String(d.horizon || 10));
      setProj(d.projection);
    }).catch(() => {}).finally(() => { loaded.current = true; });
  }, []);

  // 값 바꾸면 0.5초 뒤 자동 저장 + 재계산
  useEffect(() => {
    if (!loaded.current) return;
    setBusy(true);
    const t = setTimeout(() => {
      const hs = rows.map((r) => ({ name: r.name, monthly: num(r.monthly), current: num(r.current) }));
      api.wealthSaveHoldings(hs, Number(horizon) || 10).then((d) => setProj(d.projection)).finally(() => setBusy(false));
    }, 500);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, horizon]);

  const add = () => { if (!pick || rows.some((r) => r.name === pick)) return; setRows([...rows, { name: pick, monthly: "", current: "" }]); setPick(""); };
  const upd = (i: number, k: "monthly" | "current", v: string) => setRows(rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  const del = (i: number) => setRows(rows.filter((_, j) => j !== i));
  const itemOf = (name: string) => proj?.items.find((x) => x.name === name);
  const catOf = (name: string) => cat.find((c) => c.name === name);

  const s = proj?.summary;
  const H = Number(horizon) || 10;
  const marks = [...new Set([1, 3, 5, 10, 15, 20, 30, H])].filter((y) => y >= 1 && y <= H).sort((a, b) => a - b);
  const maxT = Math.max(1, ...(proj?.totals_by_year.map((y) => y.total) || [1]));
  const totalAt = (y: number) => proj?.totals_by_year.find((t) => t.year === y)?.total ?? 0;
  const available = cat.filter((c) => !rows.some((r) => r.name === c.name));

  return (
    <div className="lg:col-span-2 overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
        <span className="text-sm font-semibold">내 저축·상품 — 지금 하고 있는 것 + 몇 년 뒤 예상{busy ? " · 계산 중…" : ""}</span>
        <span className="text-[10px] text-white/80">자동 저장</span>
      </div>

      {/* 기간 + 상품 추가 */}
      <div className="flex flex-wrap items-end gap-3 border-b border-[#eee] p-3">
        <div className="w-48"><Slider label="예상 기간" value={horizon} onChange={setHorizon} min={1} max={40} step={1} suffix="년" /></div>
        <label className="flex-1 text-xs text-[#555]">가입한(또는 가입할) 상품 추가
          <div className="mt-0.5 flex gap-1">
            <select value={pick} onChange={(e) => setPick(e.target.value)} className="flex-1 rounded border border-[#cdcdcd] px-2 py-1 text-xs outline-none focus:border-[#217346]">
              <option value="">— 상품 선택 —</option>
              {available.map((c) => <option key={c.name} value={c.name}>{c.name} (예상 연 {c.rate}%{c.has_bonus ? " +혜택" : ""})</option>)}
            </select>
            <button onClick={add} disabled={!pick} className="rounded bg-[#217346] px-3 py-1 text-xs font-semibold text-white hover:bg-[#1b5e3a] disabled:opacity-40">추가</button>
          </div>
        </label>
      </div>

      {rows.length === 0 ? (
        <div className="px-4 py-8 text-center text-sm text-[#999]">위에서 지금 하고 있는 저축·상품을 추가하면, 혜택과 {H}년 뒤 예상 금액을 보여드립니다.</div>
      ) : (
        <div className="p-3">
          {/* 상품별 입력 + 결과 */}
          <div className="flex flex-col gap-2">
            {rows.map((r, i) => {
              const it = itemOf(r.name); const cm = catOf(r.name);
              return (
                <div key={r.name} className="rounded-lg border border-[#e6ede8] bg-[#f8faf9] p-2.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-[#1f1f1f]">{r.name}</span>
                      <span className="rounded bg-[#eef4f0] px-1.5 py-0.5 text-[10px] font-semibold text-[#217346]">예상 연 {cm?.rate ?? it?.rate ?? "—"}%</span>
                    </div>
                    <button onClick={() => del(i)} className="rounded px-1.5 text-xs text-[#c92a2a] hover:bg-[#fbeaea]">삭제</button>
                  </div>
                  {cm?.bonus_note && <div className="mt-0.5 text-[10px] text-[#7a5f10]">혜택: {cm.bonus_note}{cm.example ? ` · ${cm.example}` : ""}</div>}
                  <div className="mt-1.5 grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <MoneyField label="월 납입" value={r.monthly} onChange={(v) => upd(i, "monthly", v)} placeholder="30만" />
                    <MoneyField label="현재 잔액" value={r.current} onChange={(v) => upd(i, "current", v)} placeholder="0" />
                    <div className="text-xs text-[#555]">낸 돈(원금)<div className="mt-0.5 rounded bg-white px-2 py-1 text-right text-sm font-bold tabular-nums text-[#333]">{it ? `${eok(it.principal)}원` : "—"}</div></div>
                    <div className="text-xs text-[#555]">{H}년 뒤 예상<div className="mt-0.5 rounded bg-white px-2 py-1 text-right text-sm font-bold tabular-nums text-[#217346]">{it ? `${eok(it.total)}원` : "—"}</div></div>
                  </div>
                  {it && (it.bonus_total > 0 || it.gain > 0) && (
                    <div className="mt-1 text-right text-[10px] text-[#888]">
                      정부·세제 혜택 <b className="text-[#2f9e44]">+{eok(it.bonus_total)}원</b> · 투자수익 포함 불어난 돈 <b className="text-[#2f9e44]">+{eok(it.gain)}원</b>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* 합계 요약 */}
          {s && (
            <>
              <div className="mt-3 grid grid-cols-2 gap-2 text-center sm:grid-cols-5">
                <div className="rounded bg-[#fafafa] px-2 py-2"><div className="text-[10px] text-[#888]">월 저축 합계</div><div className="text-sm font-bold tabular-nums text-[#333]">{won(s.monthly_sum)}</div></div>
                <div className="rounded bg-[#fafafa] px-2 py-2"><div className="text-[10px] text-[#888]">낸 돈(원금)</div><div className="text-sm font-bold tabular-nums text-[#333]">{eok(s.principal)}원</div></div>
                <div className="rounded bg-[#eef7f0] px-2 py-2"><div className="text-[10px] text-[#888]">정부·세제 혜택</div><div className="text-sm font-bold tabular-nums text-[#2f9e44]">+{eok(s.bonus_total)}원</div></div>
                <div className="rounded bg-[#eef7f0] px-2 py-2"><div className="text-[10px] text-[#888]">불어난 돈</div><div className="text-sm font-bold tabular-nums text-[#2f9e44]">+{eok(s.gain)}원</div></div>
                <div className="rounded bg-[#217346] px-2 py-2"><div className="text-[10px] text-white/80">{H}년 뒤 총액</div><div className="text-sm font-bold tabular-nums text-white">{eok(s.total)}원</div></div>
              </div>

              {/* 연도별 성장 막대 */}
              <div className="mt-3">
                <div className="mb-1 text-xs font-semibold text-[#555]">시간에 따른 예상 자산</div>
                <div className="flex flex-col gap-1">
                  {marks.map((y) => (
                    <div key={y} className="flex items-center gap-2 text-[11px]">
                      <span className="w-10 shrink-0 text-right text-[#888]">{y}년</span>
                      <div className="h-3.5 flex-1 overflow-hidden rounded bg-[#eee]">
                        <div className="h-full rounded bg-[#2f9e44]" style={{ width: `${Math.max(2, (totalAt(y) / maxT) * 100)}%` }} />
                      </div>
                      <span className="w-20 shrink-0 text-right font-bold tabular-nums text-[#217346]">{eok(totalAt(y))}원</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
          {proj?.note && <div className="mt-2 text-[10px] leading-relaxed text-[#bbb]">{proj.note}</div>}
        </div>
      )}
    </div>
  );
}

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
  const [rf, setRf] = useState({ mode: "wolse", price: "300000000", own: "100000000", rate: "4.5", years: "5", appr: "3", deposit: "10000000", rent: "1000000" });
  const [rs, setRs] = useState<RealtySim | null>(null);
  const [rbusy, setRbusy] = useState(false);
  const [rl, setRl] = useState<RealtyLoans | null>(null);

  // 값을 바꾸면 0.4초 뒤 자동 계산 (버튼 불필요)
  useEffect(() => {
    setLbusy(true);
    const t = setTimeout(() => {
      api.wealthLoanSim(num(lf.amount), Number(lf.rate) || 0, Number(lf.years) || 5, Number(lf.ret) || 0)
        .then(setLs).finally(() => setLbusy(false));
    }, 400);
    return () => clearTimeout(t);
  }, [lf]);
  useEffect(() => {
    setRbusy(true);
    const t = setTimeout(() => {
      api.wealthRealtySim({
        price: num(rf.price), own_capital: num(rf.own), loan_rate: Number(rf.rate) || 0,
        years: Number(rf.years) || 5, appreciation: Number(rf.appr) || 0, mode: rf.mode,
        deposit: num(rf.deposit), rent_monthly: num(rf.rent),
      }).then(setRs).finally(() => setRbusy(false));
    }, 400);
    return () => clearTimeout(t);
  }, [rf]);
  // 부동산 대출 종류·한도 (매매가·보증금·모드 + 프로필 소득/나이/자격)
  useEffect(() => {
    const t = setTimeout(() => {
      api.wealthRealtyLoans({
        price: num(rf.price), annual_income: num(f.annual_income), age: Number(f.age) || 0,
        married: f.married, homeless: f.homeless, has_child: f.has_child,
        deposit: num(rf.deposit), mode: rf.mode,
      }).then(setRl).catch(() => {});
    }, 400);
    return () => clearTimeout(t);
  }, [rf.price, rf.deposit, rf.mode, f.annual_income, f.age, f.married, f.homeless, f.has_child]);

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

  const payload = () => ({
    age: num(f.age), married: f.married, homeless: f.homeless, has_child: f.has_child,
    annual_income: num(f.annual_income), monthly_income: num(f.monthly_income),
    monthly_saving: num(f.monthly_saving), current_assets: num(f.current_assets),
    goal_amount: num(f.goal_amount), goal_years: num(f.goal_years) || 5,
  });
  const save = () => {
    setBusy(true);
    api.wealthSaveProfile(payload()).then(fill).finally(() => setBusy(false));
  };
  // 입력을 바꾸면 0.7초 뒤 자동으로 계획·시나리오·상품 갱신 (버튼 없이도 반영)
  useEffect(() => {
    if (num(f.goal_amount) <= 0) return;
    const t = setTimeout(() => { api.wealthSaveProfile(payload()).then(setD).catch(() => {}); }, 700);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [f]);

  const gaugePos = d && d.required_monthly > 0
    ? Math.max(0, Math.min(100, (d.capacity_monthly / d.required_monthly) * 100)) : 0;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {/* ── 좌: 프로필/목표 입력 ─────────────────── */}
      <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
        <div className="bg-[#217346] px-4 py-2 text-sm font-semibold text-white">내 정보·목표</div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-3 p-4">
          <Slider label="나이" value={f.age} onChange={(v) => setF({ ...f, age: v })} min={18} max={70} step={1} suffix="세" />
          <div className="flex items-end gap-3 text-xs text-[#555]">
            <label className="flex items-center gap-1"><input type="checkbox" checked={f.married} onChange={(e) => setF({ ...f, married: e.target.checked })} />결혼</label>
            <label className="flex items-center gap-1"><input type="checkbox" checked={f.homeless} onChange={(e) => setF({ ...f, homeless: e.target.checked })} />무주택</label>
            <label className="flex items-center gap-1"><input type="checkbox" checked={f.has_child} onChange={(e) => setF({ ...f, has_child: e.target.checked })} />자녀</label>
          </div>
          <MoneyField label="연봉" value={f.annual_income} onChange={(v) => setF({ ...f, annual_income: v })} chips={CHIP_INCOME} placeholder="4천만" />
          <MoneyField label="월 실수령" value={f.monthly_income} onChange={(v) => setF({ ...f, monthly_income: v })} chips={CHIP_MONTHLY} placeholder="300만" />
          <MoneyField label="월 저축 여력" value={f.monthly_saving} onChange={(v) => setF({ ...f, monthly_saving: v })} chips={CHIP_SAVE} placeholder="100만" />
          <MoneyField label="현재 자산" value={f.current_assets} onChange={(v) => setF({ ...f, current_assets: v })} chips={CHIP_ASSETS} placeholder="1천만" />
          <MoneyField label="목표 금액" value={f.goal_amount} onChange={(v) => setF({ ...f, goal_amount: v })} chips={CHIP_GOAL} placeholder="1억" />
          <Slider label="목표 기간" value={f.goal_years} onChange={(v) => setF({ ...f, goal_years: v })} min={1} max={40} step={1} suffix="년" />
        </div>
        <div className="flex items-center justify-between border-t border-[#eee] px-4 py-2">
          <span className="text-[10px] text-[#2f9e44]">입력하면 자동으로 계획에 반영됩니다</span>
          <button onClick={save} disabled={busy} className="rounded bg-[#217346] px-4 py-1.5 text-xs font-semibold text-white hover:bg-[#1b5e3a] disabled:opacity-50">
            {busy ? "저장 중…" : "저장"}
          </button>
        </div>
        <div className="px-4 pb-3 text-[10px] leading-relaxed text-[#aaa]">
          금액칸은 "4억"·"3천만"처럼 한글로 쳐도 되고, 아래 칩을 눌러 바로 넣을 수 있습니다. 월수입·저축여력·현재자산은 가계부/소득·성장/포트폴리오에서 자동으로 채워집니다.
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
          <div className="px-4 py-10 text-center text-sm text-[#999]">왼쪽에서 목표 금액을 입력하면 자동으로 계획이 나타납니다.</div>
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

      {/* ── 내 저축·상품 (지금 하고 있는 것 + 몇 년 뒤) ── */}
      <MyHoldings />

      {/* ── 배당주·공모주 추천 (실시간) ── */}
      <PicksBoard />

      {/* ── 배당주·공모주로 소득 만들기 ── */}
      <IncomeBuilder />

      {/* ── 대출 레버리지 시뮬레이터 ─────────────────── */}
      <div className="lg:col-span-2 overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
        <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
          <span className="text-sm font-semibold">대출 레버리지 시뮬 (대출받아 투자 시)</span>
          <span className="text-[10px] text-white/80">{lbusy ? "계산 중…" : "자동 계산"}</span>
        </div>
        <div className="grid grid-cols-2 items-end gap-x-4 gap-y-3 border-b border-[#eee] p-3 text-xs text-[#555] sm:grid-cols-4">
          <MoneyField label="대출금액" value={lf.amount} onChange={(v) => setLf({ ...lf, amount: v })} chips={CHIP_LOAN} />
          <Slider label="대출금리" value={lf.rate} onChange={(v) => setLf({ ...lf, rate: v })} min={2} max={12} step={0.1} suffix="%" />
          <Slider label="기간" value={lf.years} onChange={(v) => setLf({ ...lf, years: v })} min={1} max={30} step={1} suffix="년" />
          <Slider label="기대수익률" value={lf.ret} onChange={(v) => setLf({ ...lf, ret: v })} min={0} max={20} step={0.5} suffix="%" />
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

      {/* ── 부동산 투자 시뮬레이터 ─────────────────── */}
      <div className="lg:col-span-2 overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
        <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
          <span className="text-sm font-semibold">부동산 투자 시뮬 (자기자본 + 대출 → 세 놓기){rbusy ? " · 계산 중…" : ""}</span>
          <div className="flex gap-1 text-xs">
            <button onClick={() => setRf({ ...rf, mode: "wolse" })} className={`rounded px-2 py-0.5 ${rf.mode === "wolse" ? "bg-white text-[#217346] font-bold" : "bg-white/20"}`}>월세 수익형</button>
            <button onClick={() => setRf({ ...rf, mode: "jeonse" })} className={`rounded px-2 py-0.5 ${rf.mode === "jeonse" ? "bg-white text-[#217346] font-bold" : "bg-white/20"}`}>전세 갭투자</button>
          </div>
        </div>
        <div className="grid grid-cols-2 items-end gap-x-4 gap-y-3 border-b border-[#eee] p-3 text-xs text-[#555] sm:grid-cols-3">
          <MoneyField label="매매가" value={rf.price} onChange={(v) => setRf({ ...rf, price: v })} chips={CHIP_PRICE} />
          <MoneyField label="자기자본" value={rf.own} onChange={(v) => setRf({ ...rf, own: v })} chips={CHIP_OWN} />
          <Slider label="대출금리" value={rf.rate} onChange={(v) => setRf({ ...rf, rate: v })} min={2} max={10} step={0.1} suffix="%" />
          <Slider label="보유" value={rf.years} onChange={(v) => setRf({ ...rf, years: v })} min={1} max={30} step={1} suffix="년" />
          <Slider label="연 집값상승" value={rf.appr} onChange={(v) => setRf({ ...rf, appr: v })} min={-5} max={10} step={0.5} suffix="%" />
          {rf.mode === "jeonse" ? (
            <MoneyField label="전세보증금" value={rf.deposit} onChange={(v) => setRf({ ...rf, deposit: v })} />
          ) : (
            <>
              <MoneyField label="월세보증금" value={rf.deposit} onChange={(v) => setRf({ ...rf, deposit: v })} />
              <MoneyField label="월세" value={rf.rent} onChange={(v) => setRf({ ...rf, rent: v })} />
            </>
          )}
        </div>
        {rs && (
          <div className="p-3">
            <div className="mb-2 grid grid-cols-2 gap-2 text-center sm:grid-cols-4">
              <div className="rounded bg-[#fafafa] px-2 py-1.5"><div className="text-[10px] text-[#888]">필요 대출</div><div className="text-xs font-bold tabular-nums text-[#333]">{eok(rs.loan)}원</div></div>
              <div className="rounded bg-[#fafafa] px-2 py-1.5"><div className="text-[10px] text-[#888]">월 이자</div><div className="text-xs font-bold tabular-nums" style={{ color: RED }}>{won(rs.monthly_interest)}</div></div>
              {rs.mode === "월세 수익형" ? (
                <div className="rounded bg-[#fafafa] px-2 py-1.5"><div className="text-[10px] text-[#888]">월 현금흐름</div><div className="text-xs font-bold tabular-nums" style={{ color: rs.monthly_cashflow >= 0 ? GREEN : RED }}>{rs.monthly_cashflow >= 0 ? "+" : ""}{won(rs.monthly_cashflow)}</div></div>
              ) : (
                <div className="rounded bg-[#fafafa] px-2 py-1.5"><div className="text-[10px] text-[#888]">{rs.years}년 뒤 집값</div><div className="text-xs font-bold tabular-nums text-[#333]">{eok(rs.future_price)}원</div></div>
              )}
              <div className="rounded bg-[#fafafa] px-2 py-1.5"><div className="text-[10px] text-[#888]">자기자본 수익률(ROE)</div><div className="text-xs font-bold tabular-nums" style={{ color: (rs.roe ?? 0) >= 0 ? GREEN : RED }}>{rs.roe != null ? `${rs.roe}%` : "—"}</div></div>
            </div>
            <div className="mb-2 rounded bg-[#eef4f0] px-2 py-1.5 text-[11px] text-[#245]">
              레버리지 효과: 자기자본 대비 <b>{rs.roe}%</b> vs 무대출(전액 현금) <b>{rs.roe_no_leverage}%</b>
              {rs.rent_yield_on_capital != null && <> · 월세 수익률(자기자본 대비) <b>{rs.rent_yield_on_capital}%</b></>}
            </div>
            <div className="mb-2 grid grid-cols-3 gap-2">
              {rs.scenarios.map((s) => (
                <div key={s.name} className="rounded border border-[#eee] p-2 text-center text-[11px]">
                  <div className="font-semibold text-[#555]">{s.name} (연 {s.appreciation}%)</div>
                  <div className="tabular-nums text-[10px] text-[#999]">순손익</div>
                  <div className="tabular-nums font-bold" style={{ color: s.net_profit >= 0 ? GREEN : RED }}>{s.net_profit >= 0 ? "+" : ""}{eok(s.net_profit)}원</div>
                  <div className="tabular-nums text-[10px]" style={{ color: (s.roe ?? 0) >= 0 ? GREEN : RED }}>ROE {s.roe}%</div>
                </div>
              ))}
            </div>
            <div className="rounded bg-[#fff8f0] px-2 py-1.5 text-[10px] leading-relaxed text-[#a33]">{rs.warning}</div>
          </div>
        )}

        {/* 받을 수 있는 대출·한도 */}
        {rl && (
          <div className="border-t border-[#eee] p-3">
            <div className="mb-1.5 flex items-baseline justify-between">
              <span className="text-xs font-bold text-[#217346]">받을 수 있는 대출·한도 <span className="font-normal text-[#888]">({rl.mode} 기준 · 자격 {rl.eligible_count}개)</span></span>
              <span className="text-[10px] text-[#c0392b]">최대 한도 {eok(rl.max_limit)}원</span>
            </div>
            <div className="mb-1.5 rounded bg-[#eef4f0] px-2 py-1 text-[10px] leading-relaxed text-[#245]">{rl.dsr_note}</div>
            <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
              {[...rl.loans].sort((a, b) => Number(b.eligible) - Number(a.eligible)).map((l) => (
                <div key={l.name} className={`rounded-lg border p-2 ${l.eligible ? "border-[#cfe3d6] bg-[#f7faf8]" : "border-[#eee] bg-[#fafafa] opacity-70"}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-[#1f1f1f]">{l.name}</span>
                    {l.eligible
                      ? <span className="rounded bg-[#2f9e44] px-1.5 py-0.5 text-[9px] font-bold text-white">가능</span>
                      : <span className="rounded bg-[#bbb] px-1.5 py-0.5 text-[9px] font-bold text-white">해당X</span>}
                  </div>
                  <div className="mt-0.5 flex items-center justify-between text-[10px]">
                    <span className="text-[#888]">{l.kind} · 금리 ~{l.rate}%</span>
                    <span className="font-bold tabular-nums text-[#217346]">한도 {l.limit ? `${eok(l.limit)}원` : "—"}</span>
                  </div>
                  <div className="mt-0.5 text-[9px] leading-relaxed text-[#999]">{l.cond}</div>
                  <div className="text-[9px] leading-relaxed text-[#7a5f10]">{l.note}</div>
                </div>
              ))}
            </div>
            <div className="mt-1.5 text-[9px] leading-relaxed text-[#bbb]">{rl.note}</div>
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
