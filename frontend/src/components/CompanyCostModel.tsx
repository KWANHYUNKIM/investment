"use client";

import { useEffect, useMemo, useState } from "react";
import {
  api,
  CCMCompany,
  CompanyCostModel as CCM,
  CCMMaterial,
  CCMProduct,
  CCMFinYear,
  CCMJointAllocation,
  CostRanking,
  CostRankRow,
  FutureValueBoard,
  FVRow,
  CCMBusiness,
  CCMCostNature,
  CCMLabor,
  CCMStatementAudit,
  CCMStatementCheck,
  DartFull,
  IntegrityCheck,
  IntegrityScore,
  AnalystReports,
  CompanyProducts,
  CostingEducation,
  UnitEconomics as UE,
} from "@/lib/api";

const GREEN = "#217346";

// ⚪ 교육 레이어(C5) — 정적 콘텐츠라 앱 수명 동안 한 번만 받는다.
let eduPromise: Promise<CostingEducation> | null = null;
function useCostingEdu(): CostingEducation | null {
  const [edu, setEdu] = useState<CostingEducation | null>(null);
  useEffect(() => {
    if (!eduPromise) eduPromise = api.costingEducation();
    let alive = true;
    eduPromise.then((r) => alive && setEdu(r)).catch(() => {});
    return () => { alive = false; };
  }, []);
  return edu;
}

// 숫자 옆 ⓘ — 왜 이 값이 근사인지(또는 무엇이 미공시인지) 그 자리에서 설명.
function Edu({ k, edu }: { k: string; edu: CostingEducation | null }) {
  const t = edu?.tooltips?.[k];
  if (!t) return null;
  return (
    <span className="group relative ml-1 inline-block">
      <span className="cursor-help text-[11px] text-gray-400">{t.badge}ⓘ</span>
      <span className="pointer-events-none absolute left-0 top-full z-30 hidden w-72 rounded border border-gray-300 bg-white p-2 text-left text-[11px] font-normal leading-relaxed text-gray-600 shadow-lg group-hover:block">
        <b className="text-gray-800">{t.title}</b>
        <br />
        {t.body}
      </span>
    </span>
  );
}

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
  const [view, setView] = useState<"list" | "rank" | "future">("list");

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
        {([["list", "업종별 목록"], ["rank", "괜찮은 순 (원가 경쟁력)"],
           ["future", "미래가치 (4문)"]] as const).map(([v, label]) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className="rounded border px-2.5 py-1 text-[12px]"
            style={view === v
              ? { borderColor: GREEN, color: "#fff", background: GREEN, fontWeight: 700 }
              : { borderColor: "#d0d5dd", color: "#6b7280" }}
          >
            {label}
          </button>
        ))}
      </div>

      {view === "future" ? (
        <FutureValueView sector={sectorFilter} onSector={setSectorFilter} onPick={setSel} />
      ) : view === "rank" ? (
        <CostRankingView sector={sectorFilter} sectors={sectors} onSector={setSectorFilter} onPick={setSel} />
      ) : (
      <>
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
              <div className="text-[11px] text-gray-400">
                {c.sector} · {c.n_products}개 품목
                {c.production_type && <span className="ml-1" style={{ color: GREEN }}>· {c.production_type}</span>}
              </div>
            </div>
            <div className="text-right text-[11px] text-gray-500">
              <div>
                원가율 {pct(c.cogs_ratio, 0)}
                <span className="ml-1 text-[10px]" style={{ color: c.basis.startsWith("배치") ? GREEN : "#adb5bd" }}>
                  {c.basis.startsWith("배치") ? "실측" : "추정"}
                </span>
              </div>
              <div style={{ color: c.op_margin >= 0 ? GREEN : "#c92a2a" }}>영익 {pct(c.op_margin)}</div>
              {c.integrity_pct != null && (
                <div className="mt-0.5" style={{ color: gradeColor(c.integrity_grade) }}>
                  진실성 {c.integrity_pct}%
                  {c.integrity_fail ? <span className="ml-1 text-[10px]">불일치 {c.integrity_fail}</span> : null}
                </div>
              )}
            </div>
          </button>
        ))}
      </div>
      </>
      )}
    </div>
  );
}

// ===== 레벨 1-c: 미래가치 4문(門) =====
const FV_LABEL: Record<string, string> = {
  reinvest: "재투자", conversion: "전환", endurance: "체력", market: "시장",
};

function FutureValueView({
  sector, onSector, onPick,
}: { sector: string; onSector: (s: string) => void; onPick: (t: string) => void }) {
  const [data, setData] = useState<FutureValueBoard | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [onlyLoss, setOnlyLoss] = useState(false);
  const [open, setOpen] = useState("");

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setErr("");
    api.futureValue(sector, onlyLoss)
      .then((r) => alive && setData(r))
      .catch((e) => alive && setErr(e?.message ?? "미래가치 계산 실패"))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [sector, onlyLoss]);

  if (loading && !data) return <div className="text-sm text-gray-400">미래가치 계산 중… (전 종목 재무제표 스캔)</div>;
  if (err) return <div className="text-sm text-red-600">{err}</div>;
  if (!data) return null;

  const order = ["reinvest", "conversion", "endurance", "market"];
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <select value={sector} onChange={(e) => onSector(e.target.value)}
                className="rounded border border-gray-300 px-2 py-1 text-sm">
          <option value="전체">업종 전체</option>
          {data.sectors.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <label className="flex items-center gap-1 text-[12px] text-gray-600">
          <input type="checkbox" checked={onlyLoss} onChange={(e) => setOnlyLoss(e.target.checked)} />
          적자기업만 (미래투자형 ↔ 소멸형 판별)
        </label>
        <span className="text-xs text-gray-400">
          {data.filtered ?? data.count}사 · 갱신 {data.generated_at}
          {!data.theme_ready && " · 테마 미준비(시장 항목 중립)"}
        </span>
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1 rounded bg-gray-50 px-3 py-2 text-[11px] text-gray-600">
        {Object.entries(data.weights).map(([k, w]) => (
          <span key={k}><b>{FV_LABEL[k]}</b> {w}점</span>
        ))}
        <span className="text-gray-400">※ 뉴스가 섞이는 시장 항목만 배점 최소</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[860px] text-sm">
          <thead>
            <tr className="border-b text-left text-[11px] text-gray-400">
              <th className="py-1 pr-2">#</th>
              <th className="py-1 pr-2">회사</th>
              <th className="py-1 pr-2 text-right">점수</th>
              <th className="py-1 pr-2">재투자·전환·체력·시장</th>
              <th className="py-1 pr-2">판정</th>
              <th className="py-1 pr-2 text-right">재투자율</th>
              <th className="py-1 text-right">전환</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <FVRowView key={r.ticker} r={r} order={order} open={open === r.ticker}
                         onToggle={() => setOpen(open === r.ticker ? "" : r.ticker)}
                         onPick={() => onPick(r.ticker)} />
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] leading-relaxed text-gray-400">{data.note}</p>
    </div>
  );
}

function FVRowView({ r, order, open, onToggle, onPick }:
  { r: FVRow; order: string[]; open: boolean; onToggle: () => void; onPick: () => void }) {
  const capped = r.grade !== r.raw_grade;
  return (
    <>
      <tr className="cursor-pointer border-b border-gray-100 hover:bg-gray-50" onClick={onToggle}>
        <td className="py-1.5 pr-2 tabular-nums text-gray-400">{r.rank}</td>
        <td className="py-1.5 pr-2">
          <button onClick={(e) => { e.stopPropagation(); onPick(); }}
                  className="font-semibold hover:underline" style={{ color: GREEN }}>
            {r.name}
          </button>
          <div className="text-[10px] text-gray-400">
            {r.sector}{r.year ? ` · FY${r.year}` : ""}
            {r.loss_making && <span className="ml-1 text-[#c92a2a]">· 적자</span>}
          </div>
        </td>
        <td className="py-1.5 pr-2 text-right">
          <span className="tabular-nums font-bold" style={{ color: GRADE_COLOR[r.grade] ?? "#333" }}>
            {r.score.toFixed(1)}
          </span>
          <span className="ml-1 rounded px-1 text-[10px] font-bold text-white"
                style={{ background: GRADE_COLOR[r.grade] ?? "#999" }}>
            {r.grade}
          </span>
          {capped && (
            <div className="text-[9px] text-[#c92a2a]">반증 상한 ({r.raw_grade}→{r.grade})</div>
          )}
        </td>
        <td className="py-1.5 pr-2">
          <div className="flex items-center gap-[3px]">
            {order.map((k) => {
              const p = r.parts[k];
              if (!p) return null;
              const ratio = p.max ? p.score / p.max : 0;
              return (
                <span key={k} title={`${FV_LABEL[k]} ${p.score}/${p.max} — ${p.detail}`}
                      className="h-3 rounded-sm"
                      style={{
                        width: `${p.max * 1.6}px`,
                        background: p.estimated ? "#e5e7eb" : `rgba(33,115,70,${0.25 + ratio * 0.75})`,
                      }} />
              );
            })}
          </div>
        </td>
        <td className="py-1.5 pr-2 text-[11px] text-gray-600">
          {r.verdict}
          {r.falsifiers.length > 0 && (
            <span className="ml-1 rounded px-1 text-[10px] font-bold" style={{ background: "#fbe9e9", color: "#c92a2a" }}>
              반증 {r.falsifiers.length}
            </span>
          )}
        </td>
        <td className="py-1.5 pr-2 text-right tabular-nums text-gray-600">
          {r.reinvest_rate != null ? `${(r.reinvest_rate * 100).toFixed(1)}%` : "—"}
        </td>
        <td className="py-1.5 text-right tabular-nums"
            style={{ color: (r.conversion ?? 0) > 0 ? GREEN : "#c92a2a" }}>
          {r.conversion != null ? `${r.conversion}배` : "—"}
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={7} className="bg-gray-50 px-3 py-2">
            <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
              {order.map((k) => {
                const p = r.parts[k];
                if (!p) return null;
                return (
                  <div key={k} className="rounded border border-gray-200 bg-white px-2 py-1.5">
                    <div className="flex items-baseline justify-between">
                      <span className="text-[12px] font-semibold text-gray-700">{FV_LABEL[k]}</span>
                      <span className="tabular-nums text-[12px]" style={{ color: GREEN }}>
                        {p.score}<span className="text-gray-400">/{p.max}</span>
                        {p.estimated && <span className="ml-1 text-[10px] text-amber-600">중립</span>}
                      </span>
                    </div>
                    <div className="text-[11px] text-gray-500">{p.detail}</div>
                  </div>
                );
              })}
            </div>
            {r.falsifiers.length > 0 && (
              <div className="mt-2 rounded border p-2" style={{ borderColor: "#f0c8c8", background: "#fdf6f6" }}>
                <div className="mb-1 text-[11px] font-bold" style={{ color: "#c92a2a" }}>
                  반증 신호 — 켜지면 &lsquo;미래에 투자 중&rsquo;이라는 설명이 성립하지 않는다
                </div>
                <ul className="space-y-0.5">
                  {r.falsifiers.map((f, i) => (
                    <li key={i} className="text-[11px] text-gray-700">
                      <b style={{ color: "#c92a2a" }}>[상한 {f.cap}]</b> {f.text}
                      <span className="ml-1 text-gray-400">— {f.why}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="mt-1 flex flex-wrap gap-x-4 text-[11px] text-gray-500">
              {r.revenue_eok != null && <span>매출 {r.revenue_eok.toLocaleString("ko-KR")}억</span>}
              {r.net_cash_eok != null && <span>순현금 {r.net_cash_eok.toLocaleString("ko-KR")}억</span>}
              {r.cash_positive ? <span>영업현금 흑자</span>
                : r.runway_months != null && <span>런웨이 {r.runway_months}개월</span>}
              {r.interest_cover != null && <span>이자보상 {r.interest_cover}배</span>}
              {r.sales_cagr != null && <span>매출 CAGR {(r.sales_cagr * 100).toFixed(1)}%</span>}
              {r.themes.length > 0 && <span>테마: {r.themes.slice(0, 3).join(", ")}</span>}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// ===== 레벨 1-b: 원가 경쟁력 랭킹 ("괜찮은 순") =====
const PART_LABEL: Record<string, string> = {
  profitability: "수익성", cost_trend: "원가추세", pass_through: "전가력",
  stability: "안정성", reliability: "신뢰도",
};
const GRADE_COLOR: Record<string, string> = {
  "A+": "#1b4332", A: "#217346", "B+": "#40916c", B: "#74c69d",
  C: "#e8a33d", D: "#c92a2a",
};

function CostRankingView({
  sector, sectors, onSector, onPick,
}: {
  sector: string; sectors: string[]; onSector: (s: string) => void; onPick: (t: string) => void;
}) {
  const [data, setData] = useState<CostRanking | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [open, setOpen] = useState<string>("");

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setErr("");
    api.costRanking(sector)
      .then((r) => alive && setData(r))
      .catch((e) => alive && setErr(e?.message ?? "랭킹 실패"))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [sector]);

  if (loading && !data) return <div className="text-sm text-gray-400">원가 경쟁력 계산 중…</div>;
  if (err) return <div className="text-sm text-red-600">{err}</div>;
  if (!data) return null;
  if (!data.available) {
    return <div className="rounded border border-amber-200 bg-amber-50 p-3 text-[12px] text-amber-700">{data.note}</div>;
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={sector}
          onChange={(e) => onSector(e.target.value)}
          className="rounded border border-gray-300 px-2 py-1 text-sm"
        >
          <option value="전체">업종 전체</option>
          {(data.sectors ?? sectors).map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <span className="text-xs text-gray-400">
          {data.count}개 회사 · 배치 {data.built_at}
          {data.excluded ? ` · 추정치뿐이라 제외 ${data.excluded}사` : ""}
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[820px] text-sm">
          <thead>
            <tr className="border-b text-left text-[11px] text-gray-400">
              <th className="py-1 pr-2">#</th>
              <th className="py-1 pr-2">회사</th>
              <th className="py-1 pr-2 text-right">점수</th>
              <th className="py-1 pr-2">항목별 (수익성·원가추세·전가력·안정성·신뢰도)</th>
              <th className="py-1 pr-2 text-right">영익률</th>
              <th className="py-1 pr-2 text-right">원가율</th>
              <th className="py-1 text-right">3년 추세</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <RankRow key={r.ticker} r={r} open={open === r.ticker}
                       onToggle={() => setOpen(open === r.ticker ? "" : r.ticker)}
                       onPick={() => onPick(r.ticker)} />
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[11px] leading-relaxed text-gray-400">{data.note}</p>
    </div>
  );
}

function RankRow({ r, open, onToggle, onPick }:
  { r: CostRankRow; open: boolean; onToggle: () => void; onPick: () => void }) {
  const order = ["profitability", "cost_trend", "pass_through", "stability", "reliability"];
  return (
    <>
      <tr className="cursor-pointer border-b border-gray-100 hover:bg-gray-50" onClick={onToggle}>
        <td className="py-1.5 pr-2 tabular-nums text-gray-400">{r.rank}</td>
        <td className="py-1.5 pr-2">
          <button
            onClick={(e) => { e.stopPropagation(); onPick(); }}
            className="font-semibold text-gray-800 hover:underline"
            style={{ color: GREEN }}
          >
            {r.company}
          </button>
          <div className="text-[10px] text-gray-400">
            {r.sector}{r.production_type ? ` · ${r.production_type}` : ""}
            {r.year ? ` · FY${r.year}` : ""}
          </div>
        </td>
        <td className="py-1.5 pr-2 text-right">
          <span className="tabular-nums font-bold" style={{ color: GRADE_COLOR[r.grade] ?? "#333" }}>
            {r.score.toFixed(1)}
          </span>
          <span className="ml-1 rounded px-1 text-[10px] font-bold text-white"
                style={{ background: GRADE_COLOR[r.grade] ?? "#999" }}>
            {r.grade}
          </span>
        </td>
        <td className="py-1.5 pr-2">
          <div className="flex items-center gap-[3px]">
            {order.map((k) => {
              const p = r.parts[k];
              if (!p) return null;
              const ratio = p.max ? p.score / p.max : 0;
              return (
                <span key={k} title={`${PART_LABEL[k]} ${p.score}/${p.max} — ${p.detail}`}
                      className="h-3 rounded-sm"
                      style={{
                        width: `${p.max * 1.6}px`,
                        background: p.estimated ? "#e5e7eb" : `rgba(33,115,70,${0.25 + ratio * 0.75})`,
                      }} />
              );
            })}
          </div>
          <div className="mt-0.5 text-[10px] text-gray-500">{r.headline}</div>
        </td>
        <td className="py-1.5 pr-2 text-right tabular-nums"
            style={{ color: (r.op_margin ?? 0) >= 0 ? GREEN : "#c92a2a" }}>
          {r.op_margin != null ? pct(r.op_margin) : "—"}
        </td>
        <td className="py-1.5 pr-2 text-right tabular-nums text-gray-600">
          {r.cogs_ratio != null ? pct(r.cogs_ratio, 0) : "—"}
        </td>
        <td className="py-1.5 text-right tabular-nums"
            style={{ color: (r.cogs_delta_3y_pp ?? 0) > 0 ? "#c92a2a" : "#1971c2" }}>
          {r.cogs_delta_3y_pp != null ? `${r.cogs_delta_3y_pp > 0 ? "+" : ""}${r.cogs_delta_3y_pp}%p` : "—"}
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={7} className="bg-gray-50 px-3 py-2">
            <div className="grid grid-cols-1 gap-1 sm:grid-cols-2 lg:grid-cols-3">
              {order.map((k) => {
                const p = r.parts[k];
                if (!p) return null;
                return (
                  <div key={k} className="rounded border border-gray-200 bg-white px-2 py-1.5">
                    <div className="flex items-baseline justify-between">
                      <span className="text-[12px] font-semibold text-gray-700">{PART_LABEL[k]}</span>
                      <span className="tabular-nums text-[12px]" style={{ color: GREEN }}>
                        {p.score}<span className="text-gray-400">/{p.max}</span>
                        {p.estimated && <span className="ml-1 text-[10px] text-amber-600">자료없음·중립</span>}
                      </span>
                    </div>
                    <div className="text-[11px] text-gray-500">{p.detail}</div>
                  </div>
                );
              })}
            </div>
            {r.verdict && <p className="mt-1 text-[11px] text-gray-500">원가차이 판정: {r.verdict}</p>}
          </td>
        </tr>
      )}
    </>
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
  const edu = useCostingEdu();
  const s = data.summary;
  const r = data.reconciliation;
  const isEst = data.basis.source !== "DART 실측";
  const pt = data.production_type;

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
        {pt && (
          <span
            className="rounded px-1.5 py-0.5 text-[11px] font-semibold"
            style={{ color: GREEN, background: "#e9f3ee" }}
            title={pt.reason ?? pt.archetype}
          >
            {pt.type} · {pt.archetype}
            <Edu k="production_type" edu={edu} />
          </span>
        )}
        {data.statement_audit?.available && data.statement_audit.score != null && (
          <span
            className="rounded px-1.5 py-0.5 text-[11px] font-bold"
            style={{
              color: data.statement_audit.score >= 80 ? GREEN : data.statement_audit.score >= 60 ? "#b8860b" : "#c92a2a",
              background: data.statement_audit.score >= 80 ? "#e9f3ee" : data.statement_audit.score >= 60 ? "#fdf8ef" : "#fdf2f2",
            }}
            title={data.statement_audit.verdict}
          >
            재무제표 신뢰도 {data.statement_audit.score}
          </span>
        )}
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

      {/* 최상단 — 원가 진실성(§15.1). 소비자에겐 한 숫자, 펼치면 35개 항목 전부 */}
      {data.integrity && <IntegritySection integ={data.integrity} />}

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
            <Edu k="variance_basis" edu={edu} />
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
            <span>가격차이(원자재발)<Edu k="price_variance" edu={edu} /> <b>{data.variance.price_variance_eok > 0 ? "+" : ""}{data.variance.price_variance_eok.toLocaleString("ko-KR")}억</b> ({data.variance.price_variance_pp > 0 ? "+" : ""}{data.variance.price_variance_pp}%p) <FUChip fu={data.variance.price_fu} /></span>
            <span>실제 원가율변화(1년) <b>{data.variance.actual_change_pp > 0 ? "+" : ""}{data.variance.actual_change_pp}%p</b> <FUChip fu={data.variance.actual_fu} /></span>
            <span>능률·기타(잔차)<Edu k="efficiency_variance" edu={edu} /> <b>{data.variance.efficiency_pp > 0 ? "+" : ""}{data.variance.efficiency_pp}%p</b> <FUChip fu={data.variance.efficiency_fu} /></span>
            {data.variance.cogs_ratio_change_3y_pp != null && (
              <span className="text-gray-500">3년 원가율 {data.variance.cogs_ratio_change_3y_pp > 0 ? "+" : ""}{data.variance.cogs_ratio_change_3y_pp}%p</span>
            )}
          </div>
          <p className="mt-1 text-[12px] font-semibold" style={{ color: GREEN }}>{data.variance.verdict}</p>
          <p className="text-[11px] text-gray-400">{data.variance.note}</p>
        </section>
      )}

      {/* ③-2 원가 구성 실측 — 사업보고서 「비용의 성격별 분류」 */}
      {data.report_notes?.cost_nature && (
        <CostNatureSection cn={data.report_notes.cost_nature} url={data.report_notes.url} />
      )}

      {/* ③-3 단가·물량 실측 (B3·B4) */}
      {data.business?.available && <BusinessSection biz={data.business} />}

      {/* ③-4 사업보고서 전 항목 실측 (§15.2 D1~D12) */}
      {data.dart_full && <DartFullSections d={data.dart_full} />}

      {/* ④ 결합원가 배분 (연산·등급 업종만) */}
      {data.joint_allocation && <JointAllocationSection ja={data.joint_allocation} edu={edu} />}

      {/* ⑤ 마진 정합성 */}
      <section className="rounded border border-gray-200 bg-gray-50 p-3">
        <h3 className="mb-2 text-sm font-bold text-gray-700">⑤ 마진 정합성 검증</h3>
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

      {/* ⑥ 인건비·노동생산성 (W1) */}
      {data.labor && <LaborSection labor={data.labor} />}

      {/* ⑦ 재무제표 3종 감사 — 구비 점검 + 정합성 조작탐지 */}
      {data.statement_audit && <StatementAuditSection audit={data.statement_audit} />}

      {/* ⑧ 애널리스트 리포트 취합 (Tier 1) */}
      <AnalystReportsSection ticker={data.ticker} company={data.company} verdict={data.variance?.verdict} />

      {/* ⚪ 원가회계 해설 (C5 — 접이식 카드) */}
      <CostingEduCards edu={edu} />

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

// ===== §15 원가 진실성 — 소비자는 한 줄, 전문가는 전 항목 =====
// 스코어는 "이 회사가 정직한가"가 아니라 **"공시된 숫자들이 서로 맞물리는가"** 다.
// 그래서 판정만 보여주지 않고 A·B의 출처(절 번호)와 숫자를 항상 같이 적는다.
const ST_COLOR: Record<string, string> = {
  ok: GREEN, warn: "#b8860b", fail: "#c92a2a", na: "#adb5bd",
};
const ST_LABEL: Record<string, string> = {
  ok: "일치", warn: "관찰", fail: "불일치", na: "확인불가",
};

function gradeColor(grade?: string | null): string {
  if (grade === "양호") return GREEN;
  if (grade === "보통") return "#b8860b";
  if (grade === "주의") return "#e8590c";
  if (grade === "경고") return "#c92a2a";
  return "#868e96";
}

function IntegritySection({ integ }: { integ: IntegrityScore }) {
  const [open, setOpen] = useState(false);
  const [onlyIssue, setOnlyIssue] = useState(false);
  if (!integ.available || integ.score_pct == null) {
    return (
      <section className="rounded border border-gray-200 bg-gray-50 px-3 py-2 text-[12px] text-gray-500">
        원가 진실성 — 검증할 수 있는 항목이 없습니다({integ.phrase}).
      </section>
    );
  }
  const color = gradeColor(integ.grade);
  const rows = onlyIssue
    ? integ.checks.filter((c) => c.status === "warn" || c.status === "fail")
    : integ.checks;

  return (
    <section className="rounded border" style={{ borderColor: color }}>
      {/* 레벨 0 — 소비자가 보는 한 줄 */}
      <div className="px-3 py-2">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="text-sm font-bold text-gray-700">원가 진실성</span>
          <span className="text-2xl font-bold tabular-nums" style={{ color }}>{integ.score_pct}%</span>
          <span className="rounded px-1.5 py-0.5 text-[11px] font-bold text-white" style={{ background: color }}>
            {integ.grade}
          </span>
          <span className="text-[12px] text-gray-500">검증범위 {integ.coverage_pct}%</span>
          {integ.sector_percentile != null && (
            <span className="text-[12px] text-gray-500">업종 내 {integ.sector_percentile}%ile</span>
          )}
          <span className="text-[12px] text-gray-400">
            {integ.n_total}개 중 {integ.n_ok}개 일치 · {integ.n_warn}개 관찰 · {integ.n_fail}개 불일치 ·
            {" "}{integ.n_unavailable}개 확인불가
          </span>
        </div>
        <div className="mt-1.5 flex h-2 w-full overflow-hidden rounded bg-gray-100">
          <div style={{ width: `${integ.score_pct}%`, background: color }} />
        </div>
        <p className="mt-1 text-[12px] text-gray-600">{integ.phrase}</p>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
          <button onClick={() => setOpen(!open)} className="text-[12px] font-semibold" style={{ color: GREEN }}>
            {open ? "▾ 항목 접기" : `▸ ${integ.n_total}개 항목 전부 보기`}
          </button>
          {open && (
            <label className="flex items-center gap-1 text-[11px] text-gray-500">
              <input type="checkbox" checked={onlyIssue} onChange={(e) => setOnlyIssue(e.target.checked)} />
              어긋난 항목만
            </label>
          )}
          {integ.url && (
            <a href={integ.url} target="_blank" rel="noreferrer" className="text-[11px] text-gray-400 underline">
              DART 원문
            </a>
          )}
        </div>
      </div>

      {open && (
        <div className="border-t border-gray-200 px-3 py-2">
          {/* 등급별 요약 — 무엇이 더 중한가 */}
          <div className="mb-2 flex flex-wrap gap-x-5 gap-y-1 text-[11px] text-gray-500">
            {integ.by_grade.map((g) => (
              <span key={g.grade}>
                <b className="text-gray-700">{g.grade}</b> {g.n}항목{" "}
                <span style={{ color: GREEN }}>{"●".repeat(g.ok)}</span>
                <span style={{ color: "#b8860b" }}>{"●".repeat(g.warn)}</span>
                <span style={{ color: "#c92a2a" }}>{"●".repeat(g.fail)}</span>
                <span style={{ color: "#dee2e6" }}>{"○".repeat(g.na)}</span>
              </span>
            ))}
          </div>

          <div className="space-y-1">
            {rows.map((c) => <IntegrityRow key={c.code} c={c} />)}
          </div>

          <p className="mt-2 text-[11px] leading-relaxed text-gray-400">
            {String(integ.weights.rule ?? "")} · {integ.note}
          </p>
        </div>
      )}
    </section>
  );
}

function IntegrityRow({ c }: { c: IntegrityCheck }) {
  const [open, setOpen] = useState(false);
  const color = ST_COLOR[c.status];
  return (
    <div className="rounded border border-gray-100" style={{ background: c.status === "na" ? "#fafafa" : "#fff" }}>
      <button onClick={() => setOpen(!open)} className="flex w-full items-start gap-2 px-2 py-1.5 text-left">
        <span className="mt-0.5 w-11 shrink-0 rounded text-center text-[10px] font-bold text-white" style={{ background: color }}>
          {ST_LABEL[c.status]}
        </span>
        <span className="w-8 shrink-0 text-[11px] font-semibold text-gray-400">{c.code}</span>
        <span className="min-w-0 flex-1">
          <span className="text-[12px] font-semibold text-gray-800">{c.label}</span>
          <span className="ml-1 text-[10px] text-gray-400">[{c.grade}·가중{c.weight}]</span>
          <span className="block text-[11px] leading-snug text-gray-600">{c.detail}</span>
        </span>
      </button>
      {open && (
        <div className="border-t border-gray-100 px-3 py-1.5 text-[11px] leading-relaxed text-gray-500">
          {(c.source_a || c.source_b) && (
            <div className="mb-1">
              {c.source_a && <span>A: {c.source_a}{c.a != null ? ` (${c.a})` : ""}</span>}
              {c.source_b && <span className="ml-3">B: {c.source_b}{c.b != null ? ` (${c.b})` : ""}</span>}
              {c.year && <span className="ml-3 text-gray-400">FY{c.year}</span>}
            </div>
          )}
          {c.why && <div className="text-gray-500">{c.why}</div>}
        </div>
      )}
    </div>
  );
}

// ===== §15.2 사업보고서 전 항목 실측 — 지금까지 추정이던 자리를 공시 숫자로 채운 곳 =====
function eok(won?: number | null): string {
  if (won == null) return "—";
  return `${Math.round(won / 1e8).toLocaleString("ko-KR")}억`;
}

function DartFullSections({ d }: { d: DartFull }) {
  const [open, setOpen] = useState(false);
  if (!d.available) return null;
  const seg = d.segments;
  const mp = d.materials_purchase;
  const uc = d.unit_consumption ?? [];
  const inv = d.inventory;
  const rp = d.related_party;
  const am = d.audit_meta;

  return (
    <section>
      <h3 className="mb-1 text-sm font-bold text-gray-700">
        ③-4 사업보고서 전 항목 <span className="font-normal" style={{ color: GREEN }}>실측</span>
        <span className="font-normal text-gray-400">
          {" "}— 원재료 매입액·부문 원가율·원단위·재고·특수관계자
        </span>
      </h3>

      {/* 부문별 매출·영익 — '부문 원가율 = 회사평균 상속'을 졸업하는 자리 */}
      {seg && seg.rows.length > 0 && (
        <div className="mb-3 overflow-x-auto">
          <div className="mb-0.5 text-[11px] text-gray-400">{seg.source}</div>
          <table className="w-full min-w-[480px] text-sm">
            <thead>
              <tr className="border-b text-left text-[11px] text-gray-400">
                <th className="py-1 pr-2">사업부문</th>
                <th className="py-1 pr-2 text-right">매출</th>
                <th className="py-1 pr-2 text-right">비중</th>
                <th className="py-1 pr-2 text-right">영업손익</th>
                <th className="py-1 text-right">영익률</th>
              </tr>
            </thead>
            <tbody>
              {seg.rows.map((r, i) => (
                <tr key={i} className="border-b border-gray-100">
                  <td className="py-1 pr-2 text-gray-800">{r.name}</td>
                  <td className="py-1 pr-2 text-right tabular-nums">{eok(r.revenue_won)}</td>
                  <td className="py-1 pr-2 text-right tabular-nums text-gray-500">{r.revenue_pct ?? "—"}%</td>
                  <td className="py-1 pr-2 text-right tabular-nums">{eok(r.op_won)}</td>
                  <td className="py-1 text-right tabular-nums font-semibold"
                      style={{ color: (r.op_margin ?? 0) >= 0 ? GREEN : "#c92a2a" }}>
                    {r.op_margin != null ? `${(r.op_margin * 100).toFixed(1)}%` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 원단위 — §15.4 매입액 ÷ 단가 ÷ 생산량 */}
      {uc.length > 0 && (
        <div className="mb-3 rounded border border-gray-200 bg-gray-50 px-3 py-2">
          <div className="text-[12px] font-semibold text-gray-700">
            원단위(原單位) — 제품 하나에 원재료가 얼마나 들어가나
          </div>
          {uc.map((u, i) => (
            <div key={i} className="mt-1 text-[12px] text-gray-600">
              <b className="text-gray-800">{u.segment} · {u.material}</b>{" "}
              <span className="font-bold" style={{ color: GREEN }}>{u.u.toLocaleString("ko-KR")} {u.u_unit}</span>
              <span className="ml-2 text-[11px] text-gray-400">
                매입 {eok(u.amount_won)} ÷ 단가 {u.unit_price?.toLocaleString("ko-KR")}{u.price_unit} ={" "}
                {u.qty.toLocaleString("ko-KR")}{u.qty_unit} ÷ 생산 {u.output.toLocaleString("ko-KR")}{u.output_unit}
              </span>
              {u.trend.length > 1 && (
                <span className="ml-2 text-[11px]" style={{ color: u.stable ? GREEN : "#b8860b" }}>
                  3년 {u.trend.map((t) => t.u).reverse().join(" → ")} {u.stable ? "(안정)" : "(변동)"}
                </span>
              )}
              {u.join !== "품목" && (
                <span className="ml-2 text-[10px] text-gray-400">
                  ※ 매입액표와 단가표의 품목명이 달라 {u.join}으로 연결(단가 대표품목: {u.price_item})
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      <button onClick={() => setOpen(!open)} className="text-[12px] font-semibold text-gray-600 hover:text-gray-900">
        {open ? "▾" : "▸"} 원재료 매입액 · 재고 구성 · 특수관계자 · 감사 이력
      </button>

      {open && (
        <div className="mt-2 space-y-3">
          {mp && (
            <div className="overflow-x-auto">
              <div className="mb-0.5 text-[11px] text-gray-400">
                {mp.source} · 합계 {eok(mp.total_won)}
              </div>
              <table className="w-full min-w-[480px] text-sm">
                <thead>
                  <tr className="border-b text-left text-[11px] text-gray-400">
                    <th className="py-1 pr-2">부문</th>
                    <th className="py-1 pr-2">유형</th>
                    <th className="py-1 pr-2">품목</th>
                    <th className="py-1 pr-2">용도</th>
                    <th className="py-1 pr-2 text-right">매입액</th>
                    <th className="py-1 text-right">비중</th>
                  </tr>
                </thead>
                <tbody>
                  {mp.rows.slice(0, 15).map((r, i) => (
                    <tr key={i} className="border-b border-gray-100">
                      <td className="py-1 pr-2 text-gray-500">{r.segment ?? "—"}</td>
                      <td className="py-1 pr-2 text-gray-500">{r.type ?? "—"}</td>
                      <td className="py-1 pr-2 text-gray-800">{r.item}</td>
                      <td className="py-1 pr-2 text-[11px] text-gray-400">{r.use ?? "—"}</td>
                      <td className="py-1 pr-2 text-right tabular-nums">{eok(r.amount_won)}</td>
                      <td className="py-1 text-right tabular-nums text-gray-500">{r.pct != null ? `${r.pct}%` : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {inv && (
            <div className="text-[12px] text-gray-600">
              <div className="mb-0.5 text-[11px] text-gray-400">{inv.source}</div>
              재고 <b>{eok(inv.total_won)}</b>
              {inv.raw_won != null && <> · 원재료 {eok(inv.raw_won)}</>}
              {inv.wip_won != null && <> · 재공품 {eok(inv.wip_won)}</>}
              {inv.fg_won != null && <> · 제품·상품 {eok(inv.fg_won)}</>}
              {" · "}평가손실충당금 <b style={{ color: (inv.loss_pct ?? 0) > 10 ? "#c92a2a" : "#6b7280" }}>
                {eok(inv.valuation_loss_won)}{inv.loss_pct != null ? ` (${inv.loss_pct}%)` : ""}
              </b>
            </div>
          )}

          {rp && (
            <div className="text-[12px] text-gray-600">
              <div className="mb-0.5 text-[11px] text-gray-400">{rp.source}</div>
              특수관계자 {rp.n_parties}곳 · 매출 <b>{eok(rp.sales_won)}</b> · 매입 <b>{eok(rp.purchase_won)}</b>
              <div className="mt-0.5 text-[11px] text-gray-400">
                {rp.parties.slice(0, 5).map((p) => `${p.name} ${eok(p.sales_won)}`).join(" · ")}
              </div>
            </div>
          )}

          {am?.audit_service && am.audit_service.length > 0 && (
            <div className="text-[12px] text-gray-600">
              <div className="mb-0.5 text-[11px] text-gray-400">V-1 외부감사에 관한 사항</div>
              감사인 {am.auditors?.[0] ?? "—"}
              {am.auditor_changed && <b style={{ color: "#b8860b" }}> (전기와 다름 — 감사인 변경)</b>}
              {" · "}
              {am.audit_service.map((s) => `${s.period} ${s.hours?.toLocaleString("ko-KR") ?? "—"}시간/${s.fee_mn ?? "—"}백만원`).join(" · ")}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

// ③-2 원가 구성 실측 — 사업보고서 재무제표 주석 「비용의 성격별 분류」.
// 그동안 가정(재료비=매출원가의 80%)이던 값을 공시 실측으로 대체한 자리.
const CAT_COLOR: Record<string, string> = {
  재료비: "#217346", 노무비: "#2f7ed8", 감가상각: "#8a6d3b", 기타경비: "#adb5bd",
};

function CostNatureSection({ cn, url }: { cn: CCMCostNature; url?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <section>
      <h3 className="mb-1 text-sm font-bold text-gray-700">
        ③-2 원가 구성 <span className="font-normal" style={{ color: GREEN }}>실측</span>
        <span className="font-normal text-gray-400"> — 사업보고서 「비용의 성격별 분류」 ({cn.basis})</span>
      </h3>

      <div className="flex h-5 w-full overflow-hidden rounded border border-gray-200">
        {cn.breakdown.map((b) => (
          <div
            key={b.cat}
            title={`${b.cat} ${b.amount_eok.toLocaleString("ko-KR")}억 (${b.pct}%)`}
            style={{ width: `${b.pct}%`, background: CAT_COLOR[b.cat] ?? "#ced4da" }}
            className="flex items-center justify-center text-[10px] font-semibold text-white"
          >
            {b.pct >= 8 ? `${b.cat} ${b.pct}%` : ""}
          </div>
        ))}
      </div>

      <div className="mt-1 flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-gray-600">
        <span>총비용 <b>{cn.total_cost_eok.toLocaleString("ko-KR")}억</b> (매출원가+판관비)</span>
        <span>재료비 <b style={{ color: GREEN }}>{cn.material_eok.toLocaleString("ko-KR")}억</b></span>
        <span>인건비 <b>{cn.labor_eok.toLocaleString("ko-KR")}억</b></span>
        {url && (
          <a href={url} target="_blank" rel="noreferrer" className="text-gray-400 underline hover:text-gray-700">
            공시원문 ↗
          </a>
        )}
      </div>

      {open && (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[420px] text-sm">
            <thead>
              <tr className="border-b text-left text-[11px] text-gray-400">
                <th className="py-1 pr-2">항목</th>
                <th className="py-1 pr-2">구분</th>
                <th className="py-1 pr-2 text-right">당기</th>
                <th className="py-1 text-right">전기</th>
              </tr>
            </thead>
            <tbody>
              {cn.items.map((it, i) => (
                <tr key={i} className="border-b border-gray-100">
                  <td className="py-1 pr-2 text-gray-800">{it.name}</td>
                  <td className="py-1 pr-2 text-[11px]" style={{ color: CAT_COLOR[it.cat] ?? "#868e96" }}>{it.cat}</td>
                  <td className="py-1 pr-2 text-right tabular-nums">{it.amount_eok.toLocaleString("ko-KR")}억</td>
                  <td className="py-1 text-right tabular-nums text-gray-500">
                    {it.prev_eok != null ? `${it.prev_eok.toLocaleString("ko-KR")}억` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <button onClick={() => setOpen(!open)} className="mt-1 text-[11px] text-gray-500 hover:text-gray-800">
        {open ? "▾ 접기" : `▸ 성격별 항목 ${cn.items.length}개 전체`}
      </button>
    </section>
  );
}

// ③-3 단가·물량 실측 (B3·B4) — 사업보고서 「사업의 내용」.
// 금액은 다듬을 수 있어도 **물량은 다듬기 어렵다**. 그래서 매출 검증의 기준선이 된다.
function ChgChip({ v }: { v?: number | null }) {
  if (v == null) return <span className="text-[11px] text-gray-300">—</span>;
  const up = v > 0;
  return (
    <span className="whitespace-nowrap text-[11px] font-semibold" style={{ color: up ? "#c92a2a" : v < 0 ? "#1971c2" : "#868e96" }}>
      {up ? "▲" : v < 0 ? "▼" : "→"} {v > 0 ? "+" : ""}{(v * 100).toFixed(1)}%
    </span>
  );
}

function BusinessSection({ biz }: { biz: CCMBusiness }) {
  const [open, setOpen] = useState(false);
  const util = biz.utilization[0];
  const out = biz.output_series[0];
  const mat = biz.price_trend.find((p) => p.scope === "원재료");
  const prod = biz.price_trend.find((p) => p.scope === "제품");

  return (
    <section>
      <h3 className="mb-1 text-sm font-bold text-gray-700">
        ③-3 단가·물량 <span className="font-normal" style={{ color: GREEN }}>실측</span>
        <span className="font-normal text-gray-400"> — 사업보고서 「사업의 내용」(공시 단가·생산실적)</span>
      </h3>

      {util && util.items.length > 0 && (
        <div className="mb-1 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-gray-700">
          <span className="font-semibold text-gray-500">가동률:</span>
          {util.items.filter((it) => !it.is_total).slice(0, 5).map((it, i) => (
            <span key={i}>
              {it.group && <span className="text-gray-400">{it.group} · </span>}
              {it.name}{" "}
              <b style={{ color: it.utilization_pct >= 80 ? GREEN : it.utilization_pct >= 60 ? "#b8860b" : "#c92a2a" }}>
                {it.utilization_pct}%
              </b>
              {it.capacity != null && it.output != null && (
                <span className="text-gray-400"> ({it.output.toLocaleString("ko-KR")}/{it.capacity.toLocaleString("ko-KR")} {util.unit ?? ""})</span>
              )}
            </span>
          ))}
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        {[{ blk: out, title: "생산실적", unitLabel: out?.unit },
          { blk: mat, title: "원재료 매입단가", unitLabel: mat?.unit },
          { blk: prod, title: "제품 판매단가", unitLabel: prod?.unit }]
          .filter((x) => x.blk && x.blk.items.length > 0)
          .map((x, i) => (
            <div key={i}>
              <div className="text-[11px] text-gray-400">
                {x.title}{x.unitLabel ? ` (${x.unitLabel})` : ""}
              </div>
              <table className="w-full text-sm">
                <tbody>
                  {(open ? x.blk!.items : x.blk!.items.slice(0, 5)).map((it, j) => (
                    <tr key={j} className="border-b border-gray-100">
                      <td className="py-1 pr-2 text-gray-800">
                        {it.name}
                        {it.group && <span className="ml-1 text-[11px] text-gray-400">{it.group}</span>}
                      </td>
                      <td className="py-1 pr-2 text-right tabular-nums text-gray-600">
                        {it.latest != null ? it.latest.toLocaleString("ko-KR") : "—"}
                        {it.unit && <span className="ml-1 text-[11px] text-gray-400">{it.unit}</span>}
                      </td>
                      <td className="py-1 text-right"><ChgChip v={it.chg_1y} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
      </div>

      <div className="mt-1 flex flex-wrap items-center gap-x-3 text-[11px] text-gray-400">
        <button onClick={() => setOpen(!open)} className="text-gray-500 hover:text-gray-800">
          {open ? "▾ 접기" : "▸ 전체 보기"}
        </button>
        <span>{biz.note}</span>
        {out?.dropped_rows ? <span>· 파싱 불확실 {out.dropped_rows}행 제외</span> : null}
      </div>
    </section>
  );
}

// ⑥ 인건비·노동생산성 (W1) — DART 「직원 등의 현황」 법정 공시 실측
function LaborSection({ labor }: { labor: CCMLabor }) {
  const cur = labor.current;
  if (!cur) {
    return (
      <section className="rounded border border-gray-200 p-3">
        <h3 className="mb-1 text-sm font-bold text-gray-700">⑥ 인건비·노동생산성</h3>
        <p className="text-[12px] text-gray-400">
          {labor.coverage === "no-key"
            ? "DART_API_KEY 미설정 — 직원현황 실측 불가."
            : "이 회사의 직원현황 공시를 찾지 못했습니다."}
        </p>
      </section>
    );
  }
  const eok = (v: number | null | undefined) => (v != null ? `${Math.round(v / 1e8).toLocaleString("ko-KR")}억` : "—");
  const man = (v: number | null | undefined) => (v != null ? `${Math.round(v / 1e4).toLocaleString("ko-KR")}만원` : "—");
  const prodCur = labor.productivity[0];

  return (
    <section>
      <h3 className="mb-1 text-sm font-bold text-gray-700">
        ⑥ 인건비·노동생산성 <span className="font-normal text-gray-400">(사람값 — DART 실측)</span>
      </h3>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-gray-700">
        <span>직원 <b>{cur.headcount?.toLocaleString("ko-KR") ?? "—"}명</b></span>
        <span>
          1인평균 <b style={{ color: GREEN }}>{man(cur.avg_salary)}</b>
          {cur.avg_salary_disclosed != null && (
            <span className="ml-1 text-[11px] text-gray-400">(공시 {man(cur.avg_salary_disclosed)})</span>
          )}
        </span>
        <span>총인건비 <b>{eok(cur.annual_labor)}</b></span>
        {cur.mfg_ratio != null ? (
          <span>생산부문 <b>{pct(cur.mfg_ratio, 0)}</b> → 제조노무비 <b>{cur.mfg_labor_eok?.toLocaleString("ko-KR") ?? "—"}억</b></span>
        ) : (
          <span className="text-[11px] text-gray-400">제조노무비 분리 불가 — {cur.mfg_basis}</span>
        )}
        {cur.hourly_cost != null && <span className="text-gray-500">1인시 {won(cur.hourly_cost)}</span>}
        <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-500">FY{cur.year} · {cur.source}</span>
      </div>

      {labor.consolidated && (
        <div className="mt-1 text-[12px] text-gray-600">
          연결 총인건비 <b>{labor.consolidated.consolidated_labor_eok.toLocaleString("ko-KR")}억</b>
          <span className="text-gray-400"> (주석 실측)</span> vs 제출법인 공시{" "}
          <b>{labor.consolidated.disclosed_domestic_eok.toLocaleString("ko-KR")}억</b>
          {labor.consolidated.subsidiary_share != null && (
            <span> → 자회사(국내·해외) 몫 <b>{pct(labor.consolidated.subsidiary_share, 0)}</b></span>
          )}
        </div>
      )}

      {prodCur && (
        <div className="mt-1 flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-gray-600">
          <span>인당매출 <b>{prodCur.rev_per_head_eok}억</b></span>
          {prodCur.op_per_head_eok != null && <span>인당영익 <b>{prodCur.op_per_head_eok}억</b></span>}
          {prodCur.labor_to_revenue != null && <span>인건비/매출 <b>{pct(prodCur.labor_to_revenue)}</b></span>}
          {labor.productivity.length >= 2 && (
            <span className="text-gray-400">
              (3년 인당매출 {[...labor.productivity].reverse().map((p) => p.rev_per_head_eok).join(" → ")})
            </span>
          )}
        </div>
      )}

      {cur.by_segment.length > 1 && (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[480px] text-sm">
            <thead>
              <tr className="border-b text-left text-[11px] text-gray-400">
                <th className="py-1 pr-2">사업부문</th>
                <th className="py-1 pr-2">구분</th>
                <th className="py-1 pr-2 text-right">인원</th>
                <th className="py-1 pr-2 text-right">1인평균</th>
                <th className="py-1 pr-2 text-right">근속</th>
                <th className="py-1 text-right">계약직</th>
              </tr>
            </thead>
            <tbody>
              {cur.by_segment.slice(0, 8).map((s, i) => (
                <tr key={i} className="border-b border-gray-100">
                  <td className="py-1 pr-2 text-gray-800">{s.name}</td>
                  <td className="py-1 pr-2 text-[11px]" style={{ color: s.kind === "생산" ? GREEN : "#868e96" }}>{s.kind}</td>
                  <td className="py-1 pr-2 text-right tabular-nums">{s.headcount?.toLocaleString("ko-KR") ?? "—"}</td>
                  <td className="py-1 pr-2 text-right tabular-nums">{man(s.avg_salary)}</td>
                  <td className="py-1 pr-2 text-right tabular-nums text-gray-500">{s.tenure != null ? `${s.tenure}년` : "—"}</td>
                  <td className="py-1 text-right tabular-nums text-gray-500">{s.contract?.toLocaleString("ko-KR") ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {labor.flags.length > 0 && (
        <div className="mt-2 space-y-1">
          {labor.flags.map((f, i) => (
            <div
              key={i}
              className="rounded border px-2 py-1 text-[12px]"
              style={{
                borderColor: f.severity === "alert" ? "#f1aeae" : f.severity === "warn" ? "#f0d5a8" : "#e5e7eb",
                background: f.severity === "alert" ? "#fdf2f2" : f.severity === "warn" ? "#fdf8ef" : "#fafafa",
              }}
            >
              <b style={{ color: f.severity === "alert" ? "#c92a2a" : f.severity === "warn" ? "#b8860b" : "#6b7280" }}>
                {f.severity === "info" ? "" : "⚠ "}{f.type}
              </b>
              <span className="ml-1 text-gray-700">{f.detail}</span>
              <div className="text-[11px] text-gray-500">{f.why}</div>
            </div>
          ))}
        </div>
      )}

      <ul className="mt-1 list-disc pl-5 text-[11px] text-gray-400">
        {labor.assumptions.map((a, i) => <li key={i}>{a}</li>)}
      </ul>
    </section>
  );
}

// 감사보고서 원문에서 온 항목(R*)은 '정상'이라도 항상 보여준다 — 감사의견과 KAM은
// 그 자체가 정보(감사인이 어디를 위험하게 봤는지)라서 접어두면 안 된다.
function AuditOpinionLine({ checks }: { checks: CCMStatementCheck[] }) {
  const op = checks.find((c) => c.code === "R1");
  const kam = checks.find((c) => c.code === "R5");
  const gc = checks.find((c) => c.code === "R2");
  if (!op && !kam && !gc) return null;
  return (
    <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px]">
      {op && (
        <span>
          감사의견{" "}
          <b style={{ color: op.status === "ok" ? GREEN : "#c92a2a" }}>{op.detail}</b>
        </span>
      )}
      {gc && <span style={{ color: "#c92a2a" }} className="font-semibold">계속기업 불확실성</span>}
      {kam && <span className="text-gray-600">핵심감사사항: {kam.detail.replace(/^\d+건 — /, "")}</span>}
    </div>
  );
}

// ⑦ 재무제표 3종 감사 — 구비 점검(커버리지) + 정합성 검증(조작 탐지)
function StatementAuditSection({ audit }: { audit: CCMStatementAudit }) {
  const [open, setOpen] = useState(false);
  if (!audit.available) {
    return (
      <section className="rounded border border-gray-200 p-3">
        <h3 className="mb-1 text-sm font-bold text-gray-700">⑦ 재무제표 3종 감사</h3>
        <p className="text-[12px] text-amber-600">{audit.verdict}</p>
      </section>
    );
  }
  const fails = audit.checks.filter((c) => c.status === "fail");
  const warns = audit.checks.filter((c) => c.status === "warn");
  const color = fails.length ? "#c92a2a" : warns.length ? "#b8860b" : GREEN;
  const shown = open ? audit.checks : [...fails, ...warns].slice(0, 4);

  return (
    <section>
      <h3 className="mb-1 text-sm font-bold text-gray-700">
        ⑦ 재무제표 3종 감사 <span className="font-normal text-gray-400">(구비 점검 + 정합성 = 조작 탐지)</span>
      </h3>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px]">
        {audit.statements.filter((s) => ["BS", "IS", "CIS", "CF"].includes(s.sj_div)).map((s) => (
          <span key={s.sj_div} style={{ color: s.ok ? GREEN : "#c92a2a" }}>
            {s.ok ? "●" : "○"} {s.label}
            <span className="ml-1 text-gray-400">
              {s.ok ? `${s.n_years}개년 · ${s.n_accounts}계정` : "없음"}
            </span>
          </span>
        ))}
        <span className="ml-auto rounded px-2 py-0.5 text-[12px] font-bold" style={{ color, background: "#f4f4f5" }}>
          신뢰도 {audit.score}/100
        </span>
      </div>
      <p className="mt-1 text-[12px] font-semibold" style={{ color }}>{audit.verdict}</p>
      <AuditOpinionLine checks={audit.checks} />

      {shown.length > 0 && (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="border-b text-left text-[11px] text-gray-400">
                <th className="py-1 pr-2">검증</th>
                <th className="py-1 pr-2">연도</th>
                <th className="py-1 pr-2">결과</th>
                <th className="py-1">내용</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((c, i) => {
                const cc = c.status === "fail" ? "#c92a2a" : c.status === "warn" ? "#b8860b" : GREEN;
                return (
                  <tr key={i} className="border-b border-gray-100 align-top">
                    <td className="py-1 pr-2 text-gray-800">{c.label}</td>
                    <td className="py-1 pr-2 tabular-nums text-gray-500">{c.year ?? "—"}</td>
                    <td className="py-1 pr-2 font-semibold" style={{ color: cc }}>
                      {c.status === "fail" ? "이상" : c.status === "warn" ? "관찰" : "정상"}
                    </td>
                    <td className="py-1 text-[12px] text-gray-600">
                      {c.detail}
                      {c.why && <div className="text-[11px] text-gray-400">{c.why}</div>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <button onClick={() => setOpen(!open)} className="mt-1 text-[11px] text-gray-500 hover:text-gray-800">
        {open ? "▾ 접기" : `▸ 전체 검증 ${audit.checks.length}건 보기`}
      </button>
      <p className="mt-1 text-[11px] text-gray-400">{audit.note}</p>
    </section>
  );
}

// ④ 결합원가 배분 (C3) — 기본 상대판매가치법, 부산품이 있으면 순실현가치법 보조
function JointAllocationSection({ ja, edu }: { ja: CCMJointAllocation; edu: CostingEducation | null }) {
  const [alt, setAlt] = useState(false);          // false = 기본값(상대판매가치법)
  const altOn = alt && ja.alt.available;
  const altBy = new Map(ja.alt.products.map((p) => [p.name, p]));

  return (
    <section>
      <h3 className="mb-1 text-sm font-bold text-gray-700">
        ④ 결합원가 배분 <span className="font-normal text-gray-400">(연산품 — {ja.method_basis})</span>
        <Edu k="joint_allocation" edu={edu} />
      </h3>

      <div className="mb-1 flex flex-wrap items-center gap-2 text-[12px]">
        <button
          onClick={() => setAlt(false)}
          className="rounded border px-2 py-0.5"
          style={{ borderColor: altOn ? "#d0d5dd" : GREEN, color: altOn ? "#868e96" : GREEN, fontWeight: altOn ? 400 : 700 }}
        >
          상대판매가치법 <span className="text-[10px]">(기본)</span>
        </button>
        <button
          onClick={() => ja.alt.available && setAlt(true)}
          disabled={!ja.alt.available}
          className="rounded border px-2 py-0.5 disabled:cursor-not-allowed disabled:opacity-50"
          style={{ borderColor: altOn ? GREEN : "#d0d5dd", color: altOn ? GREEN : "#868e96", fontWeight: altOn ? 700 : 400 }}
          title={ja.alt.available ? ja.alt.note : ja.alt.reason}
        >
          {ja.alt.method}
        </button>
        <span className="text-gray-400">
          결합원가 {ja.joint_cost_eok.toLocaleString("ko-KR")}억
          {altOn && ` → 부산물 NRV ${ja.alt.byproduct_nrv_eok?.toLocaleString("ko-KR")}억 차감 → ${ja.alt.joint_cost_after_eok?.toLocaleString("ko-KR")}억`}
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead>
            <tr className="border-b text-left text-[11px] text-gray-400">
              <th className="py-1 pr-2">품목</th>
              <th className="py-1 pr-2">구분<Edu k="byproduct" edu={edu} /></th>
              <th className="py-1 pr-2 text-right">매출비중</th>
              <th className="py-1 pr-2 text-right">매출(억)</th>
              <th className="py-1 pr-2 text-right">배분 결합원가(억)</th>
              <th className="py-1 text-right">매출총이익률</th>
            </tr>
          </thead>
          <tbody>
            {ja.products.map((p, i) => {
              const a = altBy.get(p.name);
              const alloc = altOn && a ? a.alloc_cogs_eok : p.alloc_cogs_eok;
              const gm = altOn && a ? a.gross_margin_pct : p.gross_margin_pct;
              return (
                <tr key={i} className="border-b border-gray-100">
                  <td className="py-1 pr-2 text-gray-800">{p.name}</td>
                  <td className="py-1 pr-2">
                    <span
                      className="rounded px-1 text-[10px] font-semibold"
                      style={p.kind === "부산품"
                        ? { color: "#7048e8", background: "#f0ebfd" }
                        : { color: GREEN, background: "#e9f3ee" }}
                    >
                      {p.kind}
                    </span>
                  </td>
                  <td className="py-1 pr-2 text-right tabular-nums">{p.sales_pct}%</td>
                  <td className="py-1 pr-2 text-right tabular-nums text-gray-600">{p.sales_eok.toLocaleString("ko-KR")}</td>
                  <td className="py-1 pr-2 text-right tabular-nums">
                    {alloc.toLocaleString("ko-KR")}
                    {altOn && a && a.delta_eok !== 0 && (
                      <span className="ml-1 text-[10px]" style={{ color: a.delta_eok < 0 ? "#1971c2" : "#c92a2a" }}>
                        ({a.delta_eok > 0 ? "+" : ""}{a.delta_eok.toLocaleString("ko-KR")})
                      </span>
                    )}
                  </td>
                  <td className="py-1 text-right tabular-nums font-semibold" style={{ color: (gm ?? 0) >= 0 ? GREEN : "#c92a2a" }}>
                    {gm != null ? `${gm}%` : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-1 text-[11px] text-gray-400">{ja.source}</p>
      <ul className="mt-1 list-disc pl-5 text-[11px] text-gray-500">
        {ja.caveats.map((c, i) => <li key={i}>{c}</li>)}
        {!ja.alt.available && ja.alt.reason && <li>{ja.alt.reason}</li>}
        {altOn && ja.alt.note && <li>{ja.alt.note}</li>}
      </ul>
    </section>
  );
}

// ⚪ 원가회계 해설 (C5) — 분석 화면 하단 접이식 카드(별도 탭으로 빼지 않음)
function CostingEduCards({ edu }: { edu: CostingEducation | null }) {
  const [open, setOpen] = useState(false);
  if (!edu) return null;
  return (
    <section>
      <button onClick={() => setOpen(!open)} className="text-sm font-semibold text-gray-600 hover:text-gray-900">
        {open ? "▾" : "▸"} 원가회계 해설 — 이 화면이 못 계산하는 것과 그 이유
      </button>
      {open && (
        <div className="mt-2 space-y-3">
          {edu.cards.map((c) => (
            <div key={c.id} className="rounded border border-gray-200 p-3">
              <div className="flex flex-wrap items-baseline gap-2">
                <h4 className="text-sm font-bold text-gray-700">{c.title}</h4>
                <span className="text-[11px] text-gray-400">{c.level}</span>
              </div>
              <div className="mt-1 space-y-0.5 text-[12px] leading-relaxed text-gray-600">
                {c.body.map((line, i) => <p key={i}>{line}</p>)}
              </div>
              {c.table && (
                <div className="mt-2 overflow-x-auto">
                  <table className="w-full min-w-[420px] text-[12px]">
                    <thead>
                      <tr className="border-b text-left text-[11px] text-gray-400">
                        {c.table.head.map((h, i) => <th key={i} className="py-1 pr-3">{h}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {c.table.rows.map((row, i) => (
                        <tr key={i} className="border-b border-gray-100">
                          {row.map((cell, j) => (
                            <td key={j} className={`py-1 pr-3 ${j === 0 ? "text-gray-700" : "tabular-nums text-gray-600"}`}>{cell}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {c.footer && (
                <ul className="mt-2 list-disc pl-5 text-[11px] text-gray-500">
                  {c.footer.map((f, i) => <li key={i}>{f}</li>)}
                </ul>
              )}
            </div>
          ))}
          <p className="text-[11px] text-gray-400">{edu.note}</p>
        </div>
      )}
    </section>
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
      <h3 className="mb-1 text-sm font-bold text-gray-700">⑥ 애널리스트 리포트 취합 <span className="font-normal text-gray-400">(원문 링크 · 내용 복제 없음)</span></h3>
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
