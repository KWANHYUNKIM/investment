"use client";

import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { api, GridRow } from "@/lib/api";
import { won } from "@/lib/format";
import { mq } from "@/lib/breakpoints";

type ColType =
  | "date" | "code" | "name" | "text" | "price" | "chg" | "ret" | "vol" | "down" | "int"
  | "mult" | "roe" | "pctn" | "mcap";
type GroupKey = "name" | "id" | "price" | "ret" | "risk" | "trade" | "fund";
type Col = { key: keyof GridRow; label: string; group: GroupKey; w: number; type: ColType };

// 종목명이 첫 열이고 자기 그룹을 혼자 쓴다. 틀 고정(sticky) 블록이 그룹 경계와 정확히
// 일치해야 그룹 헤더 칸을 쪼개지 않고 그대로 고정할 수 있다.
const COLS: Col[] = [
  { key: "name", label: "종목명", group: "name", w: 168, type: "name" },
  { key: "date", label: "날짜", group: "id", w: 110, type: "date" },
  { key: "ticker", label: "코드", group: "id", w: 78, type: "code" },
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
  { key: "name", label: "종목", bg: "#a9d08e", fg: "#244d1a" },
  { key: "id", label: "종목정보", bg: "#a9d08e", fg: "#244d1a" },
  { key: "price", label: "시세", bg: "#d9d9d9", fg: "#333" },
  { key: "ret", label: "기간 수익률", bg: "#f4b084", fg: "#7a3a0c" },
  { key: "risk", label: "리스크", bg: "#9dc3e6", fg: "#1a3a5e" },
  { key: "trade", label: "거래", bg: "#d9d9d9", fg: "#333" },
  { key: "fund", label: "펀더멘털", bg: "#c6e0b4", fg: "#2d5016" },
];

const GUTTER = 48;
const ROW_H = 34;

// 폰에서 숨기는 열. 좁은 화면의 앞자리를 날짜·코드가 차지하면 정작 봐야 할
// 현재가·등락%가 400px 밖으로 밀린다. 데이터는 그대로고 표시만 줄인다.
// 전일대비는 등락(%)과 같은 사실을 다르게 쓴 것이라 폰에서는 뺀다 — 이 셋을 빼야
// 종목명·현재가·등락% 가 스크롤 없이 한 화면에 들어온다(390px 기준 328px).
const PHONE_HIDDEN = new Set<keyof GridRow>(["date", "ticker", "sector", "change"]);
const PHONE_NAME_W = 132;

// 헤더 라벨 줄은 그룹색을 40%(=66) 알파로 깔지만, 고정 열은 아래 셀이 비쳐 보이면
// 안 되므로 같은 색을 흰 배경에 미리 섞어 불투명하게 쓴다.
function blendOverWhite(hex: string, alpha: number): string {
  const n = parseInt(hex.slice(1), 16);
  const mix = (c: number) => Math.round(c * alpha + 255 * (1 - alpha));
  const r = mix((n >> 16) & 255), g = mix((n >> 8) & 255), b = mix(n & 255);
  return `rgb(${r} ${g} ${b})`;
}

// 폰 여부. 렌더 중 window 를 직접 읽으면 SSR 과 어긋나므로 구독 형태로 읽는다.
// 기준값은 lib/breakpoints 에서만 정의한다 — Tailwind 의 sm 과 같은 640 이어야 하는데
// 여기에 숫자를 따로 적어 두면 한쪽만 바뀌었을 때 열 개수와 여백이 어긋난다.
function useIsPhone(): boolean {
  return useSyncExternalStore(
    (cb) => {
      const m = window.matchMedia(mq.phone);
      m.addEventListener("change", cb);
      return () => m.removeEventListener("change", cb);
    },
    () => window.matchMedia(mq.phone).matches,
    () => false,
  );
}

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
  const [selCell, setSelCell] = useState<{ r: number; c: number }>({ r: 0, c: 0 });

  // 폰에서는 열을 줄이고 행번호 칸을 없앤다. 첫 열(종목명)은 항상 틀 고정.
  const phone = useIsPhone();
  const cols = useMemo(
    () => (phone ? COLS.filter((c) => !PHONE_HIDDEN.has(c.key)) : COLS),
    [phone],
  );
  const colW = useCallback(
    (c: Col) => (phone && c.key === "name" ? PHONE_NAME_W : c.w),
    [phone],
  );
  const gutter = phone ? 0 : GUTTER;

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
  const totalW = gutter + cols.reduce((a, c) => a + colW(c), 0);

  function clickHeader(c: Col) {
    if (sortKey === c.key) setDesc((d) => !d);
    else {
      setSortKey(c.key);
      setDesc(true);
    }
    setLimit(200);
  }

  // 폰 전환으로 열이 줄면 선택 위치가 범위를 벗어날 수 있다.
  const selColIdx = Math.min(selCell.c, cols.length - 1);
  const selCol = cols[selColIdx];
  const selRow = shown[selCell.r];
  const nameBox = selRow ? `${colLetter(selColIdx)}${selCell.r + 2}` : "—";

  return (
    <div className="flex h-full flex-col bg-white text-[#1f1f1f]">
      {/* toolbar / search + data controls */}
      <div className="flex shrink-0 flex-wrap items-center gap-3 border-b border-[#d0d0d0] bg-[#f3f2f1] px-3 py-2">
        <div className="flex items-center gap-2 rounded border border-[#bdbdbd] bg-white px-3 py-1.5">
          <span className="text-[#888]"></span>
          <input
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setLimit(200);
            }}
            placeholder="종목명 또는 종목코드 검색"
            className="w-40 text-sm outline-none sm:w-64"
          />
        </div>

        {/* 시장 필터 — <lg 전용. 하단 시트탭 줄이 앱 내비게이션에 넘어갔으므로 여기로 올라왔다. */}
        <div className="flex items-stretch border border-[#bdbdbd] bg-white lg:hidden">
          {(["전체", "KOSPI", "KOSDAQ"] as const).map((s) => (
            <button
              key={s}
              onClick={() => { setSheet(s); setLimit(200); }}
              aria-pressed={sheet === s}
              className={`min-h-11 border-r border-[#e2e2e2] px-3.5 text-xs last:border-r-0 ${
                sheet === s ? "bg-[#217346] font-semibold text-white" : "text-[#4a4a4a]"
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        <button
          onClick={refresh}
          disabled={polling}
          className="min-h-11 rounded border border-[#cdcdcd] bg-white px-2.5 text-xs text-[#217346] hover:bg-[#eef6f0] disabled:opacity-50 lg:min-h-0 lg:py-1"
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
                {gutter > 0 && (
                  <div style={{ width: gutter, left: 0 }} className="sticky z-10 shrink-0 border-r border-[#d0d0d0] bg-[#f0f0f0]" />
                )}
                {cols.map((c, i) => (
                  <div
                    key={c.key}
                    style={i === 0 ? { width: colW(c), left: gutter } : { width: colW(c) }}
                    className={`shrink-0 border-r border-[#d0d0d0] py-1 text-center ${i === 0 ? "sticky z-10 bg-[#f0f0f0]" : ""} ${
                      selColIdx === i ? "bg-[#cfe3d3] font-semibold text-[#217346]" : ""
                    }`}
                  >
                    {colLetter(i)}
                  </div>
                ))}
              </div>

              <div className="flex text-sm font-bold">
                {gutter > 0 && (
                  <div style={{ width: gutter, left: 0 }} className="sticky z-10 shrink-0 border-b border-r border-[#bdbdbd] bg-[#e9e9e9]" />
                )}
                {GROUPS.map((g) => {
                  const w = cols.filter((c) => c.group === g.key).reduce((a, c) => a + colW(c), 0);
                  if (w === 0) return null;
                  // 첫 열 그룹(종목)은 고정 블록과 폭이 정확히 같아 통째로 붙여둘 수 있다.
                  const frozen = g.key === cols[0].group;
                  return (
                    <div
                      key={g.key}
                      style={{ width: w, backgroundColor: g.bg, color: g.fg, ...(frozen ? { left: gutter } : {}) }}
                      className={`shrink-0 border-b border-r border-white py-1.5 text-center ${frozen ? "sticky z-10" : ""}`}
                    >
                      {g.label}
                    </div>
                  );
                })}
              </div>

              <div className="flex text-sm font-semibold text-[#333]">
                {gutter > 0 && (
                  <div style={{ width: gutter, left: 0 }} className="sticky z-10 shrink-0 border-b border-r border-[#bdbdbd] bg-[#e9e9e9] py-2" />
                )}
                {cols.map((c, i) => {
                  const g = GROUPS.find((x) => x.key === c.group)!;
                  const frozen = i === 0;
                  return (
                    <button
                      key={c.key}
                      onClick={() => clickHeader(c)}
                      style={{
                        width: colW(c),
                        // 고정 열은 반투명이면 아래 셀이 비친다 — 같은 색을 미리 흰색에 섞어 쓴다.
                        backgroundColor: frozen ? blendOverWhite(g.bg, 0.4) : `${g.bg}66`,
                        ...(frozen ? { left: gutter } : {}),
                      }}
                      className={`shrink-0 truncate border-b border-r border-[#cfcfcf] py-2 hover:brightness-95 ${frozen ? "sticky z-10" : ""}`}
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
              // group: 고정 셀은 자체 배경을 깔아야 해서 행 hover 를 직접 못 받는다
              return (
                <div key={row.ticker} style={{ height: ROW_H }} className="group flex text-[13px] tabular-nums hover:bg-[#fff7e6]">
                  {gutter > 0 && (
                    <div
                      className={`sticky left-0 z-10 flex shrink-0 items-center justify-center border-b border-r border-[#e0e0e0] text-xs text-[#999] ${
                        selCell.r === ri ? "bg-[#cfe3d3] font-semibold text-[#217346]" : "bg-[#f0f0f0]"
                      }`}
                      style={{ width: gutter }}
                    >
                      {ri + 2}
                    </div>
                  )}
                  {cols.map((c, ci) => {
                    let raw = row[c.key];
                    if (lv) {
                      if (c.key === "close" && lv.price != null) raw = lv.price;
                      if (c.key === "change" && lv.change != null) raw = lv.change;
                      if (c.key === "change_pct" && lv.change_pct != null) raw = lv.change_pct;
                    }
                    const selected = selCell.r === ri && selColIdx === ci;
                    const base = "flex shrink-0 items-center border-b border-r border-[#e6e6e6] px-2 truncate transition-colors";
                    const ring = selected ? "outline outline-2 -outline-offset-2 outline-[#217346]" : "";
                    // 첫 열(종목명)은 틀 고정. 불투명 배경이 필요해 행 hover 를 group 으로 받는다.
                    const frozen = ci === 0;
                    const stick = frozen ? "sticky z-10 bg-white group-hover:bg-[#fff7e6]" : "";
                    const stickPos = frozen ? { left: gutter } : {};

                    if (c.type === "date" || c.type === "text") {
                      return (
                        <div key={c.key} style={{ width: colW(c), ...stickPos }} onClick={() => setSelCell({ r: ri, c: ci })}
                          className={`${base} ${ring} ${stick} justify-center text-[#555]`}>
                          {raw ?? "—"}
                        </div>
                      );
                    }
                    if (c.type === "code" || c.type === "name") {
                      return (
                        <div key={c.key} style={{ width: colW(c), ...stickPos }}
                          onClick={() => { setSelCell({ r: ri, c: ci }); onPickStock(row); }}
                          className={`${base} ${ring} ${stick} cursor-pointer ${c.type === "name" ? "justify-start" : "justify-center"} font-medium text-[#1155cc] underline decoration-[#1155cc]/30 underline-offset-2 hover:decoration-[#1155cc]`}>
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
                        style={{ width: colW(c), ...(v != null ? cellStyle(c.type, v) : {}), ...flashBg }}
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

      {/* sheet tabs — ≥lg 전용. 그 아래에서는 화면 바닥을 앱의 시트탭(내비게이션)이 쓰므로
          시트탭 줄이 두 개가 되면 안 된다. 시장 필터는 위 도구모음의 분할 버튼으로 옮겼다. */}
      <div className="hidden shrink-0 items-stretch gap-0.5 overflow-x-auto border-t border-[#d0d0d0] bg-[#f3f2f1] px-3 pt-1 text-xs lg:flex">
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
              className={`shrink-0 whitespace-nowrap border border-b-0 px-4 py-1.5 ${
                active ? "border-[#d0d0d0] bg-white font-semibold text-[#217346]" : "border-transparent text-[#666] hover:bg-[#e8e8e8]"
              } ${!clickable ? "opacity-60" : ""}`}
            >
              {s}
            </button>
          );
        })}
        <span className="ml-auto shrink-0 self-center pr-2 text-[11px] text-[#999]">준비 완료</span>
      </div>
    </div>
  );
}
