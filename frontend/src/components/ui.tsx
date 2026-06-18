"use client";

import { ReactNode } from "react";

// Excel-spreadsheet light theme primitives. A "Card" reads as a worksheet panel:
// white sheet, thin gray gridline border, a quiet Office-gray header bar.
export function Card({
  title,
  subtitle,
  children,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm ${className}`}>
      {title && (
        <div className="border-b border-[#d0d0d0] bg-[#f3f2f1] px-4 py-2">
          <h3 className="text-sm font-bold tracking-tight text-[#217346]">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-[#888]">{subtitle}</p>}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-semibold text-[#555]">{label}</span>
      {children}
    </label>
  );
}

const inputCls =
  "rounded border border-[#bdbdbd] bg-white px-3 py-2 text-sm text-[#1f1f1f] outline-none transition focus:border-[#217346] focus:ring-1 focus:ring-[#217346]/40 placeholder:text-[#aaa]";

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${inputCls} ${props.className ?? ""}`} />;
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`${inputCls} ${props.className ?? ""}`} />;
}

export function Button({
  children,
  loading,
  variant = "primary",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  loading?: boolean;
  variant?: "primary" | "ghost";
}) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50";
  const styles =
    variant === "primary"
      ? "bg-[#217346] text-white hover:bg-[#1b5e3a] active:bg-[#174c2f]"
      : "border border-[#cdcdcd] bg-white text-[#217346] hover:bg-[#eef6f0]";
  return (
    <button {...props} disabled={props.disabled || loading} className={`${base} ${styles} ${props.className ?? ""}`}>
      {loading && <Spinner />}
      {children}
    </button>
  );
}

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <svg className={`h-4 w-4 animate-spin text-current ${className}`} viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-700">{message}</div>
  );
}

export function Stat({ label, value, tone }: { label: string; value: string; tone?: "pos" | "neg" }) {
  const color = tone === "pos" ? "text-[#c92a2a]" : tone === "neg" ? "text-[#1971c2]" : "text-[#1f1f1f]";
  return (
    <div className="rounded border border-[#e0e0e0] bg-[#f9f9f9] px-4 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-[#888]">{label}</div>
      <div className={`mt-1 text-lg font-bold tabular-nums ${color}`}>{value}</div>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="rounded border border-dashed border-[#cdcdcd] bg-[#fafafa] px-6 py-12 text-center text-sm text-[#888]">
      {children}
    </div>
  );
}
