// 원가 진실성(§15) — 사업보고서 전 항목 파싱 + 교차검증 X1~X35

import { request } from "./client";

// ===== §15 원가 진실성 — 사업보고서 전 항목 파싱 + 교차검증 X1~X35 =====
export interface IntegrityCheck {
  code: string;                       // X1~X35
  label: string;
  grade: "치명" | "중대" | "일반" | "참고";
  weight: number;
  status: "ok" | "warn" | "fail" | "na";
  detail: string;
  a: number | string | null;
  b: number | string | null;
  source_a: string | null;            // A가 어느 절에서 왔는지 — 판정만 보여주면 믿을 근거가 없다
  source_b: string | null;
  why: string | null;
  year: number | null;
}

export interface IntegrityScore {
  ticker: string;
  available: boolean;
  score_pct: number | null;
  coverage_pct: number;
  grade: string;
  phrase: string;
  n_ok: number;
  n_warn: number;
  n_fail: number;
  n_unavailable: number;
  n_total: number;
  checked: number;
  sector_percentile?: number | null;
  by_grade: { grade: string; n: number; ok: number; warn: number; fail: number; na: number }[];
  checks: IntegrityCheck[];
  rcept?: string | null;
  url?: string | null;
  note: string;
  weights: Record<string, number | string>;
}

export interface DFMaterialRow {
  segment: string | null;
  type: string | null;
  item: string;
  use: string | null;
  amount_won: number;
  pct: number | null;
}

export interface DFSegmentRow {
  name: string;
  revenue_won: number;
  op_won?: number | null;
  assets_won?: number | null;
  depreciation_won?: number | null;
  op_margin?: number | null;
  revenue_pct: number | null;
}

export interface DFUnitConsumption {
  segment: string | null;
  type: string | null;
  material: string;
  price_item: string;
  join: string;
  year: string;
  unit_price: number | null;
  price_unit: string | null;
  amount_won: number;
  qty: number;
  qty_unit: string;
  output: number;
  output_unit: string;
  u: number;
  u_unit: string;
  trend: { year: string; u: number; qty?: number; output?: number }[];
  stable: boolean | null;
  note: string;
}

export interface DartFull {
  ticker: string;
  available: boolean;
  rcept?: string;
  url?: string;
  sections_found: string[];
  notes_found?: string[];
  notes_basis?: string | null;
  parsed?: string[];
  reason?: string;
  materials_purchase: { rows: DFMaterialRow[]; total_won: number; unit_won: number; source: string } | null;
  material_prices: {
    rows: { segment: string | null; type: string | null; item: string; prices: Record<string, number>; unit: string | null }[];
    unit_map: Record<string, string>;
    source: string;
  } | null;
  sales_mix: { rows: unknown[]; total_by_year: Record<string, number>; latest_period?: string; source: string } | null;
  segments: { rows: DFSegmentRow[]; total_revenue_won: number; source: string } | null;
  inventory: {
    items: { name: string; book_won: number; loss_won: number }[];
    total_won: number; gross_won: number | null; valuation_loss_won: number;
    loss_pct: number | null; raw_won?: number; wip_won?: number; fg_won?: number;
    source: string;
  } | null;
  related_party: {
    parties: { name: string; sales_won: number; purchase_won: number }[];
    sales_won: number; purchase_won: number; n_parties: number; source: string;
  } | null;
  audit_meta: {
    opinions?: { period: string | null; kind: string | null; auditor: string | null; opinion: string; kam: string | null }[];
    latest_opinion?: string;
    auditors?: (string | null)[];
    auditor_changed?: boolean;
    audit_service?: { period: string; hours: number | null; fee_mn: number | null }[];
    hours_chg?: number;
    fee_chg?: number;
  } | null;
  unit_consumption: DFUnitConsumption[];
  other_financial: Record<string, unknown>;
  consolidation?: Record<string, unknown>;
}

export const integrityApi = {
  dartFull: (ticker: string, refresh = false) =>
    request<DartFull>(`/api/data/dart-full?ticker=${encodeURIComponent(ticker)}${refresh ? "&refresh=true" : ""}`),
  integrity: (ticker: string, refresh = false) =>
    request<IntegrityScore>(`/api/data/integrity?ticker=${encodeURIComponent(ticker)}${refresh ? "&refresh=true" : ""}`),
};
