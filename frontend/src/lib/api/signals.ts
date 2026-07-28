// 매매신호 · 목표주가(적정주가+시나리오)

import { request } from "./client";

export interface TargetPriceScenario {
  name: string;
  r: number;
  per_mult: number;
  target: number | null;
  upside_pct: number | null;
  methods: Record<string, number>;
}

export interface TargetPriceAi {
  fair_value: number;
  targets: Record<string, number>;
  rationale: string;
  key_drivers: string[];
  confidence: string;
  model: string;
}

export interface TargetPrice {
  ticker: string;
  close: number | null;
  fundamentals: Record<string, number | null>;
  per_median?: number | null;
  target_per_used?: number;
  base: number | null;
  base_upside_pct?: number | null;
  scenarios: TargetPriceScenario[];
  note: string;
  ai: TargetPriceAi | null;
  ai_error: string | null;
  ai_enabled: boolean;
}

export interface TradeSignalItem {
  name: string;
  score: number;
  view: string;
}

export interface TradeSignals {
  ticker: string;
  date?: string;
  close?: number;
  verdict: "매수" | "중립" | "매도" | null;
  tone?: string;
  score?: number;
  rsi?: number | null;
  ma5?: number | null;
  ma20?: number | null;
  ma60?: number | null;
  ma_arrange?: string;
  cross?: string | null;
  macd_hist?: number | null;
  bb_pct?: number | null;
  vol_ratio?: number | null;
  pos_52w?: number | null;
  atr?: number | null;
  risk?: {
    stop_loss: number | null;
    target1: number | null;
    target2: number | null;
    risk_reward: number | null;
    support: number | null;
    resistance: number | null;
  };
  signals: TradeSignalItem[];
  backtest?: {
    trades: number;
    win_rate: number | null;
    strat_return_pct: number | null;
    bh_return_pct: number | null;
    avg_trade_pct: number | null;
    open_position: boolean;
  } | null;
  note?: string;
}

export const signalsApi = {
  targetPrice: (ticker: string) => request<TargetPrice>(`/api/data/target-price?ticker=${ticker}`),
  signals: (ticker: string) => request<TradeSignals>(`/api/data/signals?ticker=${ticker}`),
};
