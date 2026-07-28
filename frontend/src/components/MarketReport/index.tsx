"use client";

import { useEffect, useState } from "react";
import { api, DailyArchive } from "@/lib/api";
import { CrossAssetBlock } from "./crossasset";
import { InvestorTrendBlock } from "./investors";
import { ForeignViewBlock, MacroRow, RatesBlock } from "./macro";
import { BLUE, Block, BreadthStat, ColTh, GroupTh, NewsList, RED, Sheet, Th } from "./shared";
import { BrokerSheet, GlobalNewsSheet, MoverSheet, StockRow } from "./stocks";

export function MarketReport() {
  const [dates, setDates] = useState<string[]>([]);
  const [selected, setSelected] = useState(""); // "" = latest archived
  const [data, setData] = useState<DailyArchive | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    api
      .dailyArchiveDates()
      .then((r) => setDates(r.dates))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    setErr("");
    api
      .dailyArchive(selected || undefined)
      .then(setData)
      .catch((e) => setErr(e?.message ?? "리포트를 불러오지 못했습니다."))
      .finally(() => setLoading(false));
  }, [selected]);

  if (loading)
    return (
      <Sheet title="데일리리포트.xlsx">
        <div className="flex flex-col items-center gap-3 py-24 text-sm text-[#888]">
          <span className="h-7 w-7 animate-spin rounded-full border-2 border-[#d0d0d0] border-t-[#217346]" />
          데일리 리포트 불러오는 중… <span className="text-[#aaa]">(미저장 시 즉석 생성 ~20초)</span>
        </div>
      </Sheet>
    );
  if (err)
    return (
      <Sheet title="데일리리포트.xlsx">
        <div className="py-20 text-center text-sm text-rose-600">{err}</div>
      </Sheet>
    );
  if (!data) return null;

  const b = data.market.breadth;
  const total = Math.max(1, b.total);
  const macro = data.market.macro;
  const deepStocks = data.stocks.filter((s) => s.depth === "deep");
  const dateOptions = dates.length ? dates : data.date ? [data.date] : [];
  // 최신(오늘) 날짜만 실시간; 과거 날짜는 그날 마감값(아카이브)으로 고정.
  const latestDate = dates[0];
  const isLatest = !selected || (latestDate ? selected === latestDate : selected === data.date);

  return (
    <Sheet
      title="데일리리포트.xlsx"
      right={
        <div className="flex items-center gap-2">
          <span className="text-xs text-white/80">리포트 날짜</span>
          <select
            value={selected || data.date || ""}
            onChange={(e) => setSelected(e.target.value)}
            className="rounded border border-white/30 bg-white/15 px-2 py-0.5 text-xs font-semibold text-white outline-none [&>option]:text-[#1f1f1f]"
          >
            {dateOptions.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </div>
      }
    >
      {/* toolbar / scope */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-[#d0d0d0] bg-[#f3f2f1] px-3 py-1.5 text-xs text-[#555]">
        <span>
          기준일 <b className="text-[#217346]">{data.date}</b>
        </span>
        <span>
          전체 <b className="text-[#1f1f1f]">{data.scope.total.toLocaleString("ko-KR")}</b>종목 · 심층{" "}
          <b className="text-[#1f1f1f]">{data.scope.deep}</b>종목
        </span>
        {data.generated_at && <span className="text-[#999]">생성 {data.generated_at}</span>}
      </div>

      {/* 데이터 신선도 — 각 데이터가 언제 들어왔는지 모두 표시 */}
      <FreshnessBar data={data} />

      {/* formula-bar style summary */}
      {data.market.summary && (
        <div className="flex items-start gap-2 border-b border-[#d0d0d0] bg-white px-3 py-2 text-sm">
          <span className="mt-0.5 shrink-0 italic text-[#999]">fx</span>
          <p className="leading-relaxed text-[#333]">{data.market.summary}</p>
        </div>
      )}

      <div className="space-y-5 bg-[#fafafa] p-4">
        {/* ── breadth band ─────────────────────────────────── */}
        <Block label="시장 요약" color="#d9d9d9" fg="#333">
          <div className="flex flex-wrap items-end gap-6 px-3 py-3">
            <BreadthStat label="상승" value={b.up} color={RED} />
            <BreadthStat label="하락" value={b.down} color={BLUE} />
            <BreadthStat label="보합" value={b.flat} color="#888" />
            <div className="text-right">
              <div className="text-[11px] uppercase tracking-wide text-[#888]">전체</div>
              <div className="text-xl font-bold tabular-nums text-[#1f1f1f]">{b.total.toLocaleString("ko-KR")}</div>
            </div>
            <div className="ml-auto flex h-3 w-full max-w-md overflow-hidden rounded-sm border border-[#d0d0d0]">
              <div style={{ width: `${(b.up / total) * 100}%`, background: RED }} />
              <div style={{ width: `${(b.flat / total) * 100}%`, background: "#c9c9c9" }} />
              <div style={{ width: `${(b.down / total) * 100}%`, background: BLUE }} />
            </div>
          </div>
        </Block>

        {/* ── 투자자별 매매 동향 (일단위) — 누가 매입/매도했나 ─ */}
        <InvestorTrendBlock trend={data.market.investor_trend ?? []} reportDate={data.date} />

        {/* ── 크로스에셋 자금 흐름 (미국·글로벌 증시 · 금 · 비트코인) · 최신일만 실시간 ─ */}
        <CrossAssetBlock ca={data.market.cross_asset ?? null} live={isLatest} reportDate={data.date} />

        {/* ── global finance macro layer (전 세계 돈 관련 빅데이터) ─ */}
        {macro && macro.drivers.length > 0 && (
          <Block
            label={`글로벌 금융 빅데이터 · 전 세계 매크로${
              macro.pool_size ? ` (${macro.pool_size.toLocaleString("ko-KR")}건 취합)` : ""
            }`}
            color="#9dc3e6"
            fg="#1a3a5e"
          >
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-[#eaf1f8] text-xs text-[#555]">
                  <Th w="16%">이슈</Th>
                  <Th w="8%" center>방향</Th>
                  <Th w="7%" center>건수</Th>
                  <Th w="23%">주요 지역</Th>
                  <Th w="46%">대표 헤드라인 · 대표 내용 (여러 매체 취합)</Th>
                </tr>
              </thead>
              <tbody>
                {macro.drivers.map((d) => (
                  <MacroRow key={d.theme} d={d} />
                ))}
              </tbody>
            </table>

            {/* 지역별 글로벌 금융 뉴스 (모든 나라) */}
            {macro.by_region && macro.by_region.length > 0 && (
              <div className="border-t border-[#d0d0d0]">
                <div className="bg-[#f3f2f1] px-3 py-1 text-xs font-bold text-[#555]">지역별 글로벌 금융 뉴스</div>
                <div className="grid sm:grid-cols-2 xl:grid-cols-3">
                  {macro.by_region.map((r) => (
                    <div key={r.region} className="border-b border-r border-[#eee]">
                      <div className="flex items-baseline gap-1.5 bg-[#fafafa] px-3 py-1 text-xs font-bold text-[#1a3a5e]">
                        {r.region}
                        <span className="font-normal text-[#999]">{r.count}건</span>
                      </div>
                      <NewsList items={r.news.slice(0, 5)} dot="#9dc3e6" />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Block>
        )}

        {/* ── 외국인이 보는 한국 증시 + 금리 발표 일정 ─────────── */}
        <div className="grid gap-4 lg:grid-cols-2">
          {data.market.foreign_view && <ForeignViewBlock fv={data.market.foreign_view} />}
          {data.market.rates && <RatesBlock rates={data.market.rates} />}
        </div>

        {/* ── main sheet: per-stock investor reasons ────────── */}
        <Block label="거래·등락 상위 종목 · 투자자별 매매 이유" color="#a9d08e" fg="#244d1a">
          {deepStocks.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-[#888]">분석할 종목 데이터가 없습니다.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="border-collapse text-[13px]" style={{ minWidth: 1180 }}>
                {/* group header band */}
                <thead>
                  <tr>
                    <GroupTh w={36} bg="#e9e9e9" fg="#888" />
                    <GroupTh span={2} bg="#a9d08e" fg="#244d1a">종목정보</GroupTh>
                    <GroupTh span={2} bg="#d9d9d9" fg="#333">시세</GroupTh>
                    <GroupTh span={2} bg="#f4b084" fg="#7a3a0c">외국인</GroupTh>
                    <GroupTh span={2} bg="#9dc3e6" fg="#1a3a5e">개인</GroupTh>
                    <GroupTh span={2} bg="#c6e0b4" fg="#2d5016">기관</GroupTh>
                  </tr>
                  <tr className="bg-[#f0f0f0] text-xs text-[#444]">
                    <ColTh w={36} center>#</ColTh>
                    <ColTh w={150}>종목명</ColTh>
                    <ColTh w={70} center>코드</ColTh>
                    <ColTh w={92} right>현재가</ColTh>
                    <ColTh w={76} center>등락%</ColTh>
                    <ColTh w={96} center>외국인 매매</ColTh>
                    <ColTh w={210}>추정 사유</ColTh>
                    <ColTh w={96} center>개인 매매</ColTh>
                    <ColTh w={210}>추정 사유</ColTh>
                    <ColTh w={96} center>기관 매매</ColTh>
                    <ColTh w={210}>추정 사유</ColTh>
                  </tr>
                </thead>
                <tbody>
                  {deepStocks.map((s, i) => (
                    <StockRow key={s.ticker} s={s} n={i + 2} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Block>

        {/* ── 거래원 (어느 증권사 창구가 매매했는지) ────────────── */}
        <BrokerSheet stocks={deepStocks} />

        {/* ── 해외 뉴스 (종목별 글로벌 헤드라인) ───────────────── */}
        <GlobalNewsSheet stocks={deepStocks} />

        {/* ── movers ────────────────────────────────────────── */}
        <div className="grid gap-4 lg:grid-cols-2">
          <MoverSheet title="상승 상위" color="#f4b084" fg="#7a3a0c" rows={data.movers.gainers} />
          <MoverSheet title="하락 상위" color="#9dc3e6" fg="#1a3a5e" rows={data.movers.losers} />
        </div>
        <MoverSheet title="거래량 상위" color="#d9d9d9" fg="#333" rows={data.movers.most_traded} showVol />

        <p className="px-1 text-center text-xs leading-relaxed text-[#999]">
          매매 이유는 수급(네이버) · 가격 모멘텀 · 밸류에이션 · 뉴스 키워드를 조합한 <b className="text-[#666]">규칙 기반 추정</b>이며, 투자 권유가 아닙니다.
          리포트는 매 거래일 JSON으로 저장되어 과거 날짜를 다시 볼 수 있습니다.
        </p>
      </div>
    </Sheet>
  );
}

/* 데이터 신선도 바 — 각 데이터가 '언제 들어왔는지'(기준/갱신 시점) 한눈에. */
function FreshnessChip({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded border border-[#d8d8d8] bg-white px-2 py-0.5">
      <span className="text-[#888]">{label}</span>
      <b className="text-[#217346]">{value}</b>
      {sub && <span className="text-[#aaa]">{sub}</span>}
    </span>
  );
}

function FreshnessBar({ data }: { data: DailyArchive }) {
  const f = data.market.data_freshness;
  const ca = data.market.cross_asset;
  // data_freshness가 없는(기능 도입 이전) 과거 아카이브도 가진 정보로 최대한 표시.
  const priceDate = f?.price_date ?? data.date ?? "—";
  const investorDate = f?.investor_date ?? data.market.investor_trend?.[0]?.date ?? null;
  const caAsOf = f?.cross_asset_as_of ?? ca?.as_of ?? null;
  const gen = f?.report_generated ?? data.generated_at ?? null;
  return (
    <div className="flex flex-wrap items-center gap-1.5 border-b border-[#d0d0d0] bg-[#eef6f0] px-3 py-1.5 text-[11px] text-[#555]">
      <span className="font-bold text-[#217346]">최근 데이터</span>
      <FreshnessChip label="시세(가격)" value={priceDate} sub="장 마감 종가" />
      <FreshnessChip label="투자자 수급" value={investorDate ?? "—"} sub="마감후 집계·1일 지연" />
      {caAsOf && <FreshnessChip label="크로스에셋" value={caAsOf.slice(5)} sub="시세 기준" />}
      <FreshnessChip label="뉴스·매크로" value={gen ? gen.slice(5) : "—"} sub={f?.macro_pool ? `${f.macro_pool.toLocaleString("ko-KR")}건` : "리포트 생성시"} />
      {gen && <FreshnessChip label="리포트 생성" value={gen.slice(5)} />}
    </div>
  );
}
