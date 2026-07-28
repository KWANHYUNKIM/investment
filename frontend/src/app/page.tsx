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
import { SheetTabs } from "@/components/SheetTabs";
import { IndustryMap } from "@/components/IndustryMap";
import { CrisisSim } from "@/components/CrisisSim";
import { RealEstateMap } from "@/components/RealEstateMap";
import { MarketMovers } from "@/components/MarketMovers";
import { MarketBriefing } from "@/components/MarketBriefing";
import { CompanyCostModel } from "@/components/CompanyCostModel";
import { CompetitorCompare } from "@/components/CompetitorCompare";
import { DelistingScreener } from "@/components/DelistingScreener";
import { EarningsQuality } from "@/components/EarningsQuality";
import { Admin } from "@/components/Admin";

type Tab = "market" | "briefing" | "open" | "movers" | "score" | "watch" | "dividend" | "unitecon" | "peer" | "delisting" | "eq" | "budget" | "wealth" | "live" | "money" | "korea" | "inst" | "future" | "report" | "industry" | "crisis" | "realestate" | "admin";

// ── ERP식 좌측 사이드바: 18개 기능을 6개 모듈로 그룹핑 ────────────────────
const NAV: { group: string; icon: string; items: { id: Tab; label: string }[] }[] = [
  { group: "시장·종목", icon: "📊", items: [
    { id: "market", label: "전종목 분석" },
    { id: "score", label: "투자 점수" },
    { id: "movers", label: "급등락 원인" },
    { id: "watch", label: "관심·보유" },
    { id: "dividend", label: "배당·실적" },
    { id: "unitecon", label: "원가분석" },
    { id: "peer", label: "경쟁사 비교" },
    { id: "delisting", label: "관리종목·상폐 경보" },
    { id: "eq", label: "회계 착시 탐지" },
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
// 관리자 전용 네비(관리자에게만 노출)
const ADMIN_NAV = { group: "운영", icon: "🛠", items: [{ id: "admin" as Tab, label: "관리자" }] };
const ALL_NAV = [...NAV, ADMIN_NAV];
const TAB_LABEL: Record<Tab, string> = Object.fromEntries(
  ALL_NAV.flatMap((g) => g.items.map((it) => [it.id, it.label])),
) as Record<Tab, string>;
const GROUP_OF: Record<Tab, string> = Object.fromEntries(
  ALL_NAV.flatMap((g) => g.items.map((it) => [it.id, g.group])),
) as Record<Tab, string>;

export default function Page() {
  return (
    <LoginGate>
      <Home />
    </LoginGate>
  );
}

/**
 * 시트 목록. 폭에 따라 역할이 다르다.
 * - ≥lg: 좌측 사이드바로 문서 흐름에 상주. `collapsed` 면 아이콘 레일(w-12), 아니면 전체 메뉴(w-52).
 * - <lg: 하단 시트탭의 ⊞ 로 여는 '모든 시트' 목록. 내비게이션 본체가 아니라 긴 꼬리를 위한
 *   넘김 목록이다. ⊞ 가 화면 우하단에 있으므로 좌측이 아니라 아래에서 올라온다 —
 *   엑셀의 '모든 시트 보기'도 시트탭 옆에서 열린다.
 * 레일과 전체 메뉴를 둘 다 렌더하고 CSS 로 고르는 이유: 화면 폭을 JS 로 읽으면 SSR 과
 * 클라이언트 첫 렌더가 어긋난다. 노드 수가 적어(아이콘 7개) 중복 비용이 무시할 만하다.
 */
function Sidebar({
  tab, setTab, collapsed, nav, drawerOpen, closeDrawer,
}: {
  tab: Tab; setTab: (t: Tab) => void; collapsed: boolean; nav: typeof ALL_NAV;
  drawerOpen: boolean; closeDrawer: () => void;
}) {
  // 아코디언: 기본은 모든 그룹 펼침. 접혀도 현재 탭의 그룹은 항상 펼침 유지.
  const [closed, setClosed] = useState<Record<string, boolean>>({});
  const toggle = (g: string) => setClosed((s) => ({ ...s, [g]: !s[g] }));
  // 드로어에서 화면을 고르면 곧바로 본문을 봐야 하므로 닫는다(데스크톱에서는 무해).
  const go = (t: Tab) => { setTab(t); closeDrawer(); };

  return (
    <aside
      className={[
        "z-40 flex flex-col border-[#d7ddd9] bg-[#f3f5f4] transition-transform duration-200 motion-reduce:transition-none",
        // 폰: ⊞ 로 여는 '모든 시트' — 아래에서 올라온다
        "fixed inset-x-0 bottom-0 max-h-[72dvh] overflow-y-auto border-t shadow-[0_-8px_24px_rgba(0,0,0,0.18)]",
        drawerOpen ? "translate-y-0" : "invisible translate-y-full",
        // 데스크톱: 흐름 안 좌측 사이드바
        "lg:visible lg:static lg:z-auto lg:max-h-none lg:translate-y-0 lg:overflow-y-auto lg:border-r lg:border-t-0 lg:py-1.5 lg:shadow-none",
        collapsed ? "lg:w-12 lg:shrink-0 lg:items-center lg:gap-1 lg:py-2" : "lg:w-52 lg:shrink-0",
      ].join(" ")}
    >
      {/* 목록 제목 — 폰 전용. 무엇이 열렸는지 말해 주고 닫을 자리를 준다. */}
      <div className="sticky top-0 flex items-center justify-between border-b border-[#d7ddd9] bg-[#f3f5f4] px-3 py-2.5 lg:hidden">
        <span className="text-[13px] font-bold text-[#3d4c43]">모든 시트</span>
        <button onClick={closeDrawer} aria-label="목록 닫기"
          className="flex h-8 w-8 items-center justify-center text-sm text-[#5a6b60]">✕</button>
      </div>

      {/* 아이콘 레일 — 데스크톱 접힘 전용 */}
      {collapsed && (
        <div className="hidden w-full flex-col items-center gap-1 lg:flex">
          {nav.map((g) => {
            const active = GROUP_OF[tab] === g.group;
            return (
              <button key={g.group} title={g.group} onClick={() => go(g.items[0].id)}
                className={`flex h-9 w-9 items-center justify-center rounded text-base transition ${active ? "bg-[#217346] text-white" : "hover:bg-[#e3e9e5]"}`}>
                {g.icon}
              </button>
            );
          })}
        </div>
      )}

      {/* 전체 메뉴 — 모바일에서는 항상, 데스크톱에서는 펼침일 때만 */}
      <div className={collapsed ? "lg:hidden" : ""}>
        {nav.map((g) => {
          const isClosed = closed[g.group] && GROUP_OF[tab] !== g.group;
          return (
            <div key={g.group} className="mb-0.5">
              <button onClick={() => toggle(g.group)}
                className="flex w-full items-center gap-1.5 px-3 py-2.5 text-left text-[11px] font-bold text-[#5a6b60] hover:text-[#217346] lg:py-1.5">
                {/* 아이콘은 데스크톱 전용. 폰 화면에 이모지가 남으면 그것만으로 '앱'처럼 읽혀
                    제목표시줄의 위장이 깨진다. 접힌 레일에서는 아이콘이 유일한 단서라 거기선 남긴다. */}
                <span className="hidden text-xs lg:inline">{g.icon}</span>
                <span className="flex-1">{g.group}</span>
                <span className="text-[9px] text-[#aab4ae]">{isClosed ? "▸" : "▾"}</span>
              </button>
              {!isClosed && (
                <div className="flex flex-col">
                  {g.items.map((it) => {
                    const active = tab === it.id;
                    return (
                      <button key={it.id} onClick={() => go(it.id)}
                        className={`flex items-center border-l-[3px] py-2 pl-6 pr-3 text-left text-[13px] transition lg:py-1.5 ${
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
      </div>
    </aside>
  );
}

function Home() {
  const [tab, setTab] = useState<Tab>("market");
  const [navCollapsed, setNavCollapsed] = useState(false);
  const [navDrawer, setNavDrawer] = useState(false);
  const [online, setOnline] = useState<boolean | null>(null);
  const [coverage, setCoverage] = useState<Coverage[]>([]);
  const [isAdmin, setIsAdmin] = useState(false);

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
      try {
        const me = await api.me();
        if (alive) setIsAdmin(me.is_admin);
      } catch { /* 비관리자/미로그인 */ }
    })();
    return () => {
      alive = false;
    };
  }, []);

  // 방문자 통계: 화면 전환 시 조회 기록
  useEffect(() => { api.track(tab).catch(() => {}); }, [tab]);

  // 드로어는 ESC 로 닫힌다. 데스크톱에서는 애초에 열리지 않으므로 무해.
  useEffect(() => {
    if (!navDrawer) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setNavDrawer(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navDrawer]);

  const nav = isAdmin ? ALL_NAV : NAV;
  const kr = coverage.find((c) => c.market === "KR");
  // 하단 시트탭에 들어갈 납작한 목록. 그룹은 ⊞(전체 목록)에서만 쓰인다.
  const sheets = nav.flatMap((g) => g.items.map((it) => ({ id: it.id, label: it.label })));

  return (
    /* h-dvh: 모바일 브라우저 주소창이 접히고 펴져도 앱 높이가 잘리지 않는다(h-screen=100vh 는 잘림). */
    <div className="flex h-dvh flex-col overflow-hidden bg-[#fafafa]">
      {/* ── 제목표시줄 ────────────────────────────────────────────────
          폰에서는 파일명만 남긴다. 하단 시트탭이 현재 위치를 이미 말하고 있어 브레드크럼이
          중복이고, 그 자리를 비워야 상단이 순수한 엑셀 제목표시줄로 읽힌다. ≥lg 에서는
          사이드바가 내비게이션을 맡으므로 ☰(레일 접기)와 브레드크럼이 그대로 살아 있다. */}
      <div className="flex h-9 shrink-0 items-center gap-2 bg-[#217346] px-2 text-white sm:px-3">
        <button onClick={() => setNavCollapsed((v) => !v)} aria-label={navCollapsed ? "메뉴 펼치기" : "메뉴 접기"}
          className="hidden h-7 w-7 shrink-0 items-center justify-center rounded text-base hover:bg-white/20 lg:flex">☰</button>
        <svg viewBox="0 0 32 32" className="h-5 w-5 shrink-0" aria-hidden>
          <rect x="2" y="2" width="28" height="28" rx="4" fill="#ffffff" />
          <path
            d="M11.2 9.5h2.7l2.1 3.6 2.1-3.6h2.6l-3.3 5.5 3.5 5.8h-2.7l-2.3-3.9-2.3 3.9h-2.6l3.5-5.8z"
            fill="#217346"
          />
        </svg>
        {/* 폰: 파일명(위장) — 데스크톱: 브랜드 + 브레드크럼 */}
        <span className="truncate text-xs text-white/90 lg:hidden">매출분석_2026_상반기.xlsx</span>
        <span className="hidden shrink-0 text-sm font-semibold tracking-tight lg:inline">인베스트</span>
        <span className="hidden shrink-0 text-white/50 lg:inline">›</span>
        <span className="hidden shrink-0 text-xs text-white/70 lg:inline">{GROUP_OF[tab]}</span>
        <span className="hidden shrink-0 text-white/50 lg:inline">›</span>
        <span className="hidden truncate text-xs font-medium text-white lg:inline">{TAB_LABEL[tab]}</span>
        <div className="ml-auto flex items-center gap-4 text-xs">
          {kr && (
            <span className="hidden shrink-0 text-white/80 lg:inline">
              {kr.tickers.toLocaleString("ko-KR")}종목 · {kr.rows.toLocaleString("ko-KR")}건
            </span>
          )}
        </div>
      </div>

      {/* real-time global index strip */}
      <IndexStrip />

      {online === false && (
        <div className="shrink-0 border-b border-rose-300 bg-rose-50 px-3 py-2.5 text-sm text-rose-700 sm:px-6">
          백엔드 API에 연결할 수 없습니다. <code className="rounded bg-rose-100 px-1.5 font-mono">uvicorn app.main:app</code> 가 실행 중인지 확인하세요.
        </div>
      )}

      {/* ── 본문: 좌측 사이드바 + 콘텐츠 ─────────────────────────── */}
      <div className="flex min-h-0 flex-1">
        {/* 드로어 백드롭 — 열렸을 때만, 좁은 화면에서만 */}
        {navDrawer && (
          <div onClick={() => setNavDrawer(false)} aria-hidden
            className="fixed inset-0 z-30 bg-black/40 lg:hidden" />
        )}
        <Sidebar tab={tab} setTab={setTab} collapsed={navCollapsed} nav={nav}
          drawerOpen={navDrawer} closeDrawer={() => setNavDrawer(false)} />
        {/* min-w-0: 플렉스 아이템 기본 min-width:auto 때문에 내용(엑셀 그리드·우측 패널)이
            넓으면 main 이 뷰포트 밖으로 밀려 우측이 잘린다. 반드시 0 으로 풀어준다. */}
        <main className="min-h-0 min-w-0 flex-1">
          {tab === "market" ? (
            <MarketView />
          ) : (
            <div className="h-full overflow-y-auto bg-[#fafafa]">
              {/* 와이드 모니터에서 본문이 2,000px 넘게 늘어나면 표 칸이 벌어지고 문단이 읽기
                  어려워진다. 읽기 좋은 폭으로 묶고 가운데 정렬한다. 엑셀 그리드(전종목 분석)는
                  이 래퍼 밖이라 지금처럼 화면을 꽉 쓴다. */}
              <div className="mx-auto w-full max-w-[1600px] px-3 py-3 sm:px-5 sm:py-5">
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
                {tab === "unitecon" && <CompanyCostModel />}
                {tab === "peer" && <CompetitorCompare />}
                {tab === "delisting" && <DelistingScreener />}
                {tab === "eq" && <EarningsQuality />}
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
                {tab === "admin" && isAdmin && <Admin />}
              </div>
            </div>
          )}
        </main>
      </div>

      {/* ── 시그니처: 하단 시트탭이 폰의 내비게이션이다 (≥lg 에서는 사이드바가 맡는다) ── */}
      <SheetTabs items={sheets} active={tab} onPick={(id) => setTab(id as Tab)}
        onOpenAll={() => setNavDrawer(true)} />
    </div>
  );
}
