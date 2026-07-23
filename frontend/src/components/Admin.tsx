"use client";

import { useEffect, useMemo, useState } from "react";
import {
  api, BlogPost, BlogPostListItem, BlogSavedPost, BlogSchedulerStatus,
  AdminUser, AdminStatus, VisitorStats, Curation,
} from "@/lib/api";

const GREEN = "#217346";

type Sub = "blog" | "posts" | "curation" | "manage" | "stats";

// ── 블로그 생성 ───────────────────────────────────────────────────────────
const BLOG_KINDS = [
  { id: "market-wrap", label: "오늘의 증시 보고서(자동 발행과 동일)", needTicker: false },
  { id: "dividend-stock", label: "배당 종목 분석", needTicker: true },
  { id: "daily-report", label: "데일리 시황 리포트", needTicker: false },
  { id: "crisis-survivors", label: "위기 이겨낸 배당주", needTicker: false },
  { id: "royalty", label: "배당왕·귀족 소개", needTicker: false },
  { id: "etf", label: "배당 ETF 소개", needTicker: false },
  { id: "custom", label: "직접 작성", needTicker: false },
];

function CopyBtn({ text, label }: { text: string; label: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      onClick={async () => { try { await navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 1500); } catch { /* noop */ } }}
      className="rounded border border-[#217346] px-3 py-1 text-xs font-semibold text-[#217346] hover:bg-[#eef6f0]">
      {done ? "✓ 복사됨" : label}
    </button>
  );
}

function BlogTab() {
  const [kind, setKind] = useState("dividend-stock");
  const [ticker, setTicker] = useState("005930");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [post, setPost] = useState<BlogPost | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [view, setView] = useState<"preview" | "markdown" | "html">("preview");

  const meta = BLOG_KINDS.find((k) => k.id === kind)!;

  const gen = async () => {
    setLoading(true); setErr(""); setPost(null);
    try {
      const p = await api.adminBlogGenerate({ kind, ticker, title, body });
      setPost(p);
    } catch (e) { setErr(e instanceof Error ? e.message : "생성 실패"); }
    finally { setLoading(false); }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-xs text-[#555]">콘텐츠 유형
          <select value={kind} onChange={(e) => { setKind(e.target.value); setPost(null); }}
            className="mt-0.5 block rounded border border-[#cdcdcd] px-2 py-1.5 text-sm outline-none focus:border-[#217346]">
            {BLOG_KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}
          </select>
        </label>
        {meta.needTicker && (
          <label className="text-xs text-[#555]">종목코드/티커
            <input value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="예: 005930, KO"
              className="mt-0.5 block w-40 rounded border border-[#cdcdcd] px-2 py-1.5 text-sm outline-none focus:border-[#217346]" />
          </label>
        )}
        <button onClick={gen} disabled={loading}
          className="rounded bg-[#217346] px-4 py-2 text-sm font-semibold text-white hover:bg-[#1b5e3a] disabled:opacity-50">
          {loading ? "생성 중…" : "글 생성"}
        </button>
      </div>

      {kind === "custom" && (
        <div className="flex flex-col gap-2">
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="제목"
            className="rounded border border-[#cdcdcd] px-3 py-2 text-sm outline-none focus:border-[#217346]" />
          <textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="본문(마크다운)" rows={8}
            className="rounded border border-[#cdcdcd] px-3 py-2 text-sm outline-none focus:border-[#217346]" />
        </div>
      )}

      {err && <div className="text-sm text-rose-600">{err}</div>}

      {post && <PostViewer post={post} view={view} setView={setView} />}
    </div>
  );
}

// 생성/보관 양쪽에서 같은 모양으로 글을 보여준다(미리보기·마크다운·HTML + 복사).
const PREVIEW_CLS =
  "blog-preview text-sm leading-relaxed [&_h2]:mb-2 [&_h2]:mt-3 [&_h2]:text-lg [&_h2]:font-bold [&_h3]:mb-1 [&_h3]:mt-3 [&_h3]:font-semibold [&_table]:my-2 [&_table]:w-full [&_td]:border [&_td]:border-[#ddd] [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:border-[#ddd] [&_th]:bg-[#f2f2f2] [&_th]:px-2 [&_th]:py-1 [&_p]:my-1.5 [&_blockquote]:border-l-4 [&_blockquote]:border-[#217346] [&_blockquote]:pl-3 [&_blockquote]:text-[#555] [&_ul]:my-1.5 [&_ul]:list-disc [&_ul]:pl-5 [&_img]:my-2 [&_img]:max-w-full";

type ViewMode = "preview" | "markdown" | "html";

function PostViewer({ post, view, setView, subtitle }: {
  post: BlogPost; view: ViewMode; setView: (v: ViewMode) => void; subtitle?: string;
}) {
  return (
    <div className="rounded-md border border-[#e5e5e5]">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#eee] bg-[#f7f7f7] px-3 py-2">
        <div>
          <div className="text-[13px] font-bold text-[#333]">{post.title}</div>
          {subtitle && <div className="text-[11px] text-[#999]">{subtitle}</div>}
        </div>
        <div className="flex gap-2">
          <CopyBtn text={post.html} label="HTML 복사(네이버/티스토리)" />
          <CopyBtn text={post.markdown} label="마크다운 복사" />
        </div>
      </div>
      <div className="flex gap-1 border-b border-[#eee] px-3 py-1.5 text-xs">
        {(["preview", "markdown", "html"] as const).map((v) => (
          <button key={v} onClick={() => setView(v)}
            className={`rounded px-2 py-0.5 ${view === v ? "bg-[#217346] text-white" : "text-[#666] hover:bg-[#eee]"}`}>
            {v === "preview" ? "미리보기" : v === "markdown" ? "마크다운" : "HTML"}
          </button>
        ))}
        {post.tags?.length > 0 && (
          <span className="ml-auto self-center text-[11px] text-[#999]">태그: {post.tags.join(", ")}</span>
        )}
      </div>
      <div className="max-h-[520px] overflow-auto p-4">
        {view === "preview" ? (
          <div className={PREVIEW_CLS} dangerouslySetInnerHTML={{ __html: post.html }} />
        ) : (
          <pre className="whitespace-pre-wrap break-words text-[12px] text-[#333]">
            {view === "markdown" ? post.markdown : post.html}
          </pre>
        )}
      </div>
    </div>
  );
}

// ── 발행 보관함: 자동 발행된 증시 보고서 ──────────────────────────────────
function PostsTab() {
  const [list, setList] = useState<BlogPostListItem[]>([]);
  const [dir, setDir] = useState("");
  const [sched, setSched] = useState<BlogSchedulerStatus | null>(null);
  const [sel, setSel] = useState<string>("");
  const [post, setPost] = useState<BlogSavedPost | null>(null);
  const [view, setView] = useState<ViewMode>("preview");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const reload = async () => {
    try {
      const [r, s] = await Promise.all([api.adminBlogPosts(), api.adminBlogScheduler().catch(() => null)]);
      setList(r.posts); setDir(r.dir); if (s) setSched(s);
    } catch (e) { setErr(e instanceof Error ? e.message : "목록 실패"); }
  };
  useEffect(() => { reload(); }, []);

  const open = async (it: BlogPostListItem) => {
    setSel(it.date); setPost(null); setErr("");
    try {
      const p = await api.adminBlogPost(it.date, it.kind);
      if (p.available === false) setErr(p.reason || "글을 찾을 수 없습니다.");
      else setPost(p);
    } catch (e) { setErr(e instanceof Error ? e.message : "불러오기 실패"); }
  };

  const publishNow = async () => {
    setBusy(true); setErr("");
    try {
      const p = await api.adminBlogPublish("", true);
      setPost(p); setSel(p.date);
      await reload();
    } catch (e) { setErr(e instanceof Error ? e.message : "발행 실패"); }
    finally { setBusy(false); }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3 rounded border border-[#e5e5e5] bg-[#fafafa] px-3 py-2">
        <button onClick={publishNow} disabled={busy}
          className="rounded bg-[#217346] px-4 py-2 text-sm font-semibold text-white hover:bg-[#1b5e3a] disabled:opacity-50">
          {busy ? "발행 중…" : "오늘자 지금 발행"}
        </button>
        {sched && (
          <div className="text-[12px] text-[#555]">
            자동 발행{" "}
            <b style={{ color: sched.enabled ? GREEN : "#c92a2a" }}>
              {sched.enabled ? sched.schedule : "꺼짐"}
            </b>
            {sched.latest_post?.date && (
              <span className="text-[#999]"> · 마지막 {sched.latest_post.date}</span>
            )}
            {sched.skipped_reason && <span className="text-[#999]"> · {sched.skipped_reason}</span>}
            {sched.last_error && <span className="text-rose-600"> · 오류 {sched.last_error}</span>}
          </div>
        )}
        {dir && <span className="ml-auto text-[11px] text-[#aaa]">{dir}</span>}
      </div>

      {err && <div className="text-sm text-rose-600">{err}</div>}

      <div className="flex flex-col gap-3 lg:flex-row">
        <div className="lg:w-72 lg:shrink-0">
          <div className="mb-1 text-[11px] text-[#999]">보관된 글 {list.length}편</div>
          <div className="max-h-[520px] overflow-auto rounded border border-[#e5e5e5]">
            {list.length === 0 && (
              <div className="p-3 text-[12px] text-[#999]">
                아직 없습니다. 평일 장 마감 뒤 자동으로 쌓이고, 위 버튼으로 바로 만들 수도 있습니다.
              </div>
            )}
            {list.map((it) => (
              <button key={it.file} onClick={() => open(it)}
                className={`block w-full border-b border-[#f0f0f0] px-3 py-2 text-left hover:bg-[#f7f7f7] ${sel === it.date ? "bg-[#eef6f0]" : ""}`}>
                <div className="text-[12px] font-semibold text-[#333]">{it.date}</div>
                <div className="truncate text-[11px] text-[#666]">{it.title}</div>
                <div className="text-[10px] text-[#aaa]">{it.sections}섹션 · {it.chars.toLocaleString()}자</div>
              </button>
            ))}
          </div>
        </div>
        <div className="min-w-0 flex-1">
          {post ? (
            <PostViewer post={post} view={view} setView={setView}
              subtitle={`${post.date} · 저장 ${post.saved_at ?? "—"}`} />
          ) : (
            <div className="rounded border border-dashed border-[#ddd] p-6 text-center text-[12px] text-[#999]">
              왼쪽에서 날짜를 고르면 글이 열립니다.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── 콘텐츠 큐레이션 ───────────────────────────────────────────────────────
function CurationTab() {
  const [c, setC] = useState<Curation | null>(null);
  const [headline, setHeadline] = useState("");
  const [picks, setPicks] = useState("");
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => { api.adminCurationGet().then((r) => { setC(r); setHeadline(r.headline); setPicks(r.picks.join(", ")); setNote(r.note); }).catch(() => {}); }, []);

  const save = async () => {
    const r = await api.adminCurationSet(headline, picks.split(",").map((s) => s.trim()).filter(Boolean), note);
    setC(r); setSaved(true); setTimeout(() => setSaved(false), 1500);
  };
  return (
    <div className="flex max-w-2xl flex-col gap-3">
      <div className="text-[12px] text-[#666]">메인에 노출할 '오늘의 추천'을 설정합니다.</div>
      <label className="text-xs text-[#555]">헤드라인
        <input value={headline} onChange={(e) => setHeadline(e.target.value)} placeholder="예: 이번 주 눈여겨볼 배당주"
          className="mt-0.5 block w-full rounded border border-[#cdcdcd] px-3 py-2 text-sm outline-none focus:border-[#217346]" />
      </label>
      <label className="text-xs text-[#555]">추천 종목(쉼표 구분)
        <input value={picks} onChange={(e) => setPicks(e.target.value)} placeholder="005930, KO, JNJ"
          className="mt-0.5 block w-full rounded border border-[#cdcdcd] px-3 py-2 text-sm outline-none focus:border-[#217346]" />
      </label>
      <label className="text-xs text-[#555]">코멘트
        <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3}
          className="mt-0.5 block w-full rounded border border-[#cdcdcd] px-3 py-2 text-sm outline-none focus:border-[#217346]" />
      </label>
      <div className="flex items-center gap-3">
        <button onClick={save} className="rounded bg-[#217346] px-4 py-2 text-sm font-semibold text-white hover:bg-[#1b5e3a]">{saved ? "✓ 저장됨" : "저장"}</button>
        {c?.updated_at && <span className="text-[11px] text-[#999]">최종 수정: {c.updated_at}</span>}
      </div>
    </div>
  );
}

// ── 사용자·데이터 관리 ────────────────────────────────────────────────────
function ManageTab() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [status, setStatus] = useState<AdminStatus | null>(null);
  useEffect(() => {
    api.adminUsers().then((r) => setUsers(r.users)).catch(() => {});
    api.adminStatus().then(setStatus).catch(() => {});
  }, []);
  return (
    <div className="flex flex-col gap-4">
      <div>
        <div className="mb-1 text-sm font-bold text-[#217346]">데이터·스케줄러 상태</div>
        {status ? (
          <div className="flex flex-wrap gap-2 text-[12px]">
            {status.coverage.map((c) => (
              <div key={c.market} className="rounded border border-[#e5e5e5] px-3 py-1.5">
                <b>{c.market}</b> {c.tickers.toLocaleString()}종목 · {c.rows.toLocaleString()}건 <span className="text-[#999]">({String(c.first_date).slice(0, 10)}~{String(c.last_date).slice(0, 10)})</span>
              </div>
            ))}
            <div className="rounded border border-[#e5e5e5] px-3 py-1.5">DART <b style={{ color: status.dart_enabled ? GREEN : "#c0392b" }}>{status.dart_enabled ? "연결됨" : "미설정"}</b></div>
            <div className="rounded border border-[#e5e5e5] px-3 py-1.5">가격 수집 <b style={{ color: (status.price_scheduler as {running?: boolean}).running ? GREEN : "#999" }}>{(status.price_scheduler as {running?: boolean}).running ? "동작중" : "정지"}</b></div>
          </div>
        ) : <div className="text-xs text-[#999]">불러오는 중…</div>}
      </div>
      <div>
        <div className="mb-1 text-sm font-bold text-[#217346]">가입자 ({users.length}명)</div>
        <table className="w-full text-[12px]">
          <thead className="text-left text-[10px] uppercase text-[#999]"><tr className="border-b border-[#eee]"><th className="px-3 py-1.5">아이디</th><th className="px-3 py-1.5">이름</th><th className="px-3 py-1.5">이메일</th><th className="px-3 py-1.5">가입일</th><th className="px-3 py-1.5">권한</th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.username} className="border-t border-[#f2f2f2]">
                <td className="px-3 py-1.5 font-semibold text-[#333]">{u.username}</td>
                <td className="px-3 py-1.5 text-[#666]">{u.name || "—"}</td>
                <td className="px-3 py-1.5 text-[#666]">{u.email || "—"}</td>
                <td className="px-3 py-1.5 text-[#999]">{u.created ? new Date(u.created * 1000).toLocaleDateString("ko-KR") : "—"}</td>
                <td className="px-3 py-1.5">{u.is_admin ? <span className="rounded bg-[#fff4d6] px-1.5 py-0.5 text-[10px] font-bold text-[#8a6d1a]">관리자</span> : <span className="text-[#bbb]">일반</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── 방문자 통계 ───────────────────────────────────────────────────────────
function StatsTab() {
  const [s, setS] = useState<VisitorStats | null>(null);
  useEffect(() => { api.adminStats().then(setS).catch(() => {}); }, []);
  const maxV = useMemo(() => Math.max(1, ...(s?.top_views ?? []).map((v) => v.count)), [s]);
  const VIEW_LABEL: Record<string, string> = {
    market: "전종목 분석", dividend: "배당·실적", score: "투자 점수", movers: "급등락", watch: "관심·보유",
    briefing: "장전 브리핑", open: "개장 예측", live: "실시간 시황", report: "데일리 리포트",
    money: "자금 흐름", korea: "한국 경제", inst: "기관 추적", future: "미래 테마", industry: "산업 지도",
    budget: "가계부", wealth: "재테크", crisis: "위기 시뮬", realestate: "부동산", unitecon: "원가분해", admin: "관리자",
  };
  if (!s) return <div className="text-xs text-[#999]">불러오는 중…</div>;
  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-6">
        <div><div className="text-[10px] text-[#999]">누적 조회</div><div className="text-2xl font-extrabold tabular-nums text-[#217346]">{s.total.toLocaleString()}</div></div>
        <div><div className="text-[10px] text-[#999]">오늘</div><div className="text-2xl font-extrabold tabular-nums text-[#333]">{s.today.toLocaleString()}</div></div>
      </div>
      <div>
        <div className="mb-1 text-sm font-bold text-[#217346]">많이 본 화면</div>
        {s.top_views.length === 0 ? <div className="text-xs text-[#999]">아직 데이터가 없습니다. 사용자가 화면을 열면 집계됩니다.</div> : (
          <div className="flex flex-col gap-1">
            {s.top_views.map((v) => (
              <div key={v.view} className="flex items-center gap-2 text-[12px]">
                <span className="w-24 shrink-0 text-[#555]">{VIEW_LABEL[v.view] ?? v.view}</span>
                <div className="h-4 flex-1 rounded bg-[#f1f3f5]"><div className="h-4 rounded bg-[#217346]" style={{ width: `${(v.count / maxV) * 100}%` }} /></div>
                <span className="w-12 shrink-0 text-right tabular-nums text-[#666]">{v.count}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function Admin() {
  const [sub, setSub] = useState<Sub>("blog");
  const SUBS: { id: Sub; label: string }[] = [
    { id: "blog", label: "📝 블로그 생성" },
    { id: "posts", label: "🗂️ 발행 보관함" },
    { id: "curation", label: "⭐ 콘텐츠 큐레이션" },
    { id: "manage", label: "👥 사용자·데이터" },
    { id: "stats", label: "📊 방문자 통계" },
  ];
  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
        <span className="text-sm font-semibold">관리자 — 분석을 콘텐츠로</span>
      </div>
      <div className="flex gap-1 border-b border-[#e5e5e5] bg-[#f7f7f7] px-3 py-2">
        {SUBS.map((t) => (
          <button key={t.id} onClick={() => setSub(t.id)}
            className={`rounded px-3 py-1.5 text-[13px] font-semibold transition ${sub === t.id ? "bg-[#217346] text-white" : "text-[#555] hover:bg-[#e9efeb]"}`}>
            {t.label}
          </button>
        ))}
      </div>
      <div className="p-4">
        {sub === "blog" && <BlogTab />}
        {sub === "posts" && <PostsTab />}
        {sub === "curation" && <CurationTab />}
        {sub === "manage" && <ManageTab />}
        {sub === "stats" && <StatsTab />}
      </div>
    </div>
  );
}
