// 가계부 — 수입·거래내역·급여명세서 파싱·예산 계획

import { request, API_BASE, authHeader, ApiError } from "./client";

export interface BudgetIncome {
  monthly_net: number;
  extra: number;
  memo: string;
}

export interface BudgetTx {
  id: number;
  date: string;
  merchant: string;
  amount: number;
  category: string;
}

export interface BudgetSummary {
  month: string;
  months: string[];
  income: BudgetIncome;
  income_total: number;
  spent: number;
  refund: number;
  savings_possible: number;
  savings_rate: number | null;
  by_category: { category: string; amount: number; pct: number }[];
  categories: string[];
  count: number;
  transactions: BudgetTx[];
}

export interface BudgetPlan {
  income_total: number;
  avg_spend: number;
  surplus: number;
  savings_rate: number | null;
  emergency_months: number;
  emergency_target: number;
  invest_ratio: number;
  monthly_save: number;
  monthly_invest: number;
  stock_value: number;
  allocation: { name: string; monthly: number }[];
  steps: string[];
  note: string;
}

export interface PayslipParse {
  filename: string;
  net: number | null;
  gross: number | null;
  deduction: number | null;
  guessed: boolean;
  candidates: { label: string; amount: number }[];
  note: string;
}

export const budgetApi = {
  budgetSummary: (month?: string) => request<BudgetSummary>(`/api/data/budget/summary${month ? `?month=${month}` : ""}`),
  budgetSetIncome: (monthly_net: number, extra = 0, memo = "") =>
    request<BudgetIncome>(`/api/data/budget/income`, { method: "POST", body: JSON.stringify({ monthly_net, extra, memo }) }),
  budgetParsePayslip: async (file: File): Promise<PayslipParse> => {
    const fd = new FormData();
    fd.append("file", file);
    let res: Response;
    try {
      res = await fetch(`${API_BASE}/api/data/budget/income/parse`, { method: "POST", body: fd, headers: { ...authHeader() } });
    } catch {
      throw new ApiError(0, `백엔드에 연결할 수 없습니다 (${API_BASE}).`);
    }
    if (!res.ok) throw new ApiError(res.status, `${res.status} ${res.statusText}`);
    return res.json() as Promise<PayslipParse>;
  },
  budgetImportFile: async (file: File): Promise<{ parsed: number; sample: BudgetTx[] }> => {
    const fd = new FormData();
    fd.append("file", file);
    let res: Response;
    try {
      res = await fetch(`${API_BASE}/api/data/budget/import-file`, { method: "POST", body: fd, headers: { ...authHeader() } });
    } catch {
      throw new ApiError(0, `백엔드에 연결할 수 없습니다 (${API_BASE}).`);
    }
    if (!res.ok) throw new ApiError(res.status, `${res.status} ${res.statusText}`);
    return res.json();
  },
  budgetImport: (text: string) =>
    request<{ parsed: number; sample: BudgetTx[] }>(`/api/data/budget/import`, { method: "POST", body: JSON.stringify({ text }) }),
  budgetAdd: (items: { date: string; merchant: string; amount: number; category?: string }[]) =>
    request<{ added: number }>(`/api/data/budget/add`, { method: "POST", body: JSON.stringify(items) }),
  budgetDelete: (txId: number) => request<{ ok: boolean }>(`/api/data/budget/delete?tx_id=${txId}`, { method: "POST" }),
  budgetSetCategory: (txId: number, category: string, applyAll = true) =>
    request<{ ok: boolean }>(`/api/data/budget/category?tx_id=${txId}&category=${encodeURIComponent(category)}&apply_all=${applyAll}`, { method: "POST" }),
  budgetPlan: (emergencyMonths = 3, investRatio = 0.5) =>
    request<BudgetPlan>(`/api/data/budget/plan?emergency_months=${emergencyMonths}&invest_ratio=${investRatio}`),
};
