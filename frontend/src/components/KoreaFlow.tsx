"use client";

import { useEffect, useRef, useState } from "react";
import { api, KoreaFlow as KF, KoreaFlowItem, KoreaFlowNews } from "@/lib/api";

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
