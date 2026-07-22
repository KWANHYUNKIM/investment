"use client";

import { useEffect, useMemo, useState } from "react";
import {
  api,
  CCMCompany,
  CompanyCostModel as CCM,
  CCMMaterial,
  CCMProduct,
  CCMFinYear,
  AnalystReports,
  CompanyProducts,
  UnitEconomics as UE,
} from "@/lib/api";

const GREEN = "#217346";

function won(v: number): string {
  return `${Math.round(v).toLocaleString("ko-KR")}원`;
}
function pct(v: number, digits = 1): string {
  return `${(v * 100).toFixed(digits)}%`;
}

// F/U 칩 (유리 F=파랑, 불리 U=빨강)
function FUChip({ fu }: { fu: "U" | "F" | "—" }) {
  if (fu === "—") return <span className="text-[11px] text-gray-400">—</span>;
  const f = fu === "F";
  return (
    <span
      className="ml-1 rounded px-1 text-[10px] font-bold"
      style={{ color: f ? "#1971c2" : "#c92a2a", background: f ? "#e7f1fb" : "#fbe9e9" }}
    >
      {fu} {f ? "유리" : "불리"}
    </span>
  );
}

// 원자재 방향 칩(원가 관점: up=악재 빨강, down=호재 파랑)
function DirChip({ dir, chg }: { dir?: string | null; chg?: number | null }) {
  if (!dir || chg == null) return null;
  const up = dir === "up";
  const flat = dir === "flat";
  const color = flat ? "#868e96" : up ? "#c92a2a" : "#1971c2";
  const arrow = flat ? "→" : up ? "▲" : "▼";
  return (
    <span style={{ color }} className="whitespace-nowrap text-[11px] font-semibold">
      {arrow} {chg > 0 ? "+" : ""}
      {(chg * 100).toFixed(0)}% {up ? "악재" : flat ? "중립" : "호재"}
    </span>
  );
}

export function CompanyCostModel() {
  const [companies, setCompanies] = useState<CCMCompany[]>([]);
  const [sectors, setSectors] = useState<string[]>([]);
  const [sectorFilter, setSectorFilter] = useState("전체");
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<string>("");           // 선택 회사 ticker
  const [data, setData] = useState<CCM | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [showFin, setShowFin] = useState(false);

  useEffect(() => {
    let alive = true;
    api.companyCostModelList()
      .then((r) => {
        if (!alive) return;
        setCompanies(r.companies);
        setSectors(r.sectors);
      })
      .catch((e) => alive && setErr(e?.message ?? "회사 목록 실패"));
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    if (!sel) { setData(null); return; }
    let alive = true;
    setLoading(true);
    setErr("");
    setShowFin(false);
    api.companyCostModel(sel)
      .then((r) => alive && setData(r))
      .catch((e) => alive && setErr(e?.message ?? "회사 분석 실패"))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [sel]);

  const filtered = useMemo(() => {
    const kw = q.trim();
    return companies.filter(
      (c) =>
        (sectorFilter === "전체" || c.sector === sectorFilter) &&
        (!kw || c.company.includes(kw) || c.ticker.includes(kw)),
    );
  }, [companies, sectorFilter, q]);

  // ===== 레벨 2·3: 회사 상세 =====
  if (sel && data) {
    return <CompanyDetail data={data} loading={loading} onBack={() => setSel("")} showFin={showFin} setShowFin={setShowFin} />;
  }

  // ===== 레벨 1: 회사 목록 =====
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-bold" style={{ color: GREEN }}>원가분석 — 회사별</h2>
        <p className="text-sm text-gray-500">
          회사를 고르면 그 회사가 파는 품목 전체의 원가·영업이익과 원재료 시세, 마진 정합성을 봅니다.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <select
          value={sectorFilter}
          onChange={(e) => setSectorFilter(e.target.value)}
          className="rounded border border-gray-300 px-2 py-1 text-sm"
        >
          <option value="전체">업종 전체</option>
          {sectors.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="회사명·종목코드 검색"
          className="rounded border border-gray-300 px-2 py-1 text-sm"
        />
        <span className="text-xs text-gray-400">{filtered.length}개 회사</span>
      </div>

      {err && <div className="text-sm text-red-600">{err}</div>}

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((c) => (
          <button
            key={c.ticker}
            onClick={() => setSel(c.ticker)}
            className="flex items-center justify-between rounded border border-gray-200 bg-white px-3 py-2 text-left hover:border-gray-400 hover:bg-gray-50"
          >
            <div>
              <div className="font-semibold text-gray-800">{c.company}</div>
              <div className="text-[11px] text-gray-400">{c.sector} · {c.n_products}개 품목</div>
            </div>
            <div className="text-right text-[11px] text-gray-500">
              <div>원가율 {pct(c.cogs_ratio, 0)}</div>
              <div style={{ color: c.op_margin >= 0 ? GREEN : "#c92a2a" }}>영익 {pct(c.op_margin)}</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

// ===== 회사 상세 =====
function CompanyDetail({
  data, loading, onBack, showFin, setShowFin,
}: {
  data: CCM; loading: boolean; onBack: () => void;
  showFin: boolean; setShowFin: (v: boolean) => void;
}) {
  const [openProduct, setOpenProduct] = useState<string>("");
  const s = data.summary;
  const r = data.reconciliation;
  const isEst = data.basis.source !== "DART 실측";

  const reconColor = r.status === "ok" ? GREEN : r.status === "warn" ? "#e8a33d" : r.status === "loss" ? "#7048e8" : "#c92a2a";
  const reconLabel = r.status === "ok" ? "정합" : r.status === "warn" ? "주의" : r.status === "loss" ? "적자기업" : "불일치";

  return (
    <div className="space-y-4">
      <button onClick={onBack} className="text-sm text-gray-500 hover:text-gray-800">← 회사 목록</button>

      {/* 헤더 */}
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b pb-2">
        <h2 className="text-xl font-bold" style={{ color: GREEN }}>{data.company}</h2>
        <span className="text-xs text-gray-400">{data.ticker} · {data.sector}</span>
        <span className="text-sm text-gray-600">
          {s.revenue_eok ? `매출 ${s.revenue_eok.toLocaleString("ko-KR")}억 · ` : ""}
          영업이익률 {pct(s.op_margin)}
        </span>
        <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-500">
          {data.basis.source}{data.basis.year ? ` · FY${data.basis.year}` : ""}
        </span>
      </div>

      {/* 3개년 추세 (Phase A) */}
      {data.financials_3y && data.financials_3y.length >= 2 && (
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[12px] text-gray-600">
          <span className="font-semibold text-gray-500">3개년(DART):</span>
          <span>
            원가율{" "}
            {[...data.financials_3y].reverse().map((f, i, arr) => (
              <span key={f.year}>
                <b>{pct(f.cogs_ratio, 0)}</b>{i < arr.length - 1 ? " → " : ""}
              </span>
            ))}
          </span>
          <span>
            영익률{" "}
            {[...data.financials_3y].reverse().map((f, i, arr) => (
              <span key={f.year} style={{ color: (f.op_margin ?? 0) >= 0 ? GREEN : "#c92a2a" }}>
                <b>{f.op_margin != null ? pct(f.op_margin) : "—"}</b>{i < arr.length - 1 ? " → " : ""}
              </span>
            ))}
          </span>
          <span className="text-gray-400">
            (FY{data.financials_3y[data.financials_3y.length - 1].year}→{data.financials_3y[0].year})
          </span>
        </div>
      )}

      {loading && <div className="text-sm text-gray-400">불러오는 중…</div>}

      {/* ① 품목별 원가·영익 */}
      <section>
        <h3 className="mb-1 text-sm font-bold text-gray-700">① 품목별 원가·영업이익 (이 회사가 파는 물건 전체)</h3>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="border-b text-left text-[11px] text-gray-400">
                <th className="py-1 pr-2">품목</th>
                <th className="py-1 pr-2 text-right">소비자가</th>
                <th className="py-1 pr-2 text-right">매출원가율</th>
                <th className="py-1 pr-2">원재료 TOP</th>
                <th className="py-1 pr-2 text-right">영업이익</th>
                <th className="py-1 text-right">영익률</th>
              </tr>
            </thead>
            <tbody>
              {data.products.map((p) => (
                <ProductRow
                  key={p.id}
                  p={p}
                  open={openProduct === p.id}
                  onToggle={() => setOpenProduct(openProduct === p.id ? "" : p.id)}
                />
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-1 text-[11px] text-gray-400">
          품목을 클릭하면 소비자가→유통→원재료→가공→판관→영업이익 6단계로 펼쳐집니다.
        </p>
        <DartProductMix ticker={data.ticker} />
      </section>

      {/* ② 원재료 시세 */}
      <section>
        <h3 className="mb-1 text-sm font-bold text-gray-700">② 원가율 + 원재료 시장 시세 (회사 전체 원재료 묶음)</h3>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-sm">
            <thead>
              <tr className="border-b text-left text-[11px] text-gray-400">
                <th className="py-1 pr-2">원재료</th>
                <th className="py-1 pr-2 text-right">매출원가내 비중</th>
                <th className="py-1 pr-2">현재 시세</th>
                <th className="py-1 text-right">1년 등락 · 원가영향</th>
              </tr>
            </thead>
            <tbody>
              {data.materials.map((m: CCMMaterial, i) => (
                <tr key={i} className="border-b border-gray-100">
                  <td className="py-1 pr-2 text-gray-800">
                    {m.item}
                    {m.commodity && <span className="ml-1 text-[11px] text-gray-400">({m.commodity})</span>}
                  </td>
                  <td className="py-1 pr-2 text-right tabular-nums">{m.pct_of_cogs}%</td>
                  <td className="py-1 pr-2 text-gray-600">
                    {m.price != null ? `${m.price.toLocaleString("ko-KR")} ${m.unit ?? ""}` : "—"}
                  </td>
                  <td className="py-1 text-right"><DirChip dir={m.direction} chg={m.chg_1y} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* ②-b 표준(기준)원가 vs 실제 — 원가차이 분해 (Phase B) */}
      {data.variance && (
        <section>
          <h3 className="mb-1 text-sm font-bold text-gray-700">
            ③ 표준(기준)원가 vs 실제 — 원가차이 분해 <span className="font-normal text-gray-400">({data.variance.years})</span>
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-sm">
              <thead>
                <tr className="border-b text-left text-[11px] text-gray-400">
                  <th className="py-1 pr-2">원재료</th>
                  <th className="py-1 pr-2 text-right">원재료비(억)</th>
                  <th className="py-1 pr-2 text-right">최근1년 등락</th>
                  <th className="py-1 pr-2 text-right">가격차이(억)</th>
                  <th className="py-1 text-center">F/U</th>
                </tr>
              </thead>
              <tbody>
                {data.variance.contributions.map((c, i) => (
                  <tr key={i} className="border-b border-gray-100">
                    <td className="py-1 pr-2 text-gray-800">{c.item}</td>
                    <td className="py-1 pr-2 text-right tabular-nums">{c.material_eok.toLocaleString("ko-KR")}</td>
                    <td className="py-1 pr-2 text-right tabular-nums" style={{ color: c.chg_1y > 0 ? "#c92a2a" : c.chg_1y < 0 ? "#1971c2" : "#868e96" }}>
                      {c.chg_1y > 0 ? "+" : ""}{(c.chg_1y * 100).toFixed(1)}%
                    </td>
                    <td className="py-1 pr-2 text-right tabular-nums">{c.variance_eok > 0 ? "+" : ""}{c.variance_eok.toLocaleString("ko-KR")}</td>
                    <td className="py-1 text-center">
                      <FUChip fu={c.fu} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1 rounded bg-gray-50 px-3 py-2 text-sm">
            <span>가격차이(원자재발) <b>{data.variance.price_variance_eok > 0 ? "+" : ""}{data.variance.price_variance_eok.toLocaleString("ko-KR")}억</b> ({data.variance.price_variance_pp > 0 ? "+" : ""}{data.variance.price_variance_pp}%p) <FUChip fu={data.variance.price_fu} /></span>
            <span>실제 원가율변화(1년) <b>{data.variance.actual_change_pp > 0 ? "+" : ""}{data.variance.actual_change_pp}%p</b> <FUChip fu={data.variance.actual_fu} /></span>
            <span>능률·기타(잔차) <b>{data.variance.efficiency_pp > 0 ? "+" : ""}{data.variance.efficiency_pp}%p</b> <FUChip fu={data.variance.efficiency_fu} /></span>
            {data.variance.cogs_ratio_change_3y_pp != null && (
              <span className="text-gray-500">3년 원가율 {data.variance.cogs_ratio_change_3y_pp > 0 ? "+" : ""}{data.variance.cogs_ratio_change_3y_pp}%p</span>
            )}
          </div>
          <p className="mt-1 text-[12px] font-semibold" style={{ color: GREEN }}>{data.variance.verdict}</p>
          <p className="text-[11px] text-gray-400">{data.variance.note}</p>
        </section>
      )}

      {/* ④ 마진 정합성 */}
      <section className="rounded border border-gray-200 bg-gray-50 p-3">
        <h3 className="mb-2 text-sm font-bold text-gray-700">④ 마진 정합성 검증</h3>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
          <span>아래서 쌓은 원가 → 추정 영업이익률 <b>{pct(r.bottom_up_op_margin)}</b></span>
          <span>회사 보고 영업이익률 <b>{pct(r.reported_op_margin)}</b></span>
          <span style={{ color: reconColor }} className="font-semibold">
            차이 {r.gap_pp > 0 ? "+" : ""}{r.gap_pp}%p · {reconLabel}
          </span>
        </div>
        {r.reason && (
          <p className="mt-1 text-[12px]" style={{ color: r.status === "loss" ? "#7048e8" : "#6b7280" }}>
            {r.status === "loss" ? "※ " : ""}{r.reason}
          </p>
        )}
        <ul className="mt-2 list-disc pl-5 text-[11px] text-gray-500">
          {r.assumptions.map((a, i) => <li key={i}>{a}</li>)}
        </ul>
      </section>

      {/* ⑤ 애널리스트 리포트 취합 (Tier 1) */}
      <AnalystReportsSection ticker={data.ticker} company={data.company} verdict={data.variance?.verdict} />

      {/* 레벨3: 재무제표 근거 */}
      <section>
        <button
          onClick={() => setShowFin(!showFin)}
          className="text-sm font-semibold text-gray-600 hover:text-gray-900"
        >
          {showFin ? "▾" : "▸"} 재무제표 근거 — 이 숫자가 어디서 나왔나
        </button>
        {showFin && (
          <div className="mt-2 rounded border border-gray-200 p-3 text-sm">
            {data.financials_3y && data.financials_3y.length >= 2 ? (
              <Financials3yTable rows={data.financials_3y} />
            ) : (
              <>
                <div className="mb-1 text-[11px] text-gray-400">
                  {data.financials_detail.source}
                  {data.financials_detail.year ? ` (FY${data.financials_detail.year})` : ""}
                </div>
                <table className="w-full max-w-md text-sm">
                  <tbody>
                    {data.financials_detail.rows.map((row, i) => (
                      <tr key={i} className="border-b border-gray-100">
                        <td className="py-1 text-gray-700">{row.label}</td>
                        <td className="py-1 text-right tabular-nums text-gray-600">
                          {row.eok != null ? `${row.eok.toLocaleString("ko-KR")}억` : "—"}
                        </td>
                        <td className="py-1 text-right tabular-nums font-semibold" style={{ color: GREEN }}>
                          {row.pct}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-2 text-[11px] text-gray-400">{data.financials_detail.note}</p>
              </>
            )}
            {isEst && (
              <p className="mt-1 text-[11px] text-amber-600">
                ※ DART_API_KEY 미설정 — 현재 값은 수작업 추정 비율입니다.
              </p>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

// ① 보강: DART 사업보고서 품목별 매출구성(P1) — 있으면 표시
function DartProductMix({ ticker }: { ticker: string }) {
  const [data, setData] = useState<CompanyProducts | null>(null);
  useEffect(() => {
    let alive = true;
    setData(null);
    api.companyProducts(ticker).then((r) => alive && setData(r)).catch(() => {});
    return () => { alive = false; };
  }, [ticker]);

  if (!data || data.coverage !== "parsed" || data.products.length === 0) return null;
  const max = Math.max(...data.products.map((p) => p.pct), 1);
  return (
    <div className="mt-2 rounded border border-gray-200 bg-gray-50 p-2">
      <div className="mb-1 text-[12px] font-semibold text-gray-600">
        사업보고서 품목별 매출구성 <span className="font-normal text-gray-400">(DART 자동파싱)</span>
      </div>
      <div className="space-y-1">
        {data.products.map((p, i) => (
          <div key={i} className="flex items-center gap-2 text-[12px]">
            <div className="w-32 shrink-0 truncate text-gray-700">{p.name}</div>
            <div className="h-3 flex-1 rounded bg-gray-200">
              <div className="h-3 rounded" style={{ width: `${(p.pct / max) * 100}%`, background: "#40916c" }} />
            </div>
            <div className="w-12 shrink-0 text-right tabular-nums text-gray-600">{p.pct}%</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ⑤ 애널리스트 리포트 취합 (Tier 1: 제목·증권사·날짜·원문 링크 = 사실+링크만)
function AnalystReportsSection({ ticker, company, verdict }: { ticker: string; company: string; verdict?: string }) {
  const [data, setData] = useState<AnalystReports | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setData(null);
    api.analystReports(ticker, company)
      .then((r) => alive && setData(r))
      .catch(() => {})
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [ticker, company]);

  return (
    <section>
      <h3 className="mb-1 text-sm font-bold text-gray-700">⑤ 애널리스트 리포트 취합 <span className="font-normal text-gray-400">(원문 링크 · 내용 복제 없음)</span></h3>
      {loading && <div className="text-[12px] text-gray-400">리포트 취합 중…</div>}
      {data && data.n_reports === 0 && (
        <div className="text-[12px] text-gray-400">최근 애널리스트 리포트를 찾지 못했습니다.</div>
      )}
      {data && data.n_reports > 0 && (
        <>
          <div className="mb-1 text-[12px] text-gray-600">
            최근 <b>{data.n_reports}</b>건 · 증권사 <b>{data.broker_count}</b>곳 · 최신 {data.latest_date}
            <span className="ml-2 text-gray-400">[{data.brokers.join(" · ")}]</span>
          </div>

          {/* Tier2-ㄱ: 컨센서스 수치 */}
          {data.consensus && (
            <div className="mb-2 flex flex-wrap items-center gap-x-5 gap-y-1 rounded border border-gray-200 bg-white px-3 py-2 text-sm">
              <span className="font-semibold" style={{ color: GREEN }}>컨센서스</span>
              <span>투자의견 <b>{data.consensus.opinion_label}</b> <span className="text-gray-400">({data.consensus.opinion_score.toFixed(2)}/4)</span></span>
              {data.consensus.opinion_dist && (
                <span className="text-[12px]">
                  <span style={{ color: "#1971c2" }}>매수 {data.consensus.opinion_dist.buy}</span>
                  <span className="text-gray-400"> · 중립 {data.consensus.opinion_dist.hold}</span>
                  <span style={{ color: "#c92a2a" }}> · 매도 {data.consensus.opinion_dist.sell}</span>
                </span>
              )}
              <span>목표주가 <b>{data.consensus.target_price.toLocaleString("ko-KR")}원</b></span>
              <span className="text-gray-500">PER {data.consensus.per}배</span>
              <span className="text-gray-400 text-[11px]">추정기관 {data.consensus.n_institutions}곳 · 기준 {data.consensus.as_of}</span>
              {data.target_sample && data.target_sample.n > 0 && (
                <span className="text-[11px] text-gray-400">
                  · 리포트 추출 {data.target_sample.n}건 평균 {data.target_sample.avg?.toLocaleString("ko-KR")}원
                  ({data.target_sample.low?.toLocaleString("ko-KR")}~{data.target_sample.high?.toLocaleString("ko-KR")})
                </span>
              )}
            </div>
          )}

          {verdict && (
            <div className="mb-2 rounded bg-gray-50 px-3 py-1.5 text-[12px] text-gray-600">
              <span className="font-semibold" style={{ color: GREEN }}>원가분석 대조</span> — 시장은{" "}
              {data.consensus ? <b>{data.consensus.opinion_label}·목표 {data.consensus.target_price.toLocaleString("ko-KR")}원</b> : "리포트 다수"}
              인데, 원가구조는 “{verdict}”. (근거는 원문 링크)
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-b text-left text-[11px] text-gray-400">
                  <th className="py-1 pr-2">작성일</th>
                  <th className="py-1 pr-2">증권사</th>
                  <th className="py-1 pr-2 text-right">목표주가</th>
                  <th className="py-1 pr-2">제목</th>
                  <th className="py-1 text-right">원문</th>
                </tr>
              </thead>
              <tbody>
                {data.reports.map((rp, i) => (
                  <tr key={i} className="border-b border-gray-100">
                    <td className="py-1 pr-2 whitespace-nowrap tabular-nums text-gray-500">{rp.date}</td>
                    <td className="py-1 pr-2 whitespace-nowrap text-gray-700">{rp.broker}</td>
                    <td className="py-1 pr-2 text-right tabular-nums text-gray-700">
                      {rp.target_price ? `${rp.target_price.toLocaleString("ko-KR")}원` : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="py-1 pr-2 text-gray-600">{rp.title}</td>
                    <td className="py-1 text-right">
                      {rp.url ? (
                        <a href={rp.url} target="_blank" rel="noopener noreferrer" className="text-[12px] font-semibold" style={{ color: "#1971c2" }}>
                          원문 ↗
                        </a>
                      ) : <span className="text-[11px] text-gray-300">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-1 text-[11px] text-gray-400">{data.source}. 목표주가는 사실 수치만 취합, 리포트 원문은 링크로 연결.</p>
        </>
      )}
    </section>
  );
}

// 레벨3: DART 손익계산서 3개년 (매출→원가→판관→영익, 억원 + 비율)
function Financials3yTable({ rows }: { rows: CCMFinYear[] }) {
  const yrs = [...rows].reverse();   // 과거 → 최근
  const line = (label: string, get: (f: CCMFinYear) => number | null, ratio: (f: CCMFinYear) => number | null) => (
    <tr className="border-b border-gray-100">
      <td className="py-1 pr-3 text-gray-700 whitespace-nowrap">{label}</td>
      {yrs.map((f) => {
        const eok = get(f);
        const rt = ratio(f);
        return (
          <td key={f.year} className="py-1 pl-3 text-right tabular-nums">
            <span className="text-gray-700">{eok != null ? eok.toLocaleString("ko-KR") : "—"}</span>
            {rt != null && <span className="ml-1 text-[11px] text-gray-400">{(rt * 100).toFixed(1)}%</span>}
          </td>
        );
      })}
    </tr>
  );
  return (
    <>
      <div className="mb-1 text-[11px] text-gray-400">DART 손익계산서 3개년 (억원 · 비율)</div>
      <div className="overflow-x-auto">
        <table className="text-sm">
          <thead>
            <tr className="border-b text-[11px] text-gray-400">
              <th className="py-1 pr-3 text-left">계정</th>
              {yrs.map((f) => <th key={f.year} className="py-1 pl-3 text-right">FY{f.year}</th>)}
            </tr>
          </thead>
          <tbody>
            {line("매출액", (f) => f.revenue_eok, () => 1)}
            {line("매출원가", (f) => Math.round(f.revenue_eok * f.cogs_ratio), (f) => f.cogs_ratio)}
            {line("판매관리비", (f) => (f.sga_ratio != null ? Math.round(f.revenue_eok * f.sga_ratio) : null), (f) => f.sga_ratio)}
            {line("영업이익", (f) => (f.op_margin != null ? Math.round(f.revenue_eok * f.op_margin) : null), (f) => f.op_margin)}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[11px] text-gray-400">※ 매출원가는 손익계산서 실측, 원재료비/가공비 분해는 추정(🟡).</p>
    </>
  );
}

// 품목 행 + 6단계 워터폴 드릴다운
function ProductRow({ p, open, onToggle }: { p: CCMProduct; open: boolean; onToggle: () => void }) {
  const [td, setTd] = useState<UE | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || td) return;
    let alive = true;
    setLoading(true);
    api.unitEconomics(p.id)
      .then((r) => alive && setTd(r))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [open, p.id, td]);

  const KIND_COLOR: Record<string, string> = {
    channel: "#adb5bd", material: "#40916c", process: "#74c69d", sga: "#f4a259", profit: "#1b4332",
  };

  return (
    <>
      <tr className="cursor-pointer border-b border-gray-100 hover:bg-gray-50" onClick={onToggle}>
        <td className="py-1.5 pr-2 font-medium text-gray-800">
          <span className="mr-1 text-gray-400">{open ? "▾" : "▸"}</span>{p.product}
          <span className="ml-1 text-[11px] text-gray-400">{p.unit}</span>
        </td>
        <td className="py-1.5 pr-2 text-right tabular-nums">{won(p.retail_price)}</td>
        <td className="py-1.5 pr-2 text-right tabular-nums">{pct(p.cogs_ratio, 0)}</td>
        <td className="py-1.5 pr-2 text-[11px] text-gray-500">{p.top_materials.join(" · ")}</td>
        <td className="py-1.5 pr-2 text-right tabular-nums font-semibold" style={{ color: p.profit_per_unit >= 0 ? GREEN : "#c92a2a" }}>
          {won(p.profit_per_unit)}
        </td>
        <td className="py-1.5 text-right tabular-nums" style={{ color: p.op_margin >= 0 ? GREEN : "#c92a2a" }}>
          {pct(p.op_margin)}
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={6} className="bg-gray-50 px-3 py-2">
            {loading && <div className="text-[11px] text-gray-400">불러오는 중…</div>}
            {td && (
              <div className="space-y-1">
                {td.waterfall.map((w, i) => (
                  <div key={i} className="flex items-center gap-2 text-[12px]">
                    <div className="w-40 shrink-0 text-gray-600">{w.item}</div>
                    <div className="h-3 flex-1 rounded bg-gray-200">
                      <div
                        className="h-3 rounded"
                        style={{ width: `${Math.min(100, Math.abs(w.pct_of_retail))}%`, background: KIND_COLOR[w.kind] }}
                      />
                    </div>
                    <div className="w-24 shrink-0 text-right tabular-nums text-gray-500">
                      {won(w.won)} ({w.pct_of_retail}%)
                    </div>
                  </div>
                ))}
                {td.product.note && <p className="mt-1 text-[11px] text-gray-400">{td.product.note}</p>}
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
