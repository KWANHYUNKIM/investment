"use client";

import { useEffect } from "react";

export const RED = "#c92a2a";

export const BLUE = "#1971c2";

// 한국 시장 관례: 상승=빨강, 하락=파랑.
export function retStyle(v: number | null): React.CSSProperties {
  if (v == null) return { color: "#bbb" };
  return { color: v > 0 ? RED : v < 0 ? BLUE : "#666", fontWeight: 700 };
}

// 통화량 증가율: 확대=빨강(돈 풀림), 둔화/수축=파랑
export function growthColor(v: number | null | undefined): string {
  if (v == null) return "#888";
  return v > 0 ? RED : v < 0 ? BLUE : "#666";
}

export function gpct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${v > 0 ? "+" : ""}${v}%`;
}

// 클릭하면 뜨는 큰 차트 모달 셸 (배경 클릭·ESC로 닫힘)
export function Modal({ title, sub, onClose, children }: { title: string; sub?: string; onClose: () => void; children: React.ReactNode }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", h);
      document.body.style.overflow = "";
    };
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="w-full max-w-4xl rounded-lg bg-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between border-b border-[#eee] px-4 py-2.5">
          <div>
            <div className="text-sm font-bold text-[#1f1f1f]">{title}</div>
            {sub && <div className="text-[11px] text-[#888]">{sub}</div>}
          </div>
          <button onClick={onClose} className="rounded border border-[#ddd] px-2 py-0.5 text-xs text-[#666] hover:bg-[#f3f3f3]">닫기 ✕</button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}

export function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div className="text-[11px] text-[#888]">{label}</div>
      <div className="text-base font-bold tabular-nums" style={{ color: color ?? "#1f1f1f" }}>{value}</div>
    </div>
  );
}
