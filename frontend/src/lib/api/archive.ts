// 일별 리포트 아카이브 — 날짜별 시장/종목 스냅샷

import { request } from "./client";
import type { ForeignView, MoverRow, StockInsight } from "./market";
import type { CrossAssetLayer, MacroLayer, RateLayer } from "./macro";

export interface ArchiveStock extends StockInsight {
  why?: { direction: string; themes: string[] };
  depth?: "deep" | "bulk";
}

// 시장 전체 투자자별 매매 동향(일단위) — 순매수 금액(억원) + 수량
export interface InvestorDay {
  date: string;
  foreign: number | null; // 외국인 순매수 (억원)
  individual: number | null; // 개인 순매수 (억원)
  organ: number | null; // 기관 순매수 (억원)
  foreign_qty: number | null;
  individual_qty: number | null;
  organ_qty: number | null;
  stocks: number; // 집계 종목 수
}

export interface DailyArchive {
  date: string | null;
  generated_at?: string;
  scope: { total: number; deep: number; deep_n: number };
  market: {
    breadth: { up: number; down: number; flat: number; total: number };
    summary: string;
    data_freshness?: {
      report_generated: string | null;
      price_date: string | null;
      investor_date: string | null;
      cross_asset_as_of: string | null;
      macro_pool: number | null;
    };
    investor_trend?: InvestorDay[];
    macro: MacroLayer;
    rates?: RateLayer | null;
    foreign_view?: ForeignView | null;
    cross_asset?: CrossAssetLayer | null;
  };
  movers: { gainers: MoverRow[]; losers: MoverRow[]; most_traded: MoverRow[] };
  stocks: ArchiveStock[];
}

export interface ArchiveDatesResponse {
  dates: string[];
  scheduler: Record<string, unknown>;
}

export const archiveApi = {
  dailyArchiveDates: () => request<ArchiveDatesResponse>(`/api/data/daily-archive/dates`),
  dailyArchive: (date?: string) =>
    request<DailyArchive>(`/api/data/daily-archive${date ? `?date=${encodeURIComponent(date)}` : ""}`),
};
