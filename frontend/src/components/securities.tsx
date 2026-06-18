"use client";

import { useEffect, useMemo, useState } from "react";
import { api, Security } from "@/lib/api";

// Load the security universe once and cache it on the module.
let cache: Security[] | null = null;

export function useSecurities(market?: string) {
  const [all, setAll] = useState<Security[]>(cache ?? []);
  const [loading, setLoading] = useState(cache === null);

  useEffect(() => {
    if (cache) return;
    let alive = true;
    api
      .securities()
      .then((s) => {
        cache = s;
        if (alive) setAll(s);
      })
      .catch(() => {})
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  const list = useMemo(
    () => (market ? all.filter((s) => s.market === market) : all),
    [all, market],
  );
  return { list, loading };
}

export function label(s: Security): string {
  return s.name ? `${s.name} (${s.ticker})` : s.ticker;
}

export function TickerPicker({
  market,
  selected,
  onChange,
  max,
}: {
  market?: string;
  selected: string[];
  onChange: (next: string[]) => void;
  max?: number;
}) {
  const { list, loading } = useSecurities(market);
  const [query, setQuery] = useState("");
  const sel = new Set(selected);

  function toggle(ticker: string) {
    const next = new Set(sel);
    if (next.has(ticker)) next.delete(ticker);
    else {
      if (max && next.size >= max) return;
      next.add(ticker);
    }
    onChange([...next]);
  }

  const byTicker = useMemo(() => new Map(list.map((s) => [s.ticker, s])), [list]);
  const results = useMemo(() => {
    const n = query.trim().toLowerCase();
    const base = n
      ? list.filter((s) => s.ticker.includes(n) || (s.name ?? "").toLowerCase().includes(n))
      : list;
    return base.slice(0, 40);
  }, [list, query]);

  if (loading) return <p className="text-xs text-[#888]">종목 목록 불러오는 중…</p>;
  if (list.length === 0)
    return <p className="text-xs text-[#888]">저장된 종목이 없습니다. 먼저 데이터를 적재하세요.</p>;

  return (
    <div>
      {/* selected chips */}
      {selected.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {selected.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => toggle(t)}
              className="inline-flex items-center gap-1 rounded-full border border-[#cdcdcd] bg-[#eef6f0] px-2 py-0.5 text-xs text-[#217346] hover:bg-[#e0efe5]"
            >
              {byTicker.get(t)?.name ?? t}
              <span className="text-[#217346]">✕</span>
            </button>
          ))}
        </div>
      )}

      <div className="mb-2 flex items-center justify-between gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="종목 검색 (이름/코드)"
          className="flex-1 rounded-lg border border-[#bdbdbd] bg-white px-3 py-1.5 text-xs text-[#1f1f1f] outline-none focus:border-[#217346]"
        />
        <span className="shrink-0 text-[11px] text-[#888]">
          {selected.length}개{max ? `/${max}` : ""}
        </span>
        {selected.length > 0 && (
          <button type="button" onClick={() => onChange([])} className="shrink-0 text-[11px] text-[#888] hover:text-[#555]">
            해제
          </button>
        )}
      </div>

      <div className="grid max-h-48 grid-cols-2 gap-1 overflow-y-auto rounded-lg border border-[#d0d0d0] bg-[#fafafa] p-2 sm:grid-cols-3">
        {results.map((s) => {
          const on = sel.has(s.ticker);
          return (
            <button
              key={`${s.market}-${s.ticker}`}
              type="button"
              onClick={() => toggle(s.ticker)}
              className={`truncate rounded px-2 py-1.5 text-left text-xs transition ${
                on ? "border border-[#cdcdcd] bg-[#eef6f0] text-[#217346]" : "text-[#555] hover:bg-[#fff7e6]"
              }`}
              title={label(s)}
            >
              {s.name ?? s.ticker}
              <span className="ml-1 text-[10px] text-[#888]">{s.ticker}</span>
            </button>
          );
        })}
        {results.length === 0 && <p className="col-span-full py-3 text-center text-xs text-[#888]">검색 결과 없음</p>}
      </div>
    </div>
  );
}
