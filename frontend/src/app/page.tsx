"use client";

import { useEffect, useState } from "react";
import { api, Coverage } from "@/lib/api";
import { MarketView } from "@/components/MarketView";
import { KrOpenForecast } from "@/components/KrOpenForecast";
import { StockScore } from "@/components/StockScore";
import { WatchPortfolio } from "@/components/WatchPortfolio";
import { DividendsBoard } from "@/components/DividendsBoard";
import { DividendDeepDive } from "@/components/DividendDeepDive";
import { DividendRoyalty } from "@/components/DividendRoyalty";
import { CrisisSurvivors } from "@/components/CrisisSurvivors";
import { DividendEtf } from "@/components/DividendEtf";
import { KospiEarnings } from "@/components/KospiEarnings";
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
import { MarketBriefing } from "@/components/MarketBriefing";
import { UnitEconomics } from "@/components/UnitEconomics";

type Tab = "market" | "briefing" | "open" | "movers" | "score" | "watch" | "dividend" | "unitecon" | "budget" | "wealth" | "live" | "money" | "korea" | "inst" | "future" | "report" | "industry" | "crisis" | "realestate";

// ── ERP식 좌측 사이드바: 18개 기능을 6개 모듈로 그룹핑 ────────────────────
const NAV: { group: string; icon: string; items: { id: Tab; label: string }[] }[] = [
  { group: "시장·종목", icon: "📊", items: [
    { id: "market", label: "전종목 분석" },
    { id: "score", label: "투자 점수" },
    { id: "movers", label: "급등락 원인" },
    { id: "watch", label: "관심·보유" },
    { id: "dividend", label: "배당·실적" },
    { id: "unitecon", label: "제품 원가분해" },
  ] },
  { group: "시황·브리핑", icon: "📰", items: [
    { id: "briefing", label: "장전 브리핑" },
    { id: "open", label: "개장 예측" },
    { id: "live", label: "실시간 시황" },
    { id: "report", label: "데일리 리포트" },
  ] },
  { group: "자금·경제 흐름", icon: "💰", items: [
    { id: "money", label: "자금 흐름" },
    { id: "korea", label: "한국 경제 흐름" },
    { id: "inst", label: "기관 추적" },
  ] },
  { group: "산업·테마", icon: "🏭", items: [
    { id: "future", label: "미래 성장테마" },
    { id: "industry", label: "산업 지도" },
  ] },
  { group: "내 자산·재테크", icon: "🧮", items: [
    { id: "budget", label: "가계부" },
    { id: "wealth", label: "재테크 로드맵" },
    { id: "crisis", label: "위기 시뮬레이터" },
  ] },
  { group: "부동산", icon: "🏠", items: [
    { id: "realestate", label: "부동산 지도" },
  ] },
];
const TAB_LABEL: Record<Tab, string> = Object.fromEntries(
  NAV.flatMap((g) => g.items.map((it) => [it.id, it.label])),
) as Record<Tab, string>;
const GROUP_OF: Record<Tab, string> = Object.fromEntries(
  NAV.flatMap((g) => g.items.map((it) => [it.id, g.group])),
) as Record<Tab, string>;

export default function Page() {
  return (
    <LoginGate>
      <Home />
    </LoginGate>
  );
}

function Sidebar({ tab, setTab, collapsed }: { tab: Tab; setTab: (t: Tab) => void; collapsed: boolean }) {
  // 아코디언: 기본은 모든 그룹 펼침. 접혀도 현재 탭의 그룹은 항상 펼침 유지.
  const [closed, setClosed] = useState<Record<string, boolean>>({});
  const toggle = (g: string) => setClosed((s) => ({ ...s, [g]: !s[g] }));

  if (collapsed) {
    // 아이콘 레일: 그룹 아이콘만. 클릭 시 그 그룹의 첫 화면으로 이동.
    return (
      <aside className="flex w-12 shrink-0 flex-col items-center gap-1 border-r border-[#d7ddd9] bg-[#f3f5f4] py-2">
        {NAV.map((g) => {
          const active = GROUP_OF[tab] === g.group;
          return (
            <button key={g.group} title={g.group} onClick={() => setTab(g.items[0].id)}
              className={`flex h-9 w-9 items-center justify-center rounded text-base transition ${active ? "bg-[#217346] text-white" : "hover:bg-[#e3e9e5]"}`}>
              {g.icon}
            </button>
          );
        })}
      </aside>
    );
  }

  return (
    <aside className="flex w-52 shrink-0 flex-col overflow-y-auto border-r border-[#d7ddd9] bg-[#f3f5f4] py-1.5">
      {NAV.map((g) => {
        const isClosed = closed[g.group] && GROUP_OF[tab] !== g.group;
        return (
          <div key={g.group} className="mb-0.5">
            <button onClick={() => toggle(g.group)}
              className="flex w-full items-center gap-1.5 px-3 py-1.5 text-left text-[11px] font-bold text-[#5a6b60] hover:text-[#217346]">
              <span className="text-xs">{g.icon}</span>
              <span className="flex-1">{g.group}</span>
              <span className="text-[9px] text-[#aab4ae]">{isClosed ? "▸" : "▾"}</span>
            </button>
            {!isClosed && (
              <div className="flex flex-col">
                {g.items.map((it) => {
                  const active = tab === it.id;
                  return (
                    <button key={it.id} onClick={() => setTab(it.id)}
                      className={`flex items-center border-l-[3px] py-1.5 pl-6 pr-3 text-left text-[13px] transition ${
                        active
                          ? "border-[#217346] bg-white font-semibold text-[#217346]"
                          : "border-transparent text-[#4a4a4a] hover:bg-[#e9efeb]"
                      }`}>
                      {it.label}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </aside>
  );
}

function Home() {
  const [tab, setTab] = useState<Tab>("market");
  const [navCollapsed, setNavCollapsed] = useState(false);
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
      {/* ── 상단바 (초록 브랜드 + 현재 위치 브레드크럼) ─────────────── */}
      <div className="flex h-9 shrink-0 items-center gap-2 bg-[#217346] px-3 text-white">
        <button onClick={() => setNavCollapsed((v) => !v)} title={navCollapsed ? "메뉴 펼치기" : "메뉴 접기"}
          className="flex h-6 w-6 items-center justify-center rounded text-base hover:bg-white/20">☰</button>
        <svg viewBox="0 0 32 32" className="h-5 w-5" aria-hidden>
          <rect x="2" y="2" width="28" height="28" rx="4" fill="#ffffff" />
          <path
            d="M11.2 9.5h2.7l2.1 3.6 2.1-3.6h2.6l-3.3 5.5 3.5 5.8h-2.7l-2.3-3.9-2.3 3.9h-2.6l3.5-5.8z"
            fill="#217346"
          />
        </svg>
        <span className="text-sm font-semibold tracking-tight">인베스트</span>
        <span className="text-white/50">›</span>
        <span className="text-xs text-white/70">{GROUP_OF[tab]}</span>
        <span className="text-white/50">›</span>
        <span className="text-xs font-medium text-white">{TAB_LABEL[tab]}</span>
        <div className="ml-auto flex items-center gap-4 text-xs">
          {kr && (
            <span className="hidden text-white/80 md:inline">
              {kr.tickers.toLocaleString("ko-KR")}종목 · {kr.rows.toLocaleString("ko-KR")}건
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

      {/* ── 본문: 좌측 사이드바 + 콘텐츠 ─────────────────────────── */}
      <div className="flex min-h-0 flex-1">
        <Sidebar tab={tab} setTab={setTab} collapsed={navCollapsed} />
        <main className="min-h-0 flex-1">
          {tab === "market" ? (
            <MarketView />
          ) : (
            <div className="h-full overflow-y-auto bg-[#fafafa]">
              <div className="w-full px-5 py-5">
                {tab === "briefing" && <MarketBriefing />}
                {tab === "open" && <KrOpenForecast />}
                {tab === "movers" && <MarketMovers />}
                {tab === "score" && <StockScore />}
                {tab === "watch" && <WatchPortfolio />}
                {tab === "dividend" && (
                  <div className="flex flex-col gap-5">
                    <DividendDeepDive />
                    <CrisisSurvivors />
                    <DividendRoyalty />
                    <DividendEtf />
                    <DividendsBoard />
                    <KospiEarnings />
                  </div>
                )}
                {tab === "unitecon" && <UnitEconomics />}
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
      </div>
    </div>
  );
}
