"use client";

import { useEffect, useMemo, useState } from "react";
import { api, GlobalBattleground, GlobalCluster, GlobalMember } from "@/lib/api";

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
                        {c.tech ? " · 🔬기술주" : ""}
                        {(c.battleground_count ?? 0) > 0 ? ` · ⚔️${c.battleground_count}` : ""}
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
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  // 클러스터가 바뀌면 선택·탭·펼침 초기화 (그 업종끼리만 비교)
  useEffect(() => {
    setSel(new Set());
    setExpanded(new Set());
    setTab("all");
  }, [c.key]);

  const all = c.members ?? [];
  // 경쟁구도 선수 이름 → 국기 (멤버에서 매칭)
  const flagByName = useMemo(() => {
    const m: Record<string, string> = {};
    for (const x of all) if (x.name) m[x.name] = flag(x.country);
    return m;
  }, [all]);
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
  const toggleExpand = (m: GlobalMember) =>
    setExpanded((prev) => {
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
          {c.tech && <span className="rounded bg-[#1a3a5e] px-1.5 py-0.5 text-[10px] font-bold text-white">기술주</span>}
          <span className="text-sm text-[#666]">{c.desc}</span>
        </div>
        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-sm text-[#444]">
          <span>경쟁사 <b className="text-[#1a3a5e]">{c.count}</b>사 (한국 {c.kr_count} · 해외 {c.foreign_count})</span>
          <span>합산 시총 <b className="text-[#1a3a5e]">{usd(c.market_cap_usd)}</b></span>
          <span>평균 영업이익률 <b style={marginStyle(c.avg_op_margin)}>{c.avg_op_margin != null ? `${c.avg_op_margin}%` : "—"}</b></span>
          <span>{(c.countries ?? []).map((x) => flag(x)).join(" ")}</span>
        </div>
      </div>

      {(c.battlegrounds?.length ?? 0) > 0 && (
        <Battlegrounds list={c.battlegrounds!} flagByName={flagByName} />
      )}

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
                  <th className="min-w-[170px] border border-[#e0e0e0] px-2 py-1.5 text-left font-semibold">기업</th>
                  <th className="w-20 border border-[#e0e0e0] px-2 py-1.5 text-center font-semibold">시장</th>
                  <th className="w-28 border border-[#e0e0e0] px-2 py-1.5 text-right font-semibold">시총(USD)</th>
                  <th className="w-24 border border-[#e0e0e0] px-2 py-1.5 text-center font-semibold">영업이익률</th>
                  <th className="w-20 border border-[#e0e0e0] px-2 py-1.5 text-center font-semibold" title="투하자본이익률 — 투자 대비 이익">ROIC</th>
                  <th className="w-20 border border-[#e0e0e0] px-2 py-1.5 text-center font-semibold">등락%</th>
                  <th className="border border-[#e0e0e0] px-2 py-1.5 text-left font-semibold">사업/업종</th>
                </tr>
              </thead>
              <tbody>
                {members.map((m, i) => (
                  <MemberRow
                    key={key(m)}
                    m={m}
                    n={i + 1}
                    checked={sel.has(key(m))}
                    onToggle={() => toggle(m)}
                    open={expanded.has(key(m))}
                    onExpand={() => toggleExpand(m)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

// 경쟁 구도 — 세부 전장별로 누가 맞붙는지 미리 매핑해 보여준다.
function Battlegrounds({
  list,
  flagByName,
}: {
  list: GlobalBattleground[];
  flagByName: Record<string, string>;
}) {
  return (
    <section className="overflow-hidden rounded border border-[#d0d0d0] bg-white shadow-sm">
      <div className="border-b border-[#d0d0d0] bg-[#2b4a6f] px-3 py-1.5 text-sm font-bold text-white">
        ⚔️ 경쟁 구도 — 누가 어디서 맞붙나 (세부 전장별)
      </div>
      <div className="grid gap-px bg-[#e6e6e6] sm:grid-cols-2 xl:grid-cols-3">
        {list.map((b) => (
          <div key={b.arena} className="bg-white p-3">
            <div className="text-[13px] font-bold text-[#1a3a5e]">{b.arena}</div>
            <p className="mt-1 text-[11.5px] leading-snug text-[#555]">{b.desc}</p>
            <div className="mt-2 flex flex-wrap gap-1">
              {b.players.map((p, i) => (
                <span
                  key={p}
                  className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${
                    i === 0
                      ? "border-[#c92a2a] bg-[#fff0f0] text-[#c92a2a]"
                      : "border-[#cdd8e6] bg-[#f3f6fa] text-[#1a3a5e]"
                  }`}
                  title={i === 0 ? "선두/대표" : undefined}
                >
                  {flagByName[p] ? `${flagByName[p]} ` : ""}{p}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

// 한 기업의 펼침 상세 — 기술 / 영업이익 창출 / 해자 / 투자효율(이익·투자 대비).
function metric(v: number | null | undefined, suf = "", digits?: number): string {
  if (v == null) return "—";
  return `${digits != null ? v.toFixed(digits) : v}${suf}`;
}
function MetricCell({ label, value, hint, accent }: { label: string; value: string; hint?: string; accent?: boolean }) {
  return (
    <div className="rounded border border-[#e6e6e6] bg-[#fafbfc] px-2 py-1.5" title={hint}>
      <div className="text-[10px] text-[#888]">{label}</div>
      <div className={`text-[13px] font-bold tabular-nums ${accent ? "text-[#1a3a5e]" : "text-[#333]"}`}>{value}</div>
    </div>
  );
}
function MemberDeep({ m, cols }: { m: GlobalMember; cols: number }) {
  const p = m.profile;
  const growthLabel = m.market === "KR" ? "영업이익 YoY" : "EPS성장 YoY";
  const growthVal = m.market === "KR" ? m.op_yoy : m.eps_growth;
  return (
    <tr>
      <td colSpan={cols} className="border border-[#e0e0e0] bg-[#f6f9fc] px-4 py-3">
        {p ? (
          <div className="grid gap-2 md:grid-cols-2">
            {p.tech && (
              <div className="rounded border-l-2 border-[#1a3a5e] bg-white px-3 py-2">
                <div className="text-[11px] font-bold text-[#1a3a5e]">🔬 핵심 기술 / 제품</div>
                <p className="mt-0.5 text-[12px] leading-relaxed text-[#444]">{p.tech}</p>
              </div>
            )}
            {p.biz && (
              <div className="rounded border-l-2 border-[#2f9e44] bg-white px-3 py-2">
                <div className="text-[11px] font-bold text-[#2b8a3e]">💰 영업이익을 어떻게 내나</div>
                <p className="mt-0.5 text-[12px] leading-relaxed text-[#444]">{p.biz}</p>
              </div>
            )}
            {p.moat && (
              <div className="rounded border-l-2 border-[#e8590c] bg-white px-3 py-2">
                <div className="text-[11px] font-bold text-[#d9480f]">🛡️ 경쟁 우위 / 해자</div>
                <p className="mt-0.5 text-[12px] leading-relaxed text-[#444]">{p.moat}</p>
              </div>
            )}
            {p.invest && (
              <div className="rounded border-l-2 border-[#9c36b5] bg-white px-3 py-2">
                <div className="text-[11px] font-bold text-[#862e9c]">📈 투자(R&D·CAPEX) 대비 회수</div>
                <p className="mt-0.5 text-[12px] leading-relaxed text-[#444]">{p.invest}</p>
              </div>
            )}
          </div>
        ) : (
          <div className="mb-2 text-[12px] text-[#999]">📋 정성 프로파일 미등록 — 아래 정량 지표만 표시합니다. (업종: {m.note ?? "—"})</div>
        )}
        <div className="mt-2">
          <div className="mb-1 text-[11px] font-bold text-[#1a3a5e]">이익 · 투자 효율</div>
          <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4 lg:grid-cols-7">
            <MetricCell label="ROIC" value={metric(m.roic, "%")} hint="투하자본이익률 — 투자 대비 이익" accent />
            <MetricCell label="ROE" value={metric(m.roe, "%")} hint="자기자본이익률" />
            <MetricCell label="ROA" value={metric(m.roa, "%")} hint="총자산이익률" />
            <MetricCell label="자산회전율" value={metric(m.asset_turnover, "x", 2)} hint="매출/총자산 — 자산을 매출로 돌리는 효율" />
            <MetricCell label="영업이익률" value={metric(m.op_margin, "%")} />
            <MetricCell label="순이익률" value={metric(m.net_margin, "%")} />
            <MetricCell label="매출총이익률" value={metric(m.gross_margin, "%")} />
            <MetricCell label="매출성장 YoY" value={metric(m.rev_growth, "%")} hint="전년대비 매출 성장률" />
            <MetricCell label={growthLabel} value={metric(growthVal, "%")} />
            <MetricCell label="5년 매출CAGR" value={metric(m.rev_cagr5y, "%")} />
            <MetricCell label="부채비율" value={metric(m.debt_equity, "%")} hint="부채/자본" />
            <MetricCell label="이자보상배율" value={metric(m.interest_cov, "x")} hint="영업이익/이자비용 — 클수록 안전" />
            <MetricCell label="EV/EBITDA" value={metric(m.ev_ebitda, "x")} hint="기업가치/상각전영업이익 — 밸류" />
            <MetricCell label="PER" value={metric(m.pe)} />
            <MetricCell label="PBR" value={metric(m.pb)} />
            <MetricCell label="배당수익률" value={metric(m.div_yield, "%")} />
          </div>
          <p className="mt-1.5 text-[10px] text-[#aaa]">
            해외는 Finnhub(TTM), 한국은 DART·FnGuide(최근 사업연도) 기준. 한국 ROIC는 세후영업이익/총자산 근사치(순차입금 분리 불가).
          </p>
        </div>
      </td>
    </tr>
  );
}

function MemberRow({
  m,
  n,
  checked,
  onToggle,
  open,
  onExpand,
}: {
  m: GlobalMember;
  n: number;
  checked: boolean;
  onToggle: () => void;
  open: boolean;
  onExpand: () => void;
}) {
  const COLS = 9;
  return (
    <>
      <tr className={checked ? "bg-[#fff3d6]" : open ? "bg-[#eef6ff]" : "hover:bg-[#fff7e6]"}>
        <td className="border border-[#eee] px-1 text-center">
          <input type="checkbox" checked={checked} onChange={onToggle} className="cursor-pointer" />
        </td>
        <td className="border border-[#eee] bg-[#f7f7f7] px-1 text-center text-xs text-[#999]">{n}</td>
        <td className="border border-[#eee] px-1 py-1.5 text-center text-base">{flag(m.country)}</td>
        <td className="border border-[#eee] px-2 py-1.5">
          <button onClick={onExpand} className="flex items-center gap-1 text-left font-medium text-[#1f1f1f] hover:text-[#1971c2]">
            <span className={`inline-block text-[10px] text-[#1971c2] transition-transform ${open ? "rotate-90" : ""}`}>▶</span>
            <span>{m.name ?? m.code}</span>
            {m.profile && <span className="rounded bg-[#eef2f7] px-1 text-[9px] font-bold text-[#1a3a5e]">상세</span>}
          </button>
        </td>
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
        <td className="border border-[#eee] px-2 py-1.5 text-center font-semibold tabular-nums" style={marginStyle(m.roic)}>
          {m.roic != null ? `${m.roic}%` : "—"}
        </td>
        <td className="border border-[#eee] px-2 py-1.5 text-center font-bold tabular-nums" style={retStyle(m.change_pct)}>
          {m.change_pct != null ? `${m.change_pct > 0 ? "+" : ""}${m.change_pct}%` : "—"}
        </td>
        <td className="border border-[#eee] px-2 py-1.5 text-xs text-[#666]">{m.note ?? "—"}</td>
      </tr>
      {open && <MemberDeep m={m} cols={COLS} />}
    </>
  );
}

// 선택한 기업들을 열로 세워 나란히 비교 — 애널리스트 보고서급 (규모·수익성·재무·밸류).
function pct(v: number | null | undefined): string {
  return v == null ? "—" : `${v}%`;
}
function num(v: number | null | undefined, suffix = ""): string {
  return v == null ? "—" : `${v}${suffix}`;
}

function ProfileRow({
  label,
  picked,
  get,
}: {
  label: string;
  picked: GlobalMember[];
  get: (p: GlobalMember["profile"]) => string | undefined;
}) {
  return (
    <tr className="align-top">
      <th className="sticky left-0 z-10 border border-[#e0e0e0] bg-[#f3f6fa] px-2 py-1.5 text-left text-xs font-semibold text-[#333]">{label}</th>
      {picked.map((m) => (
        <td key={`${m.market}-${m.code}`} className="border border-[#e0e0e0] px-2 py-1.5 text-left text-[11px] leading-relaxed text-[#444]">
          {get(m.profile) ?? "—"}
        </td>
      ))}
    </tr>
  );
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
  const bRoic = bestMax((m) => m.roic);
  const bRoa = bestMax((m) => m.roa);
  const bAt = bestMax((m) => m.asset_turnover);
  const bRevG = bestMax((m) => m.rev_growth);
  const bDe = bestMin((m) => m.debt_equity); // 낮을수록 좋음
  const bPe = bestMin((m) => m.pe); // 낮을수록 저평가
  const bEv = bestMin((m) => m.ev_ebitda); // 낮을수록 저평가
  const hasProfile = picked.some((m) => m.profile);

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

            <Section title="이익 · 투자 효율 (얼마 넣어 얼마 버나)" />
            <Row label="ROIC (투하자본이익률)" render={(m) => <span style={marginStyle(m.roic)} className="font-semibold">{pct(m.roic)}</span>} medal={(m) => m.roic != null && m.roic === bRoic} />
            <Row label="ROA (총자산이익률)" render={(m) => <span style={marginStyle(m.roa)}>{pct(m.roa)}</span>} medal={(m) => m.roa != null && m.roa === bRoa} />
            <Row label="자산회전율(배)" render={(m) => num(m.asset_turnover, "x")} medal={(m) => m.asset_turnover != null && m.asset_turnover === bAt} />
            <Row label="매출성장 YoY" render={(m) => <span style={marginStyle(m.rev_growth)}>{pct(m.rev_growth)}</span>} medal={(m) => m.rev_growth != null && m.rev_growth === bRevG} />
            <Row label="5년 매출 CAGR" render={(m) => <span style={marginStyle(m.rev_cagr5y)}>{pct(m.rev_cagr5y)}</span>} />
            <Row label="이자보상배율(배)" render={(m) => num(m.interest_cov, "x")} />

            <Section title="재무 안정성 · 밸류에이션" />
            <Row label="부채비율(부채/자본)" render={(m) => pct(m.debt_equity)} medal={(m) => m.debt_equity != null && m.debt_equity === bDe} />
            <Row label="PER" render={(m) => num(m.pe)} medal={(m) => m.pe != null && m.pe > 0 && m.pe === bPe} />
            <Row label="PBR" render={(m) => num(m.pb)} />
            <Row label="EV/EBITDA(배)" render={(m) => num(m.ev_ebitda, "x")} medal={(m) => m.ev_ebitda != null && m.ev_ebitda > 0 && m.ev_ebitda === bEv} />
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

            {hasProfile && (
              <>
                <Section title="기술 · 사업 구조 (정성 분석)" />
                <ProfileRow label="🔬 핵심 기술/제품" picked={picked} get={(p) => p?.tech} />
                <ProfileRow label="💰 영업이익 창출 방식" picked={picked} get={(p) => p?.biz} />
                <ProfileRow label="🛡️ 경쟁 우위/해자" picked={picked} get={(p) => p?.moat} />
                <ProfileRow label="📈 투자 대비 회수" picked={picked} get={(p) => p?.invest} />
              </>
            )}
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
