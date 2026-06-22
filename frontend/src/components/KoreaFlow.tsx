"use client";

import { useEffect, useRef, useState } from "react";
import { api, KoreaFlow as KF, KoreaFlowItem, KoreaFlowNews, RealEstateTrades, RealEstateRent, EcosIndicator, EcosMacro } from "@/lib/api";

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

      {/* 국내 거시지표 — 한국은행 ECOS (M2·가계신용·주택가격) */}
      <EcosMacroSection />

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
      <div className="flex flex-wrap items-center gap-2 border-b border-[#e0e0e0] bg-[#1b5e3a] px-3 py-1.5">
        <span className="text-sm font-bold text-white">국내 돈 흐름 — 거시지표 (한국은행 ECOS)</span>
        <span className="text-[11px] text-white/70">M2 통화량 · 가계 빚 · 집값</span>
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
              <div className="grid gap-px bg-[#eee] sm:grid-cols-2 lg:grid-cols-4">
                {d.indicators.filter((i) => i.group === g).map((i) => (
                  <EcosCard key={i.key} ind={i} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function EcosCard({ ind }: { ind: EcosIndicator }) {
  const up = (ind.yoy ?? 0) > 0;
  return (
    <div className="bg-white p-3">
      <div className="text-xs font-semibold text-[#555]">{ind.label}</div>
      <div className="mt-1 flex items-end justify-between gap-2">
        <div>
          <div className="text-lg font-bold tabular-nums text-[#1f1f1f]">{ind.display}</div>
          <div className="text-[10px] text-[#aaa]">{ind.period} 기준</div>
        </div>
        <Sparkline pts={ind.series.map((p) => p.v)} color={up ? "#c92a2a" : "#1971c2"} />
      </div>
      <div className="mt-1.5 flex items-center gap-2 text-xs">
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
