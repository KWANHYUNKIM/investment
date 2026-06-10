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
    const id = setInterval(load, 60000); // 실시간 크롤링 (60초)
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [stock?.name]);

  return (
    <aside className="flex min-h-0 flex-1 flex-col bg-[#fbfbfb]">
      {/* header */}
      <div className="flex shrink-0 items-center justify-between border-b border-[#d0d0d0] bg-[#eef2ee] px-3 py-2.5">
        <div className="min-w-0">
          <div className="text-sm font-bold text-[#1f1f1f]">📰 종목 뉴스</div>
          {stock && (
            <div className="truncate text-xs text-[#666]">
              {stock.name} <span className="text-[#999]">{stock.ticker}</span>
              {updated && <span className="ml-1 text-[#aaa]">· {updated} 갱신</span>}
            </div>
          )}
        </div>
        {stock && (
          <button
            onClick={onOpenChart}
            className="shrink-0 rounded border border-[#cdcdcd] bg-white px-2 py-1 text-xs text-[#217346] hover:bg-[#eef6f0]"
          >
            📈 차트
          </button>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {!stock ? (
          <div className="flex h-full flex-col items-center justify-center px-6 text-center text-sm text-[#999]">
            <div className="mb-2 text-3xl">🔎</div>
            왼쪽 표에서 종목을 선택하면
            <br />
            관련 <b className="text-[#666]">국내·해외 뉴스</b>가 여기 표시됩니다.
          </div>
        ) : loading && !news ? (
          <div className="py-10 text-center text-sm text-[#999]">뉴스 불러오는 중…</div>
        ) : (
          <>
            <Section title="국내 뉴스" badge="KR" items={news?.domestic ?? []} now={now} />
            <Section title="해외 뉴스" badge="GLOBAL" items={news?.global ?? []} now={now} />
          </>
        )}
      </div>

      <div className="shrink-0 border-t border-[#e0e0e0] bg-[#f3f2f1] px-3 py-1.5 text-[10px] text-[#999]">
        출처: Google News · 60초마다 자동 갱신
      </div>
    </aside>
  );
}

function Section({
  title,
  badge,
  items,
  now,
}: {
  title: string;
  badge: string;
  items: NewsItem[];
  now: number;
}) {
  return (
    <div>
      <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-[#e6e6e6] bg-[#f0f4f0] px-3 py-1.5">
        <span className="text-xs font-bold text-[#244d1a]">{title}</span>
        <span className="rounded bg-[#cfe3d3] px-1.5 py-0.5 text-[10px] font-semibold text-[#217346]">{badge}</span>
        <span className="ml-auto text-[10px] text-[#aaa]">{items.length}건</span>
      </div>
      {items.length === 0 ? (
        <div className="px-3 py-4 text-xs text-[#bbb]">관련 기사가 없습니다.</div>
      ) : (
        <ul>
          {items.map((a, i) => (
            <Article key={`${a.link}-${i}`} a={a} now={now} />
          ))}
        </ul>
      )}
    </div>
  );
}

function Article({ a, now }: { a: NewsItem; now: number }) {
  return (
    <li className="border-b border-[#eee] px-3 py-2 hover:bg-[#f5f7f5]">
      <a href={a.link} target="_blank" rel="noopener noreferrer" className="group block">
        <div className="flex items-start gap-1.5">
          {a.important && (
            <span className="mt-0.5 shrink-0 rounded bg-[#e03131] px-1 py-0.5 text-[9px] font-bold text-white">중요</span>
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
    </li>
  );
}
