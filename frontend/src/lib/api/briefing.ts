// 장전 브리핑 · 개장 예측 · 급등락 원인

import { request } from "./client";

export interface BriefSignal { key: string; label: string; group?: string; change_pct: number | null; last?: number | null; }

export interface BriefADR { name: string; ticker?: string; change_pct: number; }

export interface BriefStory { topic: string; title: string; source: string | null; link: string; ts: number | null; }

export interface BriefOutlook {
  market: string; bias: string | null; gauge: number | null;
  expected_gap: { low?: number; high?: number }; drivers: string[]; basis: string;
}

export interface BriefNarrative { headline?: string; recap?: string[]; outlook?: string; risks?: string[]; one_liner?: string; source?: string; }

export interface Briefing {
  generated_at: string; market: string; market_label: string;
  signals: BriefSignal[]; adrs: BriefADR[]; extras: Record<string, { name?: string; change_pct?: number } | undefined>;
  flow: unknown; stories: BriefStory[]; outlook: BriefOutlook; narrative: BriefNarrative;
  ai_enabled: boolean; note: string;
}

export interface MoverNews { title: string; source: string; link: string; ts: number | null; }

export interface Mover {
  ticker: string; name: string; sector: string; close: number; change_pct: number; value: number; news: MoverNews[];
}

export interface MoverSector {
  sector: string; avg_change_pct: number; count: number; advancers: number; decliners: number;
  leaders: { name: string; ticker: string; change_pct: number }[];
}

export interface MoversAI { overall?: string; losers_cause?: string; gainers_cause?: string; drivers?: string[]; model?: string; }

export interface Movers {
  generated_at: string; count: number; breadth?: { advancers: number; decliners: number }; threshold?: number;
  gainers: Mover[]; losers: Mover[]; sectors_up: MoverSector[]; sectors_down: MoverSector[];
  ai: MoversAI | null; ai_enabled: boolean; note: string;
}

export interface MoversHistoryItem {
  generated_at: string; breadth?: { advancers: number; decliners: number };
  gainers: { name: string; change_pct: number }[]; losers: { name: string; change_pct: number }[];
  sector_up: string | null; sector_down: string | null;
  overall?: string | null; losers_cause?: string | null; gainers_cause?: string | null;
}

export interface PremarketSignal {
  key: string;
  label: string;
  group: string;
  unit: string;
  weight: number;
  direction: number;
  value: number;
  change_pct: number;
  date: string;
  impact_pct: number;
}

export interface PremarketAdr {
  ticker: string;
  name: string;
  value: number;
  change_pct: number;
  date: string;
}

export interface PremarketAi {
  bias: string;
  one_liner: string;
  narrative: string;
  sectors: { name: string; view: string }[];
  risks: string[];
  confidence: string;
  model: string;
}

export interface PremarketIndex {
  key: string;
  label: string;
  close: number;
  change_pct: number | null;
  change_5d: number | null;
  change_20d: number | null;
  ma20: number;
  vs_ma20_pct: number | null;
  trend: string;
  series: { date: string; close: number }[];
}

export interface Premarket {
  generated_at: string;
  signals: PremarketSignal[];
  adrs: PremarketAdr[];
  indices: PremarketIndex[];
  bias: "강세" | "중립" | "약세";
  tone: string;
  weighted_pct: number;
  gauge: number;
  expected_gap: { low: number; high: number };
  adr_avg: number | null;
  drivers: string[];
  ai: PremarketAi | null;
  ai_error: string | null;
  ai_enabled: boolean;
}

export interface PremarketRecord {
  based_on: string;
  made_at: string;
  prediction: {
    bias: string;
    weighted_pct: number;
    gauge: number;
    expected_gap: { low: number; high: number };
    adr_avg: number | null;
    drivers: string[];
    ai_one_liner: string | null;
  };
  graded: boolean;
  hit?: boolean;
  reason?: string;
  actual: {
    open_date: string;
    kospi_gap: number;
    kosdaq_gap: number | null;
    direction: string;
  } | null;
}

export interface PremarketHistory {
  accuracy: {
    total: number;
    hits: number;
    rate: number | null;
    recent10_hits: number;
    recent10_total: number;
    pending: number;
  };
  records: PremarketRecord[];
}

export const briefingApi = {
  premarket: () => request<Premarket>(`/api/data/premarket`),
  premarketHistory: (limit = 60) => request<PremarketHistory>(`/api/data/premarket/history?limit=${limit}`),
  briefing: (market: "auto" | "kr" | "us" = "auto") => request<Briefing>(`/api/data/briefing?market=${market}`),
  movers: (refresh = false) => request<Movers>(`/api/data/movers${refresh ? "?refresh=true" : ""}`),
  moversHistory: (limit = 50) => request<{ items: MoversHistoryItem[] }>(`/api/data/movers/history?limit=${limit}`),
};
