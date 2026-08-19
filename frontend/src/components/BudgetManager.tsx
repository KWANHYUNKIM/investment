"use client";

// 가계부 — 카드 명세서를 올리면 네 축(카테고리·카드·거래구분·고정비)으로 갈라 보여준다.
//
// 화면이 지키는 규칙 두 가지.
//  1) 지출은 항상 **그 청구월에 실제로 빠지는 돈**(tx.amount)이다. 할부 전액(total)은
//     참고로만 보여주고 합계에 넣지 않는다. 넣으면 저축 가능액이 통장과 어긋난다.
//  2) 명세서는 **보고 나서 등록**한다. 카드사마다 금액의 의미가 달라 바로 저장하면
//     틀린 걸 나중에 찾기 어렵다.

import { useMemo, useState } from "react";
import {
  api,
  type BudgetSummary,
  type BudgetPlan,
  type BudgetTx,
  type BudgetCard,
  type BudgetCardsOverview,
  type CardCycle,
  type CardStatementPreview,
  type FixedCostBoard,
} from "@/lib/api";
import { useApiData } from "@/lib/useApiData";

const RED = "#c92a2a";
const GREEN = "#217346";
const BLUE = "#1971c2";
const CAT_COLORS = ["#217346", "#4c9a6a", "#e0a34e", "#c96f6f", "#6f8fc9", "#9a7fc9", "#c99f6f", "#7fc9b0", "#c97f9f", "#8a8a8a"];

function won(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${Math.round(v).toLocaleString("ko-KR")}원`;
}
function num(v: number | null | undefined): string {
  if (v == null) return "—";
  return Math.round(v).toLocaleString("ko-KR");
}

type Axis = "category" | "card" | "tx_type" | "fixed";
const AXES: { key: Axis; label: string }[] = [
  { key: "category", label: "카테고리" },
  { key: "card", label: "카드·명의" },
  { key: "tx_type", label: "거래구분" },
  { key: "fixed", label: "고정비·변동비" },
];

export function BudgetManager() {
  const [month, setMonth] = useState("");
  const [basis, setBasis] = useState<"billing_month" | "date">("billing_month");
  const [axis, setAxis] = useState<Axis>("category");
  const [pick, setPick] = useState<{ axis: Axis; value: string } | null>(null);
  const [view, setView] = useState<"list" | "calendar">("list");
  const [day, setDay] = useState("");          // 캘린더에서 고른 하루 (YYYY-MM-DD)
  const [cat, setCat] = useState("");          // 거래 목록 카테고리 필터
  const [q, setQ] = useState("");              // 가맹점 검색
  const [version, setVersion] = useState(0);

  const [emMonths, setEmMonths] = useState(3);
  const [investRatio, setInvestRatio] = useState(0.5);

  const [net, setNet] = useState("");
  const [extra, setExtra] = useState("");
  const [payMsg, setPayMsg] = useState("");
  const [busy, setBusy] = useState("");

  const [preview, setPreview] = useState<CardStatementPreview | null>(null);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  // 카드사가 청구월을 안 알려주는 파일(롯데 결제예정금액·하나 이용내역)이 있어서
  // 등록 전에 사용자가 확정한다. 서버 추정치를 초기값으로 받는다.
  const [billMonth, setBillMonth] = useState("");
  const [paste, setPaste] = useState("");
  const [msg, setMsg] = useState("");

  const bump = () => setVersion((v) => v + 1);

  const sum = useApiData<BudgetSummary>(
    () => api.budgetSummary(month || undefined, basis),
    `${month}|${basis}|${version}`,
  );
  const plan = useApiData<BudgetPlan>(
    () => api.budgetPlan(emMonths, investRatio),
    `${emMonths}|${investRatio}|${version}`,
  );
  const cards = useApiData<BudgetCardsOverview>(() => api.budgetCards(), `${version}`);
  const fixed = useApiData<FixedCostBoard>(() => api.budgetFixedCosts(), `${version}`);

  const s = sum.data;
  const p = plan.data;

  // 명세서 파싱 → 확인 → 등록 -------------------------------------------------
  const runPreview = async (file: File) => {
    setBusy("preview");
    setMsg("");
    try {
      const rep = await api.budgetPreviewFile(file);
      setPreview(rep);
      setChosen(new Set(rep.transactions.map((t) => t.fp)));
      setBillMonth(rep.billing_month);
      if (!rep.transactions.length) setMsg(rep.note);
    } catch {
      setMsg("파일을 읽지 못했습니다. 카드사에서 받은 원본인지 확인해 주세요.");
    } finally {
      setBusy("");
    }
  };

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (f) await runPreview(f);
  };

  const onPaste = async () => {
    if (!paste.trim()) return;
    // 붙여넣기도 파일과 같은 파서를 타게 해서 결과가 갈리지 않게 한다.
    await runPreview(new File([paste], "paste.csv", { type: "text/csv" }));
  };

  const commit = async () => {
    if (!preview) return;
    // 사용자가 확정한 청구월을 전부에 씌운다(서버가 지문을 다시 만들어 중복도 맞춰진다).
    const items = preview.transactions
      .filter((t) => chosen.has(t.fp))
      .map((t) => (billMonth ? { ...t, billing_month: billMonth } : t));
    if (!items.length) return;
    setBusy("commit");
    try {
      const r = await api.budgetAdd(items);
      setMsg(`${r.added}건 등록${r.skipped ? ` · ${r.skipped}건은 이미 있어 건너뜀` : ""}`);
      setPreview(null);
      setPaste("");
      setMonth(billMonth || preview.billing_month || "");
      bump();
    } catch {
      setMsg("등록에 실패했습니다.");
    } finally {
      setBusy("");
    }
  };

  const onPayslip = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    setBusy("payslip");
    setPayMsg("");
    try {
      const r = await api.budgetParsePayslip(f);
      if (r.net != null) {
        setNet(String(r.net));
        const parts = [`실수령액 ${won(r.net)} 인식`];
        if (r.gross != null) parts.push(`지급 ${won(r.gross)}`);
        if (r.deduction != null) parts.push(`공제 ${won(r.deduction)}`);
        setPayMsg((r.guessed ? "추정 — " : "") + parts.join(" · ") + " · 확인 후 저장하세요");
      } else {
        setPayMsg("금액을 찾지 못했습니다. 직접 입력해 주세요.");
      }
    } catch {
      setPayMsg("명세서를 읽지 못했습니다 (지원: .xlsx/.xls/.pdf/.csv).");
    } finally {
      setBusy("");
    }
  };

  const saveIncome = async () => {
    setBusy("income");
    try {
      await api.budgetSetIncome(Number(net) || 0, Number(extra) || 0);
      bump();
    } finally {
      setBusy("");
    }
  };

  // 축별 버킷 ----------------------------------------------------------------
  const buckets = useMemo(() => {
    if (!s) return [] as { label: string; amount: number; pct: number; count: number }[];
    if (axis === "category") return s.by_category.map((b) => ({ label: b.category, ...b }));
    if (axis === "card") return s.by_card.map((b) => ({ label: b.card, ...b }));
    if (axis === "tx_type") return s.by_tx_type.map((b) => ({ label: b.tx_type, ...b }));
    const f = s.by_fixed;
    const total = f.fixed + f.variable;
    return [
      { label: "고정비", amount: f.fixed, pct: total ? Math.round((f.fixed / total) * 1000) / 10 : 0, count: 0 },
      { label: "변동비", amount: f.variable, pct: total ? Math.round((f.variable / total) * 1000) / 10 : 0, count: 0 },
    ];
  }, [s, axis]);

  // 축 필터가 걸린 거래 — 캘린더도 이걸 그린다(카테고리를 고르면 달력도 같이 좁혀진다).
  const rows = useMemo(() => {
    const all = s?.transactions ?? [];
    if (!pick) return all;
    return all.filter((t) => {
      if (pick.axis === "category") return t.category === pick.value;
      if (pick.axis === "card") return `${t.issuer} ${t.card}`.trim() === pick.value;
      if (pick.axis === "tx_type") return t.tx_type === pick.value;
      return pick.value === "고정비" ? !!t.fixed : !t.fixed;
    });
  }, [s, pick]);

  // 목록에 실제로 뿌릴 것 — 축 필터 위에 카테고리·검색·날짜를 더 건다.
  // 예정 할부는 맨 위에 붙인다(아직 안 나갔지만 이미 확정된 돈이라 먼저 보여야 한다).
  // 좁히는 조건이 하나라도 걸리면 예정분은 뺀다 — 거래일이 없어 그 조건에 답할 수 없다.
  const listRows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let base = rows;
    if (day) base = base.filter((t) => t.date === day);
    if (cat) base = base.filter((t) => t.category === cat);
    if (needle) base = base.filter((t) => t.merchant.toLowerCase().includes(needle));
    if (day || cat || needle || pick || !s?.projected.length) return base;
    return [...s.projected, ...base];
  }, [rows, day, cat, q, pick, s]);

  const listTotal = useMemo(
    () => listRows.reduce((a, t) => a + (t.amount > 0 ? t.amount : 0), 0),
    [listRows],
  );

  const maxBucket = buckets[0]?.amount || 1;
  const monthValue = month || s?.month || "";

  return (
    <div className="flex min-w-0 flex-col gap-4">
      {/* ── 상단: 월·기준 + 요약 ────────────────────────── */}
      <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2 bg-[#217346] px-4 py-2 text-white">
          <span className="text-sm font-semibold">가계부.xlsx</span>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <div className="flex overflow-hidden rounded border border-white/30">
              {(["billing_month", "date"] as const).map((b) => (
                <button
                  key={b}
                  onClick={() => setBasis(b)}
                  className={`px-2 py-0.5 ${basis === b ? "bg-white text-[#217346]" : "hover:bg-white/20"}`}
                  title={b === "billing_month" ? "카드값이 실제로 빠지는 달로 집계" : "카드를 긁은 날로 집계"}
                >
                  {b === "billing_month" ? "청구월" : "거래월"}
                </button>
              ))}
            </div>
            {s && s.months.length > 0 && (
              <select
                value={monthValue}
                onChange={(e) => { setMonth(e.target.value); setPick(null); setDay(""); }}
                className="rounded bg-white/20 px-1.5 py-0.5 text-xs text-white outline-none"
              >
                {/* 카드사마다 결제일이 달라 청구월이 갈린다 — 다른 달에 있는 카드가
                    '안 들어간 것처럼' 보이지 않게 전체 보기를 둔다. */}
                <option value="all" className="text-black">전체 기간</option>
                {s.months.map((m) => (
                  <option key={m} value={m} className="text-black">
                    {m}{s.future_months.includes(m) ? " (할부 예정)" : ""}
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>

        {!s ? (
          <div className="py-10 text-center text-sm text-[#888]">{sum.error ?? "불러오는 중…"}</div>
        ) : (
          <div className="grid grid-cols-2 gap-px bg-[#e8e8e8] sm:grid-cols-3 xl:grid-cols-6">
            <Cell label="수입" value={won(s.income_total)} />
            <Cell
              label={basis === "billing_month" ? "이 달 카드값" : "이 달 지출"}
              value={won(s.spent)}
              sub={s.projected_total ? `+ 할부 예정 ${num(s.projected_total)}` : undefined}
              color={RED}
            />
            <Cell
              label="확정 지출"
              value={won(s.committed)}
              sub={s.projected_total ? "명세서 + 남은 할부" : undefined}
              color={RED}
            />
            <Cell label="저축 가능" value={won(s.savings_possible)} color={s.savings_possible >= 0 ? GREEN : RED} />
            <Cell label="고정비 비중" value={`${s.by_fixed.fixed_pct}%`} sub={won(s.by_fixed.fixed)} />
            <Cell
              label="할부 잔액"
              value={won(s.installments.remaining_total)}
              sub={s.installments.next_month ? `다음 달 ${num(s.installments.next_month)}+수수료` : undefined}
              color={s.installments.remaining_total ? BLUE : undefined}
            />
          </div>
        )}
      </div>

      <div className="grid min-w-0 grid-cols-1 gap-4 xl:grid-cols-3">
        {/* ── 좌: 명세서 올리기 · 급여 · 계획 ─────────────── */}
        <div className="flex min-w-0 flex-col gap-4">
          {/* 카드 명세서 */}
          <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
            <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
              <span className="text-sm font-semibold">카드 명세서 올리기</span>
              <label className="cursor-pointer rounded bg-white/20 px-2 py-0.5 text-xs hover:bg-white/30">
                {busy === "preview" ? "읽는 중…" : "파일 선택"}
                <input type="file" accept=".xls,.xlsx,.csv,.txt,.html" className="hidden" onChange={onFile} disabled={!!busy} />
              </label>
            </div>
            <div className="p-3">
              <p className="mb-2 text-[11px] leading-relaxed text-[#666]">
                카드사에서 받은 이용대금명세서를 그대로 올리세요. 신한카드는 확장자가 <code>.xls</code> 여도
                실제로는 HTML 표라서 엑셀로는 안 열리는데, 여기서는 그대로 읽습니다.
                할부는 <b>이번 회차 결제금액 + 수수료</b>만 그 달 지출로 잡습니다.
              </p>
              <textarea
                value={paste}
                onChange={(e) => setPaste(e.target.value)}
                rows={3}
                placeholder={"또는 내역을 붙여넣기\n2026-07-02,스타벅스강남,5,600"}
                className="w-full resize-y rounded border border-[#cdcdcd] p-2 font-mono text-[11px] outline-none focus:border-[#217346]"
              />
              <div className="mt-2 flex items-center gap-2">
                <button
                  onClick={onPaste}
                  disabled={!!busy || !paste.trim()}
                  className="rounded border border-[#cdcdcd] bg-white px-3 py-1.5 text-xs font-semibold text-[#217346] hover:bg-[#eef6f0] disabled:opacity-50"
                >
                  붙여넣은 내역 읽기
                </button>
                {msg && <span className="text-[11px] text-[#456]">{msg}</span>}
              </div>

              {s && s.imports.length > 0 && !preview && (
                <div className="mt-3 border-t border-[#eee] pt-2">
                  <div className="mb-1 text-[10px] font-semibold text-[#999]">최근 등록</div>
                  <ul className="flex flex-col gap-1 text-[11px] text-[#666]">
                    {s.imports.map((im, i) => (
                      <li key={i} className="flex items-center justify-between gap-2">
                        <span className="truncate">
                          {im.at} · {im.issuer || "카드사 미상"} · {im.added}건
                        </span>
                        {im.issuer && (
                          <span className="flex shrink-0 items-center gap-1">
                            {/* 청구월이 없는 카드사는 추정치가 들어간다 — 여기서 바로 고친다. */}
                            <input
                              type="month"
                              defaultValue={im.billing_month}
                              title="청구월 변경"
                              onChange={async (e) => {
                                const to = e.target.value;
                                if (!to || to === im.billing_month) return;
                                await api.budgetMoveMonth(im.issuer, im.billing_month, to);
                                setMonth(to);
                                bump();
                              }}
                              className="rounded border border-[#e0e0e0] px-1 py-0.5 text-[10px] outline-none focus:border-[#217346]"
                            />
                            <button
                              onClick={async () => {
                                if (!confirm(`${im.issuer} ${im.billing_month} 등록분을 지울까요?`)) return;
                                await api.budgetClearImport(im.issuer, im.billing_month);
                                bump();
                              }}
                              className="text-[#bbb] hover:text-rose-500"
                            >
                              되돌리기
                            </button>
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>

          {/* 고정지출 */}
          {fixed.data && (fixed.data.items.length > 0 || fixed.data.candidates.length > 0) && (
            <FixedCosts board={fixed.data} onChange={bump} />
          )}

          {/* 카드별 결제일·이용기간 */}
          {cards.data && cards.data.cards.length > 0 && (
            <CardCycles data={cards.data} onSaved={bump} />
          )}

          {/* 급여 */}
          <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
            <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
              <span className="text-sm font-semibold">급여·수입</span>
              <label className="cursor-pointer rounded bg-white/20 px-2 py-0.5 text-xs hover:bg-white/30">
                {busy === "payslip" ? "인식 중…" : "명세서 올리기"}
                <input type="file" accept=".xlsx,.xls,.pdf,.csv" className="hidden" onChange={onPayslip} disabled={!!busy} />
              </label>
            </div>
            <div className="flex flex-wrap items-end gap-2 p-3">
              <label className="text-xs text-[#555]">
                월 실수령액
                <input
                  value={net}
                  onChange={(e) => setNet(e.target.value)}
                  inputMode="numeric"
                  placeholder={String(s?.income.monthly_net || "3000000")}
                  className="mt-0.5 block w-36 rounded border border-[#cdcdcd] px-2 py-1 text-right text-sm outline-none focus:border-[#217346]"
                />
              </label>
              <label className="text-xs text-[#555]">
                기타 수입(월)
                <input
                  value={extra}
                  onChange={(e) => setExtra(e.target.value)}
                  inputMode="numeric"
                  placeholder={String(s?.income.extra || "0")}
                  className="mt-0.5 block w-28 rounded border border-[#cdcdcd] px-2 py-1 text-right text-sm outline-none focus:border-[#217346]"
                />
              </label>
              <button
                onClick={saveIncome}
                disabled={busy === "income"}
                className="rounded bg-[#217346] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#1b5e3a] disabled:opacity-50"
              >
                {busy === "income" ? "저장 중…" : "저장"}
              </button>
            </div>
            {payMsg && <div className="border-t border-[#eee] bg-[#f7faf8] px-3 py-1.5 text-[11px] text-[#456]">{payMsg}</div>}
          </div>

          {/* 저축·투자 계획 */}
          <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
            <div className="bg-[#217346] px-4 py-2 text-sm font-semibold text-white">저축·투자 계획</div>
            <div className="p-3">
              <div className="mb-2 flex flex-wrap items-center gap-3 text-xs text-[#555]">
                <label className="flex items-center gap-1">
                  비상금
                  <select value={emMonths} onChange={(e) => setEmMonths(Number(e.target.value))} className="rounded border border-[#cdcdcd] px-1 py-0.5">
                    {[3, 6, 9, 12].map((n) => <option key={n} value={n}>{n}개월</option>)}
                  </select>
                </label>
                <label className="flex items-center gap-1">
                  투자 비중
                  <select value={investRatio} onChange={(e) => setInvestRatio(Number(e.target.value))} className="rounded border border-[#cdcdcd] px-1 py-0.5">
                    {[0.3, 0.5, 0.7].map((n) => <option key={n} value={n}>{Math.round(n * 100)}%</option>)}
                  </select>
                </label>
              </div>
              {p && (
                <>
                  <div className="mb-2 grid grid-cols-3 gap-2 text-center">
                    <Mini label="월 여유자금" value={won(p.surplus)} color={p.surplus >= 0 ? GREEN : RED} />
                    <Mini label="할부 뺀 여유" value={won(p.surplus_after_installment)} color={p.surplus_after_installment >= 0 ? GREEN : RED} />
                    <Mini label="보유 주식" value={won(p.stock_value)} />
                  </div>
                  <div className="mb-2 grid grid-cols-3 gap-2 text-center">
                    <Mini label="평균 고정비" value={won(p.avg_fixed)} />
                    <Mini label="평균 변동비" value={won(p.avg_variable)} />
                    <Mini label="비상금 목표" value={won(p.emergency_target)} />
                  </div>
                  <div className="mb-2 flex gap-2 text-center text-xs">
                    <Mini className="flex-1" label="매월 안전저축" value={won(p.monthly_save)} color={GREEN} />
                    <Mini className="flex-1" label="매월 투자" value={won(p.monthly_invest)} color={GREEN} />
                  </div>
                  <ul className="flex flex-col gap-1 rounded border border-[#f0e6c9] bg-[#fdfaf0] p-2 text-[11px] leading-relaxed text-[#7a5f10]">
                    {p.steps.map((v, i) => <li key={i}>· {v}</li>)}
                  </ul>
                </>
              )}
            </div>
          </div>
        </div>

        {/* ── 우: 미리보기 또는 분리 결과 ────────────────── */}
        <div className="flex min-w-0 flex-col gap-4 xl:col-span-2">
          {preview ? (
            <PreviewPanel
              rep={preview}
              chosen={chosen}
              setChosen={setChosen}
              billMonth={billMonth}
              setBillMonth={setBillMonth}
              onCancel={() => { setPreview(null); setMsg(""); }}
              onCommit={commit}
              busy={busy === "commit"}
            />
          ) : (
            <>
              {/* 분리 축 */}
              <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-1 border-b border-[#d0d0d0] bg-[#f3f2f1] px-2 py-1">
                  <div className="flex flex-wrap">
                    {AXES.map((a) => (
                      <button
                        key={a.key}
                        onClick={() => { setAxis(a.key); setPick(null); }}
                        className={`border-b-2 px-3 py-1 text-xs font-semibold ${
                          axis === a.key ? "border-[#217346] text-[#217346]" : "border-transparent text-[#777] hover:text-[#217346]"
                        }`}
                      >
                        {a.label}
                      </button>
                    ))}
                  </div>
                  {pick && (
                    <button onClick={() => setPick(null)} className="rounded border border-[#cdcdcd] px-2 py-0.5 text-[11px] text-[#666] hover:bg-white">
                      {pick.value} 필터 해제
                    </button>
                  )}
                </div>
                <div className="p-3">
                  {buckets.length === 0 ? (
                    <div className="py-8 text-center text-xs text-[#aaa]">
                      {s && s.projected_total > 0 ? (
                        <>
                          이 달 명세서는 아직 없고, 남은 할부 <b className="text-[#1b4f7a]">{won(s.projected_total)}</b> 만 확정돼 있습니다.
                          <div className="mt-1 text-[11px]">아래 목록에서 확인하세요.</div>
                        </>
                      ) : (
                        "이 달 내역이 없습니다. 왼쪽에서 명세서를 올려보세요."
                      )}
                    </div>
                  ) : (
                    <div className="flex flex-col gap-1.5">
                      {buckets.map((b, i) => {
                        const on = pick?.axis === axis && pick.value === b.label;
                        return (
                          <button
                            key={b.label}
                            onClick={() => setPick(on ? null : { axis, value: b.label })}
                            className={`w-full rounded px-1.5 py-1 text-left transition ${on ? "bg-[#eef6f0]" : "hover:bg-[#fafafa]"}`}
                          >
                            <div className="flex justify-between text-[11px]">
                              <span className="text-[#444]">
                                {b.label} <span className="text-[#aaa]">{b.pct}%{b.count ? ` · ${b.count}건` : ""}</span>
                              </span>
                              <span className="tabular-nums font-semibold text-[#333]">{won(b.amount)}</span>
                            </div>
                            <div className="mt-0.5 h-1.5 w-full overflow-hidden rounded-full bg-[#eee]">
                              <div className="h-full rounded-full" style={{ width: `${(b.amount / maxBucket) * 100}%`, background: CAT_COLORS[i % CAT_COLORS.length] }} />
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}
                  {axis === "fixed" && s && s.by_fixed.items.length > 0 && (
                    <div className="mt-3 border-t border-[#eee] pt-2">
                      <div className="mb-1 text-[10px] font-semibold text-[#999]">고정비로 잡힌 항목 (여러 달 반복되거나 통신·공과금·구독)</div>
                      <ul className="flex flex-wrap gap-1">
                        {s.by_fixed.items.map((it) => (
                          <li key={it.key} className="rounded border border-[#dbe9e0] bg-[#f4faf6] px-1.5 py-0.5 text-[11px] text-[#2c6b47]">
                            {it.key} {won(it.amount)}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>

              {/* 할부 */}
              {s && s.installments.count > 0 && (
                <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
                  <div className="border-b border-[#d0d0d0] bg-[#f3f2f1] px-3 py-1.5 text-xs font-bold text-[#217346]">
                    남은 할부 — 아직 안 나갔지만 이미 확정된 지출
                  </div>
                  <div className="p-3">
                    <div className="mb-2 flex flex-wrap gap-1">
                      {s.upcoming.map((u) => (
                        <div key={u.month} className="rounded border border-[#d7e3ee] bg-[#f4f8fc] px-2 py-1 text-[11px] text-[#1b4f7a]">
                          {u.month} <b className="tabular-nums">{num(u.principal)}</b>
                        </div>
                      ))}
                    </div>
                    <table className="w-full text-[11px]">
                      <thead>
                        <tr className="border-b border-[#eee] text-[10px] text-[#999]">
                          <th className="px-1 py-1 text-left font-semibold">가맹점</th>
                          <th className="px-1 py-1 text-left font-semibold">카드</th>
                          <th className="px-1 py-1 text-right font-semibold">전액</th>
                          <th className="px-1 py-1 text-right font-semibold">남은 회차</th>
                          <th className="px-1 py-1 text-right font-semibold">월 원금</th>
                          <th className="px-1 py-1 text-right font-semibold">잔액</th>
                        </tr>
                      </thead>
                      <tbody>
                        {s.installments.items.map((it, i) => (
                          <tr key={i} className="border-b border-[#f5f5f5]">
                            <td className="px-1 py-1 text-[#333]">{it.merchant}</td>
                            <td className="px-1 py-1 text-[#888]">{it.card}</td>
                            <td className="px-1 py-1 text-right tabular-nums text-[#666]">{num(it.total)}</td>
                            <td className="px-1 py-1 text-right tabular-nums text-[#666]">{it.months_left}/{it.months}</td>
                            <td className="px-1 py-1 text-right tabular-nums font-semibold text-[#333]">{num(it.monthly_principal)}</td>
                            <td className="px-1 py-1 text-right tabular-nums" style={{ color: BLUE }}>{num(it.remaining)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <p className="mt-1 text-[10px] text-[#999]">{s.installments.fee_note}</p>
                  </div>
                </div>
              )}

              {/* 거래 목록 */}
              <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#d0d0d0] bg-[#f3f2f1] px-3 py-1.5">
                  <span className="text-xs font-bold text-[#217346]">
                    거래 내역 {listRows.length}건
                    <span className="ml-1 font-normal tabular-nums text-[#666]">{won(listTotal)}</span>
                    {pick ? ` · ${pick.value}` : ""}
                    {day ? ` · ${day}` : ""}
                  </span>
                  <div className="flex flex-wrap items-center gap-2">
                    {/* 카테고리·가맹점 필터 — 축 패널을 클릭하지 않고도 바로 좁힌다. */}
                    <select
                      value={cat}
                      onChange={(e) => setCat(e.target.value)}
                      className={`rounded border px-1 py-0.5 text-[11px] outline-none ${cat ? "border-[#217346] bg-[#eef6f0] text-[#217346]" : "border-[#cdcdcd] bg-white text-[#666]"}`}
                    >
                      <option value="">카테고리 전체</option>
                      {(s?.by_category ?? []).map((c) => (
                        <option key={c.category} value={c.category}>{c.category} ({c.count})</option>
                      ))}
                    </select>
                    <input
                      value={q}
                      onChange={(e) => setQ(e.target.value)}
                      placeholder="가맹점 검색"
                      className="w-24 rounded border border-[#cdcdcd] bg-white px-1.5 py-0.5 text-[11px] outline-none focus:border-[#217346] sm:w-32"
                    />
                    {(cat || q || day) && (
                      <button
                        onClick={() => { setCat(""); setQ(""); setDay(""); }}
                        className="rounded border border-[#cdcdcd] bg-white px-2 py-0.5 text-[11px] text-[#666] hover:bg-[#f5f5f5]"
                      >
                        필터 해제
                      </button>
                    )}
                    <div className="flex overflow-hidden rounded border border-[#cdcdcd]">
                      {([["list", "목록"], ["calendar", "캘린더"]] as const).map(([v, label]) => (
                        <button
                          key={v}
                          onClick={() => setView(v)}
                          className={`px-2 py-0.5 text-[11px] ${view === v ? "bg-[#217346] text-white" : "bg-white text-[#666] hover:bg-[#eef6f0]"}`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                    {s && monthValue && monthValue !== "all" && (
                      <button
                        onClick={async () => {
                          if (!confirm(`${monthValue} 내역을 전부 지울까요?`)) return;
                          await api.budgetClearMonth(monthValue, basis);
                          bump();
                        }}
                        className="text-[11px] text-[#bbb] hover:text-rose-500"
                      >
                        이 달 비우기
                      </button>
                    )}
                  </div>
                </div>
                {view === "calendar" && <CalendarView rows={rows} day={day} setDay={setDay} />}
                <div className={view === "calendar" ? "max-h-[40vh] overflow-auto border-t border-[#eee]" : "max-h-[70vh] overflow-auto"}>
                  {view === "calendar" && !day ? (
                    <div className="py-4 text-center text-[11px] text-[#aaa]">달력에서 날짜를 누르면 그날 내역이 여기 나옵니다.</div>
                  ) : (
                    <TxTable rows={listRows} categories={s?.categories ?? []} onChange={bump} />
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// --- 조각들 -----------------------------------------------------------------

function Cell({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="bg-white px-3 py-2">
      <div className="text-[10px] text-[#888]">{label}</div>
      <div className="text-sm font-bold tabular-nums" style={{ color: color ?? "#333" }}>{value}</div>
      {sub && <div className="text-[10px] text-[#aaa] tabular-nums">{sub}</div>}
    </div>
  );
}

function Mini({ label, value, color, className = "" }: { label: string; value: string; color?: string; className?: string }) {
  return (
    <div className={`rounded bg-[#fafafa] px-2 py-1.5 ${className}`}>
      <div className="text-[10px] text-[#888]">{label}</div>
      <div className="text-xs font-bold tabular-nums" style={{ color: color ?? "#333" }}>{value}</div>
    </div>
  );
}

function TypeBadge({ type }: { type: string }) {
  const tone: Record<string, string> = {
    할부: "border-[#d7e3ee] bg-[#f4f8fc] text-[#1b4f7a]",
    해외: "border-[#e9dcc4] bg-[#fdf8ee] text-[#8a6a1f]",
    취소: "border-[#e6d6d6] bg-[#fbf5f5] text-[#8a4a4a]",
    현금서비스: "border-[#e6d6e6] bg-[#faf5fa] text-[#6a3a6a]",
  };
  if (type === "일시불") return null;
  return <span className={`rounded border px-1 text-[10px] ${tone[type] ?? "border-[#e0e0e0] bg-[#fafafa] text-[#777]"}`}>{type}</span>;
}

// --- 고정지출 -----------------------------------------------------------------
// 구독·통신·공과금은 이번 달에 많이 썼다고 다음 달에 줄일 수 있는 돈이 아니다.
// 변동비와 같은 자리에 두면 '얼마를 줄일 수 있는가' 에 답할 수 없어서 따로 뺀다.

function FixedCosts({ board, onChange }: { board: FixedCostBoard; onChange: () => void }) {
  const [busy, setBusy] = useState("");
  const pin = async (merchant: string, on: boolean) => {
    setBusy(merchant);
    try { await api.budgetSetFixed(merchant, on ? true : false); onChange(); }
    finally { setBusy(""); }
  };

  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
        <span className="text-sm font-semibold">고정지출 (계속 나가는 돈)</span>
        <span className="text-xs tabular-nums">월 {won(board.monthly_total)}</span>
      </div>
      <div className="p-3">
        <div className="mb-2 grid grid-cols-3 gap-2 text-center">
          <Mini label="항목" value={`${board.count}개`} />
          <Mini label="월 합계" value={won(board.monthly_total)} color={RED} />
          <Mini label="연 환산" value={won(board.annual_total)} color={RED} />
        </div>

        {board.items.length === 0 ? (
          <div className="py-6 text-center text-[11px] text-[#aaa]">
            아직 고정지출로 잡힌 게 없습니다. 거래 목록에서 &lsquo;고정&rsquo; 을 눌러 지정할 수 있습니다.
          </div>
        ) : (
          <table className="w-full text-[11px]">
            <thead>
              <tr className="border-b border-[#eee] text-[10px] text-[#999]">
                <th className="px-1 py-1 text-left font-semibold">항목</th>
                <th className="px-1 py-1 text-left font-semibold">주기</th>
                <th className="px-1 py-1 text-right font-semibold">월</th>
                <th className="px-1 py-1 text-right font-semibold">연</th>
                <th className="px-1 py-1" />
              </tr>
            </thead>
            <tbody>
              {board.items.map((it) => (
                <tr key={it.key} className="border-b border-[#f5f5f5]">
                  <td className="px-1 py-1">
                    <div className="text-[#333]">{it.merchant}</div>
                    <div className="text-[10px] text-[#aaa]">
                      {it.category} · {it.source}
                      {it.count > 1 && ` · ${it.count}회`}
                      {it.spread_pct != null && it.count > 1 && ` · 편차 ${it.spread_pct}%`}
                    </div>
                  </td>
                  <td className="px-1 py-1 text-[10px] text-[#777]">
                    {it.cadence}
                    {it.next_expected && <div className="text-[#bbb]">다음 {it.next_expected.slice(5)}</div>}
                  </td>
                  <td className="px-1 py-1 text-right tabular-nums font-semibold text-[#333]">{num(it.monthly)}</td>
                  <td className="px-1 py-1 text-right tabular-nums text-[#888]">{num(it.annual)}</td>
                  <td className="px-1 py-1 text-right">
                    <button
                      onClick={() => pin(it.merchant, false)}
                      disabled={busy === it.merchant}
                      title="고정지출에서 빼기(변동비로)"
                      className="text-[10px] text-[#ccc] hover:text-rose-500 disabled:opacity-50"
                    >
                      제외
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {board.candidates.length > 0 && (
          <div className="mt-3 border-t border-[#eee] pt-2">
            <div className="mb-1 text-[10px] font-semibold text-[#999]">
              반복되지만 금액이 달라 변동비로 둔 것 — 고정지출이면 눌러서 옮기세요
            </div>
            <ul className="flex flex-col gap-0.5">
              {board.candidates.map((c) => (
                <li key={c.key} className="flex items-center justify-between gap-2 text-[11px]">
                  <span className="min-w-0 truncate text-[#666]">
                    {c.merchant}
                    <span className="ml-1 text-[10px] text-[#aaa]">
                      {c.count}회 · {num(c.min)}~{num(c.max)}
                    </span>
                  </span>
                  <button
                    onClick={() => pin(c.merchant, true)}
                    disabled={busy === c.merchant}
                    className="shrink-0 rounded border border-[#cdcdcd] px-1.5 py-0.5 text-[10px] text-[#217346] hover:bg-[#eef6f0] disabled:opacity-50"
                  >
                    고정지출로
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <p className="mt-2 text-[10px] leading-relaxed text-[#aaa]">{board.note}</p>
      </div>
    </div>
  );
}

// --- 카드별 결제일·이용기간 ---------------------------------------------------
// 이건 자동으로 알아낼 수 없다. 카드사 파일에 안 적혀 있고, '결제일이 종료일보다
// 뒤면 당월' 같은 규칙도 실제와 맞지 않는다(7/18~8/18 이용분을 9월에 받는 카드가 있다).
// 그래서 네 값을 직접 받고, 그 설정이 만들어내는 실제 기간을 날짜로 되돌려 보여준다.

const DAY_OPTIONS = [0, ...Array.from({ length: 31 }, (_, i) => i + 1)];
const dayLabel = (v: number) => (v === 0 ? "말일" : `${v}일`);
const OFFSETS: [number, string][] = [[0, "당월"], [1, "익월"], [2, "다다음달"]];

function CardCycles({ data, onSaved }: { data: BudgetCardsOverview; onSaved: () => void }) {
  const [open, setOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");

  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
        <span className="text-sm font-semibold">카드 결제일·이용기간</span>
        <button
          onClick={async () => {
            setBusy("all");
            try {
              const r = await api.budgetRecalc();
              setMsg(r.note ?? `${r.changed}건의 청구월을 다시 계산했습니다.`);
              onSaved();
            } finally { setBusy(""); }
          }}
          disabled={!!busy}
          className="rounded bg-white/20 px-2 py-0.5 text-xs hover:bg-white/30 disabled:opacity-50"
        >
          {busy === "all" ? "계산 중…" : "전체 다시 계산"}
        </button>
      </div>
      <div className="p-3">
        <p className="mb-2 text-[11px] leading-relaxed text-[#666]">
          카드마다 결제일과 이용기간이 다릅니다. 등록해 두면 거래일에서 청구월을 자동으로
          계산합니다 — 할부는 거래일이 아니라 <b>회차</b> 기준입니다.
        </p>
        <ul className="flex flex-col gap-1.5">
          {data.cards.map((c) => (
            <CardCycleRow
              key={c.card}
              card={c}
              defaults={data.defaults}
              open={open === c.card}
              onToggle={() => setOpen(open === c.card ? null : c.card)}
              onSaved={(m) => { setMsg(m); onSaved(); }}
            />
          ))}
        </ul>
        {msg && <div className="mt-2 rounded bg-[#f4faf6] px-2 py-1 text-[11px] text-[#2c6b47]">{msg}</div>}
      </div>
    </div>
  );
}

function CardCycleRow({
  card, defaults, open, onToggle, onSaved,
}: {
  card: BudgetCard;
  defaults: CardCycle;
  open: boolean;
  onToggle: () => void;
  onSaved: (msg: string) => void;
}) {
  const [cfg, setCfg] = useState<CardCycle>(card.configured ? card.cycle : defaults);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof CardCycle, v: number) => setCfg({ ...cfg, [k]: v });

  const save = async (recalc: boolean) => {
    setBusy(true);
    try {
      await api.budgetSetCycle(card.card, cfg);
      const r = recalc ? await api.budgetRecalc(card.card) : { changed: 0 };
      onSaved(`${card.card} 저장${recalc ? ` · ${r.changed}건 청구월 재계산` : ""}`);
    } finally { setBusy(false); }
  };

  return (
    <li className="rounded border border-[#e8e8e8]">
      <button onClick={onToggle} className="flex w-full items-center justify-between gap-2 px-2 py-1.5 text-left hover:bg-[#fafafa]">
        <span className="min-w-0">
          <span className="text-[11px] font-semibold text-[#333]">{card.card}</span>
          <span className="ml-1 text-[10px] text-[#aaa]">{card.count}건 · {won(card.amount)}</span>
          <span className="block truncate text-[10px] text-[#888]">
            {card.configured
              ? `${card.describe}${card.window.start ? ` · ${card.billing_month} 청구분 = ${card.window.start} ~ ${card.window.end}` : ""}`
              : "설정 없음 — 청구월을 파일값/추정치로 씁니다"}
          </span>
        </span>
        <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] ${card.configured ? "bg-[#eef6f0] text-[#217346]" : "bg-[#fff3cd] text-[#8a6a1f]"}`}>
          {open ? "닫기" : card.configured ? "수정" : "설정"}
        </span>
      </button>

      {open && (
        <div className="border-t border-[#eee] bg-[#fbfbfb] p-2">
          <div className="flex flex-wrap items-end gap-2">
            <label className="text-[10px] text-[#666]">
              이용 시작
              <select value={cfg.cycle_start_day} onChange={(e) => set("cycle_start_day", Number(e.target.value))}
                className="mt-0.5 block rounded border border-[#cdcdcd] px-1 py-0.5 text-[11px]">
                {DAY_OPTIONS.map((d) => <option key={d} value={d}>{dayLabel(d)}</option>)}
              </select>
            </label>
            <label className="text-[10px] text-[#666]">
              이용 종료
              <select value={cfg.cycle_end_day} onChange={(e) => set("cycle_end_day", Number(e.target.value))}
                className="mt-0.5 block rounded border border-[#cdcdcd] px-1 py-0.5 text-[11px]">
                {DAY_OPTIONS.map((d) => <option key={d} value={d}>{dayLabel(d)}</option>)}
              </select>
            </label>
            <label className="text-[10px] text-[#666]">
              결제
              <select value={cfg.pay_offset} onChange={(e) => set("pay_offset", Number(e.target.value))}
                className="mt-0.5 block rounded border border-[#cdcdcd] px-1 py-0.5 text-[11px]">
                {OFFSETS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <label className="text-[10px] text-[#666]">
              결제일
              <select value={cfg.pay_day} onChange={(e) => set("pay_day", Number(e.target.value))}
                className="mt-0.5 block rounded border border-[#cdcdcd] px-1 py-0.5 text-[11px]">
                {DAY_OPTIONS.map((d) => <option key={d} value={d}>{dayLabel(d)}</option>)}
              </select>
            </label>
          </div>

          <CyclePreview cfg={cfg} month={card.billing_month} />

          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button onClick={() => save(true)} disabled={busy}
              className="rounded bg-[#217346] px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-[#1b5e3a] disabled:opacity-50">
              {busy ? "저장 중…" : "저장하고 청구월 다시 계산"}
            </button>
            <button onClick={() => save(false)} disabled={busy}
              className="rounded border border-[#cdcdcd] bg-white px-2.5 py-1 text-[11px] text-[#666] hover:bg-[#f5f5f5] disabled:opacity-50">
              설정만 저장
            </button>
            {card.configured && (
              <button
                onClick={async () => { setBusy(true); try { await api.budgetClearCycle(card.card); onSaved(`${card.card} 설정 해제`); } finally { setBusy(false); } }}
                disabled={busy}
                className="text-[11px] text-[#bbb] hover:text-rose-500"
              >
                설정 해제
              </button>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

/** 설정이 만들어내는 실제 기간을 브라우저에서 그대로 계산해 보여준다(저장 전 확인용). */
function CyclePreview({ cfg, month }: { cfg: CardCycle; month: string }) {
  const rows = useMemo(() => {
    const base = month || new Date().toISOString().slice(0, 7);
    const [by, bm] = base.split("-").map(Number);
    const dayIn = (y: number, m: number, d: number) => {
      const last = new Date(y, m, 0).getDate();
      return !d || d > last ? last : d;
    };
    const shift = (y: number, m: number, n: number) => {
      const t = y * 12 + (m - 1) + n;
      return [Math.floor(t / 12), (t % 12) + 1] as const;
    };
    const at = (y: number, m: number, d: number) => new Date(y, m - 1, dayIn(y, m, d));
    const spans = (cfg.cycle_start_day || 32) >= (cfg.cycle_end_day || 32);
    const iso = (d: Date) =>
      `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

    return [0, 1, 2].map((k) => {
      const [py, pm] = shift(by, bm, k);                       // 청구월
      const [ey, em] = shift(py, pm, -cfg.pay_offset);         // 이용기간이 끝나는 달
      const [sy, sm] = spans ? shift(ey, em, -1) : [ey, em];
      const start = at(sy, sm, cfg.cycle_start_day);
      const [ny, nm] = shift(ey, em, 1);
      const [nsy, nsm] = spans ? [ey, em] : [ny, nm];
      const nextStart = at(nsy, nsm, cfg.cycle_start_day);
      // 다음 주기 시작 전날까지 — 시작·종료를 같은 날로 넣으면 하루 겹치기 때문.
      const rawEnd = at(ey, em, cfg.cycle_end_day);
      const capped = new Date(nextStart.getTime() - 86400000);
      const end = rawEnd < capped ? rawEnd : capped;
      return {
        month: `${py}-${String(pm).padStart(2, "0")}`,
        start: iso(start), end: iso(end), pay: iso(at(py, pm, cfg.pay_day)),
      };
    });
  }, [cfg, month]);

  return (
    <div className="mt-2 rounded border border-[#dbe9e0] bg-[#f6faf7] p-1.5">
      <div className="mb-0.5 text-[10px] font-semibold text-[#2c6b47]">이 설정이면 이렇게 됩니다</div>
      <table className="w-full text-[10px] tabular-nums">
        <tbody>
          {rows.map((r) => (
            <tr key={r.month}>
              <td className="py-0.5 pr-2 font-semibold text-[#217346]">{r.month} 청구분</td>
              <td className="py-0.5 text-[#555]">{r.start} ~ {r.end} 이용</td>
              <td className="py-0.5 pl-2 text-right text-[#1b4f7a]">{r.pay} 결제</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// --- 캘린더 ------------------------------------------------------------------
// 청구월이 아니라 **거래일** 로 그린다. '언제 얼마나 썼나' 는 카드값이 빠지는 달이
// 아니라 긁은 날의 이야기라서다. 그래서 9월 청구분을 보고 있어도 달력은 7·8월이 뜬다.

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

/** 만 원 단위로 줄여 칸 안에 들어가게. 12,300 → 1.2만 */
function compact(v: number): string {
  if (!v) return "";
  if (v >= 10000) {
    const man = v / 10000;
    return `${man >= 100 ? Math.round(man) : man.toFixed(1).replace(/\.0$/, "")}만`;
  }
  return `${Math.round(v / 1000)}천`;
}

function CalendarView({
  rows, day, setDay,
}: {
  rows: BudgetTx[];
  day: string;
  setDay: (d: string) => void;
}) {
  const months = useMemo(() => {
    const byDay = new Map<string, { amount: number; count: number }>();
    for (const t of rows) {
      if (!t.date || t.amount <= 0) continue;
      const cur = byDay.get(t.date) ?? { amount: 0, count: 0 };
      cur.amount += t.amount;
      cur.count += 1;
      byDay.set(t.date, cur);
    }
    const keys = [...new Set([...byDay.keys()].map((d) => d.slice(0, 7)))].sort().reverse();
    const max = Math.max(1, ...[...byDay.values()].map((v) => v.amount));

    return keys.map((ym) => {
      const [y, m] = ym.split("-").map(Number);
      // Date 는 로컬 타임존 기준이라 UTC 로 만들면 하루가 밀린다 — 로컬 생성자를 쓴다.
      const first = new Date(y, m - 1, 1);
      const lastDate = new Date(y, m, 0).getDate();
      const cells: ({ date: string; dom: number; amount: number; count: number } | null)[] = [];
      for (let i = 0; i < first.getDay(); i++) cells.push(null);
      for (let dnum = 1; dnum <= lastDate; dnum++) {
        const date = `${ym}-${String(dnum).padStart(2, "0")}`;
        const hit = byDay.get(date);
        cells.push({ date, dom: dnum, amount: hit?.amount ?? 0, count: hit?.count ?? 0 });
      }
      while (cells.length % 7) cells.push(null);
      const weeks: typeof cells[] = [];
      for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
      const total = cells.reduce((a, c) => a + (c?.amount ?? 0), 0);
      return { ym, weeks, total, max };
    });
  }, [rows]);

  if (!months.length) {
    return <div className="py-10 text-center text-xs text-[#aaa]">그릴 거래가 없습니다.</div>;
  }

  return (
    <div className="flex flex-col gap-4 p-3">
      {months.map(({ ym, weeks, total, max }) => (
        <div key={ym}>
          <div className="mb-1 flex items-baseline justify-between">
            <span className="text-xs font-bold text-[#217346]">{ym.replace("-", "년 ")}월</span>
            <span className="text-[11px] tabular-nums text-[#666]">{won(total)}</span>
          </div>
          <table className="w-full table-fixed border-collapse text-[10px]">
            <thead>
              <tr>
                {WEEKDAYS.map((w, i) => (
                  <th key={w} className={`border border-[#e8e8e8] bg-[#f7f7f7] py-0.5 font-semibold ${i === 0 ? "text-[#c92a2a]" : i === 6 ? "text-[#1971c2]" : "text-[#888]"}`}>
                    {w}
                  </th>
                ))}
                <th className="w-[15%] border border-[#e8e8e8] bg-[#eef4f0] py-0.5 font-semibold text-[#217346]">주계</th>
              </tr>
            </thead>
            <tbody>
              {weeks.map((week, wi) => {
                const weekTotal = week.reduce((a, c) => a + (c?.amount ?? 0), 0);
                return (
                  <tr key={wi}>
                    {week.map((c, ci) => {
                      if (!c) return <td key={ci} className="h-12 border border-[#f0f0f0] bg-[#fbfbfb]" />;
                      const on = day === c.date;
                      // 금액이 클수록 진하게 — 제곱근이라 소액 지출도 눈에 보인다.
                      const heat = c.amount ? Math.min(1, Math.sqrt(c.amount / max)) : 0;
                      return (
                        <td
                          key={ci}
                          onClick={() => c.amount && setDay(on ? "" : c.date)}
                          title={c.amount ? `${c.date} · ${c.count}건 · ${won(c.amount)}` : c.date}
                          className={`h-12 border align-top ${c.amount ? "cursor-pointer" : ""} ${
                            on ? "border-[#217346] ring-1 ring-[#217346]" : "border-[#f0f0f0]"
                          }`}
                          style={{ background: heat ? `rgba(33,115,70,${0.08 + heat * 0.42})` : undefined }}
                        >
                          <div className={`px-1 pt-0.5 ${ci === 0 ? "text-[#c92a2a]" : ci === 6 ? "text-[#1971c2]" : "text-[#999]"}`}>
                            {c.dom}
                          </div>
                          {c.amount > 0 && (
                            <div className={`px-1 text-right font-bold tabular-nums ${heat > 0.55 ? "text-white" : "text-[#1f1f1f]"}`}>
                              {compact(c.amount)}
                            </div>
                          )}
                        </td>
                      );
                    })}
                    <td className="border border-[#e8e8e8] bg-[#f6faf7] px-1 text-right align-middle tabular-nums text-[#217346]">
                      {weekTotal ? compact(weekTotal) : ""}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

function TxTable({ rows, categories, onChange }: { rows: BudgetTx[]; categories: string[]; onChange: () => void }) {
  if (!rows.length) {
    return <div className="py-10 text-center text-xs text-[#aaa]">해당하는 거래가 없습니다.</div>;
  }
  return (
    <table className="w-full text-[11px]">
      <thead className="sticky top-0 z-10 bg-[#f7f7f7] text-[10px] text-[#999]">
        <tr>
          <th className="px-2 py-1 text-left font-semibold">거래일</th>
          <th className="px-2 py-1 text-left font-semibold">가맹점</th>
          <th className="px-1 py-1 text-left font-semibold">고정</th>
          <th className="px-2 py-1 text-left font-semibold">분류</th>
          <th className="px-2 py-1 text-right font-semibold">금액</th>
          <th className="px-2 py-1 text-right font-semibold">할부 잔여</th>
          <th className="px-1 py-1" />
        </tr>
      </thead>
      <tbody>
        {rows.map((t) => (
          // 예정분은 저장된 거래가 아니라 계산 결과다 — 편집할 게 없으니 컨트롤을 빼고
          // 배경으로 구분한다. id 가 0 이라 key 는 지문을 쓴다.
          <tr key={t.projected ? t.fp : t.id} className={`border-t border-[#f5f5f5] ${t.projected ? "bg-[#f7f9fc]" : "hover:bg-[#fafafa]"}`}>
            <td className="whitespace-nowrap px-2 py-1 text-[#999]">
              {t.projected ? (t.date ? t.date.slice(5) : "—") : t.date?.slice(5)}
            </td>
            <td className="px-2 py-1 text-[#333]">
              <div className="flex flex-wrap items-center gap-1">
                <span className={t.projected ? "text-[#556]" : undefined}>{t.merchant}</span>
                {t.projected && (
                  <span className="rounded border border-[#d7e3ee] bg-[#eaf2fa] px-1 text-[10px] text-[#1b4f7a]">예정</span>
                )}
                <TypeBadge type={t.tx_type} />
                {t.installment && t.installment.months > 1 && (
                  <span className="text-[10px] text-[#888]" title={`전액 ${won(t.total)}${t.installment.remaining ? ` · 잔액 ${won(t.installment.remaining)}` : ""}`}>
                    {t.installment.seq}/{t.installment.months}회차
                  </span>
                )}
                {t.fee > 0 && <span className="text-[10px] text-[#aa8]">수수료 {num(t.fee)}</span>}
              </div>
              <div className="text-[10px] text-[#bbb]">
                {t.projected ? `${t.card}${t.date ? "" : " · 결제일은 카드 설정을 넣으면 표시됩니다"}` : [t.issuer, t.card].filter(Boolean).join(" ")}
              </div>
            </td>
            <td className="px-1 py-1">
              {!t.projected && (
                <button
                  onClick={async () => { await api.budgetSetFixed(t.merchant, !t.fixed); onChange(); }}
                  title={t.fixed ? "고정비로 잡힘 — 눌러서 변동비로" : "변동비 — 눌러서 고정비로"}
                  className={`rounded border px-1 text-[10px] ${t.fixed ? "border-[#dbe9e0] bg-[#f4faf6] text-[#2c6b47]" : "border-[#e8e8e8] text-[#bbb] hover:text-[#666]"}`}
                >
                  {t.fixed ? "고정" : "변동"}
                </button>
              )}
            </td>
            <td className="px-2 py-1">
              {t.projected ? (
                <span className="text-[10px] text-[#999]">{t.category}</span>
              ) : (
                <select
                  value={t.category}
                  onChange={async (e) => { await api.budgetSetCategory(t.id, e.target.value, true); onChange(); }}
                  className={`rounded border px-1 py-0.5 text-[10px] outline-none focus:border-[#217346] ${
                    t.category === "기타" ? "border-[#e6b0b0] bg-[#fdf3f3] text-[#a55]" : "border-[#e0e0e0] text-[#666]"
                  }`}
                >
                  {categories.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              )}
            </td>
            <td className="px-2 py-1 text-right tabular-nums font-semibold" style={{ color: t.amount < 0 ? BLUE : t.projected ? "#1b4f7a" : "#333" }}>
              {won(t.amount)}
              {t.total !== t.charged && (
                <div className="text-[10px] font-normal text-[#bbb]">전액 {num(t.total)}</div>
              )}
            </td>
            {/* 할부 잔여 — 이 건이 앞으로 얼마나 더 나갈지. 일시불은 빈 칸으로 둔다. */}
            <td className="whitespace-nowrap px-2 py-1 text-right tabular-nums">
              {t.installment && t.installment.months > 1 ? (
                t.installment.remaining > 0 ? (
                  <>
                    <div className="font-semibold" style={{ color: BLUE }}>{num(t.installment.remaining)}</div>
                    <div className="text-[10px] text-[#aaa]">{t.installment.months - t.installment.seq}회 남음</div>
                  </>
                ) : (
                  <span className="text-[10px] text-[#ccc]">
                    {t.installment.seq >= t.installment.months ? "완납" : "잔액 미상"}
                  </span>
                )
              ) : (
                <span className="text-[#e8e8e8]">·</span>
              )}
            </td>
            <td className="px-1 py-1 text-right">
              {!t.projected && (
                <button onClick={async () => { await api.budgetDelete(t.id); onChange(); }} className="text-[#ccc] hover:text-rose-500">
                  삭제
                </button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function PreviewPanel({
  rep, chosen, setChosen, billMonth, setBillMonth, onCancel, onCommit, busy,
}: {
  rep: CardStatementPreview;
  chosen: Set<string>;
  setChosen: (s: Set<string>) => void;
  billMonth: string;
  setBillMonth: (m: string) => void;
  onCancel: () => void;
  onCommit: () => void;
  busy: boolean;
}) {
  const toggle = (fp: string) => {
    const next = new Set(chosen);
    if (next.has(fp)) next.delete(fp); else next.add(fp);
    setChosen(next);
  };
  const picked = rep.transactions.filter((t) => chosen.has(t.fp));
  const pickedSum = picked.reduce((a, t) => a + (t.amount > 0 ? t.amount : 0), 0);
  const guessed = rep.parsed_by === "generic" || rep.parsed_by === "loose";

  return (
    <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 bg-[#217346] px-4 py-2 text-white">
        <span className="text-sm font-semibold">확인 후 등록 — {rep.issuer || "카드사 미상"}</span>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1 text-xs">
            청구월
            <input
              type="month"
              value={billMonth}
              onChange={(e) => setBillMonth(e.target.value)}
              className={`rounded px-1.5 py-0.5 text-xs text-[#1f1f1f] outline-none ${
                rep.billing_month_known ? "bg-white/90" : "bg-[#fff3cd] ring-1 ring-[#e0a34e]"
              }`}
            />
          </label>
          <button onClick={onCancel} className="rounded bg-white/20 px-2 py-0.5 text-xs hover:bg-white/30">취소</button>
          <button
            onClick={onCommit}
            disabled={busy || !picked.length || !billMonth}
            className="rounded bg-white px-3 py-0.5 text-xs font-semibold text-[#217346] hover:bg-[#eef6f0] disabled:opacity-50"
          >
            {busy ? "등록 중…" : `${picked.length}건 등록`}
          </button>
        </div>
      </div>

      <div className="border-b border-[#eee] bg-[#fafafa] px-3 py-2">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Mini label="읽은 건수" value={`${rep.stats.count}건`} />
          <Mini label="이 달 청구 합계" value={won(rep.stats.spend)} color={RED} />
          <Mini label="거래 전액 합계" value={won(rep.stats.total_amount)} />
          <Mini label="수수료" value={won(rep.stats.fee)} />
        </div>
        <div className="mt-1.5 flex flex-wrap gap-1 text-[10px]">
          {rep.stats.by_tx_type.map((b) => (
            <span key={b.tx_type} className="rounded border border-[#e0e0e0] bg-white px-1.5 py-0.5 text-[#666]">
              {b.tx_type} {num(b.amount)}
            </span>
          ))}
          {rep.stats.by_card.map((b) => (
            <span key={b.card} className="rounded border border-[#dbe9e0] bg-[#f4faf6] px-1.5 py-0.5 text-[#2c6b47]">
              {b.card} {num(b.amount)}
            </span>
          ))}
          <span className="rounded border border-[#e0e0e0] bg-white px-1.5 py-0.5 text-[#999]">
            {rep.stats.date_range[0]} ~ {rep.stats.date_range[1]} · {rep.file_kind}
          </span>
        </div>
        <p className={`mt-1.5 text-[11px] ${guessed ? "text-[#8a6a1f]" : "text-[#456]"}`}>{rep.note}</p>
        {picked.length !== rep.transactions.length && (
          <p className="text-[11px] text-[#456]">선택한 {picked.length}건 합계 {won(pickedSum)}</p>
        )}
      </div>

      <div className="max-h-[60vh] overflow-auto">
        <table className="w-full text-[11px]">
          <thead className="sticky top-0 bg-[#f3f2f1] text-[10px] text-[#888]">
            <tr>
              <th className="px-2 py-1 text-left font-semibold">
                <input
                  type="checkbox"
                  checked={chosen.size === rep.transactions.length && rep.transactions.length > 0}
                  onChange={(e) => setChosen(e.target.checked ? new Set(rep.transactions.map((t) => t.fp)) : new Set())}
                />
              </th>
              <th className="px-2 py-1 text-left font-semibold">거래일</th>
              <th className="px-2 py-1 text-left font-semibold">가맹점</th>
              <th className="px-2 py-1 text-left font-semibold">분류</th>
              <th className="px-2 py-1 text-right font-semibold">이 달 청구</th>
              <th className="px-2 py-1 text-right font-semibold">거래 전액</th>
            </tr>
          </thead>
          <tbody>
            {rep.transactions.map((t) => (
              <tr key={t.fp} className={`border-t border-[#f5f5f5] ${chosen.has(t.fp) ? "" : "opacity-40"}`}>
                <td className="px-2 py-1">
                  <input type="checkbox" checked={chosen.has(t.fp)} onChange={() => toggle(t.fp)} />
                </td>
                <td className="whitespace-nowrap px-2 py-1 text-[#999]">{t.date}</td>
                <td className="px-2 py-1 text-[#333]">
                  <div className="flex flex-wrap items-center gap-1">
                    <span>{t.merchant}</span>
                    <TypeBadge type={t.tx_type} />
                    {t.installment && t.installment.months > 1 && (
                      <span className="text-[10px] text-[#888]">{t.installment.seq}/{t.installment.months}회차</span>
                    )}
                    {t.fee > 0 && <span className="text-[10px] text-[#aa8]">수수료 {num(t.fee)}</span>}
                  </div>
                </td>
                <td className="px-2 py-1 text-[#777]">{t.category}</td>
                <td className="px-2 py-1 text-right tabular-nums font-semibold text-[#333]">{num(t.amount)}</td>
                <td className="px-2 py-1 text-right tabular-nums text-[#bbb]">{num(t.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
