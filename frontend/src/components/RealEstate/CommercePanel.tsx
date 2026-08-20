"use client";

// 지역 상권 — 이 동네가 **무엇을 하는 곳인지**.
//
// 같은 값이라도 성격이 다르면 가격이 다르게 움직인다. 업무지역은 일자리에, 주거지역은
// 학군·교통에 반응한다. 그래서 실거래·관심도를 볼 때 이 배경을 함께 두려는 것이다.
//
// 판정은 업종 구성으로 한다. 사무실이 있어야 존재하는 업종(과학·기술, 시설관리·임대)과
// 사람이 살아야 존재하는 업종(교육, 보건의료, 수리·개인)의 비다. 실측으로 확인했다 —
// 중구 2.86 · 종로 1.74 · 강남 1.69 · 마포 1.27 · 강서 0.83 · 분당 0.61 · 노원 0.36.
//
// 지수를 숨기지 않고 같이 보여준다. "업무지역" 이라는 단어만 주면 근거를 확인할 수 없고,
// 경계 근처(0.7·1.2)에 있는 지역은 라벨 하나로 말할 수 없기 때문이다.

import { useEffect, useState } from "react";
import { api, type RegionCommerce } from "@/lib/api";

const CHAR_COLOR: Record<string, string> = {
  "업무·상업": "#c0392b",
  "혼합": "#e8873a",
  "주거": "#217346",
};

// 막대 색 — 업무 쪽 업종과 생활 쪽 업종을 눈으로 구분되게 한다.
const WORK_CODES = new Set(["M1", "N1"]);
const LIVE_CODES = new Set(["P1", "Q1", "S2"]);

function barColor(code: string): string {
  if (WORK_CODES.has(code)) return "#c0392b";
  if (LIVE_CODES.has(code)) return "#217346";
  return "#9aa0a6";
}

export function CommercePanel({ lawd, region }: { lawd: string; region: string }) {
  const [data, setData] = useState<RegionCommerce | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    api.realestateCommerce(lawd)
      .then((d) => alive && setData(d))
      .catch(() => { /* 배경 정보라 없다고 화면을 막지 않는다 */ });
    return () => { alive = false; };
  }, [lawd]);

  if (!data) return null;

  // 아직 수집 안 된 지역 — '주거' 로 단정하지 않고 진행률을 말한다.
  if (!data.available) {
    return (
      <div className="border-b border-[#eee] bg-[#fcfcfc] px-3 py-1.5 text-[10px] text-[#999]">
        {region} 상권 자료 수집 전 (전체 {data.coverage?.pct ?? 0}%)
      </div>
    );
  }

  const color = CHAR_COLOR[data.character] ?? "#888";
  const sorted = [...data.counts].sort((a, b) => b.share - a.share);

  return (
    <div className="border-b border-[#eee] bg-[#fcfcfc] px-3 py-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between text-[11px]"
      >
        <span className="flex items-center gap-1.5">
          <span className="rounded px-1.5 py-0.5 text-[10px] font-bold text-white"
                style={{ background: color }}>
            {data.character}
          </span>
          <span className="font-bold text-[#555]">
            점포 {data.total.toLocaleString()}개
          </span>
          {data.work_index !== null && (
            <span className="text-[#888]">업무지수 {data.work_index}</span>
          )}
        </span>
        <span className="text-[#aaa]">{open ? "접기" : "업종 구성"}</span>
      </button>

      {open && (
        <div className="mt-1.5">
          {sorted.map((c) => (
            <div key={c.code} className="mb-0.5 flex items-center gap-1.5">
              <span className="w-[68px] shrink-0 truncate text-[10px] text-[#666]">{c.name}</span>
              <div className="h-2.5 flex-1 overflow-hidden rounded-sm bg-[#f0f0f0]">
                {/* 최대 35% 를 가득 찬 것으로 본다 — 100% 기준이면 막대가 전부 납작해진다 */}
                <div className="h-full rounded-sm"
                     style={{ width: `${Math.min(100, (c.share / 35) * 100)}%`,
                              background: barColor(c.code) }} />
              </div>
              <span className="w-[42px] shrink-0 text-right text-[10px] tabular-nums text-[#555]">
                {c.share}%
              </span>
              <span className="w-[52px] shrink-0 text-right text-[10px] tabular-nums text-[#aaa]">
                {c.count.toLocaleString()}
              </span>
            </div>
          ))}
          <div className="mt-1 flex items-center gap-2 text-[9px] text-[#999]">
            <span className="flex items-center gap-0.5">
              <span className="inline-block h-2 w-2 rounded-sm bg-[#c0392b]" />업무 쪽
            </span>
            <span className="flex items-center gap-0.5">
              <span className="inline-block h-2 w-2 rounded-sm bg-[#217346]" />생활 쪽
            </span>
          </div>
          <p className="mt-1 text-[9px] leading-relaxed text-[#999]">{data.note}</p>
        </div>
      )}
    </div>
  );
}
