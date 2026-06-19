"use client";

import { useEffect, useState } from "react";
import { api, InstitutionalFlow as IF, InstFlowStock } from "@/lib/api";

const RED = "#c92a2a";
const BLUE = "#1971c2";

function eok(v: number | null | undefined): string {
  if (v == null) return "—";
  const s = Math.abs(v) >= 10000 ? `${(Math.abs(v) / 10000).toFixed(2)}조` : `${Math.round(Math.abs(v)).toLocaleString("ko-KR")}억`;
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${s}`;
}
function flowStyle(v: number | null | undefined): React.CSSProperties {
  if (v == null) return { color: "#bbb" };
  return { color: v > 0 ? RED : v < 0 ? BLUE : "#666", fontWeight: 700 };
}
function pct(v: number | null | undefined): string {
  return v == null ? "—" : `${v > 0 ? "+" : ""}${v}%`;
}
function behaviorColor(b: string): string {
  if (b.includes("손절")) return "#15467a";
  if (b.includes("이탈")) return BLUE;
  return RED; // 매집/저가매집
}

export function InstitutionalFlow() {
  const [d, setD] = useState<IF | null>(null);
  const [tab, setTab] = useState<"acc" | "dist">("dist");
  const [err, setErr] = useState("");

  useEffect(() => {
    api.institutional().then(setD).catch((e) => setErr(e?.message ?? "기관 수급을 불러오지 못했습니다."));
  }, []);

  if (err) return <Sheet right={null}><div className="py-20 text-center text-sm text-rose-600">{err}</div></Sheet>;
  if (!d) return <Sheet right={null}><div className="flex flex-col items-center gap-3 py-24 text-sm text-[#888]"><span className="h-7 w-7 animate-spin rounded-full border-2 border-[#d0d0d0] border-t-[#217346]" />기관 수급 시계열 분석 중…</div></Sheet>;

  const rows = tab === "acc" ? d.accumulating : d.distributing;

  return (
    <Sheet right={<span className="text-xs text-white/80">최근 {d.window_days}거래일 누적 · 분석 {d.universe.toLocaleString("ko-KR")}종목 · {d.as_of?.slice(5)}</span>}>
      <div className="space-y-4 bg-[#fafafa] p-4">
        <div className="rounded border border-[#d0d0d0] bg-white px-4 py-3 text-[13px] leading-relaxed text-[#444] shadow-sm">
          기관은 자금이 <b>무거워</b> 개미와 달리 <b>분할로 들어오고 분할로 빠져나가는 '프로세스'</b>가 있습니다. 어느 기관(연기금·투신 등)인지는 KRX 비공개라 알 수 없지만,
          누적된 <b>기관 순매수 시계열</b>로 <b>언제 많이 담았고 언제 던졌는지</b>와 <b>왜 팔았을지</b>를 주가 흐름·외국인 동반 여부·밸류·모멘텀으로 유추합니다. <span className="text-[#999]">(확정 인과 아님 · 推定)</span>
        </div>

        <div className="flex items-center gap-1 rounded border border-[#d0d0d0] bg-[#eef0ee] px-2 py-1.5">
          <button onClick={() => setTab("dist")} className={`rounded px-3 py-1 text-sm font-semibold ${tab === "dist" ? "bg-[#217346] text-white" : "text-[#555] hover:bg-[#e0e6e0]"}`}>
            기관 이탈·손절 상위 ({d.distributing.length})
          </button>
          <button onClick={() => setTab("acc")} className={`rounded px-3 py-1 text-sm font-semibold ${tab === "acc" ? "bg-[#217346] text-white" : "text-[#555] hover:bg-[#e0e6e0]"}`}>
            기관 매집 상위 ({d.accumulating.length})
          </button>
        </div>

        <div className="space-y-2.5">
          {rows.map((s, i) => <Card key={s.ticker} s={s} rank={i + 1} />)}
          {rows.length === 0 && <div className="py-10 text-center text-sm text-[#888]">해당 구간 데이터가 충분하지 않습니다.</div>}
        </div>

        <p className="px-1 text-center text-[11px] leading-relaxed text-[#999]">
          기관 순매수 금액 = 일별 기관 순매수 수량 × 종가 누적(개인/외국인/기관 중 '기관'). 빨강=순매수(매집)·파랑=순매도(이탈). 매매 사유는 규칙 기반 추정이며 투자 권유가 아닙니다.
        </p>
      </div>
    </Sheet>
  );
}

function Card({ s, rank }: { s: InstFlowStock; rank: number }) {
  const bColor = behaviorColor(s.behavior);
  return (
    <div className="rounded border border-[#e0e0e0] bg-white p-3 shadow-sm">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="text-xs text-[#bbb]">#{rank}</span>
        <span className="text-[15px] font-bold text-[#1f1f1f]">{s.name}</span>
        <span className="font-mono text-[11px] text-[#999]">{s.ticker}</span>
        <span className="rounded px-1.5 py-0.5 text-[10px] font-bold text-white" style={{ background: bColor }}>{s.behavior}</span>
        <span className="ml-auto text-[13px]">기간 기관 <b style={flowStyle(s.net_amt)}>{eok(s.net_amt)}</b></span>
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-[#555]">
        <span>주가 <b style={flowStyle(s.price_chg)}>{pct(s.price_chg)}</b> ({s.days}일)</span>
        <span>외국인 동반 <b style={flowStyle(s.foreign_net)}>{eok(s.foreign_net)}</b></span>
        <span className="text-[#1971c2]">최대 매수 {s.max_buy.date.slice(5)} <b style={{ color: RED }}>{eok(s.max_buy.amt)}</b></span>
        <span className="text-[#1971c2]">최대 매도 {s.max_sell.date.slice(5)} <b style={{ color: BLUE }}>{eok(s.max_sell.amt)}</b></span>
        {s.per != null && <span className="text-[#999]">PER {s.per}</span>}
        {s.pct_from_high != null && <span className="text-[#999]">고점대비 {s.pct_from_high}%</span>}
      </div>
      <div className="mt-1.5 rounded border-l-2 border-[#217346] bg-[#f1f5f1] px-2.5 py-1.5">
        <span className="text-[11px] font-bold text-[#217346]">왜 {s.net_amt < 0 ? "팔았을까" : "담았을까"} (추정): </span>
        <span className="text-[12px] leading-snug text-[#444]">{s.why.join(" · ")}</span>
      </div>
    </div>
  );
}

function Sheet({ right, children }: { right: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
        <span className="flex items-center gap-2 text-sm font-semibold">기관 추적.xlsx</span>
        {right}
      </div>
      {children}
    </div>
  );
}
