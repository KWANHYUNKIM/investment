"use client";

import { useEffect, useState } from "react";
import { api, UEProduct, UnitEconomics as UE, UEWaterfallItem } from "@/lib/api";

const GREEN = "#217346";

// 워터폴 세그먼트 색 (소비자가 → 유통 → 원재료 → 가공 → 판관 → 이익)
const KIND_COLOR: Record<string, string> = {
  channel: "#adb5bd",
  material: "#40916c",
  process: "#74c69d",
  sga: "#f4a259",
  profit: "#1b4332",
};
const KIND_LABEL: Record<string, string> = {
  channel: "유통", material: "원재료", process: "가공비", sga: "판관비", profit: "영업이익",
};

function won(v: number): string {
  return `${Math.round(v).toLocaleString("ko-KR")}원`;
}

// 원자재 방향 칩: 원가 관점(up=악재 빨강, down=호재 파랑)
function DirChip({ dir, chg }: { dir?: string | null; chg?: number | null }) {
  if (!dir || chg == null) return null;
  const up = dir === "up";
  const flat = dir === "flat";
  const color = flat ? "#868e96" : up ? "#c92a2a" : "#1971c2";
  const arrow = flat ? "→" : up ? "▲" : "▼";
  return (
    <span style={{ color }} className="ml-1 whitespace-nowrap text-[11px] font-semibold">
      {arrow} 원가 {up ? "↑" : flat ? "―" : "↓"} {chg > 0 ? "+" : ""}{(chg * 100).toFixed(0)}%
    </span>
  );
}

export function UnitEconomics() {
  const [products, setProducts] = useState<UEProduct[]>([]);
  const [sel, setSel] = useState<string>("");
  const [data, setData] = useState<UE | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [sectorFilter, setSectorFilter] = useState<string>("전체");

  useEffect(() => {
    let alive = true;
    api.unitEconomicsProducts()
      .then((r) => {
        if (!alive) return;
        setProducts(r.products);
        if (r.products.length) setSel(r.products[0].id);
      })
      .catch((e) => alive && setErr(e?.message ?? "제품 목록 실패"));
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    if (!sel) return;
    let alive = true;
    setLoading(true);
    setErr("");
    api.unitEconomics(sel)
      .then((r) => alive && setData(r))
      .catch((e) => alive && setErr(e?.message ?? "원가분해 실패"))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [sel]);

  const s = data?.summary;
  const retail = s?.retail_price ?? 1;

  // 업종별 그룹핑 (등장 순서 유지) + 업종 필터
  const sectors = Array.from(new Set(products.map((p) => p.sector)));
  const visible = sectorFilter === "전체" ? products : products.filter((p) => p.sector === sectorFilter);
  const grouped: [string, UEProduct[]][] = [];
  for (const p of visible) {
    let g = grouped.find((x) => x[0] === p.sector);
    if (!g) { g = [p.sector, []]; grouped.push(g); }
    g[1].push(p);
  }

  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 bg-[#217346] px-4 py-2 text-white">
        <span className="text-sm font-semibold">
          제품 원가분해.xlsx — 이 물건 하나 팔면 얼마 남나
          <span className="ml-2 text-[11px] font-normal text-white/70">
            {products.length}개 제품 · {sectors.length}개 업종
          </span>
        </span>
        <div className="flex items-center gap-1.5">
          <select
            value={sectorFilter}
            onChange={(e) => {
              const sec = e.target.value;
              setSectorFilter(sec);
              const first = products.find((p) => sec === "전체" || p.sector === sec);
              if (first && (sec !== "전체")) setSel(first.id);
            }}
            className="rounded border border-white/30 bg-white/10 px-2 py-1 text-xs text-white outline-none [&>option]:text-black"
          >
            <option key="all" value="전체">🗂 전체 업종</option>
            {sectors.filter(Boolean).map((sec) => (
              <option key={sec} value={sec}>{sec}</option>
            ))}
          </select>
          <select
            value={sel}
            onChange={(e) => setSel(e.target.value)}
            className="max-w-[240px] rounded border border-white/30 bg-white/10 px-2 py-1 text-xs text-white outline-none [&>optgroup]:text-black [&>option]:text-black"
          >
            {grouped.map(([sec, ps]) => (
              <optgroup key={sec || "기타"} label={sec || "기타"}>
                {ps.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.company} · {p.product}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>
      </div>

      {err && !data ? (
        <div className="py-20 text-center text-sm text-rose-600">{err}</div>
      ) : !data || !s ? (
        <div className="flex flex-col items-center gap-3 py-24 text-sm text-[#888]">
          <span className="h-7 w-7 animate-spin rounded-full border-2 border-[#d0d0d0] border-t-[#217346]" />
          원가 분해 중…
        </div>
      ) : (
        <div className="max-h-[calc(100vh-190px)] overflow-auto p-4">
          {loading && <div className="mb-2 text-xs text-[#888]">갱신 중…</div>}

          {/* 헤더 요약 */}
          <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-lg font-bold text-[#212529]">
              {data.product.company} · {data.product.product}
            </span>
            <span className="text-xs text-[#868e96]">
              {data.product.unit} · {data.product.channel} · 기준 {data.as_of}
            </span>
            <span className="rounded bg-[#e9f5ee] px-2 py-0.5 text-[11px] font-medium text-[#217346]">
              원가율·이익률 {data.basis.source}{data.basis.year ? ` (${data.basis.year})` : ""}
            </span>
          </div>

          {/* 핵심 스탯 */}
          <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="소비자가" value={won(s.retail_price)} />
            <Stat label="회사 출고가(매출)" value={won(s.factory_price)} sub={`${s.channel_label} ${won(s.distribution_take)}`} />
            <Stat label="매출원가율" value={`${(s.cogs_ratio * 100).toFixed(1)}%`} />
            <Stat label="봉지당 영업이익" value={won(s.profit_per_unit)} highlight sub={`영업이익률 ${(s.op_margin * 100).toFixed(1)}%`} />
          </div>

          {/* 워터폴 바 */}
          <div className="mb-1 text-xs font-semibold text-[#495057]">소비자가 {won(retail)}의 여정</div>
          <div className="mb-2 flex h-9 w-full overflow-hidden rounded border border-[#dee2e6]">
            {data.waterfall.map((w, i) => (
              <div
                key={i}
                title={`${w.item} · ${won(w.won)} (${w.pct_of_retail}%)`}
                style={{ width: `${(w.won / retail) * 100}%`, background: KIND_COLOR[w.kind] }}
                className="h-full"
              />
            ))}
          </div>
          <div className="mb-4 flex flex-wrap gap-x-3 gap-y-1">
            {Object.entries(KIND_LABEL).map(([k, label]) => (
              <span key={k} className="flex items-center gap-1 text-[11px] text-[#495057]">
                <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: KIND_COLOR[k] }} />
                {label}
              </span>
            ))}
          </div>

          {/* 항목별 분해 테이블 */}
          <table className="mb-4 w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-[#dee2e6] text-left text-xs text-[#868e96]">
                <th className="py-1.5 font-medium">항목</th>
                <th className="py-1.5 text-right font-medium">금액</th>
                <th className="py-1.5 text-right font-medium">소비자가 대비</th>
                <th className="py-1.5 pl-3 font-medium">원자재 시세</th>
              </tr>
            </thead>
            <tbody>
              {data.waterfall.map((w: UEWaterfallItem, i) => (
                <tr key={i} className="border-b border-[#f1f3f5]">
                  <td className="py-1.5">
                    <span className="mr-1.5 inline-block h-2 w-2 rounded-sm align-middle" style={{ background: KIND_COLOR[w.kind] }} />
                    <span className={w.kind === "profit" ? "font-bold text-[#1b4332]" : ""}>{w.item}</span>
                  </td>
                  <td className="py-1.5 text-right tabular-nums">{won(w.won)}</td>
                  <td className="py-1.5 text-right tabular-nums text-[#868e96]">{w.pct_of_retail}%</td>
                  <td className="py-1.5 pl-3">
                    {w.commodity ? (
                      <span className="text-[12px] text-[#495057]">{w.commodity}<DirChip dir={w.direction} chg={w.chg_1y} /></span>
                    ) : (
                      <span className="text-[12px] text-[#ced4da]">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* 마진 모멘텀 (핵심 결론) */}
          <MomentumCard m={data.momentum} />

          {/* 민감도 */}
          <div className="mt-4">
            <div className="mb-1 text-xs font-semibold text-[#495057]">원자재 ±10% → 봉지당 영업이익 변화</div>
            <div className="flex flex-col gap-1">
              {data.sensitivity.map((sv, i) => (
                <div key={i} className="flex items-center gap-2 text-[13px]">
                  <span className="w-32 shrink-0 truncate text-[#495057]">{sv.item}</span>
                  <div className="relative h-4 flex-1 rounded bg-[#f1f3f5]">
                    <div
                      className="absolute right-1/2 h-4 rounded-l bg-[#ffc9c9]"
                      style={{ width: `${Math.min(50, Math.abs(sv.op_delta_pct_per_10pct ?? 0) / 2)}%` }}
                    />
                  </div>
                  <span className="w-40 shrink-0 text-right tabular-nums text-[#c92a2a]">
                    {sv.op_delta_per_10pct}원 ({sv.op_delta_pct_per_10pct}%)
                  </span>
                </div>
              ))}
            </div>
          </div>

          <p className="mt-4 rounded bg-[#f8f9fa] p-2.5 text-[11px] leading-relaxed text-[#868e96]">
            💡 {data.product.note}
            <br />
            ⚠️ SKU별 원가는 공시되지 않음 → 소비자가·유통마진·제품 구성은 추정, 원가율·영업이익률은 DART 재무 기반.
            정밀화는 제조원가명세서 대조 필요.
          </p>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, sub, highlight }: { label: string; value: string; sub?: string; highlight?: boolean }) {
  return (
    <div className={`rounded border p-2 ${highlight ? "border-[#217346] bg-[#e9f5ee]" : "border-[#e9ecef] bg-[#fafafa]"}`}>
      <div className="text-[11px] text-[#868e96]">{label}</div>
      <div className={`text-base font-bold tabular-nums ${highlight ? "text-[#217346]" : "text-[#212529]"}`}>{value}</div>
      {sub && <div className="text-[10px] text-[#adb5bd]">{sub}</div>}
    </div>
  );
}

function MomentumCard({ m }: { m: UE["momentum"] }) {
  const loss = m.op_before <= 0; // 적자 기업
  const good = !loss && (m.op_change_pct ?? 0) > 0;
  const color = loss ? "#e8590c" : good ? "#1971c2" : "#c92a2a";
  const bg = loss ? "#fff4e6" : good ? "#e7f5ff" : "#fff5f5";
  return (
    <div className="rounded-md border p-3" style={{ borderColor: color, background: bg }}>
      <div className="mb-1 text-xs font-semibold" style={{ color }}>
        현재 원자재 추세가 이어지면 (판가 고정 가정)
      </div>
      <div className="flex flex-wrap items-baseline gap-x-2 text-sm">
        <span className="text-[#495057]">단위당 영업이익</span>
        <span className="font-bold tabular-nums text-[#495057]">{won(m.op_before)}</span>
        <span className="text-[#adb5bd]">→</span>
        <span className="text-lg font-bold tabular-nums" style={{ color }}>{won(m.op_after)}</span>
        {m.op_change_pct != null && (
          <span className="font-semibold tabular-nums" style={{ color }}>
            ({m.op_change_pct > 0 ? "+" : ""}{m.op_change_pct}%)
          </span>
        )}
      </div>
      <div className="mt-1 text-[12px] font-medium" style={{ color }}>{m.verdict}</div>
    </div>
  );
}
