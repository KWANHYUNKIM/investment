"use client";

import { useEffect, useMemo, useState } from "react";
import { api, GlobalCluster, GlobalMember } from "@/lib/api";

const RED = "#c92a2a";
const BLUE = "#1971c2";

const FLAG: Record<string, string> = {
  KR: "🇰🇷", US: "🇺🇸", JP: "🇯🇵", CN: "🇨🇳", TW: "🇹🇼", HK: "🇭🇰",
  NL: "🇳🇱", DE: "🇩🇪", FR: "🇫🇷", CH: "🇨🇭", UK: "🇬🇧", GB: "🇬🇧",
  DK: "🇩🇰", LU: "🇱🇺", SE: "🇸🇪", AR: "🇦🇷", SG: "🇸🇬",
};
const flag = (c?: string | null) => (c ? FLAG[c] ?? "🏳️" : "🏳️");

// USD 금액 → $X.XT / $X.XB / $X.XM
function usd(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${v.toFixed(0)}`;
}

function retStyle(v: number | null | undefined): React.CSSProperties {
  if (v == null) return { color: "#bbb" };
  const a = Math.min(Math.abs(v) / 40, 1) * 0.62;
  if (v > 0) return { backgroundColor: `rgba(224,49,49,${a})`, color: a > 0.4 ? "#fff" : RED };
  if (v < 0) return { backgroundColor: `rgba(28,126,214,${a})`, color: a > 0.4 ? "#fff" : BLUE };
  return { color: "#666" };
}
function marginStyle(v: number | null | undefined): React.CSSProperties {
  if (v == null) return { color: "#bbb" };
  return { color: v > 0 ? RED : v < 0 ? BLUE : "#666" };
}

export function GlobalMap() {
  const [clusters, setClusters] = useState<GlobalCluster[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [detail, setDetail] = useState<GlobalCluster | null>(null);
  const [finnhub, setFinnhub] = useState(true);
  const [foreignLoaded, setForeignLoaded] = useState(0);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    api
      .globalClusters()
      .then((r) => {
        setClusters(r.clusters);
        setFinnhub(r.finnhub);
        setForeignLoaded(r.foreign_loaded);
        if (r.clusters[0]) setSelected(r.clusters[0].key);
      })
      .catch((e) => setErr(e?.message ?? "글로벌 클러스터를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selected) return;
    api.globalCluster(selected).then(setDetail).catch(() => setDetail(null));
  }, [selected]);

  if (err) return <div className="py-20 text-center text-sm text-rose-600">{err}</div>;

  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 bg-[#1a3a5e] px-4 py-2 text-white">
        <span className="flex items-center gap-2 text-sm font-semibold">🌍 글로벌 경쟁지도.xlsx</span>
        <span className="text-xs text-white/80">
          {clusters.length}개 기술/산업 클러스터 · 한국+미국+일본+유럽+중화권 · 시총 USD 환산
        </span>
      </div>

      {!finnhub && (
        <div className="border-b border-[#f0d9a0] bg-[#fff8e6] px-4 py-1.5 text-[12px] text-[#7a5b00]">
          ⚠️ 해외 펀더멘털(Finnhub) 미연동 — 해외 종목은 목록만 표시됩니다. <b>FINNHUB_API_KEY</b>를 .env에 넣으면 영업이익률·시총까지 채워집니다.
          {foreignLoaded > 0 && <> (현재 {foreignLoaded}종목 적재됨)</>}
        </div>
      )}

      <div className="flex min-h-[70vh]">
        {/* left: cluster list */}
        <aside className="flex w-[340px] shrink-0 flex-col border-r border-[#d0d0d0] bg-[#fafafa]">
          <div className="grid grid-cols-[1fr_auto] border-b border-[#d0d0d0] bg-[#eef2f7] px-3 py-1.5 text-[11px] font-semibold text-[#1a3a5e]">
            <span>클러스터 (대표기업)</span>
            <span className="text-right">평균 영업이익률</span>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {loading ? (
              <div className="py-10 text-center text-sm text-[#888]">불러오는 중…</div>
            ) : (
              clusters.map((c) => {
                const active = c.key === selected;
                return (
                  <button
                    key={c.key}
                    onClick={() => setSelected(c.key)}
                    className={`grid w-full grid-cols-[1fr_auto] items-center gap-1 border-b border-[#eee] px-3 py-2 text-left transition ${
                      active ? "bg-[#dbe7f3]" : "hover:bg-[#eef6ff]"
                    }`}
                  >
                    <span className="min-w-0">
                      <span className={`block truncate text-[13px] ${active ? "font-bold text-[#1a3a5e]" : "text-[#1f1f1f]"}`}>
                        {c.label}
                      </span>
                      <span className="block truncate text-[11px] text-[#999]">
                        {c.leader} · {usd(c.market_cap_usd)} · {(c.countries ?? []).map((x) => flag(x)).join("")}
                      </span>
                      <span className="block truncate text-[10px] text-[#aaa]">
                        한국 {c.kr_count} · 해외 {c.foreign_count}사
                      </span>
                    </span>
                    <span className="text-right text-xs font-bold tabular-nums" style={marginStyle(c.avg_op_margin)}>
                      {c.avg_op_margin != null ? `${c.avg_op_margin}%` : "—"}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </aside>

        {/* right: cluster members */}
        <main className="min-w-0 flex-1 overflow-x-auto bg-[#fafafa] p-4">
          {!detail ? (
            <div className="py-24 text-center text-sm text-[#888]">좌측에서 클러스터를 선택하세요.</div>
          ) : (
            <ClusterDetail c={detail} />
          )}
        </main>
      </div>
    </div>
  );
}

function ClusterDetail({ c }: { c: GlobalCluster }) {
  const [tab, setTab] = useState<"all" | "KR" | "GL" | "compare">("all");
  const [sel, setSel] = useState<Set<string>>(new Set());

  // 클러스터가 바뀌면 선택·탭 초기화 (그 업종끼리만 비교)
  useEffect(() => {
    setSel(new Set());
    setTab("all");
  }, [c.key]);

  const all = c.members ?? [];
  const members = useMemo(() => {
    if (tab === "KR") return all.filter((m) => m.market === "KR");
    if (tab === "GL") return all.filter((m) => m.market === "GL");
    return all; // all & compare 모두 전체 목록에서 고름
  }, [all, tab]);

  const key = (m: GlobalMember) => `${m.market}-${m.code}`;
  const toggle = (m: GlobalMember) =>
    setSel((prev) => {
      const n = new Set(prev);
      const k = key(m);
      if (n.has(k)) n.delete(k);
      else n.add(k);
      return n;
    });
  const picked = all.filter((m) => sel.has(key(m)));
  const compareMode = tab === "compare";

  return (
    <div className="space-y-4">
      <div className="rounded border border-[#d0d0d0] bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h2 className="text-lg font-bold text-[#1f1f1f]">{c.label}</h2>
          <span className="text-sm text-[#666]">{c.desc}</span>
        </div>
        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-sm text-[#444]">
          <span>경쟁사 <b className="text-[#1a3a5e]">{c.count}</b>사 (한국 {c.kr_count} · 해외 {c.foreign_count})</span>
          <span>합산 시총 <b className="text-[#1a3a5e]">{usd(c.market_cap_usd)}</b></span>
          <span>평균 영업이익률 <b style={marginStyle(c.avg_op_margin)}>{c.avg_op_margin != null ? `${c.avg_op_margin}%` : "—"}</b></span>
          <span>{(c.countries ?? []).map((x) => flag(x)).join(" ")}</span>
        </div>
      </div>

      <section className="overflow-hidden rounded border border-[#d0d0d0] bg-white shadow-sm">
        <div className="flex flex-wrap items-center gap-1 border-b border-[#d0d0d0] bg-[#eef2f7] px-3 py-1.5">
          <span className="mr-2 text-sm font-bold text-[#1a3a5e]">경쟁사 비교 (시총순)</span>
          {(["all", "KR", "GL", "compare"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded px-2 py-0.5 text-xs font-semibold ${
                tab === t ? "bg-[#1a3a5e] text-white" : "text-[#555] hover:bg-[#dde6f0]"
              }`}
            >
              {t === "all" ? "전체" : t === "KR" ? "한국" : t === "GL" ? "해외" : `비교${sel.size ? ` (${sel.size})` : ""}`}
            </button>
          ))}
          {sel.size > 0 && (
            <button
              onClick={() => setSel(new Set())}
              className="ml-auto rounded px-2 py-0.5 text-xs font-semibold text-[#1971c2] hover:bg-[#dde6f0]"
            >
              선택 해제
            </button>
          )}
        </div>

        {compareMode && picked.length < 2 ? (
          <div className="px-4 py-6 text-center text-sm text-[#888]">
            비교할 기업을 <b>2개 이상</b> 체크하세요. (전체/한국/해외 탭에서 체크 후 이 탭에서 나란히 비교)
            {picked.length === 1 && <div className="mt-1 text-xs text-[#aaa]">현재 1개 선택됨</div>}
          </div>
        ) : compareMode ? (
          <CompareTable picked={picked} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr className="bg-[#f0f0f0] text-xs text-[#444]">
                  <th className="w-9 border border-[#e0e0e0] px-1 py-1.5 text-center font-semibold">✓</th>
                  <th className="w-9 border border-[#e0e0e0] px-1 py-1.5 text-center font-semibold">#</th>
                  <th className="w-12 border border-[#e0e0e0] px-1 py-1.5 text-center font-semibold">국가</th>
                  <th className="min-w-[160px] border border-[#e0e0e0] px-2 py-1.5 text-left font-semibold">기업</th>
                  <th className="w-20 border border-[#e0e0e0] px-2 py-1.5 text-center font-semibold">시장</th>
                  <th className="w-28 border border-[#e0e0e0] px-2 py-1.5 text-right font-semibold">시총(USD)</th>
                  <th className="w-24 border border-[#e0e0e0] px-2 py-1.5 text-center font-semibold">영업이익률</th>
                  <th className="w-20 border border-[#e0e0e0] px-2 py-1.5 text-center font-semibold">등락%</th>
                  <th className="border border-[#e0e0e0] px-2 py-1.5 text-left font-semibold">사업/업종</th>
                </tr>
              </thead>
              <tbody>
                {members.map((m, i) => (
                  <MemberRow key={key(m)} m={m} n={i + 1} checked={sel.has(key(m))} onToggle={() => toggle(m)} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function MemberRow({
  m,
  n,
  checked,
  onToggle,
}: {
  m: GlobalMember;
  n: number;
  checked: boolean;
  onToggle: () => void;
}) {
  return (
    <tr className={checked ? "bg-[#fff3d6]" : "hover:bg-[#fff7e6]"}>
      <td className="border border-[#eee] px-1 text-center">
        <input type="checkbox" checked={checked} onChange={onToggle} className="cursor-pointer" />
      </td>
      <td className="border border-[#eee] bg-[#f7f7f7] px-1 text-center text-xs text-[#999]">{n}</td>
      <td className="border border-[#eee] px-1 py-1.5 text-center text-base">{flag(m.country)}</td>
      <td className="border border-[#eee] px-2 py-1.5 font-medium text-[#1f1f1f]">{m.name ?? m.code}</td>
      <td className="border border-[#eee] px-2 py-1.5 text-center">
        <span
          className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
            m.market === "KR" ? "bg-[#e7f0e7] text-[#244d1a]" : "bg-[#e7eef7] text-[#1a3a5e]"
          }`}
        >
          {m.market === "KR" ? `KR ${m.code}` : m.code}
        </span>
      </td>
      <td className="border border-[#eee] px-2 py-1.5 text-right font-semibold tabular-nums text-[#1f1f1f]">{usd(m.market_cap_usd)}</td>
      <td className="border border-[#eee] px-2 py-1.5 text-center font-semibold tabular-nums" style={marginStyle(m.op_margin)}>
        {m.op_margin != null ? `${m.op_margin}%` : "—"}
      </td>
      <td className="border border-[#eee] px-2 py-1.5 text-center font-bold tabular-nums" style={retStyle(m.change_pct)}>
        {m.change_pct != null ? `${m.change_pct > 0 ? "+" : ""}${m.change_pct}%` : "—"}
      </td>
      <td className="border border-[#eee] px-2 py-1.5 text-xs text-[#666]">{m.note ?? "—"}</td>
    </tr>
  );
}

// 선택한 기업들을 열로 세워 나란히 비교 — 애널리스트 보고서급 (규모·수익성·재무·밸류).
function pct(v: number | null | undefined): string {
  return v == null ? "—" : `${v}%`;
}
function num(v: number | null | undefined, suffix = ""): string {
  return v == null ? "—" : `${v}${suffix}`;
}

function CompareTable({ picked }: { picked: GlobalMember[] }) {
  const bestMax = (f: (m: GlobalMember) => number | null | undefined) => {
    const ns = picked.map(f).filter((v): v is number => v != null);
    return ns.length ? Math.max(...ns) : null;
  };
  const bestMin = (f: (m: GlobalMember) => number | null | undefined) => {
    const ns = picked.map(f).filter((v): v is number => v != null);
    return ns.length ? Math.min(...ns) : null;
  };
  const bCap = bestMax((m) => m.market_cap_usd);
  const bRev = bestMax((m) => m.revenue_usd);
  const bOp = bestMax((m) => m.op_profit_usd);
  const bOpM = bestMax((m) => m.op_margin);
  const bNetM = bestMax((m) => m.net_margin);
  const bRoe = bestMax((m) => m.roe);
  const bDe = bestMin((m) => m.debt_equity); // 낮을수록 좋음
  const bPe = bestMin((m) => m.pe); // 낮을수록 저평가

  // 같은 사업이면 비교가 의미. 모두 같은 note면 배너로 강조.
  const notes = picked.map((m) => (m.note ?? "").trim()).filter(Boolean);
  const sameBiz = notes.length === picked.length && new Set(notes.map((n) => n.toLowerCase())).size === 1;

  const Section = ({ title }: { title: string }) => (
    <tr>
      <th
        colSpan={picked.length + 1}
        className="sticky left-0 border border-[#e0e0e0] bg-[#dbe7f3] px-2 py-1 text-left text-[11px] font-bold text-[#1a3a5e]"
      >
        {title}
      </th>
    </tr>
  );
  const Row = ({
    label,
    render,
    medal,
  }: {
    label: string;
    render: (m: GlobalMember) => React.ReactNode;
    medal?: (m: GlobalMember) => boolean;
  }) => (
    <tr className="hover:bg-[#fafafa]">
      <th className="sticky left-0 z-10 border border-[#e0e0e0] bg-[#f3f6fa] px-2 py-1.5 text-left text-xs font-semibold text-[#333]">
        {label}
      </th>
      {picked.map((m) => (
        <td key={`${m.market}-${m.code}`} className="border border-[#e0e0e0] px-2 py-1.5 text-center text-[13px] tabular-nums">
          {render(m)}
          {medal && medal(m) ? " 🥇" : ""}
        </td>
      ))}
    </tr>
  );

  return (
    <div className="space-y-2 p-3">
      {sameBiz && (
        <div className="rounded bg-[#eef6f0] px-3 py-1.5 text-[12px] text-[#244d1a]">
          ✓ 동일 사업군 — <b>{notes[0]}</b> · 같은 제품/사업을 두고 직접 경쟁하는 기업들입니다.
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 min-w-[120px] border border-[#e0e0e0] bg-[#eef2f7] px-2 py-2 text-left text-xs font-bold text-[#1a3a5e]">
                항목 ＼ 기업
              </th>
              {picked.map((m) => (
                <th key={`${m.market}-${m.code}`} className="min-w-[130px] border border-[#e0e0e0] bg-[#1a3a5e] px-2 py-2 text-center text-white">
                  <div className="text-lg">{flag(m.country)}</div>
                  <div className="text-[13px] font-bold leading-tight">{m.name ?? m.code}</div>
                  <div className="text-[10px] font-normal text-white/70">{m.market === "KR" ? `KR ${m.code}` : m.code}{m.fy ? ` · ${m.fy}` : ""}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <Section title="규모" />
            <Row label="시가총액(USD)" render={(m) => usd(m.market_cap_usd)} medal={(m) => m.market_cap_usd != null && m.market_cap_usd === bCap} />
            <Row label="매출액(USD)" render={(m) => usd(m.revenue_usd)} medal={(m) => m.revenue_usd != null && m.revenue_usd === bRev} />
            <Row label="영업이익(USD)" render={(m) => <span style={marginStyle(m.op_profit_usd)}>{usd(m.op_profit_usd)}</span>} medal={(m) => m.op_profit_usd != null && m.op_profit_usd === bOp} />
            <Row label="순이익(USD)" render={(m) => <span style={marginStyle(m.net_income_usd)}>{usd(m.net_income_usd)}</span>} />

            <Section title="수익성 (얼마나 남는지)" />
            <Row label="영업이익률" render={(m) => <span style={marginStyle(m.op_margin)} className="font-semibold">{pct(m.op_margin)}</span>} medal={(m) => m.op_margin != null && m.op_margin === bOpM} />
            <Row label="순이익률" render={(m) => <span style={marginStyle(m.net_margin)}>{pct(m.net_margin)}</span>} medal={(m) => m.net_margin != null && m.net_margin === bNetM} />
            <Row label="매출총이익률" render={(m) => pct(m.gross_margin)} />
            <Row label="ROE" render={(m) => <span style={marginStyle(m.roe)}>{pct(m.roe)}</span>} medal={(m) => m.roe != null && m.roe === bRoe} />

            <Section title="재무 안정성 · 밸류에이션" />
            <Row label="부채비율(부채/자본)" render={(m) => pct(m.debt_equity)} medal={(m) => m.debt_equity != null && m.debt_equity === bDe} />
            <Row label="PER" render={(m) => num(m.pe)} medal={(m) => m.pe != null && m.pe > 0 && m.pe === bPe} />
            <Row label="PBR" render={(m) => num(m.pb)} />
            <Row label="배당수익률" render={(m) => pct(m.div_yield)} />

            <Section title="시장 · 사업" />
            <Row label="당일 등락%" render={(m) => <span style={retStyle(m.change_pct)} className="rounded px-1.5 py-0.5 font-bold">{m.change_pct != null ? `${m.change_pct > 0 ? "+" : ""}${m.change_pct}%` : "—"}</span>} />
            <Row label="국가" render={(m) => <span>{flag(m.country)} {m.country ?? "—"}</span>} />
            <tr>
              <th className="sticky left-0 z-10 border border-[#e0e0e0] bg-[#f3f6fa] px-2 py-1.5 text-left text-xs font-semibold text-[#333]">주요 사업/제품</th>
              {picked.map((m) => (
                <td key={`${m.market}-${m.code}`} className="border border-[#e0e0e0] px-2 py-1.5 text-left text-[11px] leading-snug text-[#555]">
                  {m.note ?? "—"}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      <p className="text-[11px] leading-relaxed text-[#999]">
        🥇 = 항목별 최우수(부채비율·PER은 낮을수록). 해외는 Finnhub(TTM), 한국은 DART·FnGuide(최근 사업연도) 기준이라 시점이 다소 다를 수 있습니다.
        제품·사업부문별 영업이익(발생처 세분)은 공개 무료 데이터로는 정량화가 어려워 '주요 사업/제품' 수준으로 제공합니다.
      </p>
    </div>
  );
}
