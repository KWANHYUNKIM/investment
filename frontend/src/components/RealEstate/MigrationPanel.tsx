"use client";

// 인구이동 — 사람이 어디에서 어디로 옮겨 갔는가.
//
// 가격은 결과고 이동은 원인에 가깝다. 계속 들어오는 동네와 계속 빠지는 동네는 같은
// 호가라도 다른 자산이다. 전입신고 전수(행정안전부)라 표본 오차가 없다.
//
// 전체 순이동과 **청년(20~34세) 순이동을 나란히** 둔다. 한 숫자로 뭉치면 "전체는
// 늘었는데 청년은 빠지는" 동네를 못 본다. 그 둘은 임대 수요·상권에 다르게 작용한다.

import { useEffect, useState } from "react";
import { api, type RegionMigration } from "@/lib/api";

const IN = "#c0392b";     // 유입 — 실거래 화면의 상승색과 같은 쪽
const OUT = "#2a6fb5";    // 유출

function signed(n: number): string {
  return `${n > 0 ? "+" : ""}${n.toLocaleString()}`;
}

function Stat({ label, value, sub }: { label: string; value: number; sub: string }) {
  const color = value > 0 ? IN : value < 0 ? OUT : "#888";
  return (
    <div className="flex-1">
      <div className="text-[9px] text-[#999]">{label}</div>
      <div className="text-[13px] font-bold tabular-nums" style={{ color }}>
        {signed(value)}
      </div>
      <div className="text-[9px] text-[#aaa] tabular-nums">{sub}</div>
    </div>
  );
}

export function MigrationPanel({ lawd, region }: { lawd: string; region: string }) {
  const [data, setData] = useState<RegionMigration | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    api.realestateMigration(lawd)
      .then((d) => alive && setData(d))
      .catch(() => { /* 배경 정보라 없다고 화면을 막지 않는다 */ });
    return () => { alive = false; };
  }, [lawd]);

  if (!data) return null;

  if (!data.available) {
    return (
      <div className="border-b border-[#eee] bg-[#fcfcfc] px-3 py-1.5 text-[10px] text-[#999]">
        {region} 인구이동 자료 수집 전
      </div>
    );
  }

  const span = data.months.length;
  // 막대 길이 기준 — 상위 상대의 규모에 맞춘다. 고정값이면 작은 지역이 전부 납작해진다.
  const maxPartner = Math.max(
    1, ...data.inbound.map((b) => b.total), ...data.outbound.map((b) => b.total),
  );

  return (
    <div className="border-b border-[#eee] bg-[#fcfcfc] px-3 py-2">
      <button onClick={() => setOpen((v) => !v)} className="w-full">
        <div className="mb-1 flex items-center justify-between text-[10px] text-[#999]">
          <span>인구이동 · 최근 {span}개월</span>
          <span className="text-[#aaa]">{open ? "접기" : "이동 흐름"}</span>
        </div>
        <div className="flex gap-2 text-left">
          <Stat label="순이동" value={data.net}
                sub={`전입 ${data.in_total.toLocaleString()} / 전출 ${data.out_total.toLocaleString()}`} />
          <Stat label="청년 순이동 (20~34세)" value={data.net_young}
                sub={`전입 ${data.in_young.toLocaleString()} / 전출 ${data.out_young.toLocaleString()}`} />
        </div>
      </button>

      {open && (
        <div className="mt-2">
          {(["inbound", "outbound"] as const).map((side) => {
            const list = data[side];
            if (!list.length) return null;
            const color = side === "inbound" ? IN : OUT;
            return (
              <div key={side} className="mb-1.5">
                <div className="mb-0.5 text-[9px] font-bold" style={{ color }}>
                  {side === "inbound" ? "어디에서 왔나" : "어디로 갔나"}
                </div>
                {list.slice(0, 5).map((b) => (
                  <div key={b.cd} className="mb-0.5 flex items-center gap-1.5">
                    <span className="w-[92px] shrink-0 truncate text-[10px] text-[#666]">
                      {b.name}
                    </span>
                    <div className="h-2.5 flex-1 overflow-hidden rounded-sm bg-[#f0f0f0]">
                      <div className="h-full rounded-sm"
                           style={{ width: `${(b.total / maxPartner) * 100}%`, background: color }} />
                    </div>
                    <span className="w-[46px] shrink-0 text-right text-[10px] tabular-nums text-[#555]">
                      {b.total.toLocaleString()}
                    </span>
                    <span className="w-[46px] shrink-0 text-right text-[10px] tabular-nums text-[#aaa]">
                      청년 {b.young.toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            );
          })}
          <p className="mt-1 text-[9px] leading-relaxed text-[#999]">{data.note}</p>
        </div>
      )}
    </div>
  );
}
