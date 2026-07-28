// 재테크 로드맵 — 목표계획·자격 상품추천·대출/부동산/배당/공모주 시뮬

import { request } from "./client";

export interface WealthProduct {
  name: string;
  category: string;
  eligible: boolean;
  cond: string;
  benefit: string;
  cap: number;
  priority: number;
  link: string;
  example: string;
}

export interface WealthPlan {
  profile: Record<string, unknown>;
  goal: { amount: number; years: number };
  required_monthly: number;
  capacity_monthly: number;
  feasible: boolean | null;
  shortfall: number;
  reach_years: number | null;
  assumed_return: number;
  scenarios: {
    key: string; name: string; desc: string; safety: string; risk: string;
    return_mid: number; return_low: number; return_high: number;
    balance_at_goal_years: number; balance_low: number; balance_high: number;
    reach_years: number | null; reach_years_low: number | null; reach_years_high: number | null;
    time_saved_vs_safe: number | null; recommended: boolean;
  }[];
  projection: { year: number; balance: number }[];
  products: WealthProduct[];
  eligible_count: number;
  allocation: { name: string; monthly: number; category: string; why: string }[];
  steps: string[];
  note: string;
}

export interface LoanSim {
  loan_amount: number; loan_rate: number; loan_years: number; invest_return: number;
  monthly_payment: number; total_repay: number; total_interest: number;
  invest_value: number; net_profit: number; worthwhile: boolean;
  breakeven_return: number | null;
  scenarios: { name: string; return: number; invest_value: number; net_profit: number; worthwhile: boolean }[];
  loans: { name: string; rate: number; note: string }[];
  verdict: string; warning: string;
}

export interface RealtySim {
  mode: string; price: number; own_capital: number; loan: number; loan_rate: number; years: number; appreciation: number;
  deposit: number; rent_monthly: number; monthly_interest: number; monthly_cashflow: number;
  rent_yield_on_capital: number | null; total_interest: number;
  future_price: number; sale_gain: number; net_profit: number; roe: number | null; roe_no_leverage: number;
  scenarios: { name: string; appreciation: number; future_price: number; sale_gain: number; net_profit: number; roe: number | null }[];
  note: string; warning: string;
}

export interface RealtyLoan {
  name: string; kind: string; rate: number; limit: number | null; eligible: boolean; cond: string; note: string;
}

export interface RealtyLoans {
  price: number; annual_income: number; mode: string; ltv_pct: number;
  loans: RealtyLoan[]; eligible_count: number; max_limit: number; dsr_note: string; note: string;
}

export interface HoldingCatalogItem {
  name: string; category: string; benefit: string; example: string; rate: number; bonus_note: string; has_bonus: boolean;
}

export interface HoldingItem {
  name: string; category: string; monthly: number; current: number; rate: number; bonus_note: string;
  principal: number; invest_value: number; bonus_total: number; total: number; gain: number;
  yearly: { year: number; total: number }[];
}

export interface HoldingsData {
  holdings: { name: string; monthly: number; current: number }[];
  horizon: number;
  catalog: HoldingCatalogItem[];
  projection: {
    horizon: number;
    items: HoldingItem[];
    totals_by_year: { year: number; total: number }[];
    summary: { monthly_sum: number; principal: number; bonus_total: number; gain: number; total: number };
    note: string;
  };
}

export interface DividendSim {
  invest: number; yield_pct: number; years: number; growth_pct: number; reinvest: boolean; tax_pct: number;
  annual_gross: number; annual_net: number; monthly_net: number; final_value: number; total_dividends_net: number;
  yearly: { year: number; dividend_net: number; cum_net: number; value: number }[];
  targets: { monthly: number; invest: number }[];
  examples: { name: string; yield: string; note: string }[];
  guide: string[]; note: string;
}

export interface IpoSim {
  offer_price: number; alloc_shares: number; cost: number; subscribe_amount: number; margin_estimate: number;
  scenarios: { gain_pct: number; sell_price: number; profit: number; roi_on_cost: number | null }[];
  guide: string[]; note: string;
}

export interface DividendPick {
  ticker: string; name: string; sector: string | null; close: number | null;
  div_yield: number; per: number | null; pbr: number | null; roe: number | null;
  market_cap: number | null; foreign_ratio: number | null; op_yoy: number | null;
  score: number; grade: string; reasons: string[]; stability: string; cycle: string;
  monthly_per_10m: number; naver_url: string;
}

export interface DividendPicks { generated_at: string; picks: DividendPick[]; guide: string[]; note: string; }

export interface IpoScheduleItem {
  no?: string; name: string; subscribe: string; status: string; price_confirmed: string | null; price_band: string; underwriter: string;
  market?: string; shares?: string; offer_amount_text?: string; offer_amount_won?: number | null;
  listing_date?: string; demand_competition?: string; lockup?: string; detail_url?: string;
}

export interface IpoSchedule {
  items: IpoScheduleItem[]; upcoming_count: number; source: string; generated_at: string; error?: string; guide?: string[]; note: string;
}

export const wealthApi = {
  wealthPlan: () => request<WealthPlan>(`/api/data/wealth/plan`),
  wealthSaveProfile: (profile: Record<string, unknown>) =>
    request<WealthPlan>(`/api/data/wealth/profile`, { method: "POST", body: JSON.stringify(profile) }),
  wealthLoanSim: (loanAmount: number, loanRate: number, loanYears: number, investReturn: number) =>
    request<LoanSim>(`/api/data/wealth/loan-sim?loan_amount=${loanAmount}&loan_rate=${loanRate}&loan_years=${loanYears}&invest_return=${investReturn}`),
  wealthRealtySim: (p: { price: number; own_capital: number; loan_rate: number; years: number; appreciation: number; mode: string; deposit: number; rent_monthly: number }) =>
    request<RealtySim>(`/api/data/wealth/realty-sim?price=${p.price}&own_capital=${p.own_capital}&loan_rate=${p.loan_rate}&years=${p.years}&appreciation=${p.appreciation}&mode=${p.mode}&deposit=${p.deposit}&rent_monthly=${p.rent_monthly}`),
  wealthRealtyLoans: (p: { price: number; annual_income: number; age: number; married: boolean; homeless: boolean; has_child: boolean; deposit: number; mode: string }) =>
    request<RealtyLoans>(`/api/data/wealth/realty-loans?price=${p.price}&annual_income=${p.annual_income}&age=${p.age}&married=${p.married}&homeless=${p.homeless}&has_child=${p.has_child}&deposit=${p.deposit}&mode=${p.mode}`),
  wealthHoldings: () => request<HoldingsData>(`/api/data/wealth/holdings`),
  wealthSaveHoldings: (holdings: { name: string; monthly: number; current: number }[], horizon: number) =>
    request<HoldingsData>(`/api/data/wealth/holdings`, { method: "POST", body: JSON.stringify({ holdings, horizon }) }),
  wealthDividendSim: (p: { invest: number; yield_pct: number; years: number; growth_pct: number; reinvest: boolean }) =>
    request<DividendSim>(`/api/data/wealth/dividend-sim?invest=${p.invest}&yield_pct=${p.yield_pct}&years=${p.years}&growth_pct=${p.growth_pct}&reinvest=${p.reinvest}`),
  wealthIpoSim: (p: { offer_price: number; alloc_shares: number; subscribe_amount: number }) =>
    request<IpoSim>(`/api/data/wealth/ipo-sim?offer_price=${p.offer_price}&alloc_shares=${p.alloc_shares}&subscribe_amount=${p.subscribe_amount}`),
  wealthDividendPicks: (top = 12) => request<DividendPicks>(`/api/data/wealth/dividend-picks?top=${top}`),
  wealthIpoSchedule: () => request<IpoSchedule>(`/api/data/wealth/ipo-schedule`),
};
