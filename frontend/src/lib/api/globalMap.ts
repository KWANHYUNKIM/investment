// 글로벌 경쟁지도 — 클러스터·배틀그라운드·기업 프로파일

import { request } from "./client";

// 기업 프로파일 — 기술/사업모델/해자/투자 (정성 큐레이션)
export interface GlobalProfile {
  tech?: string; // 핵심 기술/제품
  biz?: string; // 영업이익을 어떻게 내는지
  moat?: string; // 경쟁 우위/해자
  invest?: string; // R&D·CAPEX 투자와 그 회수
}

export interface GlobalMember {
  market: "KR" | "GL";
  code: string;
  name: string | null;
  country: string | null;
  market_cap_usd: number | null;
  revenue_usd?: number | null; // 매출액 (USD)
  op_profit_usd?: number | null; // 영업이익 (USD)
  net_income_usd?: number | null; // 순이익 (USD)
  op_margin: number | null; // 영업이익률 %
  net_margin?: number | null; // 순이익률 %
  gross_margin?: number | null; // 매출총이익률 %
  roe?: number | null; // ROE %
  debt_equity?: number | null; // 부채/자본 %
  pe?: number | null; // PER
  pb?: number | null; // PBR
  div_yield?: number | null; // 배당수익률 %
  // 투자효율 (이익/투자 대비)
  roic?: number | null; // 투하자본이익률 %
  roa?: number | null; // 총자산이익률 %
  asset_turnover?: number | null; // 자산회전율 (배)
  ev_ebitda?: number | null; // EV/EBITDA (배)
  rev_growth?: number | null; // 매출성장률 YoY %
  eps_growth?: number | null; // EPS성장률 YoY %
  rev_cagr5y?: number | null; // 5년 매출 CAGR %
  interest_cov?: number | null; // 이자보상배율 (배)
  op_yoy?: number | null; // 영업이익 YoY % (한국)
  fy?: string | null; // 기준 사업연도
  change_pct: number | null;
  note: string | null; // 주요제품 / 업종
  profile?: GlobalProfile | null;
}

export interface GlobalBattleground {
  arena: string; // 세부 전장 이름
  desc: string; // 경쟁 구도 설명
  players: string[]; // 주요 선수
}

export interface GlobalCluster {
  key: string;
  label: string;
  desc: string;
  count: number;
  kr_count: number;
  foreign_count: number;
  countries: string[];
  market_cap_usd: number;
  avg_op_margin: number | null;
  leader: string | null;
  tech?: boolean; // 기술주 클러스터
  battleground_count?: number; // index용
  battlegrounds?: GlobalBattleground[]; // detail용
  members?: GlobalMember[];
}

export interface GlobalClustersResponse {
  clusters: GlobalCluster[];
  finnhub: boolean;
  foreign_loaded: number;
}

export const globalMapApi = {
  globalClusters: () => request<GlobalClustersResponse>(`/api/data/global-clusters`),
  globalCluster: (key: string) => request<GlobalCluster>(`/api/data/global-cluster?key=${encodeURIComponent(key)}`),
};
