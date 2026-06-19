"use client";

import { useState } from "react";
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

  return (
    <div className="flex h-full">
      <div className="min-w-0 flex-1">
        <ExcelGrid
          onPickStock={(r: GridRow) => setActive({ ticker: r.ticker, name: r.name, sector: r.sector })}
        />
      </div>
      <div className="flex h-full w-[400px] shrink-0 flex-col border-l border-[#d0d0d0]">
        {active && (
          <div className="flex shrink-0 gap-2 border-b border-[#d0d0d0] bg-[#eef2ee] px-3 py-2">
            <button
              onClick={() => setReport(active)}
              className="flex-1 rounded bg-[#217346] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#1b5e3a]"
            >
               오늘 리포트
            </button>
            <button
              onClick={() => setChart(active)}
              className="rounded border border-[#cdcdcd] bg-white px-3 py-1.5 text-xs font-semibold text-[#217346] hover:bg-[#eef6f0]"
            >
               차트
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
