// 제품 단위 원가분해 + 경쟁사 원가·주가·뉴스 비교

import { request } from "./client";

// --- 제품 단위 원가분해 (unit economics) ------------------------------------
export interface UEProduct {
  id: string;
  ticker: string;
  company: string;
  product: string;
  unit: string;
  sector: string;
}

export interface UEWaterfallItem {
  item: string;
  won: number;
  pct_of_retail: number;
  kind: "channel" | "material" | "process" | "sga" | "profit";
  commodity?: string | null;
  commodity_key?: string | null;
  chg_1y?: number | null;
  direction?: "up" | "down" | "flat" | null;
}

export interface UESensitivity {
  item: string;
  commodity: string;
  op_delta_per_10pct: number;
  op_delta_pct_per_10pct: number | null;
  chg_1y: number | null;
  direction: "up" | "down" | "flat" | null;
}

export interface UnitEconomics {
  product: { ticker: string; company: string; product: string; unit: string; channel: string; note: string };
  as_of: string;
  basis: { source: string; year: number | null };
  summary: {
    retail_price: number;
    distribution_take: number;
    channel_label: string;
    factory_price: number;
    cogs_ratio: number;
    sga_ratio: number;
    op_margin: number;
    profit_per_unit: number;
  };
  waterfall: UEWaterfallItem[];
  materials: UEWaterfallItem[];
  sensitivity: UESensitivity[];
  momentum: {
    cost_delta_won: number;
    op_before: number;
    op_after: number;
    op_change_pct: number | null;
    verdict: string;
  };
  company?: {
    year: number | null;
    headcount: number | null;
    avg_salary_manwon: number | null;
    revenue_eok: number | null;
    labor_eok: number | null;
    labor_pct: number | null;
    sga_eok: number | null;
    op_eok: number | null;
    sga_per_day_eok: number | null;
  } | null;
}

// ── 경쟁사 원가·주가·뉴스 비교 (peer-compare) ──────────────────────────
export interface PeerCostRow {
  id: string;
  ticker: string;
  company: string;
  product: string;
  unit: string | null;
  is_base: boolean;
  retail_price: number | null;
  factory_price: number | null;
  cogs_ratio: number | null;
  sga_ratio: number | null;
  op_margin: number | null;
  profit_per_unit: number | null;
  material_pct: number | null;
  process_pct: number | null;
  basis_source: string | null;
  top_materials: { item: string; commodity: string | null; chg_1y: number | null; direction: string | null }[];
  annual_vol: number | null;
  ret_pct: number | null;
}

export interface PeerPrice {
  dates: string[];
  series: Record<string, (number | null)[]>;
  vol: Record<string, number | null>;
  ret_pct: Record<string, number | null>;
  meta: Record<string, { company: string; product: string; is_base: boolean }>;
}

export interface PeerCompare {
  product: string;
  sector: string;
  as_of: string;
  window_days: number;
  peers: PeerCostRow[];
  price: PeerPrice;
}

export interface PeerNewsItem {
  company: string;
  ticker: string;
  scope: "domestic" | "global";
  title: string | null;
  link: string | null;
  source: string | null;
  ts: number | null;
}

export interface PeerNews {
  product: string;
  sector: string;
  companies: { company: string; ticker: string }[];
  items: PeerNewsItem[];
}

export interface PeerGlobalMember {
  name: string;
  code: string;
  market: "KR" | "GLOBAL";
  country: string | null;
  market_cap_usd: number | null;
  op_margin: number | null;
  change_pct: number | null;
  is_base: boolean;
  is_leader?: boolean;
}

export interface PeerGlobal {
  product: string;
  sector: string;
  cluster: { key: string; label: string | null } | null;
  krw_usd: number;
  members: PeerGlobalMember[];
  base: { name: string; market_cap_usd: number | null } | null;
  leader: { name: string; market_cap_usd: number | null } | null;
  headroom_x: number | null;
  foreign_enabled: boolean;
  foreign_missing: number;
}

export const unitEconomicsApi = {
  unitEconomicsProducts: () =>
    request<{ as_of: string; products: UEProduct[] }>(`/api/data/unit-economics/products`),
  unitEconomics: (product: string) =>
    request<UnitEconomics>(`/api/data/unit-economics?product=${encodeURIComponent(product)}`),
  peerCompare: (product: string) =>
    request<PeerCompare>(`/api/data/peer-compare?product=${encodeURIComponent(product)}`),
  peerNews: (product: string, per = 6) =>
    request<PeerNews>(`/api/data/peer-news?product=${encodeURIComponent(product)}&per=${per}`),
  peerGlobal: (product: string) =>
    request<PeerGlobal>(`/api/data/peer-global?product=${encodeURIComponent(product)}`),
};
