"use client";

import { useEffect, useState } from "react";
import { api, CrossAssetLayer, CrossAsset } from "@/lib/api";
import { AssetDetailModal } from "@/components/AssetDetailModal";
import { BLUE, Block, RED, fmtSigned, retStyle } from "./shared";

/* region flags for the global finance feed */
export const REGION_FLAG: Record<string, string> = {
  한국: "",
  미국: "",
  유럽: "",
  중국: "",
  일본: "",
  글로벌: "",
};

/* format a cross-asset value by its unit */
export function assetValue(a: CrossAsset): string {
  if (a.value == null) return "—";
  const v = a.value;
  if (a.unit === "pct") return `${v.toFixed(2)}%`;
  if (a.unit === "usd") return `$${v.toLocaleString("en-US", { maximumFractionDigits: v >= 100 ? 0 : 2 })}`;
  if (a.unit === "krw") return `₩${v.toLocaleString("ko-KR", { maximumFractionDigits: 1 })}`;
  return v.toLocaleString("en-US", { maximumFractionDigits: 2 }); // pt
}

/* 크로스에셋 자금 흐름 — 어느 판으로 현금이 흐르는지 한눈에 (실시간 폴링) */
export const EMPTY_CA: CrossAssetLayer = {
  groups: [],
  count: 0,
  flow: { verdict: "불러오는 중…", tone: "중립", score: 0, desc: "실시간 시세를 불러오는 중입니다.", metrics: { equities: null, crypto: null, gold: null, usdkrw: null }, summary: "" },
};

export function CrossAssetBlock({
  ca: initial,
  live: allowLive,
  reportDate,
}: {
  ca: CrossAssetLayer | null;
  live: boolean;
  reportDate?: string | null;
}) {
  const [ca, setCa] = useState<CrossAssetLayer>(initial ?? EMPTY_CA);
  const [live, setLive] = useState(false);
  const [picked, setPicked] = useState<string | null>(null); // asset key for the drill-in modal

  useEffect(() => {
    // 과거 날짜: 그날 마감값(아카이브)으로 고정 — 실시간 폴링하지 않는다.
    if (!allowLive) {
      setCa(initial ?? EMPTY_CA);
      setLive(false);
      return;
    }
    // 최신(오늘) 날짜만 실시간 갱신.
    let alive = true;
    const load = () =>
      api
        .crossAsset()
        .then((d) => {
          if (alive) {
            setCa(d);
            setLive(true);
          }
        })
        .catch(() => {});
    load(); // refresh immediately on mount …
    const id = setInterval(load, 30000); // … then live every 30초
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [allowLive, initial]);

  // 과거 날짜인데 그 일자의 크로스에셋 스냅샷이 저장돼 있지 않은 경우.
  if (!allowLive && !initial) {
    return (
      <Block label="크로스에셋 자금 흐름 · 미국/글로벌 증시 · 금 · 비트코인" color="#ffe08a" fg="#7a5b00">
        <div className="px-3 py-4 text-sm text-[#999]">
          {reportDate} 일자에는 크로스에셋 데이터가 저장되어 있지 않습니다. (해당 기능 도입 이전 날짜)
        </div>
      </Block>
    );
  }

  const flow = ca.flow;
  const tone = flow.tone === "긍정" ? RED : flow.tone === "부정" ? BLUE : "#666";
  return (
    <Block label="크로스에셋 자금 흐름 · 미국/글로벌 증시 · 금 · 비트코인" color="#ffe08a" fg="#7a5b00">
      {/* money-flow verdict banner */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-[#eee] bg-[#fffaf0] px-3 py-2">
        <span className="rounded-full px-3 py-1 text-sm font-bold text-white" style={{ background: tone }}>
          {flow.verdict}
        </span>
        {allowLive ? (
          <span className="flex items-center gap-1 text-[11px] font-bold" style={{ color: live ? "#2f9e44" : "#aaa" }}>
            <span className={`inline-block h-1.5 w-1.5 rounded-full ${live ? "animate-pulse" : ""}`} style={{ background: live ? "#2f9e44" : "#bbb" }} />
            {live ? "LIVE" : "…"}
            {ca.as_of && <span className="font-normal text-[#999]">{ca.as_of.slice(11)}</span>}
          </span>
        ) : (
          <span className="flex items-center gap-1 rounded bg-[#f0ead6] px-1.5 py-0.5 text-[11px] font-bold text-[#7a5b00]">
            {reportDate} 마감값 (아카이브)
          </span>
        )}
        <span className="text-[15px] text-[#444]">{flow.desc}</span>
        <span className="ml-auto text-[13px] text-[#999]">
          글로벌 증시 {fmtSigned(flow.metrics.equities)} · 암호화폐 {fmtSigned(flow.metrics.crypto)} · 금 {fmtSigned(flow.metrics.gold)} · 원/달러 {fmtSigned(flow.metrics.usdkrw)}
        </span>
      </div>
      <div className="grid sm:grid-cols-2 xl:grid-cols-4">
        {ca.groups.map((g) => (
          <div key={g.group} className="border-b border-r border-[#eee]">
            <div className="bg-[#fafafa] px-3 py-1.5 text-sm font-bold text-[#7a5b00]">{g.group}</div>
            <table className="w-full border-collapse text-[15px]">
              <tbody>
                {g.assets.map((a) => (
                  <tr
                    key={a.key}
                    onClick={() => setPicked(a.key)}
                    className="cursor-pointer hover:bg-[#fff7e6]"
                    title="클릭하면 장 마감 상세가 열립니다"
                  >
                    <td className="border-t border-[#f0f0f0] px-3 py-2 font-medium text-[#1155cc] hover:underline">{a.label}</td>
                    <td className="border-t border-[#f0f0f0] px-2 py-2 text-right tabular-nums text-[#1f1f1f]">
                      {assetValue(a)}
                    </td>
                    <td
                      className="border-t border-[#f0f0f0] px-2 py-2 text-right font-bold tabular-nums"
                      style={retStyle(a.change_pct)}
                    >
                      {a.change_pct != null ? `${a.change_pct > 0 ? "+" : ""}${a.change_pct}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
      <p className="px-3 py-1.5 text-[12px] text-[#999]">
        종목을 클릭하면 그 장이 어떻게 끝났는지(장 마감 OHLC·최근 시세·구성종목) 엑셀로 열립니다. 금리(국채 10년)·원/달러 상승은 위험회피(현금·안전자산 선호), 증시·비트코인 상승은 위험선호 신호로 읽습니다. 시세 FinanceDataReader{allowLive ? " · 30초마다 실시간 갱신(해외장은 지연 시세)." : ` · ${reportDate} 장 마감 기준 저장값(과거 날짜는 실시간 갱신하지 않습니다).`}
      </p>
      {picked && (
        <AssetDetailModal
          assetKey={picked}
          onClose={() => setPicked(null)}
          asOf={allowLive ? undefined : reportDate ?? undefined}
        />
      )}
    </Block>
  );
}
