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
  // 아직 명세서가 안 나온 할부 회차 — 저장된 거래가 아니라 계산으로 만든 예정분이다.
  projected?: boolean;
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
  // 실제 내역은 없고 할부 예정만 있는 달 (months 안에 함께 들어 있다)
  future_months: string[];
  basis: "billing_month" | "date";
  income: BudgetIncome;
  income_total: number;
  spent: number;
  refund: number;
  // 남은 할부 회차 — 명세서는 아직이지만 이미 확정된 지출
  projected: BudgetTx[];
  projected_total: number;
  committed: number;          // spent + projected_total
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
  // 카드 설정으로 청구월을 계산한 건수. conflict 는 파일이 말한 청구월과 설정이 어긋난 경우.
  cycle_applied?: number;
  cycle_conflict?: { stated: string; by_cycle: string[] };
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

// --- 카드별 결제 주기 -------------------------------------------------------
// 이용기간과 결제일은 카드마다 다르고 자동으로 알아낼 수 없다(파일에 안 적혀 있다).
// 등록해 두면 거래일에서 청구월을 계산한다 — 할부는 거래일이 아니라 회차 기준.
export interface CardCycle {
  cycle_start_day: number;   // 0 = 말일
  cycle_end_day: number;     // 0 = 말일
  pay_day: number;           // 0 = 말일
  pay_offset: number;        // 0=당월 결제, 1=익월, 2=다다음달
}

export interface CardCycleWindow {
  start?: string;
  end?: string;
  pay?: string;
}

export interface BudgetCard {
  card: string;
  issuer: string;
  count: number;
  amount: number;
  months: string[];
  billing_month: string;
  configured: boolean;
  cycle: CardCycle;
  describe: string;
  window: CardCycleWindow;
}

export interface BudgetCardsOverview {
  cards: BudgetCard[];
  defaults: CardCycle;
}

// --- 고정지출 ---------------------------------------------------------------
// 구독·통신·공과금처럼 계속 나가는 돈. 변동비와 섞어 두면 '얼마를 줄일 수 있는가' 에
// 답할 수 없어서 따로 뺀다. 판정 근거(source)를 같이 주므로 화면에서 설명할 수 있다.
export interface FixedCost {
  merchant: string;
  key: string;
  category: string;
  cards: string[];
  count: number;
  months: string[];
  min: number;
  max: number;
  avg: number;
  last_amount: number;
  total: number;
  steady: boolean;
  spread_pct: number | null;
  interval_days: number;
  cadence: string;
  last_date: string;
  next_expected: string;
  source: string;
  monthly: number;
  annual: number;
}

export interface FixedCostCandidate extends Omit<FixedCost, "source" | "monthly" | "annual"> {
  reason: string;
}

export interface FixedCostBoard {
  items: FixedCost[];
  candidates: FixedCostCandidate[];
  count: number;
  monthly_total: number;
  annual_total: number;
  by_category: { category: string; monthly: number }[];
  note: string;
}

// --- 메일 명세서 자동 수집 ---------------------------------------------------
// 카드사가 매달 보내는 e-메일 명세서를 받은편지함에서 걷어 온다. 카드사 API 는 개인에게
// 열려 있지 않고 승인문자는 할부·취소·청구월을 못 잡아서, 개인이 얻을 수 있는 가장
// 정확한 원본이 명세서다. 확신이 서는 것만 자동 등록하고 나머지는 대기함에 쌓인다.
export interface MailPendingItem {
  id: string;
  at: string;
  sent_at: string;
  subject: string;
  sender: string;
  filename: string;
  saved_path: string;
  issuer: string;
  billing_month: string;
  billing_month_known: boolean;
  parsed_by: string;
  file_kind: string;
  count: number;
  spend: number;
  date_range: [string, string];
  note: string;
  reason: string;               // 왜 자동 등록하지 않았는가
  cycle_conflict: { stated: string; by_cycle: string[] } | null;
  sample: BudgetTx[];
}

export interface MailHistoryItem {
  at: string;
  subject: string;
  filename?: string;
  issuer?: string;
  billing_month?: string;
  action: "imported" | "approved" | "locked";
  added?: number;
  skipped?: number;
  reason?: string;
}

export interface MailScanResult {
  ok: boolean;
  reason?: string;
  examined: number;
  imported: number;
  added?: number;
  pending: number;
  locked?: number;
  days?: number;
  note: string;
}

export interface MailBoard {
  configured: boolean;          // .env 에 IMAP 자격증명이 들어와 있는가
  enabled: boolean;             // 스케줄러 스위치
  autoimport: boolean;
  host: string;
  account: string;
  folder: string;
  days: number;
  interval_min: number;
  has_passwords: boolean;
  last_scan: { at: string; examined: number; imported: number; pending: number; locked: number } | null;
  pending: MailPendingItem[];
  history: MailHistoryItem[];
  issuers: string[];
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
  budgetFixedCosts: () => request<FixedCostBoard>(`/api/data/budget/fixed-costs`),
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

  // 메일 명세서 수집 — 상태 조회 / 즉시 확인 / 대기함 승인·폐기
  budgetMail: () => request<MailBoard>(`/api/data/budget/mail`),
  budgetMailScan: (days?: number, rescan = false) =>
    request<MailScanResult>(
      `/api/data/budget/mail/scan?rescan=${rescan}${days ? `&days=${days}` : ""}`,
      { method: "POST" }),
  budgetMailItem: (itemId: string) =>
    request<MailPendingItem & { ok: boolean }>(`/api/data/budget/mail/item?item_id=${itemId}`),
  budgetMailApprove: (itemId: string) =>
    request<{ ok: boolean; added?: number; skipped?: number; issuer?: string; billing_month?: string; reason?: string }>(
      `/api/data/budget/mail/approve?item_id=${itemId}`, { method: "POST" }),
  budgetMailDiscard: (itemId: string) =>
    request<{ ok: boolean }>(`/api/data/budget/mail/discard?item_id=${itemId}`, { method: "POST" }),

  budgetCards: () => request<BudgetCardsOverview>(`/api/data/budget/cards`),
  budgetSetCycle: (card: string, c: CardCycle) =>
    request<{ ok: boolean; cycle: CardCycle }>(
      `/api/data/budget/cycle?card=${encodeURIComponent(card)}&cycle_start_day=${c.cycle_start_day}` +
      `&cycle_end_day=${c.cycle_end_day}&pay_day=${c.pay_day}&pay_offset=${c.pay_offset}`,
      { method: "POST" }),
  budgetClearCycle: (card: string) =>
    request<{ ok: boolean }>(`/api/data/budget/cycle/clear?card=${encodeURIComponent(card)}`, { method: "POST" }),
  budgetRecalc: (card?: string) =>
    request<{ changed: number; cards?: string[]; note?: string }>(
      `/api/data/budget/recalc${card ? `?card=${encodeURIComponent(card)}` : ""}`, { method: "POST" }),

  budgetPlan: (emergencyMonths = 3, investRatio = 0.5) =>
    request<BudgetPlan>(`/api/data/budget/plan?emergency_months=${emergencyMonths}&invest_ratio=${investRatio}`),
};
