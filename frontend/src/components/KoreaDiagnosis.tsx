"use client";

import { useEffect, useState } from "react";
import { api, KoreaDiagnosis as KD } from "@/lib/api";
import { Card, Spinner } from "@/components/ui";

const STATUS_BG: Record<string, string> = { good: "#eaf6ee", neutral: "#fdf2e3", warn: "#fdecec", na: "#f2f2f2" };

// **볼드** 마크업만 간단 렌더
function Narrative({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <p className="text-sm leading-relaxed text-[#333]">
      {parts.map((p, i) =>
        p.startsWith("**") && p.endsWith("**")
          ? <b key={i} className="text-[#111]">{p.slice(2, -2)}</b>
          : <span key={i}>{p}</span>,
      )}
    </p>
  );
}

export function KoreaDiagnosis() {
  const [d, setD] = useState<KD | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    api.koreaDiagnosis().then(setD).catch(() => setErr(true));
  }, []);

  if (err) return null;
  if (!d) {
    return (
      <Card title="한국경제 종합 진단" subtitle="GDP·물가·경상·유동성·금리·심리로 보는 현재 국면">
        <div className="flex items-center gap-2 py-8 text-sm text-[#888]"><Spinner /> 진단 계산 중…</div>
      </Card>
    );
  }
  if (!d.available) {
    return (
      <Card title="한국경제 종합 진단" subtitle="ECOS 실측 기반">
        <div className="py-6 text-center text-sm text-[#999]">{d.reason ?? "ECOS 미연동 — backend/.env 에 ECOS_API_KEY 필요"}</div>
      </Card>
    );
  }

  return (
    <Card title="한국경제 종합 진단" subtitle={`${d.source ?? ""} · 갱신 ${d.generated_at?.slice(5, 16)}`}>
      {/* 종합 국면 + 점수 */}
      <div className="rounded-lg border p-4" style={{ borderColor: (d.regime_color ?? "#217346") + "44", background: (d.regime_color ?? "#217346") + "0c" }}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-[11px] font-semibold text-[#888]">현재 국면</div>
            <div className="text-lg font-extrabold" style={{ color: d.regime_color }}>{d.regime}</div>
          </div>
          {d.score != null && (
            <div className="flex items-center gap-3">
              <div className="text-right">
                <div className="text-[10px] text-[#888]">종합 점수</div>
                <div className="text-2xl font-extrabold tabular-nums" style={{ color: d.regime_color }}>{d.score}<span className="text-sm text-[#aaa]">/100</span></div>
              </div>
              <span className="rounded-full px-2.5 py-1 text-xs font-bold text-white" style={{ background: d.regime_color }}>{d.score_label}</span>
            </div>
          )}
        </div>
        {d.narrative && <div className="mt-2 border-t border-black/5 pt-2"><Narrative text={d.narrative} /></div>}
      </div>

      {/* 축별 진단 */}
      <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
        {d.axes.map((a) => (
          <div key={a.key} className="rounded-lg border border-[#eaeaea] p-3" style={{ background: STATUS_BG[a.status] }}>
            <div className="flex items-center justify-between">
              <span className="text-[13px] font-bold text-[#333]">{a.title}</span>
              <span className="rounded-full px-2 py-0.5 text-[10px] font-bold text-white" style={{ background: a.color }}>{a.status_label}</span>
            </div>
            <div className="mt-1 text-[12px] font-semibold leading-snug" style={{ color: a.color }}>{a.headline}</div>
            {a.metrics.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5">
                {a.metrics.map((m, i) => (
                  <span key={i} className="text-[11px] text-[#666]">{m.k} <b className="tabular-nums text-[#333]">{m.v}</b></span>
                ))}
              </div>
            )}
            {a.detail && <div className="mt-1 text-[10px] leading-relaxed text-[#999]">{a.detail}</div>}
          </div>
        ))}
      </div>
      {d.note && <p className="mt-2.5 text-[10px] leading-relaxed text-[#aaa]">{d.note}</p>}
    </Card>
  );
}
