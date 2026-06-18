// Small formatting helpers shared across the dashboard.

export function pct(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

export function num(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toLocaleString("en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function compact(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toLocaleString("en-US", { notation: "compact", maximumFractionDigits: 1 });
}

export function signed(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const s = pct(v, digits);
  return v > 0 ? `+${s}` : s;
}

// Share quantity in 만(10k) units with sign: -1,596,173 -> "-159.6만".
export function manShares(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const sign = v > 0 ? "+" : v < 0 ? "-" : "";
  const a = Math.abs(v);
  if (a >= 10000) return `${sign}${(a / 10000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}만`;
  return `${sign}${a.toLocaleString("ko-KR")}`;
}

// Relative time in Korean from a unix-seconds timestamp.
export function ago(ts: number | null | undefined, nowMs: number): string {
  if (ts == null) return "";
  const diff = Math.floor(nowMs / 1000 - ts);
  if (diff < 60) return "방금";
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}일 전`;
  const d = new Date(ts * 1000);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

// Korean market convention: RED = up (상승), BLUE = down (하락).
export const UP = "#e03131";
export const DOWN = "#1c7ed6";
export const FLAT = "#868e96";

export function tone(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v) || v === 0) return FLAT;
  return v > 0 ? UP : DOWN;
}

export function toneClass(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v) || v === 0) return "text-[#888]";
  return v > 0 ? "text-[#c92a2a]" : "text-[#1971c2]";
}

export function arrow(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v) || v === 0) return "";
  return v > 0 ? "▲" : "▼";
}

// Korean won — integer, thousands separated.
export function won(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return Math.round(v).toLocaleString("ko-KR");
}

// Deterministic colour per series — used for charts and weight tables.
const PALETTE = [
  "#38bdf8", "#34d399", "#fbbf24", "#f472b6", "#a78bfa",
  "#fb7185", "#22d3ee", "#a3e635", "#fdba74", "#c084fc",
  "#4ade80", "#facc15", "#60a5fa", "#f87171", "#2dd4bf",
];
export function colorFor(key: string, index: number): string {
  return PALETTE[index % PALETTE.length] ?? "#94a3b8";
}
