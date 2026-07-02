"use client";

import { useEffect, useState } from "react";
import { api, BudgetSummary, BudgetPlan } from "@/lib/api";

const RED = "#c92a2a";
const GREEN = "#2f9e44";

function won(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${Math.round(v).toLocaleString("ko-KR")}원`;
}
const CAT_COLORS = ["#217346", "#4c9a6a", "#e0a34e", "#c96f6f", "#6f8fc9", "#9a7fc9", "#c99f6f", "#7fc9b0", "#c97f9f", "#8a8a8a"];

// 한글 카드 CSV는 EUC-KR인 경우가 많다 → UTF-8 시도 후 깨지면 EUC-KR로 재해석.
async function fileToText(file: File): Promise<string> {
  const buf = await file.arrayBuffer();
  const utf8 = new TextDecoder("utf-8", { fatal: false }).decode(buf);
  if (utf8.includes("�")) {
    try { return new TextDecoder("euc-kr").decode(buf); } catch { return utf8; }
  }
  return utf8;
}

export function BudgetManager() {
  const [sum, setSum] = useState<BudgetSummary | null>(null);
  const [plan, setPlan] = useState<BudgetPlan | null>(null);
  const [month, setMonth] = useState<string | undefined>(undefined);
  const [net, setNet] = useState("");
  const [extra, setExtra] = useState("");
  const [csv, setCsv] = useState("");
  const [busy, setBusy] = useState("");
  const [payMsg, setPayMsg] = useState("");
  const [emMonths, setEmMonths] = useState(3);
  const [investRatio, setInvestRatio] = useState(0.5);

  const loadSummary = (m?: string) => api.budgetSummary(m).then((r) => {
    setSum(r); setMonth(r.month);
    if (net === "" && r.income.monthly_net) setNet(String(r.income.monthly_net));
    if (extra === "" && r.income.extra) setExtra(String(r.income.extra));
  }).catch(() => {});
  const loadPlan = () => api.budgetPlan(emMonths, investRatio).then(setPlan).catch(() => {});

  useEffect(() => { loadSummary(); }, []);
  useEffect(() => { loadPlan(); /* eslint-disable-next-line */ }, [emMonths, investRatio, sum?.count]);

  const saveIncome = () => {
    setBusy("income");
    api.budgetSetIncome(Number(net) || 0, Number(extra) || 0)
      .then(() => loadSummary(month)).finally(() => setBusy(""));
  };
  const importCsv = () => {
    if (!csv.trim()) return;
    setBusy("import");
    api.budgetImport(csv)
      .then((r) => { setCsv(""); loadSummary(); alert(`${r.parsed}건 등록됨`); })
      .catch(() => alert("파싱 실패 — 날짜가 포함된 카드내역 형식인지 확인하세요."))
      .finally(() => setBusy(""));
  };
  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const name = f.name.toLowerCase();
    // 엑셀은 서버에서 헤더 인식 파싱, 텍스트/CSV는 미리보기로 붙여넣기
    if (name.endsWith(".xlsx") || name.endsWith(".xls")) {
      setBusy("import");
      try {
        const r = await api.budgetImportFile(f);
        loadSummary();
        alert(`${r.parsed}건 등록됨 (카드 엑셀 자동 인식)`);
      } catch {
        alert("엑셀을 읽지 못했습니다. 카드사에서 받은 원본 엑셀인지 확인하세요.");
      } finally {
        setBusy("");
        e.target.value = "";
      }
    } else {
      setCsv(await fileToText(f));
      e.target.value = "";
    }
  };
  const onPayslip = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setBusy("payslip"); setPayMsg("");
    try {
      const r = await api.budgetParsePayslip(f);
      if (r.net != null) {
        setNet(String(r.net));
        const parts = [`실수령액 ${won(r.net)} 인식`];
        if (r.gross != null) parts.push(`지급 ${won(r.gross)}`);
        if (r.deduction != null) parts.push(`공제 ${won(r.deduction)}`);
        setPayMsg((r.guessed ? "⚠ 추정: " : "✓ ") + parts.join(" · ") + " — 확인 후 저장하세요");
      } else {
        setPayMsg("금액을 찾지 못했습니다. 직접 입력해 주세요.");
      }
    } catch {
      setPayMsg("명세서를 읽지 못했습니다 (지원: .xlsx/.xls/.pdf/.csv).");
    } finally {
      setBusy("");
      e.target.value = "";
    }
  };
  const del = (id: number) => api.budgetDelete(id).then(() => loadSummary(month)).catch(() => {});
  const setCat = (id: number, category: string) =>
    api.budgetSetCategory(id, category, true).then(() => loadSummary(month)).catch(() => {});

  const s = sum;
  const maxCat = s?.by_category[0]?.amount || 1;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {/* ── 좌: 수입·카드내역 입력 ─────────────────── */}
      <div className="flex flex-col gap-4">
        {/* 급여 */}
        <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
          <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
            <span className="text-sm font-semibold">급여·수입.xlsx</span>
            <label className="cursor-pointer rounded bg-white/20 px-2 py-0.5 text-xs hover:bg-white/30">
              {busy === "payslip" ? "인식 중…" : "명세서 올리기(엑셀/PDF)"}
              <input type="file" accept=".xlsx,.xls,.pdf,.csv" className="hidden" onChange={onPayslip} disabled={busy === "payslip"} />
            </label>
          </div>
          <div className="flex flex-wrap items-end gap-2 p-3">
            <label className="text-xs text-[#555]">
              월 실수령액
              <input value={net} onChange={(e) => setNet(e.target.value)} inputMode="numeric" placeholder="3,000,000"
                className="mt-0.5 block w-36 rounded border border-[#cdcdcd] px-2 py-1 text-right text-sm outline-none focus:border-[#217346]" />
            </label>
            <label className="text-xs text-[#555]">
              기타 수입(월)
              <input value={extra} onChange={(e) => setExtra(e.target.value)} inputMode="numeric" placeholder="0"
                className="mt-0.5 block w-28 rounded border border-[#cdcdcd] px-2 py-1 text-right text-sm outline-none focus:border-[#217346]" />
            </label>
            <button onClick={saveIncome} disabled={busy === "income"}
              className="rounded bg-[#217346] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#1b5e3a] disabled:opacity-50">
              {busy === "income" ? "저장 중…" : "저장"}
            </button>
          </div>
          {payMsg && (
            <div className="border-t border-[#eee] bg-[#f7faf8] px-3 py-1.5 text-[11px] text-[#456]">{payMsg}</div>
          )}
        </div>

        {/* 카드내역 업로드 */}
        <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
          <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
            <span className="text-sm font-semibold">카드내역 올리기</span>
            <label className="cursor-pointer rounded bg-white/20 px-2 py-0.5 text-xs hover:bg-white/30">
              {busy === "import" ? "인식 중…" : "엑셀/CSV 파일 선택"}
              <input type="file" accept=".csv,.txt,.xlsx,.xls" className="hidden" onChange={onFile} disabled={busy === "import"} />
            </label>
          </div>
          <div className="p-3">
            <textarea value={csv} onChange={(e) => setCsv(e.target.value)} rows={5}
              placeholder={"카드사에서 받은 내역(CSV/표)을 붙여넣으세요.\n예) 2026-07-02,스타벅스강남,5,600\n2026-07-01,GS25,12,300"}
              className="w-full resize-y rounded border border-[#cdcdcd] p-2 font-mono text-[11px] outline-none focus:border-[#217346]" />
            <div className="mt-2 flex items-center gap-2">
              <button onClick={importCsv} disabled={busy === "import" || !csv.trim()}
                className="rounded bg-[#217346] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#1b5e3a] disabled:opacity-50">
                {busy === "import" ? "등록 중…" : "내역 등록"}
              </button>
              <span className="text-[10px] text-[#999]">날짜·가맹점·금액을 자동 인식하고 카테고리를 분류합니다.</span>
            </div>
          </div>
        </div>

        {/* 저축·투자 계획 */}
        <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
          <div className="bg-[#217346] px-4 py-2 text-sm font-semibold text-white">저축·투자 계획</div>
          <div className="p-3">
            <div className="mb-2 flex flex-wrap items-center gap-3 text-xs text-[#555]">
              <label className="flex items-center gap-1">비상금
                <select value={emMonths} onChange={(e) => setEmMonths(Number(e.target.value))}
                  className="rounded border border-[#cdcdcd] px-1 py-0.5">
                  {[3, 6, 9, 12].map((n) => <option key={n} value={n}>{n}개월</option>)}
                </select>
              </label>
              <label className="flex items-center gap-1">투자 비중
                <select value={investRatio} onChange={(e) => setInvestRatio(Number(e.target.value))}
                  className="rounded border border-[#cdcdcd] px-1 py-0.5">
                  {[0.3, 0.5, 0.7].map((n) => <option key={n} value={n}>{Math.round(n * 100)}%</option>)}
                </select>
              </label>
            </div>
            {plan && (
              <>
                <div className="mb-2 grid grid-cols-3 gap-2 text-center">
                  <div className="rounded bg-[#fafafa] px-2 py-1.5">
                    <div className="text-[10px] text-[#888]">월 여유자금</div>
                    <div className="text-xs font-bold tabular-nums" style={{ color: plan.surplus >= 0 ? GREEN : RED }}>{won(plan.surplus)}</div>
                  </div>
                  <div className="rounded bg-[#fafafa] px-2 py-1.5">
                    <div className="text-[10px] text-[#888]">비상금 목표</div>
                    <div className="text-xs font-bold tabular-nums text-[#333]">{won(plan.emergency_target)}</div>
                  </div>
                  <div className="rounded bg-[#fafafa] px-2 py-1.5">
                    <div className="text-[10px] text-[#888]">보유 주식</div>
                    <div className="text-xs font-bold tabular-nums text-[#333]">{won(plan.stock_value)}</div>
                  </div>
                </div>
                <div className="mb-2 flex gap-2 text-center text-xs">
                  <div className="flex-1 rounded bg-[#eef4f0] px-2 py-1.5">
                    <div className="text-[10px] text-[#888]">매월 안전저축</div>
                    <div className="font-bold text-[#217346]">{won(plan.monthly_save)}</div>
                  </div>
                  <div className="flex-1 rounded bg-[#eef4f0] px-2 py-1.5">
                    <div className="text-[10px] text-[#888]">매월 투자</div>
                    <div className="font-bold text-[#217346]">{won(plan.monthly_invest)}</div>
                  </div>
                </div>
                <ul className="flex flex-col gap-1 rounded border border-[#f0e6c9] bg-[#fdfaf0] p-2 text-[11px] leading-relaxed text-[#7a5f10]">
                  {plan.steps.map((v, i) => <li key={i}>• {v}</li>)}
                </ul>
              </>
            )}
          </div>
        </div>
      </div>

      {/* ── 우: 월별 지출 요약 ─────────────────────── */}
      <div className="overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm">
        <div className="flex items-center justify-between bg-[#217346] px-4 py-2 text-white">
          <span className="text-sm font-semibold">이번 달 지출.xlsx</span>
          {s && s.months.length > 0 && (
            <select value={month} onChange={(e) => { setMonth(e.target.value); loadSummary(e.target.value); }}
              className="rounded bg-white/20 px-1.5 py-0.5 text-xs text-white outline-none">
              {s.months.map((m) => <option key={m} value={m} className="text-black">{m}</option>)}
            </select>
          )}
        </div>

        {!s ? (
          <div className="py-16 text-center text-sm text-[#888]">불러오는 중…</div>
        ) : (
          <div className="max-h-[calc(100vh-210px)] overflow-auto p-3">
            {/* 요약 카드 */}
            <div className="mb-3 grid grid-cols-3 gap-2 text-center">
              <div className="rounded bg-[#fafafa] px-2 py-2">
                <div className="text-[10px] text-[#888]">수입</div>
                <div className="text-sm font-bold tabular-nums text-[#333]">{won(s.income_total)}</div>
              </div>
              <div className="rounded bg-[#fafafa] px-2 py-2">
                <div className="text-[10px] text-[#888]">지출</div>
                <div className="text-sm font-bold tabular-nums" style={{ color: RED }}>{won(s.spent)}</div>
              </div>
              <div className="rounded bg-[#fafafa] px-2 py-2">
                <div className="text-[10px] text-[#888]">저축 가능</div>
                <div className="text-sm font-bold tabular-nums" style={{ color: s.savings_possible >= 0 ? GREEN : RED }}>{won(s.savings_possible)}</div>
              </div>
            </div>
            {s.savings_rate != null && (
              <div className="mb-3 text-center text-[11px] text-[#666]">저축률 <b style={{ color: s.savings_rate >= 0 ? GREEN : RED }}>{s.savings_rate}%</b></div>
            )}

            {/* 카테고리별 지출 */}
            {s.by_category.length === 0 ? (
              <div className="py-10 text-center text-xs text-[#aaa]">이 달 카드내역이 없습니다. 왼쪽에서 내역을 올려보세요.</div>
            ) : (
              <div className="mb-3 flex flex-col gap-1.5">
                {s.by_category.map((c, i) => (
                  <div key={c.category}>
                    <div className="flex justify-between text-[11px]">
                      <span className="text-[#444]">{c.category} <span className="text-[#aaa]">{c.pct}%</span></span>
                      <span className="tabular-nums font-semibold text-[#333]">{won(c.amount)}</span>
                    </div>
                    <div className="mt-0.5 h-1.5 w-full overflow-hidden rounded-full bg-[#eee]">
                      <div className="h-full rounded-full" style={{ width: `${(c.amount / maxCat) * 100}%`, background: CAT_COLORS[i % CAT_COLORS.length] }} />
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* 최근 거래 */}
            {s.transactions.length > 0 && (
              <div className="rounded border border-[#eee]">
                <div className="border-b border-[#eee] bg-[#f7f7f7] px-2 py-1 text-[10px] font-semibold text-[#888]">거래 내역 ({s.count}건)</div>
                <div className="max-h-64 overflow-auto">
                  <table className="w-full text-[11px]">
                    <tbody>
                      {s.transactions.map((t) => (
                        <tr key={t.id} className="border-t border-[#f5f5f5]">
                          <td className="whitespace-nowrap px-2 py-1 text-[#999]">{t.date?.slice(5)}</td>
                          <td className="px-2 py-1 text-[#333]">{t.merchant}</td>
                          <td className="px-2 py-1">
                            <select value={t.category} onChange={(e) => setCat(t.id, e.target.value)}
                              className={`rounded border px-1 py-0.5 text-[10px] outline-none focus:border-[#217346] ${t.category === "기타" ? "border-[#e6b0b0] bg-[#fdf3f3] text-[#a55]" : "border-[#e0e0e0] text-[#666]"}`}>
                              {(s.categories || []).map((c) => <option key={c} value={c}>{c}</option>)}
                            </select>
                          </td>
                          <td className="px-2 py-1 text-right tabular-nums" style={{ color: t.amount < 0 ? "#1971c2" : "#333" }}>{won(t.amount)}</td>
                          <td className="px-1 py-1 text-right"><button onClick={() => del(t.id)} className="text-[#ccc] hover:text-rose-500">✕</button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
