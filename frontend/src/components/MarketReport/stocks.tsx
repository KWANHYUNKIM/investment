"use client";

import { MoverRow, ArchiveStock, BrokerHouse } from "@/lib/api";
import { won, manShares } from "@/lib/format";
import { InvestorCells } from "./investors";
import { BLUE, Block, RED, Th, retStyle } from "./shared";

export function HouseTags({ houses }: { houses: BrokerHouse[] }) {
  if (!houses || houses.length === 0) return <span className="text-xs text-[#bbb]">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {houses.map((h, i) => (
        <span
          key={i}
          className={`rounded px-1.5 py-0.5 text-[11px] ${
            h.foreign ? "bg-[#fde7e9] font-semibold text-[#c92a2a]" : "bg-[#f0f0f0] text-[#555]"
          }`}
          title={h.volume != null ? `${h.volume.toLocaleString("ko-KR")}주` : undefined}
        >
          {h.foreign && " "}
          {h.name}
          {h.volume != null && <span className="ml-1 tabular-nums text-[#999]">{manShares(h.volume)}</span>}
        </span>
      ))}
    </div>
  );
}

export function BrokerSheet({ stocks }: { stocks: ArchiveStock[] }) {
  const rows = stocks.filter((s) => s.brokers && (s.brokers.buy.length > 0 || s.brokers.sell.length > 0));
  if (rows.length === 0) return null;
  return (
    <Block label="거래원 · 매매 상위 증권사 창구 (외국계 추정 · 20분 지연)" color="#c6e0b4" fg="#2d5016">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px]" style={{ minWidth: 900 }}>
          <thead>
            <tr className="bg-[#eaf3e3] text-xs text-[#2d5016]">
              <Th w="16%">종목</Th>
              <Th w="34%">매수 상위 창구</Th>
              <Th w="34%">매도 상위 창구</Th>
              <Th w="16%" center>외국계 추정</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => {
              const fn = s.brokers!.foreign?.net ?? null;
              const fColor = fn == null ? "#888" : fn > 0 ? RED : fn < 0 ? BLUE : "#888";
              return (
                <tr key={s.ticker} className="hover:bg-[#fff7e6]">
                  <td className="border border-[#eee] px-2 py-1.5 align-top">
                    <span className="font-medium text-[#1f1f1f]">{s.name}</span>
                    <span className="ml-1 font-mono text-[11px] text-[#999]">{s.ticker}</span>
                  </td>
                  <td className="border border-[#eee] px-2 py-1.5 align-top">
                    <HouseTags houses={s.brokers!.buy} />
                  </td>
                  <td className="border border-[#eee] px-2 py-1.5 align-top">
                    <HouseTags houses={s.brokers!.sell} />
                  </td>
                  <td className="border border-[#eee] px-2 py-1.5 text-center align-top font-bold tabular-nums" style={{ color: fColor }}>
                    {fn == null
                      ? "—"
                      : `${fn > 0 ? "순매수" : fn < 0 ? "순매도" : "보합"} ${manShares(Math.abs(fn)).replace("+", "")}주`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="px-3 py-1.5 text-[11px] text-[#999]">
         표시는 외국계 창구(모간스탠리·제이피모간·골드만삭스 등). 당일 매매 상위 5개 회원사 기준 추정치이며, 기관 세부주체(연기금·투신 등)는 KRX 비공개 구간으로 제공되지 않습니다.
      </p>
    </Block>
  );
}

/* per-stock global (English) headlines — the 해외 뉴스 sheet */
export function GlobalNewsSheet({ stocks }: { stocks: ArchiveStock[] }) {
  const rows = stocks.flatMap((s) =>
    (s.news_global ?? []).map((n) => ({ name: s.name, ticker: s.ticker, ...n })),
  );
  if (rows.length === 0) return null;
  return (
    <Block label="해외 뉴스 · 종목별 글로벌 헤드라인 (Google News EN)" color="#f4b084" fg="#7a3a0c">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="bg-[#fbe7d6] text-xs text-[#7a3a0c]">
              <Th w="16%">종목</Th>
              <Th w="9%" center>코드</Th>
              <Th w="60%">헤드라인 (EN)</Th>
              <Th w="15%">출처</Th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 60).map((r, i) => (
              <tr key={i} className="hover:bg-[#fff7e6]">
                <td className="border border-[#eee] px-2 py-1.5 font-medium text-[#1f1f1f]">{r.name}</td>
                <td className="border border-[#eee] px-2 py-1.5 text-center font-mono text-xs text-[#888]">{r.ticker}</td>
                <td className="border border-[#eee] px-2 py-1.5">
                  <a
                    href={r.link ?? "#"}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[#1155cc] hover:underline"
                  >
                    {r.title}
                  </a>
                </td>
                <td className="border border-[#eee] px-2 py-1.5 text-xs text-[#888]">{r.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Block>
  );
}

/* one stock row in the main investor-reason sheet */
export function StockRow({ s, n }: { s: ArchiveStock; n: number }) {
  const find = (k: string) => s.investors.find((iv) => iv.key === k);
  return (
    <tr className="hover:bg-[#fff7e6]">
      <td className="border border-[#e6e6e6] bg-[#f0f0f0] px-1 text-center text-xs text-[#999]">{n}</td>
      <td className="border border-[#e6e6e6] px-2 py-1.5 font-medium text-[#1155cc]">{s.name}</td>
      <td className="border border-[#e6e6e6] px-2 py-1.5 text-center font-mono text-xs text-[#555]">{s.ticker}</td>
      <td className="border border-[#e6e6e6] px-2 py-1.5 text-right tabular-nums text-[#1f1f1f]">{won(s.close)}</td>
      <td className="border border-[#e6e6e6] px-2 py-1.5 text-center font-bold tabular-nums" style={retStyle(s.change_pct)}>
        {s.change_pct != null ? `${s.change_pct > 0 ? "+" : ""}${s.change_pct}%` : "—"}
      </td>
      <InvestorCells iv={find("foreign")} />
      <InvestorCells iv={find("individual")} />
      <InvestorCells iv={find("organ")} />
    </tr>
  );
}

/* compact mover mini-sheet */
export function MoverSheet({
  title,
  color,
  fg,
  rows,
  showVol,
}: {
  title: string;
  color: string;
  fg: string;
  rows: MoverRow[];
  showVol?: boolean;
}) {
  return (
    <Block label={title} color={color} fg={fg}>
      <table className="w-full border-collapse text-[13px]">
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.ticker} className="hover:bg-[#fff7e6]">
              <td className="border border-[#eee] bg-[#f0f0f0] px-1 text-center text-xs text-[#999]" style={{ width: 30 }}>
                {i + 1}
              </td>
              <td className="border border-[#eee] px-2 py-1.5">
                <span className="text-[#1f1f1f]">{r.name}</span>
                <span className="ml-1.5 font-mono text-[11px] text-[#999]">{r.ticker}</span>
              </td>
              <td className="border border-[#eee] px-2 py-1.5 text-right tabular-nums text-[#333]">{won(r.close)}</td>
              {showVol ? (
                <td className="border border-[#eee] px-2 py-1.5 text-right tabular-nums text-[#555]">
                  {r.volume != null ? r.volume.toLocaleString("ko-KR") : "—"}
                </td>
              ) : (
                <td
                  className="border border-[#eee] px-2 py-1.5 text-right font-bold tabular-nums"
                  style={retStyle(r.change_pct)}
                >
                  {r.change_pct != null ? `${r.change_pct > 0 ? "+" : ""}${r.change_pct}%` : "—"}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </Block>
  );
}
