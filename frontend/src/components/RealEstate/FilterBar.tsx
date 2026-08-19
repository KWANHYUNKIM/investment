"use client";

import { useEffect, useRef, useState, ReactNode } from "react";
import type { PropertyKind, PropertyKindMeta, TradeKind } from "@/lib/api";
import { TRADE_META, AreaUnit } from "./format";
import {
  AREA_BUCKETS, BUILD_AGES, FLOOR_BANDS, DEFAULT_FILTERS,
  Filters, activeCount,
} from "./filters";

/* 네이버 부동산 상단 필터바 — 칩을 누르면 아래로 패널이 열리는 방식. */

function Chip({
  label, value, active, children, width = 240,
}: {
  label: string;
  value?: string | null;
  active: boolean;
  children: ReactNode;
  width?: number;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className={`flex items-center gap-1 whitespace-nowrap rounded-full border px-3 py-1.5 text-[12px] font-semibold transition ${
          active
            ? "border-[#217346] bg-[#217346] text-white"
            : "border-[#d5d5d5] bg-white text-[#444] hover:border-[#217346] hover:text-[#217346]"
        }`}
      >
        {active && value ? value : label}
        <span className={`text-[8px] transition ${open ? "rotate-180" : ""}`}>▼</span>
      </button>
      {open && (
        <div
          style={{ width }}
          className="absolute left-0 top-[calc(100%+6px)] z-[1200] rounded-lg border border-[#ddd] bg-white p-3 shadow-[0_6px_20px_rgba(0,0,0,.14)]"
        >
          {children}
        </div>
      )}
    </div>
  );
}

function Toggle({ on, onClick, children }: { on: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`rounded border px-2 py-1 text-[11px] font-semibold transition ${
        on ? "border-[#217346] bg-[#eef6f0] text-[#217346]" : "border-[#ddd] bg-white text-[#666] hover:border-[#bbb]"
      }`}
    >
      {children}
    </button>
  );
}

function NumInput({
  value, onChange, placeholder,
}: {
  value: number | null;
  onChange: (v: number | null) => void;
  placeholder: string;
}) {
  return (
    <input
      type="number"
      value={value ?? ""}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
      className="w-full rounded border border-[#ddd] px-2 py-1 text-[12px] outline-none focus:border-[#217346]"
    />
  );
}

export function FilterBar({
  filters, onChange, areaUnit, onAreaUnit, resultCount, kinds, kind, onKind,
}: {
  filters: Filters;
  onChange: (f: Filters) => void;
  areaUnit: AreaUnit;
  onAreaUnit: (u: AreaUnit) => void;
  resultCount: number | null;
  kinds: PropertyKindMeta[];
  kind: PropertyKind;
  onKind: (k: PropertyKind) => void;
}) {
  const f = filters;
  const set = (patch: Partial<Filters>) => onChange({ ...f, ...patch });
  const nActive = activeCount(f);

  const toggleIn = (arr: string[], key: string) =>
    arr.includes(key) ? arr.filter((k) => k !== key) : [...arr, key];

  const priceLabel =
    f.priceMin != null || f.priceMax != null
      ? `${f.priceMin ?? "0"}~${f.priceMax ?? "∞"}억`
      : null;
  const areaLabel = f.areas.length ? `면적 ${f.areas.length}` : null;
  const buildLabel = BUILD_AGES.find((b) => b.key === f.buildAge)?.label ?? null;
  const floorLabel = f.floors.length
    ? f.floors.map((k) => FLOOR_BANDS.find((b) => b.key === k)?.label).join("·")
    : null;
  const moreActive = f.minDeals > 0 || f.jeonseRatioMin != null || f.favOnly;

  const kindMeta = kinds.find((k) => k.key === kind);
  const rentBlocked = !!kindMeta && !kindMeta.has_rent;

  return (
    <div className="flex flex-col gap-2">
      {/* 매물 종류 — 네이버의 아파트/오피스텔/빌라… 탭 */}
      {kinds.length > 0 && (
        <div className="flex flex-wrap items-center gap-1 border-b border-[#eee] pb-2">
          {kinds.map((k) => (
            <button
              key={k.key}
              onClick={() => onKind(k.key)}
              className={`rounded px-2.5 py-1 text-[12px] font-bold transition ${
                kind === k.key
                  ? "bg-[#f0f6f2] text-[#217346] shadow-[inset_0_-2px_0_#217346]"
                  : "text-[#777] hover:bg-[#f5f5f5] hover:text-[#333]"
              }`}
            >
              {k.label}
            </button>
          ))}
        </div>
      )}

    <div className="flex flex-wrap items-center gap-1.5">
      {/* 거래유형 — 네이버의 매매/전세/월세 세그먼트 */}
      <div className="flex overflow-hidden rounded-full border border-[#d5d5d5] bg-white">
        {(["sale", "jeonse", "wolse"] as TradeKind[]).map((t) => {
          const on = f.trade === t;
          const blocked = rentBlocked && t !== "sale";
          return (
            <button
              key={t}
              disabled={blocked}
              title={blocked ? `${kindMeta?.label}은(는) 전월세 실거래가 공공데이터에 없습니다` : undefined}
              onClick={() => set({ trade: t, monthlyMax: t === "wolse" ? f.monthlyMax : null })}
              style={on ? { background: TRADE_META[t].color } : undefined}
              className={`px-3.5 py-1.5 text-[12px] font-bold transition ${
                on ? "text-white"
                  : blocked ? "cursor-not-allowed text-[#ccc]"
                  : "text-[#666] hover:bg-[#f4f4f4]"
              }`}
            >
              {TRADE_META[t].label}
            </button>
          );
        })}
      </div>

      <Chip label="가격" value={priceLabel} active={priceLabel != null} width={250}>
        <div className="mb-2 text-[11px] font-bold text-[#555]">
          {f.trade === "wolse" ? "보증금 (억)" : "가격 (억)"}
        </div>
        <div className="flex items-center gap-1.5">
          <NumInput value={f.priceMin} onChange={(v) => set({ priceMin: v })} placeholder="최소" />
          <span className="text-[#bbb]">~</span>
          <NumInput value={f.priceMax} onChange={(v) => set({ priceMax: v })} placeholder="최대" />
        </div>
        {f.trade === "wolse" && (
          <>
            <div className="mb-2 mt-3 text-[11px] font-bold text-[#555]">월세 상한 (만원)</div>
            <NumInput value={f.monthlyMax} onChange={(v) => set({ monthlyMax: v })} placeholder="예: 150" />
          </>
        )}
        <div className="mt-2 flex flex-wrap gap-1">
          {[3, 5, 8, 10, 15, 20].map((v) => (
            <Toggle key={v} on={f.priceMax === v} onClick={() => set({ priceMin: null, priceMax: v })}>
              {v}억 이하
            </Toggle>
          ))}
          <Toggle on={f.priceMin == null && f.priceMax == null} onClick={() => set({ priceMin: null, priceMax: null })}>
            전체
          </Toggle>
        </div>
      </Chip>

      <Chip label="면적" value={areaLabel} active={f.areas.length > 0} width={230}>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[11px] font-bold text-[#555]">전용면적</span>
          <div className="flex overflow-hidden rounded border border-[#ddd]">
            {(["m2", "pyeong"] as AreaUnit[]).map((u) => (
              <button
                key={u}
                onClick={() => onAreaUnit(u)}
                className={`px-2 py-0.5 text-[10px] font-bold ${
                  areaUnit === u ? "bg-[#217346] text-white" : "bg-white text-[#666]"
                }`}
              >
                {u === "m2" ? "㎡" : "평"}
              </button>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap gap-1">
          {AREA_BUCKETS.map((b) => (
            <Toggle key={b.key} on={f.areas.includes(b.key)} onClick={() => set({ areas: toggleIn(f.areas, b.key) })}>
              {b.label}
            </Toggle>
          ))}
        </div>
        {f.areas.length > 0 && (
          <button onClick={() => set({ areas: [] })} className="mt-2 text-[11px] text-[#888] underline">
            면적 초기화
          </button>
        )}
      </Chip>

      <Chip label="준공" value={buildLabel} active={f.buildAge != null} width={200}>
        <div className="mb-2 text-[11px] font-bold text-[#555]">입주년차</div>
        <div className="flex flex-wrap gap-1">
          {BUILD_AGES.map((b) => (
            <Toggle
              key={b.key}
              on={f.buildAge === b.key}
              onClick={() => set({ buildAge: f.buildAge === b.key ? null : b.key })}
            >
              {b.label}
            </Toggle>
          ))}
        </div>
      </Chip>

      <Chip label="층수" value={floorLabel} active={f.floors.length > 0} width={190}>
        <div className="mb-2 text-[11px] font-bold text-[#555]">거래 층</div>
        <div className="flex flex-wrap gap-1">
          {FLOOR_BANDS.map((b) => (
            <Toggle key={b.key} on={f.floors.includes(b.key)} onClick={() => set({ floors: toggleIn(f.floors, b.key) })}>
              {b.label}
              <span className="ml-1 text-[9px] text-[#aaa]">
                {b.max === Infinity ? `${b.min}층~` : `${b.min}-${b.max}층`}
              </span>
            </Toggle>
          ))}
        </div>
      </Chip>

      <Chip label="더보기" value={moreActive ? "조건 적용" : null} active={moreActive} width={260}>
        <div className="mb-1.5 text-[11px] font-bold text-[#555]">최소 거래건수</div>
        <div className="flex flex-wrap gap-1">
          {[0, 2, 3, 5, 10].map((n) => (
            <Toggle key={n} on={f.minDeals === n} onClick={() => set({ minDeals: n })}>
              {n === 0 ? "전체" : `${n}건 이상`}
            </Toggle>
          ))}
        </div>
        {f.trade === "sale" && (
          <>
            <div className="mb-1.5 mt-3 text-[11px] font-bold text-[#555]">
              전세가율 하한 <span className="font-normal text-[#999]">(같은 달 전세 실거래 기준)</span>
            </div>
            <div className="flex flex-wrap gap-1">
              {[null, 60, 70, 80].map((v) => (
                <Toggle key={String(v)} on={f.jeonseRatioMin === v} onClick={() => set({ jeonseRatioMin: v })}>
                  {v == null ? "전체" : `${v}% 이상`}
                </Toggle>
              ))}
            </div>
          </>
        )}
        <div className="mt-3">
          <Toggle on={f.favOnly} onClick={() => set({ favOnly: !f.favOnly })}>
            ★ 관심단지만 보기
          </Toggle>
        </div>
      </Chip>

      {nActive > 0 && (
        <button
          onClick={() => onChange({ ...DEFAULT_FILTERS, trade: f.trade })}
          className="flex items-center gap-1 whitespace-nowrap rounded-full border border-[#e2b7b7] bg-white px-3 py-1.5 text-[12px] font-semibold text-[#c0392b] hover:bg-[#fdf1f1]"
        >
          ↺ 초기화 <span className="rounded-full bg-[#c0392b] px-1.5 text-[10px] text-white">{nActive}</span>
        </button>
      )}

      {resultCount != null && (
        <span className="ml-auto whitespace-nowrap text-[11px] text-[#888]">
          결과 <b className="text-[#217346]">{resultCount.toLocaleString()}</b>개
        </span>
      )}
    </div>
    </div>
  );
}
