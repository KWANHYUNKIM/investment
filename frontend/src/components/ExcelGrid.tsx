"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, GridRow } from "@/lib/api";
import { won } from "@/lib/format";

type ColType =
  | "date" | "code" | "name" | "text" | "price" | "chg" | "ret" | "vol" | "down" | "int"
  | "mult" | "roe" | "pctn" | "mcap";
type GroupKey = "id" | "price" | "ret" | "risk" | "trade" | "fund";
type Col = { key: keyof GridRow; label: string; group: GroupKey; w: number; type: ColType };

const COLS: Col[] = [
  { key: "date", label: "날짜", group: "id", w: 110, type: "date" },
  { key: "ticker", label: "코드", group: "id", w: 78, type: "code" },
  { key: "name", label: "종목명", group: "id", w: 168, type: "name" },
  { key: "sector", label: "소속", group: "id", w: 82, type: "text" },
  { key: "close", label: "현재가", group: "price", w: 104, type: "price" },
  { key: "change", label: "전일대비", group: "price", w: 104, type: "chg" },
  { key: "change_pct", label: "등락(%)", group: "ret", w: 92, type: "ret" },
  { key: "ret_1w", label: "1주(%)", group: "ret", w: 88, type: "ret" },
  { key: "ret_1m", label: "1개월(%)", group: "ret", w: 92, type: "ret" },
  { key: "ret_3m", label: "3개월(%)", group: "ret", w: 92, type: "ret" },
  { key: "ret_6m", label: "6개월(%)", group: "ret", w: 92, type: "ret" },
  { key: "ret_12m", label: "1년(%)", group: "ret", w: 92, type: "ret" },
  { key: "ret_ytd", label: "연초대비(%)", group: "ret", w: 108, type: "ret" },
  { key: "vol", label: "변동성(%)", group: "risk", w: 100, type: "vol" },
  { key: "pct_from_high", label: "고점대비(%)", group: "risk", w: 110, type: "down" },
  { key: "volume", label: "거래량", group: "trade", w: 130, type: "int" },
  { key: "per", label: "PER", group: "fund", w: 78, type: "mult" },
  { key: "pbr", label: "PBR", group: "fund", w: 78, type: "mult" },
  { key: "roe", label: "ROE(%)", group: "fund", w: 82, type: "roe" },
  { key: "div_yield", label: "배당(%)", group: "fund", w: 80, type: "pctn" },
  { key: "foreign_ratio", label: "외인(%)", group: "fund", w: 84, type: "pctn" },
  { key: "market_cap", label: "시총", group: "fund", w: 96, type: "mcap" },
];

const GROUPS: { key: GroupKey; label: string; bg: string; fg: string }[] = [
  { key: "id", label: "종목정보", bg: "#a9d08e", fg: "#244d1a" },
  { key: "price", label: "시세", bg: "#d9d9d9", fg: "#333" },
  { key: "ret", label: "기간 수익률", bg: "#f4b084", fg: "#7a3a0c" },
  { key: "risk", label: "리스크", bg: "#9dc3e6", fg: "#1a3a5e" },
  { key: "trade", label: "거래", bg: "#d9d9d9", fg: "#333" },
  { key: "fund", label: "펀더멘털", bg: "#c6e0b4", fg: "#2d5016" },
];

const GUTTER = 48;
const ROW_H = 34;

function colLetter(i: number): string {
  let s = "";
  i += 1;
  while (i > 0) {
    const m = (i - 1) % 26;
    s = String.fromCharCode(65 + m) + s;
    i = Math.floor((i - 1) / 26);
  }
  return s;
}

function cellStyle(type: ColType, v: number): React.CSSProperties {
  if (type === "ret") {
    const a = Math.min(Math.abs(v) / 40, 1) * 0.62;
    if (v > 0) return { backgroundColor: `rgba(224,49,49,${a})`, color: a > 0.4 ? "#fff" : "#c92a2a" };
    if (v < 0) return { backgroundColor: `rgba(28,126,214,${a})`, color: a > 0.4 ? "#fff" : "#1971c2" };
    return { color: "#666" };
  }
  if (type === "vol") {
    const a = Math.min(v / 60, 1) * 0.6;
    return { backgroundColor: `rgba(237,125,49,${a})`, color: a > 0.45 ? "#fff" : "#9a4a09" };
  }
  if (type === "down") {
    const a = Math.min(Math.abs(v) / 50, 1) * 0.55;
    return { backgroundColor: `rgba(28,126,214,${a})`, color: a > 0.4 ? "#fff" : "#1864ab" };
  }
  if (type === "chg") {
    if (v > 0) return { color: "#c92a2a" };
    if (v < 0) return { color: "#1971c2" };
    return { color: "#666" };
  }
  if (type === "roe") {
    const a = Math.min(Math.max(v, 0) / 30, 1) * 0.5; // higher ROE = greener
    return { backgroundColor: `rgba(112,173,71,${a})`, color: a > 0.35 ? "#1b3d0c" : "#2d5016" };
  }
  return {};
}

function cellText(type: ColType, v: number): string {
  if (type === "price") return won(v);
  if (type === "int") return v.toLocaleString("ko-KR");
  if (type === "vol") return v.toFixed(1);
  if (type === "chg") return `${v > 0 ? "▲ " : v < 0 ? "▼ " : ""}${won(Math.abs(v))}`;
  if (type === "mult") return v.toFixed(2);
  if (type === "roe") return v.toFixed(1);
  if (type === "pctn") return v.toFixed(2);
  if (type === "mcap") {
    if (v >= 1e12) return `${(v / 1e12).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}조`;
    if (v >= 1e8) return `${(v / 1e8).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}억`;
    return v.toLocaleString("ko-KR");
  }
  return `${v > 0 ? "+" : ""}${v.toFixed(2)}`;
}

const SHEETS = ["Data", "전체", "KOSPI", "KOSDAQ", "수익률", "리스크", "뉴스", "보유", "설정", "평균"] as const;

type Live = { price: number | null; change: number | null; change_pct: number | null };

export function ExcelGrid({ onPickStock }: { onPickStock: (row: GridRow) => void }) {
  const [rows, setRows] = useState<GridRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  const [q, setQ] = useState("");
  const [sheet, setSheet] = useState<string>("전체");
  const [sortKey, setSortKey] = useState<keyof GridRow>("volume");
  const [desc, setDesc] = useState(true);
  const [limit, setLimit] = useState(200);
  const [selCell, setSelCell] = useState<{ r: number; c: number }>({ r: 0, c: 2 });

  // --- live snapshot polling ---
  const [live, setLive] = useState<Map<string, Live>>(new Map());
  const [flash, setFlash] = useState<Map<string, "up" | "down">>(new Map());
  const [auto, setAuto] = useState(true);
  const [polling, setPolling] = useState(false);
  const prevPx = useRef<Map<string, number>>(new Map());

  useEffect(() => {
    api
      .screenTable()
      .then(setRows)
      .catch((e) => setErr(e?.message ?? "데이터를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, []);

  const refresh = useCallback(async () => {
    setPolling(true);
    try {
      const snap = await api.live();
      const m = new Map<string, Live>();
      const fl = new Map<string, "up" | "down">();
      for (const qt of snap.quotes) {
        m.set(qt.ticker, { price: qt.price, change: qt.change, change_pct: qt.change_pct });
        const prev = prevPx.current.get(qt.ticker);
        if (prev != null && qt.price != null && qt.price !== prev) {
          fl.set(qt.ticker, qt.price > prev ? "up" : "down");
        }
        if (qt.price != null) prevPx.current.set(qt.ticker, qt.price);
      }
      setLive(m);
      if (fl.size) {
        setFlash(fl);
        setTimeout(() => setFlash(new Map()), 1300);
      }
    } catch {
      /* keep last good snapshot */
    } finally {
      setPolling(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    if (!auto) return;
    const id = setInterval(refresh, 15000);
    return () => clearInterval(id);
  }, [auto, refresh]);

  const boardFilter = sheet === "KOSPI" || sheet === "KOSDAQ" ? sheet : null;

  const view = useMemo(() => {
    const n = q.trim().toLowerCase();
    let list = rows.filter((x) => {
      if (boardFilter && x.sector !== boardFilter) return false;
      if (!n) return true;
      return x.ticker.includes(n) || (x.name ?? "").toLowerCase().includes(n);
    });
    const dir = desc ? -1 : 1;
    list = [...list].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      if (typeof av === "string" || typeof bv === "string")
        return dir * String(av ?? "").localeCompare(String(bv ?? ""), "ko");
      return dir * (((av as number) ?? -Infinity) - ((bv as number) ?? -Infinity));
    });
    return list;
  }, [rows, q, boardFilter, sortKey, desc]);

  const shown = view.slice(0, limit);
  const totalW = GUTTER + COLS.reduce((a, c) => a + c.w, 0);

  function clickHeader(c: Col) {
    if (sortKey === c.key) setDesc((d) => !d);
    else {
      setSortKey(c.key);
      setDesc(true);
    }
    setLimit(200);
  }

  const selCol = COLS[selCell.c];
  const selRow = shown[selCell.r];
  const nameBox = selRow ? `${colLetter(selCell.c)}${selCell.r + 2}` : "—";

  return (
    <div className="flex h-full flex-col bg-white text-[#1f1f1f]">
      {/* toolbar / search + data controls */}
      <div className="flex shrink-0 flex-wrap items-center gap-3 border-b border-[#d0d0d0] bg-[#f3f2f1] px-3 py-2">
        <div className="flex items-center gap-2 rounded border border-[#bdbdbd] bg-white px-3 py-1.5">
          <span className="text-[#888]">🔍</span>
          <input
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setLimit(200);
            }}
            placeholder="종목명 또는 종목코드 검색"
            className="w-64 text-sm outline-none"
          />
        </div>

        <button
          onClick={refresh}
          disabled={polling}
          className="rounded border border-[#cdcdcd] bg-white px-2.5 py-1 text-xs text-[#217346] hover:bg-[#eef6f0] disabled:opacity-50"
        >
          {polling ? "계산 중…" : "↻ 새로고침"}
        </button>
        <label className="flex items-center gap-1.5 text-xs text-[#555]">
          <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} />
          자동
        </label>

        <span className="ml-auto text-xs text-[#666]">
          {view.length.toLocaleString("ko-KR")}개 · 정렬 {COLS.find((c) => c.key === sortKey)?.label} {desc ? "↓" : "↑"}
        </span>
      </div>

      {/* formula bar */}
      <div className="flex shrink-0 items-center gap-2 border-b border-[#d0d0d0] bg-white px-3 py-1.5 text-sm">
        <div className="flex w-24 items-center justify-center border border-[#d0d0d0] bg-[#f9f9f9] px-2 py-1 font-mono text-[#444]">
          {nameBox}
        </div>
        <span className="italic text-[#999]">fx</span>
        <div className="flex-1 truncate px-2 text-[#333]">
          {selRow ? `${selCol.label}: ${selRow[selCol.key] ?? ""}` : ""}
        </div>
      </div>

      {/* scrollable grid */}
      <div className="min-h-0 flex-1 overflow-auto bg-[#fafafa]">
        {loading ? (
          <div className="py-20 text-center text-base text-[#888]">불러오는 중…</div>
        ) : err ? (
          <div className="py-20 text-center text-base text-rose-600">{err}</div>
        ) : (
          <div style={{ width: totalW, minWidth: "100%" }}>
            <div className="sticky top-0 z-20 bg-white">
              <div className="flex border-b border-[#d0d0d0] bg-[#f0f0f0] text-xs text-[#888]">
                <div style={{ width: GUTTER }} className="shrink-0 border-r border-[#d0d0d0]" />
                {COLS.map((c, i) => (
                  <div
                    key={c.key}
                    style={{ width: c.w }}
                    className={`shrink-0 border-r border-[#d0d0d0] py-1 text-center ${
                      selCell.c === i ? "bg-[#cfe3d3] font-semibold text-[#217346]" : ""
                    }`}
                  >
                    {colLetter(i)}
                  </div>
                ))}
              </div>

              <div className="flex text-sm font-bold">
                <div style={{ width: GUTTER }} className="shrink-0 border-b border-r border-[#bdbdbd] bg-[#e9e9e9]" />
                {GROUPS.map((g) => {
                  const w = COLS.filter((c) => c.group === g.key).reduce((a, c) => a + c.w, 0);
                  if (w === 0) return null;
                  return (
                    <div
                      key={g.key}
                      style={{ width: w, backgroundColor: g.bg, color: g.fg }}
                      className="shrink-0 border-b border-r border-white py-1.5 text-center"
                    >
                      {g.label}
                    </div>
                  );
                })}
              </div>

              <div className="flex text-sm font-semibold text-[#333]">
                <div style={{ width: GUTTER }} className="shrink-0 border-b border-r border-[#bdbdbd] bg-[#e9e9e9] py-2" />
                {COLS.map((c) => {
                  const g = GROUPS.find((x) => x.key === c.group)!;
                  return (
                    <button
                      key={c.key}
                      onClick={() => clickHeader(c)}
                      style={{ width: c.w, backgroundColor: `${g.bg}66` }}
                      className="shrink-0 truncate border-b border-r border-[#cfcfcf] py-2 hover:brightness-95"
                      title={c.label}
                    >
                      {c.label}
                      {sortKey === c.key && <span className="ml-1">{desc ? "▼" : "▲"}</span>}
                    </button>
                  );
                })}
              </div>
            </div>

            {shown.map((row, ri) => {
              const lv = live.get(row.ticker);
              const fdir = flash.get(row.ticker);
              return (
                <div key={row.ticker} style={{ height: ROW_H }} className="flex text-[13px] tabular-nums hover:bg-[#fff7e6]">
                  <div
                    className={`flex shrink-0 items-center justify-center border-b border-r border-[#e0e0e0] bg-[#f0f0f0] text-xs text-[#999] ${
                      selCell.r === ri ? "bg-[#cfe3d3] font-semibold text-[#217346]" : ""
                    }`}
                    style={{ width: GUTTER }}
                  >
                    {ri + 2}
                  </div>
                  {COLS.map((c, ci) => {
                    let raw = row[c.key];
                    if (lv) {
                      if (c.key === "close" && lv.price != null) raw = lv.price;
                      if (c.key === "change" && lv.change != null) raw = lv.change;
                      if (c.key === "change_pct" && lv.change_pct != null) raw = lv.change_pct;
                    }
                    const selected = selCell.r === ri && selCell.c === ci;
                    const base = "flex shrink-0 items-center border-b border-r border-[#e6e6e6] px-2 truncate transition-colors";
                    const ring = selected ? "outline outline-2 -outline-offset-2 outline-[#217346]" : "";

                    if (c.type === "date" || c.type === "text") {
                      return (
                        <div key={c.key} style={{ width: c.w }} onClick={() => setSelCell({ r: ri, c: ci })}
                          className={`${base} ${ring} justify-center text-[#555]`}>
                          {raw ?? "—"}
                        </div>
                      );
                    }
                    if (c.type === "code" || c.type === "name") {
                      return (
                        <div key={c.key} style={{ width: c.w }}
                          onClick={() => { setSelCell({ r: ri, c: ci }); onPickStock(row); }}
                          className={`${base} ${ring} cursor-pointer ${c.type === "name" ? "justify-start" : "justify-center"} font-medium text-[#1155cc] underline decoration-[#1155cc]/30 underline-offset-2 hover:decoration-[#1155cc]`}>
                          {raw ?? "—"}
                        </div>
                      );
                    }
                    const v = raw as number | null;
                    const flashBg =
                      c.key === "close" && fdir
                        ? { backgroundColor: fdir === "up" ? "rgba(224,49,49,0.28)" : "rgba(28,126,214,0.28)" }
                        : undefined;
                    return (
                      <div key={c.key}
                        style={{ width: c.w, ...(v != null ? cellStyle(c.type, v) : {}), ...flashBg }}
                        onClick={() => setSelCell({ r: ri, c: ci })}
                        className={`${base} ${ring} justify-end ${v == null ? "text-[#ccc]" : ""}`}>
                        {v == null ? "—" : cellText(c.type, v)}
                      </div>
                    );
                  })}
                </div>
              );
            })}

            {shown.length === 0 && <div className="py-16 text-center text-base text-[#888]">검색 결과가 없습니다.</div>}
            {limit < view.length && (
              <button
                onClick={() => setLimit((l) => l + 400)}
                className="w-full border-b border-[#e0e0e0] bg-[#f3f2f1] py-2.5 text-sm text-[#217346] hover:bg-[#e8e8e8]"
              >
                더보기 ({(view.length - limit).toLocaleString("ko-KR")}행 남음)
              </button>
            )}
          </div>
        )}
      </div>

      {/* sheet tabs */}
      <div className="flex shrink-0 items-stretch gap-0.5 border-t border-[#d0d0d0] bg-[#f3f2f1] px-3 pt-1 text-xs">
        {SHEETS.map((s) => {
          const active = sheet === s;
          const clickable = s === "전체" || s === "KOSPI" || s === "KOSDAQ";
          return (
            <button
              key={s}
              onClick={() => {
                if (clickable) {
                  setSheet(s);
                  setLimit(200);
                }
              }}
              className={`border border-b-0 px-4 py-1.5 ${
                active ? "border-[#d0d0d0] bg-white font-semibold text-[#217346]" : "border-transparent text-[#666] hover:bg-[#e8e8e8]"
              } ${!clickable ? "opacity-60" : ""}`}
            >
              {s}
            </button>
          );
        })}
        <span className="ml-auto self-center pr-2 text-[11px] text-[#999]">준비 완료</span>
      </div>
    </div>
  );
}
