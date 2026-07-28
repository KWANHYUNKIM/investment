// 업종 경쟁지도 — 업종별 구성원·연구(기술/M&A/계약/실적/전략)

import { request } from "./client";

// --- Industry / competition map -------------------------------------------
export interface IndustryMember {
  ticker: string;
  name: string | null;
  products: string | null;
  region?: string | null;
  representative?: string | null;
  homepage?: string | null;
  market_cap: number | null;
  change_pct: number | null;
  fy?: string | null; // 최근 사업연도 (YYYY/MM)
  sales?: number | null; // 매출액 (억)
  op_profit?: number | null; // 영업이익 (억)
  net_income?: number | null; // 당기순이익 (억)
  op_margin?: number | null; // 영업이익률 (%)
  op_yoy?: number | null; // 영업이익 전년대비 (%)
  per?: number | null; // PER (배) — 같은 업종 내 밸류 비교
  pbr?: number | null; // PBR (배)
  roe?: number | null; // ROE (%)
}

export interface IndustryGroup {
  industry: string;
  count: number;
  market_cap: number;
  avg_change_pct: number | null;
  op_profit?: number | null; // 업종 합산 영업이익 (억)
  op_margin?: number | null; // 업종 영업이익률 (%)
  op_count?: number; // 실적 집계된 기업 수
  leader: string | null;
  members: IndustryMember[];
}

export interface IndustryIndexItem {
  industry: string;
  count: number;
  market_cap: number;
  avg_change_pct: number | null;
  op_profit?: number | null;
  op_margin?: number | null;
  op_count?: number;
  leader: string | null;
}

export interface ThemeItem {
  company: string;
  ticker: string | null;
  title: string;
  link: string | null;
  source: string | null;
  themes: string[];
}

export interface ThemeBucket {
  key: string;
  label: string;
  count: number;
  items: ThemeItem[];
}

export interface IndustryResearch {
  industry: string;
  leader: string | null;
  count: number;
  market_cap: number;
  analyzed: string[];
  competitors: { ticker: string; name: string | null; market_cap: number | null; products: string | null }[];
  themes: ThemeBucket[];
  summary: string;
}

export interface IndustriesIndexResponse {
  industries: IndustryIndexItem[];
  scheduler?: Record<string, unknown>;
}

export interface IndustryDetailResponse {
  group: IndustryGroup;
  research: IndustryResearch | null;
}

export const industryApi = {
  industries: () => request<IndustriesIndexResponse>(`/api/data/industries`),
  industry: (name: string) =>
    request<IndustryDetailResponse>(`/api/data/industry?name=${encodeURIComponent(name)}`),
};
