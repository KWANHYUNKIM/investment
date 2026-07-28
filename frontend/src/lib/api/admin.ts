// 관리자 — 블로그 발행/보관함·방문 통계·큐레이션

import { request } from "./client";

export interface BlogPost { title: string; markdown: string; html: string; tags: string[]; generated_at: string; }

// 자동 발행되어 data/blog_posts 에 보관된 글
export interface BlogSavedPost extends BlogPost {
  date: string; kind: string; saved_at?: string; reused?: boolean;
  path?: string; markdown_path?: string; available?: boolean; reason?: string;
}

export interface BlogPostListItem {
  date: string; kind: string; title: string; tags: string[];
  saved_at: string; chars: number; sections: number; file: string;
}

export interface BlogSchedulerStatus {
  running: boolean; enabled: boolean; schedule: string;
  posts: number; last_run: string | null; last_post_date: string | null;
  last_title: string | null; skipped_reason: string | null; last_error: string | null;
  latest_post: { date?: string; title?: string; saved_at?: string } | null;
}

export interface AdminUser { username: string; email: string | null; name: string | null; created: number | null; is_admin: boolean; }

export interface AdminStatus {
  coverage: { market: string; tickers: number; rows: number; first_date: string; last_date: string }[];
  price_scheduler: Record<string, unknown>;
  report_scheduler: Record<string, unknown>;
  fundamentals_crawler: Record<string, unknown>;
  dart_enabled: boolean;
}

export interface VisitorStats {
  total: number; today: number;
  top_views: { view: string; count: number }[];
  daily: { date: string; count: number }[];
}

export interface Curation { headline: string; picks: string[]; note: string; updated_at: string | null; }

export const adminApi = {
  // 관리자
  adminBlogGenerate: (p: { kind: string; ticker?: string; title?: string; body?: string }) =>
    request<BlogPost>("/api/admin/blog/generate", { method: "POST", body: JSON.stringify(p) }),
  adminUsers: () => request<{ users: AdminUser[]; admins: string[] }>("/api/admin/users"),
  adminBlogPublish: (date = "", force = true) =>
    request<BlogSavedPost>("/api/admin/blog/publish", {
      method: "POST", body: JSON.stringify({ date, force }),
    }),
  adminBlogPosts: (limit = 60) =>
    request<{ posts: BlogPostListItem[]; dir: string }>(`/api/admin/blog/posts?limit=${limit}`),
  adminBlogPost: (date = "", kind = "market-wrap") =>
    request<BlogSavedPost>(
      `/api/admin/blog/post?date=${encodeURIComponent(date)}&kind=${encodeURIComponent(kind)}`),
  adminBlogScheduler: () => request<BlogSchedulerStatus>("/api/admin/blog/scheduler"),
  adminStatus: () => request<AdminStatus>("/api/admin/status"),
  adminStats: () => request<VisitorStats>("/api/admin/stats"),
  adminCurationGet: () => request<Curation>("/api/admin/curation"),
  adminCurationSet: (headline: string, picks: string[], note: string) =>
    request<Curation>("/api/admin/curation", { method: "POST", body: JSON.stringify({ headline, picks, note }) }),
};
