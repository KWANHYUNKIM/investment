// 가계부 — 카드 명세서 취합·지출 분리·급여·저축 계획
//
// 금액 필드가 넷이라 헷갈리기 쉬운데 의미가 다르다.
//   amount  그 청구월에 실제로 빠지는 돈 (= charged + fee) ← 지출 집계는 항상 이것
//   charged 이번 회차 결제 원금 (할부면 전액이 아니라 1회차분)
//   fee     수수료·이자·해외이용수수료
//   total   거래 전액 (할부 원금 총액)

import { request, API_BASE, authHeader, ApiError } from "./client";

export interface BudgetIncome {
  monthly_net: number;
  extra: number;
  memo: string;
}

export interface BudgetInstallmentRef {
  months: number;
  seq: number;
  remaining: number;
}

export interface BudgetTx {
  id: number;
  date: string;
  billing_month: string;
  merchant: string;
  amount: number;
  charged: number;
  fee: number;
  total: number;
  category: string;
  issuer: string;
  card: string;
  tx_type: string;
  installment: BudgetInstallmentRef | null;
  fixed?: boolean;
  fp: string;
}

interface Bucket {
  key: string;
  amount: number;
  count: number;
  pct: number;
}
export type CategoryBucket = Bucket & { category: string };
export type CardBucket = Bucket & { card: string };
export type TxTypeBucket = Bucket & { tx_type: string };

export interface BudgetInstallment {
  card: string;
  merchant: string;
  category: string;
  total: number;
  months: number;
  seq: number;
  months_left: number;
  remaining: number;
  monthly_principal: number;
  last_fee: number;
  billing_month: string;
}

export interface BudgetInstallmentBoard {
  items: BudgetInstallment[];
  count: number;
  remaining_total: number;
  next_month: number;
  fee_note: string;
  schedule?: { month: string; principal: number; items: { merchant: string; card: string; amount: number; seq: number; months: number }[] }[];
}

export interface BudgetImportLog {
  filename: string;
  issuer: string;
  billing_month: string;
  parsed_by: string;
  added: number;
  skipped: number;
  at: string;
}

export interface BudgetSummary {
  month: string;
  months: string[];
  basis: "billing_month" | "date";
  income: BudgetIncome;
  income_total: number;
  spent: number;
  refund: number;
  savings_possible: number;
  savings_rate: number | null;
  by_category: CategoryBucket[];
  by_card: CardBucket[];
  by_tx_type: TxTypeBucket[];
  by_fixed: { fixed: number; variable: number; fixed_pct: number; items: Bucket[] };
  categories: string[];
  tx_types: string[];
  cards: string[];
  issuers: string[];
  installments: Omit<BudgetInstallmentBoard, "schedule">;
  upcoming: { month: string; principal: number; items: { merchant: string; card: string; amount: number; seq: number; months: number }[] }[];
  count: number;
  transactions: BudgetTx[];
  imports: BudgetImportLog[];
}

export interface BudgetParseStats {
  count: number;
  spend: number;
  total_amount: number;
  fee: number;
  by_tx_type: { tx_type: string; amount: number }[];
  by_card: { card: string; amount: number }[];
  date_range: [string, string];
}

// 저장 전 확인용 — /budget/preview-file 응답
export interface CardStatementPreview {
  filename: string;
  issuer: string;
  billing_month: string;
  billing_months: string[];
  // false 면 파일에 청구월이 없어 '마지막 거래월 +1' 로 추정한 값이다 — 등록 전에 고르게 한다.
  billing_month_known: boolean;
  file_kind: string;
  parsed_by: string;
  note: string;
  stats: BudgetParseStats;
  transactions: BudgetTx[];
}

export interface CardImportResult extends Omit<CardStatementPreview, "transactions" | "filename"> {
  parsed: number;
  added: number;
  skipped: number;
  sample: BudgetTx[];
}

export interface BudgetPlan {
  income_total: number;
  avg_spend: number;
  avg_fixed: number;
  avg_variable: number;
  surplus: number;
  surplus_after_installment: number;
  savings_rate: number | null;
  emergency_months: number;
  emergency_target: number;
  invest_ratio: number;
  monthly_save: number;
  monthly_invest: number;
  stock_value: number;
  installment_remaining: number;
  installment_next_month: number;
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

async function upload<T>(path: string, file: File): Promise<T> {
  const fd = new FormData();
  fd.append("file", file);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { method: "POST", body: fd, headers: { ...authHeader() } });
  } catch {
    throw new ApiError(0, `백엔드에 연결할 수 없습니다 (${API_BASE}).`);
  }
  if (!res.ok) throw new ApiError(res.status, `${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const budgetApi = {
  budgetSummary: (month?: string, basis: "billing_month" | "date" = "billing_month") =>
    request<BudgetSummary>(`/api/data/budget/summary?basis=${basis}${month ? `&month=${month}` : ""}`),
  budgetInstallments: () => request<BudgetInstallmentBoard>(`/api/data/budget/installments`),
  budgetIssuers: () => request<{ issuers: string[]; categories: string[] }>(`/api/data/budget/issuers`),

  budgetSetIncome: (monthly_net: number, extra = 0, memo = "") =>
    request<BudgetIncome>(`/api/data/budget/income`, { method: "POST", body: JSON.stringify({ monthly_net, extra, memo }) }),
  budgetParsePayslip: (file: File) => upload<PayslipParse>(`/api/data/budget/income/parse`, file),

  // 카드 명세서: 먼저 확인(preview) → 고른 것만 등록(add). 한 번에 넣으려면 importFile.
  budgetPreviewFile: (file: File) => upload<CardStatementPreview>(`/api/data/budget/preview-file`, file),
  budgetImportFile: (file: File) => upload<CardImportResult>(`/api/data/budget/import-file`, file),
  budgetImport: (text: string) =>
    request<CardImportResult>(`/api/data/budget/import`, { method: "POST", body: JSON.stringify({ text }) }),
  budgetAdd: (items: Partial<BudgetTx>[]) =>
    request<{ added: number; skipped: number }>(`/api/data/budget/add`, { method: "POST", body: JSON.stringify(items) }),

  budgetDelete: (txId: number) => request<{ ok: boolean }>(`/api/data/budget/delete?tx_id=${txId}`, { method: "POST" }),
  budgetSetCategory: (txId: number, category: string, applyAll = true) =>
    request<{ ok: boolean }>(`/api/data/budget/category?tx_id=${txId}&category=${encodeURIComponent(category)}&apply_all=${applyAll}`, { method: "POST" }),
  budgetSetFixed: (merchant: string, fixed: boolean | null) =>
    request<{ ok: boolean }>(`/api/data/budget/fixed?merchant=${encodeURIComponent(merchant)}${fixed === null ? "" : `&fixed=${fixed}`}`, { method: "POST" }),
  budgetClearMonth: (month: string, by: "billing_month" | "date" = "billing_month") =>
    request<{ removed: number }>(`/api/data/budget/clear-month?month=${month}&by=${by}`, { method: "POST" }),
  budgetClearImport: (issuer: string, billingMonth: string) =>
    request<{ removed: number }>(`/api/data/budget/clear-import?issuer=${encodeURIComponent(issuer)}&billing_month=${billingMonth}`, { method: "POST" }),
  // 추정 청구월이 한 달 어긋났을 때 — 지우고 다시 올리지 않아도 되게.
  budgetMoveMonth: (issuer: string, fromMonth: string, toMonth: string) =>
    request<{ moved: number; merged: number; to: string }>(
      `/api/data/budget/move-month?issuer=${encodeURIComponent(issuer)}&from_month=${fromMonth}&to_month=${toMonth}`,
      { method: "POST" }),

  budgetPlan: (emergencyMonths = 3, investRatio = 0.5) =>
    request<BudgetPlan>(`/api/data/budget/plan?emergency_months=${emergencyMonths}&invest_ratio=${investRatio}`),
};
