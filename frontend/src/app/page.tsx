"use client";

import { useEffect, useState } from "react";
import { api, Coverage } from "@/lib/api";
import { MarketView } from "@/components/MarketView";
import { KrOpenForecast } from "@/components/KrOpenForecast";
import { StockScore } from "@/components/StockScore";
import { WatchPortfolio } from "@/components/WatchPortfolio";
import { DividendsBoard } from "@/components/DividendsBoard";
import { BudgetManager } from "@/components/BudgetManager";
import { IncomeGrowth } from "@/components/IncomeGrowth";
import { WealthPlan } from "@/components/WealthPlan";
import { LoginGate } from "@/components/LoginGate";
import { MarketReport } from "@/components/MarketReport";
import { LivePulse } from "@/components/LivePulse";
import { FutureTheme } from "@/components/FutureTheme";
import { MoneyFlow } from "@/components/MoneyFlow";
import { KoreaFlow } from "@/components/KoreaFlow";
import { InstitutionalFlow } from "@/components/InstitutionalFlow";
import { IndexStrip } from "@/components/IndexStrip";
import { IndustryMap } from "@/components/IndustryMap";
import { CrisisSim } from "@/components/CrisisSim";
import { RealEstateMap } from "@/components/RealEstateMap";
import { MarketMovers } from "@/components/MarketMovers";

type Tab = "market" | "open" | "movers" | "score" | "watch" | "dividend" | "budget" | "wealth" | "live" | "money" | "korea" | "inst" | "future" | "report" | "industry" | "crisis" | "realestate";

const TABS: { id: Tab; label: string }[] = [
  { id: "market", label: "전종목 분석" },
  { id: "open", label: "개장 예측" },
  { id: "movers", label: "급등락 원인" },
  { id: "score", label: "투자 점수" },
  { id: "watch", label: "관심·보유" },
  { id: "dividend", label: "배당·실적" },
  { id: "budget", label: "가계부" },
  { id: "wealth", label: "재테크 로드맵" },
  { id: "live", label: "실시간 시황" },
  { id: "money", label: "자금 흐름" },
  { id: "korea", label: "한국 경제 흐름" },
  { id: "inst", label: "기관 추적" },
  { id: "future", label: "미래 성장테마" },
  { id: "report", label: "데일리 리포트" },
  { id: "industry", label: "산업 지도" },
  { id: "crisis", label: "위기 시뮬레이터" },
  { id: "realestate", label: "부동산 지도" },
];

export default function Page() {
  return (
    <LoginGate>
      <Home />
    </LoginGate>
  );
}

function Home() {
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
    <div className="flex h-screen flex-col overflow-hidden bg-[#fafafa]">
      {/* ── Excel title bar (green) ───────────────────────────── */}
      <div className="flex h-9 shrink-0 items-center gap-2 bg-[#217346] px-4 text-white">
        <svg viewBox="0 0 32 32" className="h-5 w-5" aria-hidden>
          <rect x="2" y="2" width="28" height="28" rx="4" fill="#ffffff" />
          <path
            d="M11.2 9.5h2.7l2.1 3.6 2.1-3.6h2.6l-3.3 5.5 3.5 5.8h-2.7l-2.3-3.9-2.3 3.9h-2.6l3.5-5.8z"
            fill="#217346"
          />
        </svg>
        <span className="text-sm font-semibold tracking-tight">매출분석_2026_상반기.xlsx</span>
        <span className="text-xs text-white/70">— Excel</span>
        <div className="ml-auto flex items-center gap-4 text-xs">
          {kr && (
            <span className="hidden text-white/80 md:inline">
              {kr.tickers.toLocaleString("ko-KR")}행 · {kr.rows.toLocaleString("ko-KR")}건
            </span>
          )}
        </div>
      </div>

      {/* real-time global index strip */}
      <IndexStrip />

      {online === false && (
        <div className="shrink-0 border-b border-rose-300 bg-rose-50 px-6 py-2.5 text-sm text-rose-700">
          백엔드 API에 연결할 수 없습니다. <code className="rounded bg-rose-100 px-1.5 font-mono">uvicorn app.main:app</code> 가 실행 중인지 확인하세요.
        </div>
      )}

      {/* main fills the rest of the viewport */}
      <main className="min-h-0 flex-1">
        {tab === "market" ? (
          <MarketView />
        ) : (
          <div className="h-full overflow-y-auto bg-[#fafafa]">
            <div className="w-full px-5 py-5">
              {tab === "open" && <KrOpenForecast />}
              {tab === "movers" && <MarketMovers />}
              {tab === "score" && <StockScore />}
              {tab === "watch" && <WatchPortfolio />}
              {tab === "dividend" && <DividendsBoard />}
              {tab === "budget" && <BudgetManager />}
              {tab === "wealth" && (
                <div className="flex flex-col gap-5">
                  <div>
                    <div className="mb-2 border-l-4 border-[#217346] pl-2 text-sm font-bold text-[#217346]">1. 소득 파악 — 급여·부업·투자 수익</div>
                    <IncomeGrowth />
                  </div>
                  <div>
                    <div className="mb-2 border-l-4 border-[#217346] pl-2 text-sm font-bold text-[#217346]">2. 목표·재테크 로드맵 — 상품 추천·위험도 시나리오·대출 레버리지</div>
                    <WealthPlan />
                  </div>
                </div>
              )}
              {tab === "live" && <LivePulse />}
              {tab === "money" && <MoneyFlow />}
              {tab === "korea" && <KoreaFlow />}
              {tab === "inst" && <InstitutionalFlow />}
              {tab === "future" && <FutureTheme />}
              {tab === "report" && <MarketReport />}
              {tab === "industry" && <IndustryMap />}
              {tab === "crisis" && <CrisisSim />}
              {tab === "realestate" && <RealEstateMap />}
            </div>
          </div>
        )}
      </main>

      {/* ── Excel worksheet tabs (bottom workbook navigation) ──── */}
      <div className="flex h-9 shrink-0 items-stretch border-t border-[#d0d0d0] bg-[#f3f2f1] text-xs">
        <div className="flex select-none items-center gap-2 px-2.5 text-[#9a9a9a]">
          <span>⏮</span>
          <span>◀</span>
          <span>▶</span>
          <span>⏭</span>
        </div>
        <div className="flex items-stretch gap-0.5 pt-1">
          {TABS.map((t) => {
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`border border-b-0 px-4 py-1 transition ${
                  active
                    ? "border-[#d0d0d0] bg-white font-semibold text-[#217346]"
                    : "border-transparent text-[#666] hover:bg-[#e8e8e8]"
                }`}
              >
                {t.label}
              </button>
            );
          })}
        </div>
        <div className="flex select-none items-center px-2 text-base leading-none text-[#bbb]">＋</div>
      </div>
    </div>
  );
}
