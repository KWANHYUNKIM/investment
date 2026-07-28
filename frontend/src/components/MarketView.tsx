"use client";

import { useEffect, useState } from "react";
import { GridRow } from "@/lib/api";
import { ExcelGrid } from "./ExcelGrid";
import { NewsPanel, PickedStock } from "./NewsPanel";
import { InvestorFlow } from "./InvestorFlow";
import { FundamentalsPanel } from "./FundamentalsPanel";
import { HolderList } from "./HolderList";
import { StockDetail } from "./StockDetail";
import { ReportModal } from "./ReportModal";

export function MarketView() {
  const [active, setActive] = useState<PickedStock | null>(null);
  const [chart, setChart] = useState<PickedStock | null>(null);
  const [report, setReport] = useState<PickedStock | null>(null);
  // 상세 패널은 ≥xl 에서만 흐름 안에 상주한다. 그보다 좁으면 종목을 골랐을 때만
  // 우측에서 덮는 시트로 열린다 — 400px 가 상시 자리를 차지하면 폰에서 그리드가 사라진다.
  const [sheet, setSheet] = useState(false);

  useEffect(() => {
    if (!sheet) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setSheet(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sheet]);

  const pick = (r: GridRow) => {
    setActive({ ticker: r.ticker, name: r.name, sector: r.sector });
    setSheet(true);
  };

  return (
    <div className="flex h-full min-w-0">
      <div className="min-w-0 flex-1">
        <ExcelGrid onPickStock={pick} />
      </div>

      {/* 시트 백드롭 — 좁은 화면에서 열렸을 때만 */}
      {sheet && (
        <div onClick={() => setSheet(false)} aria-hidden
          className="fixed inset-0 z-30 bg-black/40 xl:hidden" />
      )}

      <div
        className={[
          "flex h-full flex-col border-l border-[#d0d0d0] bg-white",
          // 좁은 화면: 우측에서 덮는 시트. 폭을 꽉 채우지 않고 좌측에 40px 를 남기는 이유는
          // 그 띠가 유일하게 남는 백드롭이기 때문이다 — 폰에는 ESC 가 없으므로 화면을 꽉 채우면
          // 상단 ✕ 말고는 빠져나갈 길이 없어진다.
          "fixed inset-y-0 right-0 z-40 w-[calc(100%-2.5rem)] max-w-[400px] shadow-2xl transition-transform duration-200 motion-reduce:transition-none",
          sheet ? "translate-x-0" : "invisible translate-x-full",
          // ≥xl: 흐름 안에 상주하는 고정 패널
          "xl:visible xl:static xl:z-auto xl:w-[400px] xl:max-w-none xl:translate-x-0 xl:shrink-0 xl:shadow-none",
        ].join(" ")}
      >
        {active && (
          <div className="flex shrink-0 items-center gap-2 border-b border-[#d0d0d0] bg-[#eef2ee] px-3 py-2">
            <button
              onClick={() => setReport(active)}
              className="min-h-11 flex-1 rounded bg-[#217346] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#1b5e3a] xl:min-h-0"
            >
               오늘 리포트
            </button>
            <button
              onClick={() => setChart(active)}
              className="min-h-11 rounded border border-[#cdcdcd] bg-white px-3 py-1.5 text-xs font-semibold text-[#217346] hover:bg-[#eef6f0] xl:min-h-0"
            >
               차트
            </button>
            {/* 시트로 열렸을 때만 필요한 닫기 */}
            <button
              onClick={() => setSheet(false)} aria-label="상세 닫기"
              className="min-h-11 min-w-11 rounded border border-[#cdcdcd] bg-white px-2.5 py-1.5 text-xs font-semibold text-[#666] hover:bg-[#f3f2f1] xl:hidden"
            >
              ✕
            </button>
          </div>
        )}
        <InvestorFlow stock={active} />
        <FundamentalsPanel stock={active} />
        <HolderList stock={active} />
        <NewsPanel stock={active} onOpenChart={() => active && setChart(active)} />
      </div>

      {chart && (
        <StockDetail ticker={chart.ticker} name={chart.name} sector={chart.sector} onClose={() => setChart(null)} />
      )}
      {report && <ReportModal stock={report} onClose={() => setReport(null)} />}
    </div>
  );
}
