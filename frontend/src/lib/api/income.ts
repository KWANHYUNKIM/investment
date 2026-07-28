// 소득·성장 — 급여 상세/인상 이력·인상 시뮬·부업

import { request } from "./client";

export interface SalaryItem { label: string; amount: number }

export interface SalaryComputed {
  earnings: SalaryItem[];
  deductions: SalaryItem[];
  memo: string;
  gross: number;
  deduction: number;
  net: number;
  annual_net: number;
  annual_gross: number;
  updated: string | null;
}

export interface SalaryHistory { date: string; gross: number; net: number; annual_net: number }

export interface RaiseSim {
  base_net: number; new_net: number; monthly_increase: number; annual_increase: number;
  years: number; invest_ratio: number; annual_return: number;
  invest_monthly: number; contributed: number; future_value: number; investment_gain: number; note: string;
}

export interface SideRow { id: number; date: string; source: string; amount: number; memo: string }

export interface SideList {
  month: string | null; months: string[]; rows: SideRow[];
  month_total: number; total: number; sources: { source: string; amount: number }[];
}

export interface IncomeOverview {
  salary: SalaryComputed | null;
  side: { this_month: number; total: number; count: number };
  investment: { value: number; pnl: number; pnl_pct: number | null };
  total_month_income: number;
  annual_est: number;
  tips: string[];
}

export const incomeApi = {
  incomeOverview: () => request<IncomeOverview>(`/api/data/income/overview`),
  incomeSalaryGet: () => request<{ salary: SalaryComputed | null; history: SalaryHistory[] }>(`/api/data/income/salary`),
  incomeSalarySet: (earnings: SalaryItem[], deductions: SalaryItem[], memo = "") =>
    request<SalaryComputed>(`/api/data/income/salary`, { method: "POST", body: JSON.stringify({ earnings, deductions, memo }) }),
  incomeRaiseSim: (p: { raise_pct?: number; raise_amount?: number; years?: number; invest_ratio?: number; annual_return?: number }) => {
    const q = new URLSearchParams();
    if (p.raise_pct != null) q.set("raise_pct", String(p.raise_pct));
    if (p.raise_amount != null) q.set("raise_amount", String(p.raise_amount));
    if (p.years != null) q.set("years", String(p.years));
    if (p.invest_ratio != null) q.set("invest_ratio", String(p.invest_ratio));
    if (p.annual_return != null) q.set("annual_return", String(p.annual_return));
    return request<RaiseSim>(`/api/data/income/raise-sim?${q.toString()}`);
  },
  incomeSideList: (month?: string) => request<SideList>(`/api/data/income/side${month ? `?month=${month}` : ""}`),
  incomeSideAdd: (items: { date: string; source: string; amount: number; memo?: string }[]) =>
    request<{ added: number }>(`/api/data/income/side`, { method: "POST", body: JSON.stringify(items) }),
  incomeSideDelete: (sid: number) => request<{ ok: boolean }>(`/api/data/income/side/delete?sid=${sid}`, { method: "POST" }),
};
