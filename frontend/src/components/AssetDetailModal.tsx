"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api, AssetDetail, AssetConstituent, ConstituentQuote } from "@/lib/api";

// KR convention: red = up, blue = down.
const RED = "#c92a2a";
const BLUE = "#1971c2";

function retStyle(v: number | null | undefined): React.CSSProperties {
  if (v == null) return { color: "#bbb" };
  const a = Math.min(Math.abs(v) / 40, 1) * 0.62;
  if (v > 0) return { backgroundColor: `rgba(224,49,49,${a})`, color: a > 0.4 ? "#fff" : RED };
  if (v < 0) return { backgroundColor: `rgba(28,126,214,${a})`, color: a > 0.4 ? "#fff" : BLUE };
  return { color: "#666" };
}

function fmt(v: number | null | undefined, unit: string): string {
  if (v == null) return "—";
  if (unit === "pct") return `${v.toFixed(2)}%`;
  if (unit === "usd") return `$${v.toLocaleString("en-US", { maximumFractionDigits: v >= 100 ? 0 : 2 })}`;
  if (unit === "krw") return `₩${v.toLocaleString("ko-KR", { maximumFractionDigits: 1 })}`;
  return v.toLocaleString("en-US", { maximumFractionDigits: 2 });
}
function fmtVol(v: number | null | undefined): string {
  if (v == null || v === 0) return "—";
  if (v >= 1e9) return `${(v / 1e9).toLocaleString("en-US", { maximumFractionDigits: 1 })}B`;
  if (v >= 1e6) return `${(v / 1e6).toLocaleString("en-US", { maximumFractionDigits: 1 })}M`;
  if (v >= 1e3) return `${(v / 1e3).toLocaleString("en-US", { maximumFractionDigits: 1 })}K`;
  return v.toLocaleString("en-US");
}

export function AssetDetailModal({ assetKey, onClose }: { assetKey: string; onClose: () => void }) {
  const [d, setD] = useState<AssetDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    setLoading(true);
    setErr("");
    api
      .assetDetail(assetKey)
      .then(setD)
      .catch((e) => setErr(e?.message ?? "불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, [assetKey]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    // lock body scroll while the full page is open
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  const s = d?.session;
  const up = (s?.change_pct ?? 0) > 0;
  const down = (s?.change_pct ?? 0) < 0;
  const accent = up ? RED : down ? BLUE : "#94a3b8";
  const unit = d?.unit ?? "pt";

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#fafafa] text-[#1f1f1f]">
      {/* Excel green title bar (full-page) */}
      <div className="flex h-10 shrink-0 items-center gap-3 bg-[#217346] px-4 text-white">
        <button onClick={onClose} className="rounded bg-white/15 px-2 py-0.5 text-xs font-semibold hover:bg-white/25">
          ← 닫기
        </button>
        <span className="truncate text-sm font-semibold">
          📊 {d?.label ?? assetKey} — 장마감.xlsx
          {d?.symbol && <span className="ml-1 font-mono text-xs text-white/70">{d.symbol}</span>}
        </span>
      </div>
      <div className="h-1 shrink-0" style={{ background: accent }} />

      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex flex-col items-center gap-3 py-28 text-sm text-[#888]">
            <span className="h-7 w-7 animate-spin rounded-full border-2 border-[#d0d0d0] border-t-[#217346]" />
            시세 불러오는 중…
          </div>
        ) : err || !d || !s ? (
          <div className="py-28 text-center text-sm text-rose-600">{err || "데이터를 불러오지 못했습니다."}</div>
        ) : (
          <div className="mx-auto max-w-6xl space-y-5 p-5">
            {/* session close hero */}
            <div className="flex flex-wrap items-end justify-between gap-4 rounded-xl border px-5 py-4" style={{ borderColor: `${accent}33`, background: `${accent}0d` }}>
              <div>
                <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-[#217346]">
                  <span>장 마감</span>
                  {s.date && <span className="font-normal normal-case tracking-normal text-[#888]">· {s.date}</span>}
                </div>
                <div className="mt-0.5 text-4xl font-bold leading-none tabular-nums text-[#1f1f1f]">{fmt(s.close, unit)}</div>
              </div>
              <div className="text-right text-xl font-bold tabular-nums" style={{ color: accent }}>
                <div>{s.change != null ? `${s.change > 0 ? "▲ " : s.change < 0 ? "▼ " : ""}${fmt(Math.abs(s.change), unit)}` : ""}</div>
                <div className="text-lg">{s.change_pct != null ? `${s.change_pct > 0 ? "+" : ""}${s.change_pct}%` : "—"}</div>
              </div>
            </div>

            {/* OHLC + 52w */}
            <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 rounded-lg border border-[#e6e6e6] bg-white px-4 py-3 text-sm sm:grid-cols-3">
              <Stat label="시가" v={fmt(s.open, unit)} />
              <Stat label="고가" v={fmt(s.high, unit)} />
              <Stat label="저가" v={fmt(s.low, unit)} />
              <Stat label="전일 종가" v={fmt(s.prev_close, unit)} />
              <Stat label="거래량" v={fmtVol(s.volume)} />
              <Stat label="52주 고 / 저" v={`${fmt(s.high_52w, unit)} / ${fmt(s.low_52w, unit)}`} />
            </div>

            {/* recent sessions */}
            <Sheet title="최근 시세 (일별)">
              <div className="max-h-72 overflow-y-auto rounded border border-[#d0d0d0]">
                <table className="w-full border-collapse text-[13px]">
                  <thead className="sticky top-0">
                    <tr className="bg-[#217346] text-xs text-white">
                      <Th>일자</Th><Th right>시가</Th><Th right>고가</Th><Th right>저가</Th><Th right>종가</Th><Th center>등락%</Th><Th right>거래량</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...d.history].reverse().map((r) => (
                      <tr key={r.date} className="odd:bg-white even:bg-[#f7f9f7] hover:bg-[#fff7e6]">
                        <Td>{r.date}</Td>
                        <Td right>{fmt(r.open, unit)}</Td>
                        <Td right>{fmt(r.high, unit)}</Td>
                        <Td right>{fmt(r.low, unit)}</Td>
                        <Td right bold>{fmt(r.close, unit)}</Td>
                        <td className="border border-[#eee] px-2 py-1 text-center font-bold tabular-nums" style={retStyle(r.change_pct)}>
                          {r.change_pct != null ? `${r.change_pct > 0 ? "+" : ""}${r.change_pct}%` : "—"}
                        </td>
                        <Td right>{fmtVol(r.volume)}</Td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Sheet>

            {/* constituents — 전종목분석 스타일 그리드 */}
            {d.total_constituents > 0 && (
              <ConstituentGrid detail={d} />
            )}

            <p className="border-t border-[#e6e6e6] pt-3 text-[11px] leading-relaxed text-[#888]">
              시세 FinanceDataReader · 종가/지연 시세 기준. 구성종목의 현재가·수익률은 50개씩 불러옵니다(개별 조회 비용 때문).
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── constituent grid (mirrors 전종목분석 layout) ─────────────────────────── */
type CKey = "symbol" | "name" | "sector" | "close" | "change" | "change_pct" | "ret_1w" | "ret_1m" | "ret_3m" | "ret_12m";
type CType = "code" | "name" | "text" | "price" | "chg" | "ret";
type CCol = { key: CKey; label: string; group: GKey; w: number; type: CType };
type GKey = "id" | "price" | "ret";

const CGROUPS: { key: GKey; label: string; bg: string; fg: string }[] = [
  { key: "id", label: "종목정보", bg: "#a9d08e", fg: "#244d1a" },
  { key: "price", label: "시세", bg: "#d9d9d9", fg: "#333" },
  { key: "ret", label: "기간 수익률", bg: "#f4b084", fg: "#7a3a0c" },
];
const CCOLS: CCol[] = [
  { key: "symbol", label: "코드", group: "id", w: 96, type: "code" },
  { key: "name", label: "종목명", group: "id", w: 240, type: "name" },
  { key: "sector", label: "섹터", group: "id", w: 150, type: "text" },
  { key: "close", label: "현재가", group: "price", w: 110, type: "price" },
  { key: "change", label: "전일대비", group: "price", w: 100, type: "chg" },
  { key: "change_pct", label: "등락(%)", group: "ret", w: 92, type: "ret" },
  { key: "ret_1w", label: "1주(%)", group: "ret", w: 88, type: "ret" },
  { key: "ret_1m", label: "1개월(%)", group: "ret", w: 92, type: "ret" },
  { key: "ret_3m", label: "3개월(%)", group: "ret", w: 92, type: "ret" },
  { key: "ret_12m", label: "1년(%)", group: "ret", w: 88, type: "ret" },
];
const GUTTER = 44;

type Row = AssetConstituent & Partial<ConstituentQuote>;

function colLetter(i: number): string {
  let s = "";
  i += 1;
  while (i > 0) {
    s = String.fromCharCode(65 + ((i - 1) % 26)) + s;
    i = Math.floor((i - 1) / 26);
  }
  return s;
}

function ConstituentGrid({ detail }: { detail: AssetDetail }) {
  const curr = detail.key === "shanghai" ? "¥" : "$"; // sp500/nasdaq = USD, 상해 = CNY
  const [q, setQ] = useState("");
  const [limit, setLimit] = useState(50);
  const [sortKey, setSortKey] = useState<CKey | null>(null);
  const [desc, setDesc] = useState(true);
  const [quotes, setQuotes] = useState<Map<string, ConstituentQuote>>(new Map());
  const [busy, setBusy] = useState(false);
  const loading = useRef<Set<string>>(new Set());

  const filtered = useMemo(() => {
    const n = q.trim().toLowerCase();
    let list: Row[] = detail.constituents.map((c) => ({ ...c, ...(quotes.get(c.symbol) ?? {}) }));
    if (n) list = list.filter((r) => r.symbol.toLowerCase().includes(n) || (r.name ?? "").toLowerCase().includes(n));
    if (sortKey) {
      const dir = desc ? -1 : 1;
      list = [...list].sort((a, b) => {
        const av = a[sortKey], bv = b[sortKey];
        if (typeof av === "string" || typeof bv === "string")
          return dir * String(av ?? "").localeCompare(String(bv ?? ""), "en");
        return dir * (((av as number) ?? -Infinity) - ((bv as number) ?? -Infinity));
      });
    }
    return list;
  }, [detail.constituents, quotes, q, sortKey, desc]);

  const shown = filtered.slice(0, limit);

  // Lazily fetch quotes for the currently visible symbols (batch ≤ 50).
  const shownKey = shown.map((r) => r.symbol).join(",");
  useEffect(() => {
    const need = shown.filter((r) => r.close === undefined && !loading.current.has(r.symbol)).map((r) => r.symbol);
    if (need.length === 0) return;
    const batch = need.slice(0, 50);
    batch.forEach((s) => loading.current.add(s));
    setBusy(true);
    api
      .assetQuotes(batch)
      .then((res) => {
        setQuotes((prev) => {
          const m = new Map(prev);
          for (const qt of res.quotes) m.set(qt.symbol, qt);
          return m;
        });
      })
      .catch(() => {})
      .finally(() => {
        batch.forEach((s) => loading.current.delete(s));
        setBusy(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shownKey]);

  const totalW = GUTTER + CCOLS.reduce((a, c) => a + c.w, 0);
  function clickHeader(c: CCol) {
    if (sortKey === c.key) setDesc((x) => !x);
    else { setSortKey(c.key); setDesc(true); }
  }
  function cellText(type: CType, v: number): string {
    if (type === "price") return `${curr}${v.toLocaleString("en-US", { maximumFractionDigits: v >= 100 ? 0 : 2 })}`;
    if (type === "chg") return `${v > 0 ? "▲ " : v < 0 ? "▼ " : ""}${Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
    return `${v > 0 ? "+" : ""}${v.toFixed(2)}`;
  }
  function chgStyle(v: number): React.CSSProperties {
    return { color: v > 0 ? RED : v < 0 ? BLUE : "#666" };
  }

  return (
    <Sheet
      title={`구성종목 · 전종목 분석`}
      meta={`총 ${detail.total_constituents.toLocaleString("ko-KR")}개${detail.constituents.length < detail.total_constituents ? ` (상위 ${detail.constituents.length}개)` : ""}`}
    >
      {/* toolbar */}
      <div className="flex flex-wrap items-center gap-2 border-b border-[#d0d0d0] bg-[#f3f2f1] px-3 py-1.5">
        <div className="flex items-center gap-1.5 rounded border border-[#bdbdbd] bg-white px-2 py-1">
          <span className="text-[#888]">🔍</span>
          <input
            value={q}
            onChange={(e) => { setQ(e.target.value); setLimit(50); }}
            placeholder="심볼·종목명 검색"
            className="w-48 text-sm outline-none"
          />
        </div>
        {busy && <span className="text-xs text-[#217346]">시세 불러오는 중…</span>}
        <span className="ml-auto text-xs text-[#666]">
          {filtered.length.toLocaleString("ko-KR")}개{sortKey ? ` · 정렬 ${CCOLS.find((c) => c.key === sortKey)?.label} ${desc ? "↓" : "↑"}` : ""}
        </span>
      </div>

      <div className="overflow-x-auto">
        <div style={{ width: totalW, minWidth: "100%" }}>
          {/* column-letter row */}
          <div className="sticky top-0 z-10 flex border-b border-[#d0d0d0] bg-[#f0f0f0] text-xs text-[#888]">
            <div style={{ width: GUTTER }} className="shrink-0 border-r border-[#d0d0d0]" />
            {CCOLS.map((c, i) => (
              <div key={c.key} style={{ width: c.w }} className="shrink-0 border-r border-[#d0d0d0] py-0.5 text-center">
                {colLetter(i)}
              </div>
            ))}
          </div>
          {/* group bands */}
          <div className="flex text-sm font-bold">
            <div style={{ width: GUTTER }} className="shrink-0 border-b border-r border-[#bdbdbd] bg-[#e9e9e9]" />
            {CGROUPS.map((g) => {
              const w = CCOLS.filter((c) => c.group === g.key).reduce((a, c) => a + c.w, 0);
              return (
                <div key={g.key} style={{ width: w, background: g.bg, color: g.fg }} className="shrink-0 border-b border-r border-white py-1 text-center">
                  {g.label}
                </div>
              );
            })}
          </div>
          {/* column headers (sortable) */}
          <div className="flex text-sm font-semibold text-[#333]">
            <div style={{ width: GUTTER }} className="shrink-0 border-b border-r border-[#bdbdbd] bg-[#e9e9e9] py-1.5" />
            {CCOLS.map((c) => {
              const g = CGROUPS.find((x) => x.key === c.group)!;
              return (
                <button key={c.key} onClick={() => clickHeader(c)} style={{ width: c.w, background: `${g.bg}66` }}
                  className="shrink-0 truncate border-b border-r border-[#cfcfcf] py-1.5 hover:brightness-95">
                  {c.label}{sortKey === c.key && <span className="ml-1">{desc ? "▼" : "▲"}</span>}
                </button>
              );
            })}
          </div>
          {/* rows */}
          {shown.map((row, ri) => (
            <div key={row.symbol} className="flex text-[13px] tabular-nums hover:bg-[#fff7e6]">
              <div style={{ width: GUTTER }} className="flex shrink-0 items-center justify-center border-b border-r border-[#e0e0e0] bg-[#f0f0f0] text-xs text-[#999]">
                {ri + 2}
              </div>
              {CCOLS.map((c) => {
                const raw = row[c.key];
                const base = "flex shrink-0 items-center border-b border-r border-[#e6e6e6] px-2 truncate py-1.5";
                if (c.type === "text" || c.type === "code") {
                  return (
                    <div key={c.key} style={{ width: c.w }} className={`${base} ${c.type === "code" ? "justify-center font-mono text-xs text-[#555]" : "justify-start text-[#555]"}`}>
                      {(raw as string) ?? "—"}
                    </div>
                  );
                }
                if (c.type === "name") {
                  return (
                    <div key={c.key} style={{ width: c.w }} className={`${base} justify-start font-medium text-[#1f1f1f]`}>
                      {(raw as string) ?? "—"}
                    </div>
                  );
                }
                const v = raw as number | null | undefined;
                const style = c.type === "ret" ? (v != null ? retStyle(v) : {}) : c.type === "chg" && v != null ? chgStyle(v) : {};
                return (
                  <div key={c.key} style={{ width: c.w, ...style }} className={`${base} justify-end ${v == null ? "text-[#ccc]" : ""}`}>
                    {v == null ? "—" : cellText(c.type, v)}
                  </div>
                );
              })}
            </div>
          ))}
          {limit < filtered.length && (
            <button onClick={() => setLimit((l) => l + 50)} className="w-full border-b border-[#e0e0e0] bg-[#f3f2f1] py-2 text-sm text-[#217346] hover:bg-[#e8e8e8]">
              더보기 ({(filtered.length - limit).toLocaleString("ko-KR")}개 남음 · 현재가 함께 로딩)
            </button>
          )}
        </div>
      </div>
    </Sheet>
  );
}

/* ── small shared bits ────────────────────────────────────────────────────── */
function Sheet({ title, meta, children }: { title: string; meta?: string; children: React.ReactNode }) {
  return (
    <section className="overflow-hidden rounded border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex items-baseline gap-2 border-b border-white bg-[#a9d08e] px-3 py-1.5 text-sm font-bold text-[#244d1a]">
        {title}
        {meta && <span className="text-xs font-normal text-[#2d5016]/70">{meta}</span>}
      </div>
      {children}
    </section>
  );
}
function Stat({ label, v }: { label: string; v: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-xs text-[#888]">{label}</span>
      <span className="font-semibold tabular-nums text-[#1f1f1f]">{v}</span>
    </div>
  );
}
function Th({ children, right, center }: { children?: React.ReactNode; right?: boolean; center?: boolean }) {
  return <th className={`border border-[#1c5e38] px-2 py-1.5 font-semibold ${right ? "text-right" : center ? "text-center" : "text-left"}`}>{children}</th>;
}
function Td({ children, right, bold }: { children?: React.ReactNode; right?: boolean; bold?: boolean }) {
  return <td className={`border border-[#eee] px-2 py-1 ${right ? "text-right tabular-nums" : ""} ${bold ? "font-bold text-[#1f1f1f]" : "text-[#444]"}`}>{children}</td>;
}
