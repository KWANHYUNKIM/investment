"use client";

import { useEffect, useRef, useState } from "react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine, Legend } from "recharts";
import { api, KoreaFlow as KF, KoreaFlowItem, KoreaFlowNews, RealEstateTrades, RealEstateRent, EcosIndicator, EcosMacro, MoneySupply, MoneyCountry, MoneyCrisis, MoneyAnalysis, StructuralCountry, AssetLinkItem, Regime, RealRate, RealEconomy, WorldIndicator } from "@/lib/api";
import { MortgageForecast } from "@/components/MortgageForecast";
import { KoreaDiagnosis } from "@/components/KoreaDiagnosis";

const RED = "#c92a2a";
const BLUE = "#1971c2";

// 한국 시장 관례: 상승=빨강, 하락=파랑.
function retStyle(v: number | null): React.CSSProperties {
  if (v == null) return { color: "#bbb" };
  return { color: v > 0 ? RED : v < 0 ? BLUE : "#666", fontWeight: 700 };
}
function pctTxt(v: number | null): string {
  if (v == null) return "—";
  return `${v > 0 ? "+" : ""}${v}%`;
}
// 자금: 유입=빨강(자산↑), 이탈=파랑(자산↓)
function dirColor(d?: string) {
  return d === "유입" ? RED : d === "이탈" ? BLUE : "#666";
}
function leanColor(l?: string) {
  return l === "긍정" ? RED : l === "부정" ? BLUE : "#666";
}

export function KoreaFlow() {
  const [d, setD] = useState<KF | null>(null);
  const [live, setLive] = useState(false);
  const [err, setErr] = useState("");
  const [at, setAt] = useState("");
  const first = useRef(true);

  useEffect(() => {
    let alive = true;
    const load = () =>
      api
        .koreaFlow()
        .then((r) => {
          if (!alive) return;
          setD(r);
          setLive(true);
          setAt(new Date().toLocaleTimeString("ko-KR", { hour12: false }));
        })
        .catch((e) => {
          if (alive && first.current) setErr(e?.message ?? "한국 경제 흐름을 불러오지 못했습니다.");
        })
        .finally(() => {
          first.current = false;
        });
    load();
    const id = setInterval(load, 60000); // 60초마다 갱신
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  if (err && !d)
    return <div className="py-20 text-center text-sm text-rose-600">{err}</div>;
  if (!d)
    return (
      <div className="flex flex-col items-center gap-3 py-24 text-sm text-[#888]">
        <span className="h-7 w-7 animate-spin rounded-full border-2 border-[#d0d0d0] border-t-[#217346]" />
        한국 경제 흐름 취합 중…
      </div>
    );

  const v = d.verdict;

  return (
    <div className="space-y-5">
      {/* 한국경제 종합 진단 — 지금 어느 국면인가 (ECOS 실측) */}
      <KoreaDiagnosis />

      {/* 종합 판정 */}
      <section className="rounded border border-[#d0d0d0] bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-2">
          <Badge label="부동산(리츠) 자금" value={v.real_estate_dir} color={dirColor(v.real_estate_dir)} />
          <Badge label="국채·채권 자금" value={v.bond_dir} color={dirColor(v.bond_dir)} />
          <span className="ml-auto flex items-center gap-3 text-xs">
            <span className="flex items-center gap-1.5 font-bold" style={{ color: live ? "#2f9e44" : "#aaa" }}>
              <span className={`inline-block h-2 w-2 rounded-full ${live ? "animate-pulse" : ""}`} style={{ background: live ? "#2f9e44" : "#bbb" }} />
              LIVE {at && <span className="font-normal text-[#999]">갱신 {at}</span>}
            </span>
            <span className="text-[#999]">기준 {d.as_of?.slice(5)}</span>
          </span>
        </div>
        <p className="mt-3 text-sm font-medium text-[#333]">{v.narrative}</p>
        <p className="mt-1 text-[11px] text-[#aaa]">{d.note}</p>
      </section>

      {/* 모기지(주담대) 금리 시나리오 예측 */}
      <MortgageForecast />

      {/* 국내 거시지표 — 한국은행 ECOS (M2·가계신용·주택가격) */}
      <EcosMacroSection />

      {/* 통화량 — 과거 경제위기·해외 주요국 비교 */}
      <MoneySupplySection />

      {/* 통화량 심층분석 — 마샬케이·실질통화량·신용 / 돈의 행선지 / 레짐 */}
      <MoneyAnalysisSection />

      {/* 실물경제 — 한국 국민계정 + 세계 비교 */}
      <RealEconomySection />

      {/* 부동산 실거래 거래액·거래량 (국토부 RTMS) */}
      <RealEstateSection />

      {/* 부동산 전월세 실거래 (국토부 RTMS) */}
      <RentSection />

      {/* 부동산 ETF / 리츠 */}
      <FlowTable
        title="부동산으로 가는 돈 — 리츠·부동산 ETF"
        subtitle="가격이 오르면 부동산 자산으로 자금 유입 신호 (1개월 평균이 판정 기준)"
        items={d.real_estate}
      />

      {/* 국채 / 채권 ETF */}
      <FlowTable
        title="국채·채권으로 가는 돈 — 국고채·종합채권 ETF"
        subtitle="안전자산(채권) 선호 신호. 국고채 금리·발행 정확한 수치는 ECOS 키 연동 시 추가"
        items={d.bonds}
      />

      {/* 뉴스 동향 */}
      <section>
        <h3 className="mb-2 text-sm font-bold text-[#244d1a]">부동산·국채 뉴스 동향</h3>
        <div className="grid gap-3 md:grid-cols-2">
          {d.news.map((c) => (
            <NewsCard key={c.key} c={c} />
          ))}
        </div>
      </section>
    </div>
  );
}

function Sparkline({ pts, color }: { pts: number[]; color: string }) {
  if (pts.length < 2) return null;
  const w = 120, h = 30, pad = 2;
  const min = Math.min(...pts), max = Math.max(...pts);
  const span = max - min || 1;
  const xs = (i: number) => pad + (i / (pts.length - 1)) * (w - 2 * pad);
  const ys = (v: number) => h - pad - ((v - min) / span) * (h - 2 * pad);
  const dPath = pts.map((v, i) => `${i === 0 ? "M" : "L"}${xs(i).toFixed(1)},${ys(v).toFixed(1)}`).join(" ");
  return (
    <svg width={w} height={h} className="overflow-visible">
      <path d={dPath} fill="none" stroke={color} strokeWidth={1.5} />
      <circle cx={xs(pts.length - 1)} cy={ys(pts[pts.length - 1])} r={2} fill={color} />
    </svg>
  );
}

function EcosMacroSection() {
  const [d, setD] = useState<EcosMacro | null>(null);
  const [loading, setLoading] = useState(true);
  const [sel, setSel] = useState<EcosIndicator | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .ecosMacro()
      .then((r) => alive && setD(r))
      .catch(() => alive && setD(null))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <section className="overflow-hidden rounded-lg border border-[#e0e0e0]">
      {sel && <EcosChartModal ind={sel} onClose={() => setSel(null)} />}
      <div className="flex flex-wrap items-center gap-2 border-b border-[#e0e0e0] bg-[#1b5e3a] px-3 py-1.5">
        <span className="text-sm font-bold text-white">국내 돈 흐름 — 거시지표 (한국은행 ECOS)</span>
        <span className="text-[11px] text-white/70">M2 통화량 · 가계 빚 · 집값 · <span className="text-white/90">카드를 클릭하면 크게 보기</span></span>
      </div>
      {loading ? (
        <div className="py-8 text-center text-sm text-[#888]">거시지표 불러오는 중…</div>
      ) : !d || !d.available ? (
        <div className="px-4 py-6 text-center text-sm text-[#999]">{d?.reason ?? "거시지표를 불러오지 못했습니다."}</div>
      ) : (
        <div className="divide-y divide-[#eee]">
          {Array.from(new Set(d.indicators.map((i) => i.group))).map((g) => (
            <div key={g} className="p-2">
              <div className="mb-1 px-1 text-[11px] font-bold uppercase tracking-wide text-[#1b5e3a]">{g}</div>
              <div className="grid gap-px bg-[#eee] md:grid-cols-2 xl:grid-cols-3">
                {d.indicators.filter((i) => i.group === g).map((i) => (
                  <EcosCard key={i.key} ind={i} onOpen={() => setSel(i)} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

// 전체 기간 누적 변화 텍스트: level=%, rate=%p, index=p, flow=억$
function spanChange(ind: EcosIndicator): { text: string; up: boolean } {
  const s = ind.span;
  if (s.kind === "level") {
    const v = s.change_pct ?? 0;
    return { text: `${v > 0 ? "+" : ""}${v}%`, up: v >= 0 };
  }
  const v = s.change_delta ?? 0;
  const unit = s.kind === "rate" ? "%p" : s.kind === "flow" ? "억$" : "p";
  return { text: `${v > 0 ? "+" : ""}${v}${unit}`, up: v >= 0 };
}

function EcosChartTip({ active, payload, label, kind }: { active?: boolean; payload?: { value: number }[]; label?: string; kind: string }) {
  if (!active || !payload || !payload.length) return null;
  const unit = kind === "rate" ? "%" : "";
  return (
    <div className="rounded border border-[#d0d0d0] bg-white px-2 py-1 text-[11px] shadow-sm">
      <div className="text-[#888]">{label}</div>
      <div className="font-bold tabular-nums text-[#1f1f1f]">{payload[0].value.toLocaleString("ko-KR")}{unit}</div>
    </div>
  );
}

function EcosCard({ ind, onOpen }: { ind: EcosIndicator; onOpen: () => void }) {
  const chg = spanChange(ind);
  const color = chg.up ? RED : BLUE;
  // 100 기준선이 의미 있는 심리지수만 기준선 표시
  const showBase = ind.kind === "index";
  return (
    <div className="group cursor-pointer bg-white p-3 transition hover:bg-[#f7faf8]" onClick={onOpen} title="클릭하면 크게 보기">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-semibold text-[#555]">{ind.label}</span>
        <span className="text-lg font-bold tabular-nums text-[#1f1f1f]">{ind.display}</span>
      </div>
      <div className="mt-0.5 flex items-center justify-between text-[10px]">
        <span className="text-[#aaa]">{ind.period} 기준</span>
        <span className="tabular-nums text-[#aaa]">
          {ind.span.from} → {ind.span.to} <span className="font-bold" style={{ color }}>{chg.text}</span>
        </span>
      </div>

      {/* 전체 기간 그래프 */}
      <div className="mt-1.5 h-28 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={ind.series} margin={{ top: 4, right: 6, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#f3f3f3" vertical={false} />
            <XAxis dataKey="t" tick={{ fill: "#bbb", fontSize: 9 }} minTickGap={48} interval="preserveStartEnd" tickLine={false} />
            <YAxis hide domain={["auto", "auto"]} />
            {showBase && <ReferenceLine y={100} stroke="#d0d0d0" strokeDasharray="3 3" />}
            <Tooltip content={<EcosChartTip kind={ind.kind} />} />
            <Line dataKey="v" stroke={color} dot={false} strokeWidth={1.4} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-1 flex items-center gap-2 text-xs">
        <span className="text-[#888]">{ind.yoy_label}</span>
        <span className="font-bold tabular-nums" style={retStyle(ind.yoy)}>
          {ind.yoy != null ? `${ind.yoy > 0 ? "+" : ""}${ind.yoy}%` : "—"}
        </span>
        {ind.mom != null && (
          <span className="text-[#aaa]">· MoM <span style={retStyle(ind.mom)}>{ind.mom > 0 ? "+" : ""}{ind.mom}%</span></span>
        )}
      </div>
      <p className="mt-1 text-[10px] leading-tight text-[#999]">{ind.desc}</p>
    </div>
  );
}

// 클릭하면 뜨는 큰 차트 모달 셸 (배경 클릭·ESC로 닫힘)
function Modal({ title, sub, onClose, children }: { title: string; sub?: string; onClose: () => void; children: React.ReactNode }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", h);
      document.body.style.overflow = "";
    };
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="w-full max-w-4xl rounded-lg bg-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between border-b border-[#eee] px-4 py-2.5">
          <div>
            <div className="text-sm font-bold text-[#1f1f1f]">{title}</div>
            {sub && <div className="text-[11px] text-[#888]">{sub}</div>}
          </div>
          <button onClick={onClose} className="rounded border border-[#ddd] px-2 py-0.5 text-xs text-[#666] hover:bg-[#f3f3f3]">닫기 ✕</button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div className="text-[11px] text-[#888]">{label}</div>
      <div className="text-base font-bold tabular-nums" style={{ color: color ?? "#1f1f1f" }}>{value}</div>
    </div>
  );
}

function fmtNum(v: number): string {
  return Math.abs(v) >= 100 ? Math.round(v).toLocaleString("ko-KR") : v.toLocaleString("ko-KR", { maximumFractionDigits: 2 });
}

function EcosChartModal({ ind, onClose }: { ind: EcosIndicator; onClose: () => void }) {
  const chg = spanChange(ind);
  const color = chg.up ? RED : BLUE;
  const showBase = ind.kind === "index";
  const vals = ind.series.map((p) => p.v);
  const min = Math.min(...vals), max = Math.max(...vals);
  const minPt = ind.series.find((p) => p.v === min);
  const maxPt = ind.series.find((p) => p.v === max);
  const unit = ind.kind === "rate" ? "%" : "";
  const chgColor = chg.up ? RED : BLUE;
  return (
    <Modal title={ind.label} sub={`${ind.span.from} ~ ${ind.span.to} · 전체 ${ind.span.n.toLocaleString("ko-KR")}개 구간 · 한국은행 ECOS`} onClose={onClose}>
      <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Stat label={`현재 (${ind.period})`} value={ind.display} />
        <Stat label="전 구간 누적" value={chg.text} color={chgColor} />
        <Stat label={ind.yoy_label} value={ind.yoy != null ? `${ind.yoy > 0 ? "+" : ""}${ind.yoy}%` : "—"} color={ind.yoy != null ? growthColor(ind.yoy) : undefined} />
        <Stat label="최고" value={`${fmtNum(max)}${unit}`} color={RED} />
        <Stat label="최저" value={`${fmtNum(min)}${unit}`} color={BLUE} />
      </div>
      <div className="h-[420px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={ind.series} margin={{ top: 8, right: 16, bottom: 4, left: 8 }}>
            <CartesianGrid stroke="#eee" vertical={false} />
            <XAxis dataKey="t" tick={{ fill: "#888", fontSize: 11 }} minTickGap={60} interval="preserveStartEnd" />
            <YAxis orientation="right" width={58} tick={{ fill: "#888", fontSize: 11 }} domain={["auto", "auto"]} tickFormatter={(v) => fmtNum(Number(v))} />
            {showBase && <ReferenceLine y={100} stroke="#c0c0c0" strokeDasharray="4 4" label={{ value: "100 중립", fontSize: 10, fill: "#999", position: "insideTopRight" }} />}
            {ind.kind === "flow" && <ReferenceLine y={0} stroke="#c0c0c0" />}
            <Tooltip content={<EcosChartTip kind={ind.kind} />} />
            <Line dataKey="v" stroke={color} dot={false} strokeWidth={1.8} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-3 text-xs leading-snug text-[#666]">{ind.desc}</p>
      {maxPt && minPt && (
        <p className="mt-1 text-[11px] text-[#999]">최고 {maxPt.t} · 최저 {minPt.t} · 시작 {ind.span.from} {fmtNum(ind.span.first)}{unit} → 현재 {fmtNum(ind.span.last)}{unit}</p>
      )}
    </Modal>
  );
}

// 통화량 증가율: 확대=빨강(돈 풀림), 둔화/수축=파랑
function growthColor(v: number | null | undefined): string {
  if (v == null) return "#888";
  return v > 0 ? RED : v < 0 ? BLUE : "#666";
}
function toneColor(t?: string): string {
  return t === "hot" ? RED : t === "cold" ? BLUE : t === "mixed" ? "#b8860b" : "#666";
}
function gpct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${v > 0 ? "+" : ""}${v}%`;
}

function MoneySupplySection() {
  const [d, setD] = useState<MoneySupply | null>(null);
  const [loading, setLoading] = useState(true);
  const [selC, setSelC] = useState<MoneyCountry | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .moneySupply()
      .then((r) => alive && setD(r))
      .catch(() => alive && setD(null))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <section className="overflow-hidden rounded-lg border border-[#e0e0e0]">
      {selC && <CountryChartModal c={selC} onClose={() => setSelC(null)} />}
      <div className="flex flex-wrap items-center gap-2 border-b border-[#e0e0e0] bg-[#1b5e3a] px-3 py-1.5">
        <span className="text-sm font-bold text-white">통화량 — 과거 위기·해외 주요국 비교</span>
        <span className="text-[11px] text-white/70">지금 풀린 돈을 IMF·금융위기·코로나, 그리고 미·중·일과 견줌</span>
      </div>
      {loading ? (
        <div className="py-8 text-center text-sm text-[#888]">통화량 비교 집계 중…</div>
      ) : !d || !d.available ? (
        <div className="px-4 py-6 text-center text-sm text-[#999]">{d?.reason ?? "통화량 비교 데이터를 불러오지 못했습니다."}</div>
      ) : (
        <div className="space-y-4 p-3">
          {/* 헤드라인 + 판정 */}
          {d.headline && (
            <div className="rounded border border-[#e6e6e6] bg-[#f8faf9] p-3">
              <div className="flex flex-wrap items-end gap-x-6 gap-y-1">
                <div>
                  <div className="text-[11px] text-[#888]">한국 M2 통화량 ({d.headline.kr_m2_period})</div>
                  <div className="text-lg font-bold tabular-nums text-[#1f1f1f]">{d.headline.kr_m2_display ?? "—"}</div>
                </div>
                <div>
                  <div className="text-[11px] text-[#888]">한국 전년동월比</div>
                  <div className="text-base font-bold tabular-nums" style={{ color: growthColor(d.headline.kr_m2_yoy) }}>{gpct(d.headline.kr_m2_yoy)}</div>
                </div>
                <div>
                  <div className="text-[11px] text-[#888]">미국 M2 전년동월比</div>
                  <div className="text-base font-bold tabular-nums" style={{ color: growthColor(d.headline.us_m2_yoy) }}>{gpct(d.headline.us_m2_yoy)}</div>
                </div>
                {d.verdict?.avg_20y != null && (
                  <div>
                    <div className="text-[11px] text-[#888]">한국 장기평균(’02~)</div>
                    <div className="text-base font-bold tabular-nums text-[#555]">{gpct(d.verdict.avg_20y)}</div>
                  </div>
                )}
              </div>
              {d.verdict && (
                <p className="mt-2 text-sm font-medium text-[#333]">
                  <span className="mr-1.5 rounded px-1.5 py-0.5 text-xs font-bold text-white" style={{ background: d.verdict.stance.includes("확대") ? RED : d.verdict.stance.includes("둔화") ? BLUE : "#888" }}>
                    {d.verdict.stance}
                  </span>
                  {d.verdict.narrative}
                </p>
              )}
            </div>
          )}

          {/* 해외 주요국 통화량 증가율 */}
          <div>
            <div className="mb-1.5 text-xs font-bold text-[#244d1a]">해외 주요국 통화량(M2) 증가율 — 국가 간 동일 기준(World Bank, 연%) <span className="font-normal text-[#999]">· 카드 클릭하면 크게</span></div>
            <div className="grid gap-px bg-[#eee] sm:grid-cols-2 lg:grid-cols-4">
              {d.countries.map((c) => (
                <CountryCard key={c.iso} c={c} onOpen={() => setSelC(c)} />
              ))}
            </div>
          </div>

          {/* 과거 경제위기 때 통화량 */}
          <div>
            <div className="mb-1.5 text-xs font-bold text-[#244d1a]">과거 경제위기 때 통화량은 어떻게 움직였나</div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {d.crises.map((c) => (
                <CrisisCard key={c.key} c={c} />
              ))}
            </div>
          </div>

          <p className="text-[10px] leading-tight text-[#aaa]">{d.note}</p>
          <p className="text-[10px] text-[#bbb]">출처: {d.source}</p>
        </div>
      )}
    </section>
  );
}

function MoneyGrowthTip({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: number }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="rounded border border-[#d0d0d0] bg-white px-2 py-1 text-[11px] shadow-sm">
      <span className="text-[#888]">{label}년 </span>
      <span className="font-bold tabular-nums" style={{ color: growthColor(payload[0].value) }}>{gpct(payload[0].value)}</span>
    </div>
  );
}

function CountryCard({ c, onOpen }: { c: MoneyCountry; onOpen: () => void }) {
  const color = toneColor(c.tone);
  return (
    <div className="cursor-pointer bg-white p-3 transition hover:bg-[#f7faf8]" onClick={onOpen} title="클릭하면 크게 보기">
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold text-[#333]">{c.name} <span className="font-normal text-[#aaa]">({c.currency})</span></span>
        <span className="text-[10px] text-[#aaa]">{c.avg_years}</span>
      </div>
      <div className="mt-1 flex items-end justify-between gap-2">
        <div className="text-lg font-bold tabular-nums" style={{ color }}>{gpct(c.latest)}<span className="ml-1 text-[10px] font-normal text-[#aaa]">{c.latest_year}</span></div>
        <div className="text-right text-[10px] text-[#aaa]">평균 {gpct(c.avg)}</div>
      </div>
      {/* 전체 기간 통화량 증가율 그래프 */}
      <div className="mt-1 h-24 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={c.series} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#f3f3f3" vertical={false} />
            <XAxis dataKey="year" tick={{ fill: "#bbb", fontSize: 9 }} minTickGap={40} interval="preserveStartEnd" tickLine={false} />
            <YAxis hide domain={["auto", "auto"]} />
            <ReferenceLine y={0} stroke="#d0d0d0" />
            <Tooltip content={<MoneyGrowthTip />} />
            <Line dataKey="growth" stroke={color} dot={false} strokeWidth={1.4} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-1 flex items-center gap-2 text-[10px] text-[#999]">
        <span>최고 <span className="font-bold" style={{ color: RED }}>{gpct(c.max)}</span> <span className="text-[#bbb]">’{String(c.max_year).slice(2)}</span></span>
        <span>최저 <span className="font-bold" style={{ color: BLUE }}>{gpct(c.min)}</span> <span className="text-[#bbb]">’{String(c.min_year).slice(2)}</span></span>
      </div>
    </div>
  );
}

function CountryChartModal({ c, onClose }: { c: MoneyCountry; onClose: () => void }) {
  const color = toneColor(c.tone);
  return (
    <Modal title={`${c.name} 통화량(M2) 증가율`} sub={`${c.avg_years} · 광의통화 전년比 증가율(%) · World Bank`} onClose={onClose}>
      <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label={`최신 (${c.latest_year})`} value={gpct(c.latest)} color={color} />
        <Stat label="기간 평균" value={gpct(c.avg)} />
        <Stat label={`최고 (’${String(c.max_year).slice(2)})`} value={gpct(c.max)} color={RED} />
        <Stat label={`최저 (’${String(c.min_year).slice(2)})`} value={gpct(c.min)} color={BLUE} />
      </div>
      <div className="h-[420px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={c.series} margin={{ top: 8, right: 16, bottom: 4, left: 8 }}>
            <CartesianGrid stroke="#eee" vertical={false} />
            <XAxis dataKey="year" tick={{ fill: "#888", fontSize: 11 }} minTickGap={40} interval="preserveStartEnd" />
            <YAxis orientation="right" width={48} tick={{ fill: "#888", fontSize: 11 }} domain={["auto", "auto"]} tickFormatter={(v) => `${v}%`} />
            <ReferenceLine y={0} stroke="#c0c0c0" />
            <Tooltip content={<MoneyGrowthTip />} />
            <Line dataKey="growth" stroke={color} dot={{ r: 2, fill: color }} strokeWidth={1.8} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-3 text-[11px] leading-snug text-[#777]">
        증가율이 높을수록 통화량이 빠르게 늘어난(유동성 확대) 해. 1997 외환위기·2008 금융위기·2020 코로나 같은 구간의 굴곡이 보인다.
      </p>
    </Modal>
  );
}

function GrowthChips({ label, pts }: { label: string; pts: { year: number; growth: number | null }[] | null }) {
  if (!pts || pts.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-1 text-[11px]">
      <span className="text-[#999]">{label}</span>
      {pts.map((p) => (
        <span key={p.year} className="rounded bg-[#f1f1f1] px-1.5 py-0.5 tabular-nums">
          ’{String(p.year).slice(2)} <span className="font-bold" style={{ color: growthColor(p.growth) }}>{gpct(p.growth)}</span>
        </span>
      ))}
    </div>
  );
}

function CrisisCard({ c }: { c: MoneyCrisis }) {
  const accent = toneColor(c.tone);
  return (
    <div className="flex flex-col rounded-lg border border-[#e0e0e0] bg-white p-3" style={{ borderTop: `3px solid ${accent}` }}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-bold text-[#222]">{c.name}</span>
        <span className="shrink-0 text-[11px] font-semibold tabular-nums text-[#888]">{c.period}</span>
      </div>
      <div className="text-[11px] text-[#aaa]">{c.scope}</div>
      <div className="mt-1.5 text-sm font-bold" style={{ color: accent }}>{c.headline}</div>
      <div className="mt-1.5 space-y-1">
        <GrowthChips label="한국 M2" pts={c.kr_growth} />
        <GrowthChips label="미국 M2" pts={c.us_growth} />
      </div>
      <p className="mt-2 text-xs leading-snug text-[#555]">{c.narrative}</p>
      <p className="mt-1.5 border-t border-[#f0f0f0] pt-1.5 text-[11px] leading-snug text-[#7a6a00]">
        <span className="font-bold">교훈 </span>{c.lesson}
      </p>
      {c.data_note && <p className="mt-1 text-[10px] text-[#bbb]">※ {c.data_note}</p>}
    </div>
  );
}

// 두 시계열(M2 vs 자산, 둘 다 지수 100 기준)을 한 칸에 겹쳐 그림
function DualSpark({ a, b, colorA, colorB }: { a: number[]; b: number[]; colorA: string; colorB: string }) {
  const all = [...a, ...b];
  if (all.length < 2) return null;
  const w = 150, h = 44, pad = 3;
  const min = Math.min(...all), max = Math.max(...all);
  const span = max - min || 1;
  const path = (pts: number[]) => {
    const xs = (i: number) => pad + (i / (pts.length - 1)) * (w - 2 * pad);
    const ys = (val: number) => h - pad - ((val - min) / span) * (h - 2 * pad);
    return pts.map((val, i) => `${i === 0 ? "M" : "L"}${xs(i).toFixed(1)},${ys(val).toFixed(1)}`).join(" ");
  };
  return (
    <svg width={w} height={h} className="overflow-visible">
      <path d={path(a)} fill="none" stroke={colorA} strokeWidth={1.3} strokeDasharray="3 2" />
      <path d={path(b)} fill="none" stroke={colorB} strokeWidth={1.6} />
    </svg>
  );
}

function MoneyAnalysisSection() {
  const [d, setD] = useState<MoneyAnalysis | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api
      .moneyAnalysis()
      .then((r) => alive && setD(r))
      .catch(() => alive && setD(null))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <section className="overflow-hidden rounded-lg border border-[#e0e0e0]">
      <div className="flex flex-wrap items-center gap-2 border-b border-[#e0e0e0] bg-[#143d28] px-3 py-1.5">
        <span className="text-sm font-bold text-white">통화량 심층분석 — 비교·판단용 파생지표</span>
        <span className="text-[11px] text-white/70">마샬케이·실질통화량·신용 / 돈의 행선지 / 실질금리·침체</span>
      </div>
      {loading ? (
        <div className="py-8 text-center text-sm text-[#888]">심층분석 계산 중… <span className="text-[#bbb]">(World Bank·자산시세 취합)</span></div>
      ) : !d || !d.available ? (
        <div className="px-4 py-6 text-center text-sm text-[#999]">{d?.reason ?? "심층분석 데이터를 불러오지 못했습니다."}</div>
      ) : (
        <div className="space-y-4 p-3">
          {/* A. 구조지표 — 분모를 붙인 비교 */}
          {d.structural.length > 0 && <StructuralBlock rows={d.structural} />}

          {/* B. 돈의 행선지 */}
          {d.asset_link && (
            <div>
              <div className="mb-1.5 text-xs font-bold text-[#244d1a]">돈의 행선지 — 통화량(M2)이 풀릴 때 어떤 자산이 반응했나</div>
              <p className="mb-2 text-[11px] leading-snug text-[#777]">{d.asset_link.narrative}</p>
              <div className="grid gap-3 sm:grid-cols-3">
                {d.asset_link.assets.map((a) => (
                  <AssetLinkCard key={a.key} a={a} />
                ))}
              </div>
              <p className="mt-1 text-[10px] text-[#aaa]">점선=한국 M2 · 실선=자산 (둘 다 시작연도=100 지수). 상관계수는 연 증가율 기준.</p>
            </div>
          )}

          {/* C. 레짐 — 실질금리·침체 */}
          {d.regime && <RegimeBlock r={d.regime} />}

          <p className="text-[10px] leading-tight text-[#aaa]">{d.note}</p>
          <p className="text-[10px] text-[#bbb]">출처: {d.source}</p>
        </div>
      )}
    </section>
  );
}

// 현재값을 평균 대비로 색칠 (높음=빨강=유동성 과다, 낮음=파랑)
function vsAvgColor(latest: number | null, avg: number | null | undefined): string {
  if (latest == null || avg == null) return "#333";
  if (latest > avg * 1.05) return RED;
  if (latest < avg * 0.95) return BLUE;
  return "#333";
}

function StructuralBlock({ rows }: { rows: StructuralCountry[] }) {
  return (
    <div>
      <div className="mb-1.5 text-xs font-bold text-[#244d1a]">구조지표 — 통화량에 ‘분모’를 붙여 비교 (World Bank, 연)</div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[12px]">
          <thead>
            <tr className="bg-[#f0f0f0] text-[11px] text-[#444]">
              <th className="border border-[#e6e6e6] px-2 py-1.5 text-left font-semibold">국가</th>
              <th className="border border-[#e6e6e6] px-2 py-1.5 text-center font-semibold">마샬케이 M2/GDP<div className="font-normal text-[#999]">경제규모 대비 통화량</div></th>
              <th className="border border-[#e6e6e6] px-2 py-1.5 text-center font-semibold">유통속도 GDP/M2<div className="font-normal text-[#999]">돈이 도는 속도</div></th>
              <th className="border border-[#e6e6e6] px-2 py-1.5 text-center font-semibold">실질 통화량<div className="font-normal text-[#999]">명목−물가</div></th>
              <th className="border border-[#e6e6e6] px-2 py-1.5 text-center font-semibold">민간신용/GDP<div className="font-normal text-[#999]">레버리지</div></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.iso} className={c.iso === "KOR" ? "bg-[#f1f8f3]" : "hover:bg-[#fafafa]"}>
                <td className="border border-[#e6e6e6] px-2 py-1.5 font-bold text-[#1f1f1f]">{c.name}</td>
                <td className="border border-[#e6e6e6] px-2 py-1.5 text-center">
                  <div className="flex items-center justify-center gap-2">
                    <div className="text-right">
                      <div className="font-bold tabular-nums" style={{ color: vsAvgColor(c.marshall_k.latest, c.marshall_k.avg) }}>{c.marshall_k.latest}%</div>
                      <div className="text-[10px] text-[#999]">평균 {c.marshall_k.avg}% · {c.marshall_k.trend}</div>
                    </div>
                    <Sparkline pts={c.marshall_k.series.map((p) => p.v)} color={vsAvgColor(c.marshall_k.latest, c.marshall_k.avg)} />
                  </div>
                </td>
                <td className="border border-[#e6e6e6] px-2 py-1.5 text-center tabular-nums">
                  <div className="font-bold text-[#333]">{c.velocity.latest}</div>
                  <div className="text-[10px] text-[#999]">{c.velocity.trend}</div>
                </td>
                <td className="border border-[#e6e6e6] px-2 py-1.5 text-center tabular-nums">
                  <span className="font-bold" style={{ color: growthColor(c.real_m2.latest) }}>{gpct(c.real_m2.latest)}</span>
                  <div className="text-[10px] text-[#999]">{c.real_m2.latest_year}</div>
                </td>
                <td className="border border-[#e6e6e6] px-2 py-1.5 text-center tabular-nums">
                  <span className="font-bold text-[#333]">{c.credit_gdp.latest}%</span>
                  <div className="text-[10px] text-[#999]">평균 {c.credit_gdp.avg}%</div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-1 text-[10px] leading-tight text-[#aaa]">
        마샬케이가 장기평균보다 높고 ‘상승’이면 경제규모 대비 돈이 과하게 풀린 상태(빨강). 유통속도가 낮아지면 푼 돈이 실물보다 자산에 고인다는 뜻. 실질 통화량이 −면 물가가 명목 증가를 갉아먹는 중.
      </p>
    </div>
  );
}

function AssetLinkCard({ a }: { a: AssetLinkItem }) {
  const color = a.outpaced === "asset" ? RED : BLUE;
  return (
    <div className="rounded-lg border border-[#e0e0e0] bg-white p-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-bold text-[#222]">{a.label}</span>
        <span className="text-[10px] text-[#aaa]">{a.from}~{a.to}</span>
      </div>
      <div className="mt-1 flex items-center justify-between">
        <DualSpark a={a.m2_series.map((p) => p.v)} b={a.series.map((p) => p.v)} colorA="#999" colorB={color} />
        {a.corr != null && (
          <div className="text-right">
            <div className="text-[10px] text-[#999]">M2 상관</div>
            <div className="text-base font-bold tabular-nums" style={{ color: a.corr > 0.3 ? RED : a.corr < -0.3 ? BLUE : "#666" }}>
              {a.corr > 0 ? "+" : ""}{a.corr}
            </div>
          </div>
        )}
      </div>
      <div className="mt-1.5 flex items-center justify-between text-[11px]">
        <span className="text-[#666]">자산 <span className="font-bold" style={{ color: RED }}>{gpct(a.asset_total_ret)}</span></span>
        <span className="text-[#666]">M2 <span className="font-bold text-[#888]">{gpct(a.m2_total_ret)}</span></span>
      </div>
      <p className="mt-1 text-[10px] leading-tight text-[#999]">
        {a.outpaced === "asset" ? "통화 증가폭보다 더 올라 ‘돈의 행선지’ 신호" : "통화 증가폭에 못 미침"}
      </p>
    </div>
  );
}

function RegimeBlock({ r }: { r: Regime }) {
  const rateCard = (label: string, x: RealRate | null) => {
    if (!x) return null;
    const stance = x.real > 0.5 ? "긴축" : x.real < -0.5 ? "완화" : "중립";
    const col = x.real > 0.5 ? BLUE : x.real < -0.5 ? RED : "#666"; // 완화(돈풀기)=빨강
    return (
      <div className="rounded border border-[#e6e6e6] bg-white p-2.5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-[#333]">{label} 실질금리</span>
          <span className="rounded px-1.5 py-0.5 text-[10px] font-bold text-white" style={{ background: col }}>{stance}</span>
        </div>
        <div className="mt-1 text-lg font-bold tabular-nums" style={{ color: col }}>{x.real > 0 ? "+" : ""}{x.real}%p</div>
        <div className="text-[10px] text-[#999]">정책 {x.policy}% − 물가 {x.inflation ?? "—"}% <span className="text-[#bbb]">({x.period})</span></div>
      </div>
    );
  };
  return (
    <div>
      <div className="mb-1.5 text-xs font-bold text-[#244d1a]">레짐 — 실질금리(돈줄 방향)와 경기침체(NBER)</div>
      <div className="grid gap-2 sm:grid-cols-2">
        {rateCard("한국", r.kr)}
        {rateCard("미국", r.us)}
      </div>
      {r.recessions.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] text-[#888]">미국 침체기:</span>
          {r.recessions.map((s, i) => (
            <span key={i} className="rounded bg-[#eef0ef] px-1.5 py-0.5 text-[10px] tabular-nums text-[#555]">{s.start}~{s.end}</span>
          ))}
          <span className="ml-1 rounded px-1.5 py-0.5 text-[10px] font-bold text-white" style={{ background: r.us_recession_now ? RED : "#3a9d5d" }}>
            현재 {r.us_recession_now ? "침체" : "확장"}
          </span>
        </div>
      )}
      {r.narrative && <p className="mt-1.5 text-[11px] leading-snug text-[#666]">{r.narrative}</p>}
    </div>
  );
}

// 실물경제 — 국가별 색 (세계=검정, 한국=빨강 강조)
const ENT_COLOR: Record<string, string> = {
  WLD: "#111111", KOR: "#c92a2a", USA: "#1971c2", CHN: "#e8590c", JPN: "#7048e8", DEU: "#2b8a3e", IND: "#c2255c",
};

function mergeWorld(ind: WorldIndicator): Record<string, number>[] {
  const years = Array.from(new Set(ind.entities.flatMap((e) => e.series.map((p) => p.year)))).sort((a, b) => a - b);
  return years.map((y) => {
    const row: Record<string, number> = { year: y };
    ind.entities.forEach((e) => {
      const p = e.series.find((s) => s.year === y);
      if (p) row[e.iso] = p.v;
    });
    return row;
  });
}

function WorldTip({ active, payload, label, unit }: { active?: boolean; payload?: { dataKey: string; name: string; value: number; color: string }[]; label?: number; unit: string }) {
  if (!active || !payload || !payload.length) return null;
  const rows = payload.filter((p) => p.value != null).sort((a, b) => b.value - a.value);
  return (
    <div className="rounded border border-[#d0d0d0] bg-white px-2 py-1 text-[11px] shadow-sm">
      <div className="mb-0.5 font-bold text-[#666]">{label}년</div>
      {rows.map((p) => (
        <div key={p.dataKey} className="flex justify-between gap-3 tabular-nums">
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="font-bold text-[#222]">{p.value}{unit}</span>
        </div>
      ))}
    </div>
  );
}

function WorldLines({ ind, big }: { ind: WorldIndicator; big?: boolean }) {
  const zeroLine = ind.kind === "rate" || ind.kind === "ratio";
  return (
    <LineChart data={mergeWorld(ind)} margin={{ top: 6, right: big ? 16 : 6, bottom: 2, left: big ? 8 : 0 }}>
      <CartesianGrid stroke={big ? "#eee" : "#f3f3f3"} vertical={false} />
      <XAxis dataKey="year" tick={{ fill: big ? "#888" : "#bbb", fontSize: big ? 11 : 9 }} minTickGap={big ? 50 : 36} interval="preserveStartEnd" tickLine={false} />
      {big ? <YAxis orientation="right" width={46} tick={{ fill: "#888", fontSize: 11 }} domain={["auto", "auto"]} tickFormatter={(v) => `${v}${ind.unit}`} /> : <YAxis hide domain={["auto", "auto"]} />}
      {zeroLine && <ReferenceLine y={0} stroke="#c8c8c8" />}
      <Tooltip content={<WorldTip unit={ind.unit} />} />
      {big && <Legend wrapperStyle={{ fontSize: 11 }} />}
      {ind.entities.map((e) => (
        <Line key={e.iso} dataKey={e.iso} name={e.name} stroke={ENT_COLOR[e.iso] ?? "#888"} dot={false}
          strokeWidth={e.iso === "WLD" ? 2.2 : big ? 1.6 : 1.3} strokeDasharray={e.iso === "WLD" ? "5 3" : undefined}
          connectNulls isAnimationActive={false} />
      ))}
    </LineChart>
  );
}

function WorldIndicatorCard({ ind, onOpen }: { ind: WorldIndicator; onOpen: () => void }) {
  return (
    <div className="cursor-pointer rounded-lg border border-[#e0e0e0] bg-white p-3 transition hover:bg-[#f7faf8]" onClick={onOpen} title="클릭하면 크게 보기">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-bold text-[#222]">{ind.label}</span>
        {ind.world_latest != null && (
          <span className="text-[11px] text-[#888]">세계 <span className="font-bold text-[#111]">{ind.world_latest}{ind.unit}</span> <span className="text-[#bbb]">’{String(ind.world_year).slice(2)}</span></span>
        )}
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
        {ind.entities.filter((e) => e.iso !== "WLD").map((e) => (
          <span key={e.iso} className="text-[11px] tabular-nums" style={{ color: ENT_COLOR[e.iso] ?? "#666" }}>
            <span className="font-semibold">{e.name}</span> {e.latest}{ind.unit}
          </span>
        ))}
      </div>
      <div className="mt-1.5 h-36 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <WorldLines ind={ind} />
        </ResponsiveContainer>
      </div>
      <p className="mt-1 text-[10px] leading-tight text-[#999]">{ind.desc}</p>
    </div>
  );
}

function WorldIndicatorModal({ ind, onClose }: { ind: WorldIndicator; onClose: () => void }) {
  return (
    <Modal title={ind.label} sub={`World Bank · 단위 ${ind.unit} · 한·미·중·일·독·인도${ind.world_latest != null ? " + 세계집계" : ""}`} onClose={onClose}>
      <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
        {ind.entities.map((e) => (
          <Stat key={e.iso} label={`${e.name} (${e.latest_year})`} value={`${e.latest}${ind.unit}`} color={ENT_COLOR[e.iso]} />
        ))}
      </div>
      <div className="h-[420px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <WorldLines ind={ind} big />
        </ResponsiveContainer>
      </div>
      <p className="mt-3 text-xs leading-snug text-[#666]">{ind.desc}</p>
    </Modal>
  );
}

function RealEconomySection() {
  const [d, setD] = useState<RealEconomy | null>(null);
  const [loading, setLoading] = useState(true);
  const [selK, setSelK] = useState<EcosIndicator | null>(null);
  const [selW, setSelW] = useState<WorldIndicator | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .realEconomy()
      .then((r) => alive && setD(r))
      .catch(() => alive && setD(null))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <section className="overflow-hidden rounded-lg border border-[#e0e0e0]">
      {selK && <EcosChartModal ind={selK} onClose={() => setSelK(null)} />}
      {selW && <WorldIndicatorModal ind={selW} onClose={() => setSelW(null)} />}
      <div className="flex flex-wrap items-center gap-2 border-b border-[#e0e0e0] bg-[#0f3d2e] px-3 py-1.5">
        <span className="text-sm font-bold text-white">실물경제 — 한국 & 세계</span>
        <span className="text-[11px] text-white/70">소비·투자·수출·고용·물가 (돈이 실제로 만들어내는 것)</span>
      </div>
      {loading ? (
        <div className="py-8 text-center text-sm text-[#888]">실물경제 지표 집계 중… <span className="text-[#bbb]">(World Bank·ECOS 취합)</span></div>
      ) : !d || !d.available ? (
        <div className="px-4 py-6 text-center text-sm text-[#999]">{d?.reason ?? "실물경제 데이터를 불러오지 못했습니다."}</div>
      ) : (
        <div className="space-y-4 p-3">
          {/* 한국 — ECOS 국민계정·고용 (EcosCard 재사용) */}
          {d.korea.length > 0 && (
            <div>
              <div className="mb-1.5 text-xs font-bold text-[#244d1a]">한국 — 국민계정·고용 (한국은행 ECOS, 실질·계절조정·분기) <span className="font-normal text-[#999]">· 카드 클릭하면 크게</span></div>
              <div className="grid gap-px bg-[#eee] md:grid-cols-2 xl:grid-cols-3">
                {d.korea.map((i) => (
                  <EcosCard key={i.key} ind={i} onOpen={() => setSelK(i)} />
                ))}
              </div>
            </div>
          )}

          {/* 세계 — World Bank 다국 비교 */}
          {d.world.length > 0 && (
            <div>
              <div className="mb-1.5 text-xs font-bold text-[#244d1a]">세계 비교 — 한·미·중·일·독·인도 + 세계집계 (World Bank, 연) <span className="font-normal text-[#999]">· 카드 클릭하면 크게</span></div>
              <div className="grid gap-3 md:grid-cols-2">
                {d.world.map((w) => (
                  <WorldIndicatorCard key={w.key} ind={w} onOpen={() => setSelW(w)} />
                ))}
              </div>
            </div>
          )}

          <p className="text-[10px] leading-tight text-[#aaa]">{d.note}</p>
          <p className="text-[10px] text-[#bbb]">출처: {d.source}</p>
        </div>
      )}
    </section>
  );
}

function RentSection() {
  const [d, setD] = useState<RealEstateRent | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api
      .realestateRent()
      .then((r) => alive && setD(r))
      .catch(() => alive && setD(null))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  const maxCnt = d?.available ? Math.max(...d.monthly.map((m) => m.count || 0), 1) : 1;

  return (
    <section className="overflow-hidden rounded-lg border border-[#e0e0e0]">
      <div className="flex flex-wrap items-center gap-2 border-b border-[#e0e0e0] bg-[#217346] px-3 py-1.5">
        <span className="text-sm font-bold text-white">부동산 전월세 실거래 — 전국 아파트</span>
        {d?.source && <span className="text-[11px] text-white/70">{d.source}</span>}
      </div>
      {loading ? (
        <div className="py-8 text-center text-sm text-[#888]">전월세 실거래 집계 중…</div>
      ) : !d || !d.available ? (
        <div className="px-4 py-6 text-center text-sm text-[#999]">{d?.reason ?? "전월세 실거래 데이터를 불러오지 못했습니다."}</div>
      ) : (
        <div className="p-3">
          {/* 헤드라인 */}
          <div className="mb-3 flex flex-wrap items-end gap-x-6 gap-y-1">
            <div>
              <div className="text-[11px] text-[#888]">최신 완성월 ({d.latest_label}) 전월세 거래</div>
              <div className="text-lg font-bold tabular-nums text-[#1f1f1f]">{d.latest_count?.toLocaleString("ko-KR")}건</div>
            </div>
            <div>
              <div className="text-[11px] text-[#888]">월세 비중</div>
              <div className="text-base font-bold tabular-nums text-[#b8860b]">{d.latest_wolse_ratio ?? "—"}%</div>
            </div>
            <div>
              <div className="text-[11px] text-[#888]">평균 전세보증금</div>
              <div className="text-base font-bold tabular-nums text-[#217346]">{d.latest_avg_jeonse_eok != null ? `${d.latest_avg_jeonse_eok}억` : "—"}</div>
            </div>
            {d.mom_count_pct != null && (
              <div>
                <div className="text-[11px] text-[#888]">전월 대비 거래량</div>
                <div className="text-base font-bold tabular-nums" style={retStyle(d.mom_count_pct)}>{d.mom_count_pct > 0 ? "+" : ""}{d.mom_count_pct}%</div>
              </div>
            )}
            <span className="ml-auto text-[11px] text-[#aaa]">전세=초록 · 월세=주황 · 당월(잠정) 미완성</span>
          </div>

          {/* 월별 전세/월세 적층 막대 */}
          <div className="mb-4 space-y-1">
            {d.monthly.map((m) => {
              const tot = m.count || 1;
              const jw = ((m.jeonse || 0) / tot) * 100;
              const ww = ((m.wolse || 0) / tot) * 100;
              const scale = ((m.count || 0) / maxCnt) * 100;
              return (
                <div key={m.ym} className="flex items-center gap-2 text-xs">
                  <span className="w-16 shrink-0 tabular-nums text-[#666]">{m.label}{m.provisional ? "*" : ""}</span>
                  <div className="relative h-4 flex-1 rounded bg-[#f3f3f3]">
                    <div className="absolute left-0 top-0 flex h-4 overflow-hidden rounded" style={{ width: `${scale}%` }}>
                      <div className="h-4 bg-[#3a9d5d]" style={{ width: `${jw}%` }} />
                      <div className="h-4 bg-[#e0a93b]" style={{ width: `${ww}%` }} />
                    </div>
                  </div>
                  <span className="w-40 shrink-0 text-right tabular-nums text-[#333]">
                    {m.count.toLocaleString("ko-KR")}건 <span className="text-[#aaa]">월세{m.wolse_ratio ?? "—"}%·전세{m.avg_jeonse_eok ?? "—"}억</span>
                  </span>
                </div>
              );
            })}
            <p className="pt-0.5 text-[10px] text-[#aaa]">* 잠정(신고 진행중) · 월세 비중↑ = 전세의 월세화</p>
          </div>

          {/* 시도별 — 완성 최신월 */}
          <div>
            <div className="mb-1 text-xs font-bold text-[#244d1a]">시도별 전월세 (기준 {d.region_ym?.slice(0, 4)}.{d.region_ym?.slice(4)})</div>
            <div className="grid grid-cols-1 gap-x-4 gap-y-0.5 sm:grid-cols-2">
              {d.by_sido.slice(0, 12).map((s) => (
                <div key={s.sido} className="flex items-center justify-between border-b border-[#f0f0f0] py-0.5 text-xs">
                  <span className="text-[#444]">{s.sido}</span>
                  <span className="tabular-nums text-[#333]">{s.count.toLocaleString("ko-KR")}건 <span className="text-[#b8860b]">월세{s.wolse_ratio ?? "—"}%</span> <span className="text-[#217346]">전세{s.avg_jeonse_eok ?? "—"}억</span></span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

// 억 → 보기 좋은 단위 (1조=10,000억)
function eok(v: number | null | undefined): string {
  if (v == null) return "—";
  if (Math.abs(v) >= 10000) return `${(v / 10000).toLocaleString("ko-KR", { maximumFractionDigits: 2 })}조`;
  return `${Math.round(v).toLocaleString("ko-KR")}억`;
}

function RealEstateSection() {
  const [d, setD] = useState<RealEstateTrades | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api
      .realestateTrades()
      .then((r) => alive && setD(r))
      .catch(() => alive && setD(null))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  const maxAmt = d?.available ? Math.max(...d.monthly.map((m) => m.amount_eok || 0), 1) : 1;

  return (
    <section className="overflow-hidden rounded-lg border border-[#e0e0e0]">
      <div className="flex flex-wrap items-center gap-2 border-b border-[#e0e0e0] bg-[#217346] px-3 py-1.5">
        <span className="text-sm font-bold text-white">부동산 실거래 거래액·거래량 — 전국 아파트 매매</span>
        {d?.source && <span className="text-[11px] text-white/70">{d.source}</span>}
      </div>

      {loading ? (
        <div className="py-8 text-center text-sm text-[#888]">실거래 집계 중… <span className="text-[#bbb]">(최초 수십 초)</span></div>
      ) : !d || !d.available ? (
        <div className="px-4 py-6 text-center text-sm text-[#999]">
          {d?.reason ?? "부동산 실거래 데이터를 불러오지 못했습니다."}
        </div>
      ) : (
        <div className="p-3">
          {/* 헤드라인 */}
          <div className="mb-3 flex flex-wrap items-end gap-x-6 gap-y-1">
            <div>
              <div className="text-[11px] text-[#888]">최신 완성월 ({d.latest_label})</div>
              <div className="text-lg font-bold text-[#1f1f1f]">
                {d.latest_count?.toLocaleString("ko-KR")}건 <span className="text-[#217346]">· {eok(d.latest_amount_eok)}</span>
              </div>
            </div>
            {d.mom_count_pct != null && (
              <div>
                <div className="text-[11px] text-[#888]">전월 대비 거래량</div>
                <div className="text-base font-bold tabular-nums" style={retStyle(d.mom_count_pct)}>
                  {d.mom_count_pct > 0 ? "+" : ""}{d.mom_count_pct}%
                </div>
              </div>
            )}
            <span className="ml-auto text-[11px] text-[#aaa]">{d.scope} · 당월(잠정)은 신고기한 30일 탓에 미완성</span>
          </div>

          {/* 월별 거래대금 막대 */}
          <div className="mb-4 space-y-1">
            {d.monthly.map((m) => (
              <div key={m.ym} className="flex items-center gap-2 text-xs">
                <span className="w-16 shrink-0 tabular-nums text-[#666]">{m.label}{m.provisional ? "*" : ""}</span>
                <div className="relative h-4 flex-1 rounded bg-[#f0f0f0]">
                  <div
                    className="absolute left-0 top-0 h-4 rounded"
                    style={{ width: `${((m.amount_eok || 0) / maxAmt) * 100}%`, background: m.provisional ? "#bcd6c2" : "#3a9d5d" }}
                  />
                </div>
                <span className="w-28 shrink-0 text-right tabular-nums text-[#333]">{eok(m.amount_eok)} · {m.count.toLocaleString("ko-KR")}건</span>
              </div>
            ))}
            <p className="pt-0.5 text-[10px] text-[#aaa]">* 잠정(신고 진행중)</p>
          </div>

          {/* 시도별 거래대금 막대 — 완성 최신월 */}
          {(() => {
            const maxSido = Math.max(...d.by_sido.map((s) => s.amount_eok || 0), 1);
            return (
              <div className="mb-4">
                <div className="mb-1.5 text-xs font-bold text-[#244d1a]">
                  시도별 거래대금 (기준 {d.region_ym?.slice(0, 4)}.{d.region_ym?.slice(4)})
                </div>
                <div className="grid gap-x-6 gap-y-1 md:grid-cols-2">
                  {d.by_sido.map((s) => (
                    <div key={s.sido} className="flex items-center gap-2 text-xs">
                      <span className="w-24 shrink-0 truncate text-[#444]">{s.sido}</span>
                      <div className="relative h-3.5 flex-1 rounded bg-[#f0f0f0]">
                        <div className="absolute left-0 top-0 h-3.5 rounded bg-[#3a9d5d]" style={{ width: `${((s.amount_eok || 0) / maxSido) * 100}%` }} />
                      </div>
                      <span className="w-24 shrink-0 text-right tabular-nums text-[#333]">{eok(s.amount_eok)} <span className="text-[#aaa]">{s.count.toLocaleString("ko-KR")}건</span></span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}

          {/* 상위 시군구 — 완성 최신월 */}
          <div>
            <div className="mb-1 text-xs font-bold text-[#244d1a]">거래대금 상위 시군구</div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 sm:grid-cols-3">
              {d.top_sigungu.map((r) => (
                <div key={`${r.sido}-${r.region}`} className="flex items-center justify-between border-b border-[#f0f0f0] py-0.5 text-xs">
                  <span className="truncate text-[#444]" title={`${r.sido} ${r.region}`}>{r.region}</span>
                  <span className="shrink-0 tabular-nums text-[#333]">{eok(r.amount_eok)} <span className="text-[#aaa]">{r.count}건</span></span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function Badge({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded border border-[#e0e0e0] bg-[#f7f7f7] px-2.5 py-1 text-xs">
      <span className="text-[#888]">{label}</span>
      <span className="font-bold" style={{ color }}>{value}</span>
    </span>
  );
}

function FlowTable({ title, subtitle, items }: { title: string; subtitle: string; items: KoreaFlowItem[] }) {
  return (
    <section className="overflow-hidden rounded-lg border border-[#e0e0e0]">
      <div className="border-b border-[#e0e0e0] bg-[#a9d08e] px-3 py-1.5">
        <span className="text-sm font-bold text-[#244d1a]">{title}</span>
        <p className="text-[11px] text-[#2d5016]/80">{subtitle}</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="bg-[#f0f0f0] text-xs text-[#444]">
              <th className="border border-[#e6e6e6] px-2 py-1.5 text-left font-semibold">종목</th>
              <th className="border border-[#e6e6e6] px-2 py-1.5 text-center font-semibold">코드</th>
              <th className="border border-[#e6e6e6] px-2 py-1.5 text-right font-semibold">현재가</th>
              <th className="border border-[#e6e6e6] px-2 py-1.5 text-center font-semibold">당일</th>
              <th className="border border-[#e6e6e6] px-2 py-1.5 text-center font-semibold">1주</th>
              <th className="border border-[#e6e6e6] px-2 py-1.5 text-center font-semibold">1개월</th>
              <th className="border border-[#e6e6e6] px-2 py-1.5 text-center font-semibold">3개월</th>
              <th className="border border-[#e6e6e6] px-2 py-1.5 text-center font-semibold">52주高 대비</th>
            </tr>
          </thead>
          <tbody>
            {items.map((m) => (
              <tr key={m.key} className="hover:bg-[#fff7e6]">
                <td className="border border-[#e6e6e6] px-2 py-1.5 font-medium text-[#1f1f1f]">{m.label}</td>
                <td className="border border-[#e6e6e6] px-2 py-1.5 text-center font-mono text-xs text-[#777]">{m.code}</td>
                <td className="border border-[#e6e6e6] px-2 py-1.5 text-right tabular-nums">{m.close?.toLocaleString("ko-KR") ?? "—"}</td>
                <td className="border border-[#e6e6e6] px-2 py-1.5 text-center tabular-nums" style={retStyle(m.change_pct)}>{pctTxt(m.change_pct)}</td>
                <td className="border border-[#e6e6e6] px-2 py-1.5 text-center tabular-nums" style={retStyle(m.ret_1w)}>{pctTxt(m.ret_1w)}</td>
                <td className="border border-[#e6e6e6] px-2 py-1.5 text-center tabular-nums" style={retStyle(m.ret_1m)}>{pctTxt(m.ret_1m)}</td>
                <td className="border border-[#e6e6e6] px-2 py-1.5 text-center tabular-nums" style={retStyle(m.ret_3m)}>{pctTxt(m.ret_3m)}</td>
                <td className="border border-[#e6e6e6] px-2 py-1.5 text-center tabular-nums text-[#777]">{pctTxt(m.pct_from_high)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function NewsCard({ c }: { c: KoreaFlowNews }) {
  return (
    <div className="rounded-lg border border-[#e0e0e0] bg-white p-3">
      <div className="mb-2 flex items-center gap-2">
        <span className="text-base">{c.icon}</span>
        <span className="text-sm font-bold text-[#333]">{c.label}</span>
        <span className="ml-auto text-xs font-bold" style={{ color: leanColor(c.lean) }}>
          {c.lean} <span className="font-normal text-[#aaa]">({c.count}건)</span>
        </span>
      </div>
      {c.digest.length > 0 && (
        <ul className="mb-2 space-y-0.5">
          {c.digest.map((t, i) => (
            <li key={i} className="truncate text-[11px] text-[#666]">· {t}</li>
          ))}
        </ul>
      )}
      <ul className="space-y-1">
        {c.headlines.slice(0, 4).map((h, i) => (
          <li key={i} className="truncate text-xs">
            <a href={h.link} target="_blank" rel="noopener noreferrer" className="text-[#1155cc] hover:underline">
              {h.title}
            </a>
            <span className="ml-1 text-[10px] text-[#aaa]">{h.source}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
