"use client";

import { useEffect, useState } from "react";
import { api, NewsItem, NewsResponse } from "@/lib/api";
import { ago } from "@/lib/format";

export type PickedStock = { ticker: string; name: string | null; sector: string | null };

export function NewsPanel({
  stock,
  onOpenChart,
}: {
  stock: PickedStock | null;
  onOpenChart: () => void;
}) {
  const [news, setNews] = useState<NewsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [updated, setUpdated] = useState("");
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!stock?.name) {
      setNews(null);
      return;
    }
    let alive = true;
    const load = async () => {
      setLoading(true);
      try {
        const r = await api.news(stock.name as string);
        if (alive) {
          setNews(r);
          setNow(Date.now());
          setUpdated(
            new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
          );
        }
      } catch {
        if (alive) setNews({ domestic: [], global: [], cached: false });
      } finally {
        if (alive) setLoading(false);
      }
    };
    load();
    const id = setInterval(load, 60000); // 자동 재계산 (60초)
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [stock?.name]);

  return (
    <aside className="flex min-h-0 flex-1 flex-col bg-white">
      {/* sheet title bar (green) */}
      <div className="flex shrink-0 items-center justify-between bg-[#217346] px-3 py-1.5 text-white">
        <span className="flex items-center gap-1.5 text-sm font-semibold">📰 종목뉴스.xlsx</span>
        {stock && (
          <button
            onClick={onOpenChart}
            className="shrink-0 rounded border border-white/30 bg-white/15 px-2 py-0.5 text-xs font-semibold text-white hover:bg-white/25"
          >
            📈 차트
          </button>
        )}
      </div>

      {/* formula-bar style selected-cell line */}
      <div className="flex shrink-0 items-center gap-2 border-b border-[#d0d0d0] bg-white px-3 py-1 text-xs">
        <span className="italic text-[#999]">fx</span>
        {stock ? (
          <span className="truncate text-[#333]">
            {stock.name} <span className="font-mono text-[#888]">{stock.ticker}</span>
            {updated && <span className="ml-1 text-[#aaa]">· {updated} 갱신</span>}
          </span>
        ) : (
          <span className="text-[#aaa]">종목 미선택</span>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto bg-[#fafafa]">
        {!stock ? (
          <div className="flex h-full flex-col items-center justify-center px-6 text-center text-sm text-[#999]">
            <div className="mb-2 text-3xl">🔎</div>
            왼쪽 표에서 종목을 선택하면
            <br />
            관련 <b className="text-[#666]">국내·해외 뉴스</b>가 여기 표시됩니다.
          </div>
        ) : loading && !news ? (
          <div className="py-10 text-center text-sm text-[#999]">불러오는 중…</div>
        ) : (
          <>
            <NewsSheet title="국내 뉴스" badge="KR" bg="#a9d08e" fg="#244d1a" items={news?.domestic ?? []} now={now} />
            <NewsSheet title="해외 뉴스" badge="GLOBAL" bg="#f4b084" fg="#7a3a0c" items={news?.global ?? []} now={now} />
          </>
        )}
      </div>

      <div className="shrink-0 border-t border-[#d0d0d0] bg-[#f3f2f1] px-3 py-1 text-[10px] text-[#999]">
        준비 완료 · 출처: Google News
      </div>
    </aside>
  );
}

function NewsSheet({
  title,
  badge,
  bg,
  fg,
  items,
  now,
}: {
  title: string;
  badge: string;
  bg: string;
  fg: string;
  items: NewsItem[];
  now: number;
}) {
  return (
    <table className="w-full border-collapse text-[13px]">
      <thead className="sticky top-0 z-10">
        {/* coloured group-header band */}
        <tr>
          <th
            colSpan={2}
            style={{ background: bg, color: fg }}
            className="border border-white px-2 py-1 text-left text-xs font-bold"
          >
            {title}
            <span className="ml-1.5 rounded bg-black/10 px-1 text-[10px]">{badge}</span>
            <span className="ml-1.5 font-normal opacity-70">{items.length}건</span>
          </th>
        </tr>
        {/* column header */}
        <tr className="bg-[#f0f0f0] text-[11px] text-[#555]">
          <th className="w-7 border border-[#d6d6d6] py-0.5 text-center font-semibold">#</th>
          <th className="border border-[#d6d6d6] px-2 py-0.5 text-left font-semibold">제목 · 출처</th>
        </tr>
      </thead>
      <tbody>
        {items.length === 0 ? (
          <tr>
            <td className="border border-[#eee] bg-[#f0f0f0] text-center text-xs text-[#bbb]">—</td>
            <td className="border border-[#eee] px-2 py-2 text-xs text-[#bbb]">관련 기사가 없습니다.</td>
          </tr>
        ) : (
          items.map((a, i) => (
            <tr
              key={`${a.link}-${i}`}
              className="align-top hover:bg-[#fff7e6]"
              style={a.important ? { background: "rgba(224,49,49,0.06)" } : undefined}
            >
              <td className="w-7 border border-[#eee] bg-[#f0f0f0] text-center text-xs text-[#999]">{i + 1}</td>
              <td className="border border-[#eee] px-2 py-1.5">
                <a href={a.link} target="_blank" rel="noopener noreferrer" className="group block">
                  <div className="flex items-start gap-1.5">
                    {a.important && (
                      <span className="mt-0.5 shrink-0 rounded-sm bg-[#c92a2a] px-1 py-0.5 text-[9px] font-bold text-white">
                        중요
                      </span>
                    )}
                    <span className="text-[13px] leading-snug text-[#222] group-hover:text-[#1155cc] group-hover:underline">
                      {a.title}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center gap-2 text-[11px] text-[#999]">
                    <span className="truncate">{a.source}</span>
                    {a.ts && <span className="shrink-0">· {ago(a.ts, now)}</span>}
                  </div>
                </a>
              </td>
            </tr>
          ))
        )}
      </tbody>
    </table>
  );
}
