"use client";

import { useEffect, useState } from "react";
import { api, Coverage } from "@/lib/api";
import { MarketView } from "@/components/MarketView";
import { MarketReport } from "@/components/MarketReport";
import { Backtest } from "@/components/Backtest";
import { Portfolio } from "@/components/Portfolio";

type Tab = "market" | "report" | "backtest" | "portfolio";

const TABS: { id: Tab; label: string }[] = [
  { id: "market", label: "전종목 분석" },
  { id: "report", label: "데일리 리포트" },
  { id: "backtest", label: "백테스트" },
  { id: "portfolio", label: "포트폴리오" },
];

export default function Home() {
  const [tab, setTab] = useState<Tab>("market");
  const [online, setOnline] = useState<boolean | null>(null);
  const [coverage, setCoverage] = useState<Coverage[]>([]);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        await api.health();
        const cov = await api.coverage();
        if (alive) {
          setOnline(true);
          setCoverage(cov);
        }
      } catch {
        if (alive) setOnline(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const kr = coverage.find((c) => c.market === "KR");

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {/* top bar — full width app chrome */}
      <header className="flex h-14 shrink-0 items-center gap-7 border-b border-slate-800 bg-slate-950 px-6">
        {/* 회사용 위장: 엑셀로 열린 문서처럼 보이게 한다 */}
        <div className="flex items-center gap-2">
          <svg viewBox="0 0 32 32" className="h-5 w-5" aria-hidden>
            <rect x="2" y="2" width="28" height="28" rx="4" fill="#217346" />
            <path
              d="M11.2 9.5h2.7l2.1 3.6 2.1-3.6h2.6l-3.3 5.5 3.5 5.8h-2.7l-2.3-3.9-2.3 3.9h-2.6l3.5-5.8z"
              fill="#ffffff"
            />
          </svg>
          <span className="text-[15px] font-semibold tracking-tight text-slate-200">
            매출분석_2026_상반기.xlsx
          </span>
          <span className="hidden text-xs text-slate-500 sm:inline">Excel</span>
        </div>
        <nav className="flex h-full items-stretch gap-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`relative px-4 text-[15px] font-semibold transition ${
                tab === t.id ? "text-white" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {t.label}
              {tab === t.id && <span className="absolute inset-x-3 -bottom-px h-0.5 rounded bg-[#ff5252]" />}
            </button>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-4 text-xs">
          {kr && (
            <span className="hidden text-slate-500 md:inline">
              수록 <b className="text-slate-300">{kr.tickers.toLocaleString("ko-KR")}</b>종목 · 일봉{" "}
              <b className="text-slate-300">{kr.rows.toLocaleString("ko-KR")}</b>건
            </span>
          )}
          <span className="flex items-center gap-2">
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                online === null ? "bg-amber-400" : online ? "bg-emerald-400" : "bg-rose-500"
              }`}
            />
            <span className="hidden text-slate-400 sm:inline">
              {online === null ? "연결 중" : online ? "실시간 데이터" : "오프라인"}
            </span>
          </span>
        </div>
      </header>

      {online === false && (
        <div className="shrink-0 border-b border-rose-900/60 bg-rose-950/40 px-6 py-2.5 text-sm text-rose-300">
          백엔드 API에 연결할 수 없습니다. <code className="font-mono">uvicorn app.main:app</code> 가 실행 중인지 확인하세요.
        </div>
      )}

      {/* main fills the rest of the viewport */}
      <main className="min-h-0 flex-1">
        {tab === "market" ? (
          <MarketView />
        ) : (
          <div className="h-full overflow-y-auto">
            <div className="mx-auto max-w-6xl px-6 py-6">
              {tab === "report" && <MarketReport />}
              {tab === "backtest" && <Backtest coverage={coverage} />}
              {tab === "portfolio" && <Portfolio coverage={coverage} />}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
