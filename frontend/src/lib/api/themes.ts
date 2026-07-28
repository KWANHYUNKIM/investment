// 미래 성장테마 — 메가트렌드 동향 + 매핑 종목

import { request } from "./client";

// 미래 성장테마 — 메가트렌드 동향 + 매핑 종목(미래가치 후보)
export interface FutureThemeMember {
  ticker: string;
  name: string | null;
  products: string | null;
  wics_sector: string | null;
  market_cap: number | null;
  close: number | null;
  change_pct: number | null;
  ret_1m: number | null;
  ret_3m: number | null;
  ret_12m: number | null;
  pct_from_high: number | null;
  per: number | null;
  pbr: number | null;
  beaten: boolean; // 최근 하락(파란) = 미래가치 후보
}

export interface FutureThemeNews {
  count: number;
  pos: number;
  neg: number;
  lean: "긍정" | "부정" | "중립";
  headlines: { title: string; link: string; source: string }[];
  digest: string[];
}

export interface FutureThemeIndexItem {
  key: string;
  label: string;
  icon: string;
  desc: string;
  momentum_score: number;
  member_count: number;
  beaten_count: number;
  news_count: number;
  lean: "긍정" | "부정" | "중립";
}

export interface FutureTheme {
  key: string;
  label: string;
  icon: string;
  desc: string;
  news: FutureThemeNews;
  momentum_score: number;
  member_count: number;
  beaten_count: number;
  members: FutureThemeMember[];
}

export interface FutureThemesResponse {
  themes: FutureThemeIndexItem[];
}

export interface FutureThemesStatus {
  running: boolean;
  ticks: number;
  theme_refreshes: number;
  snapshots: number;
  last_run: string | null;
  last_snapshot_date: string | null;
  last_error: string | null;
  interval_sec: number;
  snapshot_dates: string[];
}

export const themesApi = {
  futureThemes: () => request<FutureThemesResponse>(`/api/data/future-themes`),
  futureThemesStatus: () => request<FutureThemesStatus>(`/api/data/future-themes/status`),
  futureTheme: (key: string) => request<FutureTheme>(`/api/data/future-theme?key=${encodeURIComponent(key)}`),
};
