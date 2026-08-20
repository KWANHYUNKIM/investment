"use client";

// 지역별 부동산 관심도 — 검색량으로 본 '어디가 뜨고 있나'.
//
// 거래량은 관심의 **결과**라 몇 주 늦는다. 계약서를 쓰기까지 시간이 걸리기 때문이다.
// 검색은 그보다 먼저 튄다 — 사기 전에 찾아보므로. 그래서 이 패널이 진짜로 노리는 건
// 순위표가 아니라 **'검색은 올랐는데 거래는 아직 안 붙은 지역'** 이다.
//
// index 를 검색 횟수로 읽으면 안 된다. 데이터랩은 절대값을 주지 않으므로, 모든 요청에
// 같은 앵커 키워드를 끼워 넣고 그 값으로 나눈 '앵커 대비 배수'다. 화면에서도 '배' 로
// 적어 숫자의 정체를 숨기지 않는다.

import { useMemo, useState } from "react";
import { api, type InterestBoard, type RealEstateRegion } from "@/lib/api";
import { useApiData } from "@/lib/useApiData";

const GREEN = "#217346";
const RED = "#c92a2a";

function pct(v: number | null): string {
  if (v === null || !Number.isFinite(v)) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(0)}%`;
}

export function InterestPanel({
  regions,
  onPick,
  onClose,
}: {
  regions: RealEstateRegion[];
  onPick: (lawd: string) => void;
  onClose: () => void;
}) {
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [tab, setTab] = useState<"rank" | "gap">("rank");
  const board = useApiData<InterestBoard>(() => api.realestateInterest(), `${version}`);
  const d = board.data;

  const collect = async () => {
    setBusy(true);
    setMsg("");
    try {
      const r = await api.realestateInterestCollect();
      setMsg(r.started ? "수집을 시작했습니다. 1~2분 뒤 새로고침하세요." : (r.reason || "시작하지 못했습니다."));
      setVersion((v) => v + 1);
    } catch {
      setMsg("수집을 시작하지 못했습니다.");
    } finally {
      setBusy(false);
    }
  };

  // 검색 관심도와 실거래 건수를 같은 지역 위에 놓고, 순위 차이를 본다.
  // 검색 순위가 거래 순위보다 한참 앞서면 '아직 거래로 안 옮겨간 관심'이다.
  const gaps = useMemo(() => {
    if (!d?.items?.length || !regions.length) return [];
    const byTrades = [...regions].sort((a, b) => b.count - a.count);
    const tradeRank = new Map(byTrades.map((r, i) => [r.lawd, i + 1]));
    return d.items
      .filter((it) => tradeRank.has(it.lawd))
      .map((it) => ({ ...it, tradeRank: tradeRank.get(it.lawd)!, gap: tradeRank.get(it.lawd)! - it.rank }))
      .filter((it) => it.gap > 0)
      .sort((a, b) => b.gap - a.gap)
      .slice(0, 30);
  }, [d, regions]);

  const rows = tab === "rank" ? (d?.items ?? []).slice().sort((a, b) => a.rank - b.rank).slice(0, 60) : gaps;

  return (
    <div className="flex h-full w-[320px] flex-col border-l border-[#e0e0e0] bg-white shadow-[-2px_0_10px_rgba(0,0,0,.08)]">
      <div className="flex shrink-0 items-center justify-between border-b border-[#eee] px-3 py-2">
        <div className="text-xs font-bold text-[#333]">검색 관심도</div>
        <button onClick={onClose} className="px-1 text-[13px] text-[#999] hover:text-[#333]">×</button>
      </div>

      {!d ? (
        <div className="p-3 text-[11px] text-[#999]">불러오는 중…</div>
      ) : !d.ready ? (
        <div className="flex flex-col gap-2 p-3">
          <p className="rounded border border-[#f0e6c9] bg-[#fdfaf0] p-2 text-[11px] leading-relaxed text-[#7a5f10]">
            {d.message}
          </p>
          <button
            onClick={collect}
            disabled={busy || d.warming}
            className="rounded bg-[#217346] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#1b5e3a] disabled:opacity-50"
          >
            {d.warming ? "수집 중…" : busy ? "시작 중…" : "관심도 수집"}
          </button>
          {msg && <div className="text-[11px] text-[#456]">{msg}</div>}
          <p className="text-[10px] leading-relaxed text-[#999]">{d.note}</p>
        </div>
      ) : (
        <>
          <div className="flex shrink-0 border-b border-[#eee]">
            {([["rank", "관심도 순위"], ["gap", "검색↑ 거래↓"]] as const).map(([k, label]) => (
              <button
                key={k}
                onClick={() => setTab(k)}
                className={`flex-1 px-2 py-1.5 text-[11px] font-semibold ${
                  tab === k ? "border-b-2 border-[#217346] text-[#217346]" : "text-[#888] hover:bg-[#f7f7f7]"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {tab === "gap" && (
            <p className="shrink-0 bg-[#f7faf8] px-3 py-1.5 text-[10px] leading-relaxed text-[#5a7]">
              검색 순위가 실거래 순위보다 앞선 지역. 관심이 아직 거래로 옮겨가지 않았다는 뜻이다.
            </p>
          )}

          <div className="min-h-0 flex-1 overflow-y-auto">
            <table className="w-full text-[11px]">
              <thead className="sticky top-0 bg-[#f5f5f5] text-[10px] text-[#888]">
                <tr>
                  <th className="px-2 py-1 text-left font-semibold">지역</th>
                  <th className="px-2 py-1 text-right font-semibold">관심도</th>
                  <th className="px-2 py-1 text-right font-semibold">{tab === "gap" ? "순위차" : "추세"}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((it) => (
                  <tr
                    key={it.lawd}
                    onClick={() => onPick(it.lawd)}
                    className="cursor-pointer border-t border-[#f2f2f2] hover:bg-[#f2f7f4]"
                  >
                    <td className="px-2 py-1">
                      <span className="mr-1 text-[#bbb]">{it.rank}</span>
                      <span className="font-semibold text-[#333]">{it.region}</span>
                      <span className="ml-1 text-[10px] text-[#aaa]">{it.sido}</span>
                    </td>
                    <td className="px-2 py-1 text-right tabular-nums text-[#333]">{it.index.toFixed(2)}배</td>
                    <td
                      className="px-2 py-1 text-right tabular-nums font-semibold"
                      style={{
                        color: tab === "gap"
                          ? GREEN
                          : (it.trend_pct ?? 0) > 0 ? RED : GREEN,
                      }}
                    >
                      {tab === "gap" && "gap" in it ? `+${(it as { gap: number }).gap}` : pct(it.trend_pct)}
                    </td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr><td colSpan={3} className="px-2 py-6 text-center text-[#aaa]">해당하는 지역이 없습니다.</td></tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="shrink-0 border-t border-[#eee] px-3 py-1.5 text-[10px] leading-relaxed text-[#999]">
            {d.updated} 기준 · 앵커 &ldquo;{d.anchor}&rdquo; 대비 배수 · {d.count}곳
            <button
              onClick={collect}
              disabled={busy || d.warming}
              className="ml-2 text-[#217346] hover:underline disabled:opacity-50"
            >
              {d.warming ? "수집 중…" : "다시 수집"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
