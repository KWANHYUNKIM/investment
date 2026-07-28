"use client";

import { MacroDriver, RateLayer, ForeignView as ForeignViewType } from "@/lib/api";
import { BLUE, Block, DigestList, NewsList, RED } from "./shared";

/* 외국인이 보는 한국 증시 — 외신(영문) 시각 + 대표 내용 */
export function ForeignViewBlock({ fv }: { fv: ForeignViewType }) {
  const tone = fv.lean === "긍정" ? RED : fv.lean === "부정" ? BLUE : "#666";
  return (
    <Block label="외국인이 보는 한국 증시 (외신 시각)" color="#f4b084" fg="#7a3a0c">
      <div className="space-y-2 px-3 py-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className="rounded-full px-2.5 py-0.5 text-xs font-bold text-white"
            style={{ background: tone }}
          >
            {fv.lean}
          </span>
          <span className="text-xs text-[#888]">
            긍정 {fv.pos} · 부정 {fv.neg} · 영문 보도 {fv.pool_size}건
          </span>
        </div>
        {fv.summary && <p className="text-[13px] leading-relaxed text-[#444]">{fv.summary}</p>}
        {fv.headlines.length > 0 && (
          <NewsList items={fv.headlines.slice(0, 5).map((h) => ({ title: h.title ?? "", link: h.link ?? "#", source: h.source ?? "" }))} dot="#f4b084" />
        )}
        {fv.digest.length > 0 && (
          <div className="border-t border-[#eee] pt-2">
            <div className="mb-1 text-[11px] font-bold text-[#7a3a0c]">대표 내용 (여러 매체 취합)</div>
            <DigestList lines={fv.digest} color="#f4b084" />
          </div>
        )}
      </div>
    </Block>
  );
}

/* 금리 발표 일정 + 인상 시기 전망 */
export function RatesBlock({ rates }: { rates: RateLayer }) {
  return (
    <Block label="금리 발표 일정 · 인상 시기 전망" color="#9dc3e6" fg="#1a3a5e">
      <div className="space-y-2.5 px-3 py-2.5">
        <div className="grid grid-cols-2 gap-2">
          {rates.schedule.map((m) => {
            const soon = m.d_day != null && m.d_day <= 7;
            return (
              <div
                key={m.key}
                className="rounded border border-[#dbe7f3] bg-[#f7fbff] px-2.5 py-2"
              >
                <div className="flex items-center gap-1 text-xs font-bold text-[#1a3a5e]">
                  <span>{m.flag}</span>
                  <span>{m.name}</span>
                </div>
                <div className="mt-1 flex items-baseline gap-1.5">
                  <span className="text-lg font-bold tabular-nums text-[#1f1f1f]">{m.next_label ?? "—"}</span>
                  {m.d_day != null && (
                    <span
                      className="rounded px-1.5 py-0.5 text-[11px] font-bold"
                      style={{ background: soon ? RED : "#dbe7f3", color: soon ? "#fff" : "#1a3a5e" }}
                    >
                      D-{m.d_day}
                    </span>
                  )}
                </div>
                <div className="mt-0.5 text-[11px] text-[#999]">
                  다음 발표일{m.next_date ? ` · ${m.next_date}` : ""} · 2026 {m.remaining_2026}회 남음
                </div>
              </div>
            );
          })}
        </div>
        {rates.digest.length > 0 && (
          <div className="border-t border-[#eee] pt-2">
            <div className="mb-1 text-[11px] font-bold text-[#1a3a5e]">금리 시기 전망 (대표 내용)</div>
            <DigestList lines={rates.digest} color="#9dc3e6" />
          </div>
        )}
        {rates.outlook.length > 0 && (
          <NewsList items={rates.outlook.slice(0, 4).map((h) => ({ title: h.title ?? "", link: h.link ?? "#", source: h.source ?? "" }))} dot="#9dc3e6" />
        )}
      </div>
    </Block>
  );
}

/* macro driver row */
export function MacroRow({ d }: { d: MacroDriver }) {
  const color = d.direction === "긍정" ? RED : d.direction === "부정" ? BLUE : "#666";
  const regions = Object.entries(d.regions ?? {}).sort((a, b) => b[1] - a[1]);
  const top = d.headlines[0];
  return (
    <tr className="border-b border-[#eee] hover:bg-[#fff7e6]">
      <td className="border border-[#eee] px-2 py-1.5 font-semibold text-[#1f1f1f]">{d.theme}</td>
      <td className="border border-[#eee] px-2 py-1.5 text-center font-bold" style={{ color }}>
        {d.direction}
      </td>
      <td className="border border-[#eee] px-2 py-1.5 text-center tabular-nums text-[#555]">{d.count}</td>
      <td className="border border-[#eee] px-2 py-1.5">
        <div className="flex flex-wrap gap-1">
          {regions.slice(0, 5).map(([reg, n]) => (
            <span key={reg} className="rounded bg-[#eaf1f8] px-1.5 py-0.5 text-[11px] text-[#1a3a5e]">
              {reg} {n}
            </span>
          ))}
        </div>
      </td>
      <td className="border border-[#eee] px-2 py-1.5 align-top text-[#555]">
        {top ? (
          <a href={top.link ?? "#"} target="_blank" rel="noopener noreferrer" className="font-medium hover:text-[#1155cc] hover:underline">
            {top.region && <span className="mr-1 text-[11px] text-[#999]">[{top.region}]</span>}
            {top.title}
            {top.source && <span className="ml-1 text-xs text-[#999]">· {top.source}</span>}
          </a>
        ) : (
          "—"
        )}
        {d.digest && d.digest.length > 0 && (
          <ul className="mt-1 space-y-0.5 border-l-2 border-[#dbe7f3] pl-2">
            {d.digest.map((line, i) => (
              <li key={i} className="flex gap-1 text-[12px] leading-snug text-[#666]">
                <span className="text-[#9dc3e6]">·</span>
                <span>{line}</span>
              </li>
            ))}
          </ul>
        )}
      </td>
    </tr>
  );
}
