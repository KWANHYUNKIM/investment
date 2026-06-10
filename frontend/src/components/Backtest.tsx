"use client";

import { useState } from "react";
import {
  Area,
  AreaChart,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
} from "recharts";
import { api, ApiError, BacktestResponse, Coverage, Metrics } from "@/lib/api";
import { TickerPicker, useSecurities } from "./securities";
import { Button, Card, Empty, ErrorBox, Field, Select, Input, Stat } from "./ui";
import { pct, num, signed } from "@/lib/format";

const SCHEMES = [
  { v: "equal", l: "동일가중 (Equal)" },
  { v: "inverse_vol", l: "역변동성 (Inverse Vol)" },
  { v: "min_variance", l: "최소분산 (Min Variance)" },
  { v: "max_sharpe", l: "최대샤프 (Max Sharpe)" },
];
const REBAL = [
  { v: "M", l: "월간" },
  { v: "Q", l: "분기" },
  { v: "W", l: "주간" },
  { v: "Y", l: "연간" },
  { v: "D", l: "일간" },
];

export function Backtest({ coverage }: { coverage: Coverage[] }) {
  const market = coverage[0]?.market;
  const { list } = useSecurities(market);
  const [tickers, setTickers] = useState<string[]>([]);
  const [scheme, setScheme] = useState("equal");
  const [rebalance, setRebalance] = useState("M");
  const [costBps, setCostBps] = useState(10);
  const [lookback, setLookback] = useState(252);
  const [benchmark, setBenchmark] = useState("");
  const [start, setStart] = useState("");

  const [res, setRes] = useState<BacktestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function run() {
    if (tickers.length < 2) {
      setError("종목을 2개 이상 선택하세요.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const r = await api.backtest({
        tickers,
        market,
        scheme,
        rebalance,
        cost_bps: costBps,
        lookback,
        benchmark: benchmark || null,
        start: start || null,
      });
      setRes(r);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "백테스트 실패");
      setRes(null);
    } finally {
      setLoading(false);
    }
  }

  const chartData =
    res?.dates.map((d, i) => ({
      date: d,
      strategy: res.equity_curve[i],
      benchmark: res.benchmark?.equity_curve[i],
      drawdown: res.drawdown[i],
    })) ?? [];
  const step = Math.max(1, Math.floor(chartData.length / 250));
  const thin = chartData.filter((_, i) => i % step === 0);
  const latestWeights = res ? Object.entries(res.weights).at(-1) : undefined;

  return (
    <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
      <Card title="백테스트 설정">
        <div className="space-y-4">
          <div>
            <span className="mb-1.5 block text-xs font-medium text-slate-400">종목 선택 (≥2)</span>
            <TickerPicker market={market} selected={tickers} onChange={setTickers} />
          </div>
          <Field label="가중 방식">
            <Select value={scheme} onChange={(e) => setScheme(e.target.value)}>
              {SCHEMES.map((s) => (
                <option key={s.v} value={s.v}>
                  {s.l}
                </option>
              ))}
            </Select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="리밸런싱">
              <Select value={rebalance} onChange={(e) => setRebalance(e.target.value)}>
                {REBAL.map((r) => (
                  <option key={r.v} value={r.v}>
                    {r.l}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="비용 (bps)">
              <Input type="number" value={costBps} min={0} step={1} onChange={(e) => setCostBps(+e.target.value)} />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="룩백 (일)">
              <Input type="number" value={lookback} min={20} step={1} onChange={(e) => setLookback(+e.target.value)} />
            </Field>
            <Field label="시작일">
              <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
            </Field>
          </div>
          <Field label="벤치마크 (선택 종목 중)">
            <Select value={benchmark} onChange={(e) => setBenchmark(e.target.value)}>
              <option value="">없음</option>
              {tickers.map((t) => (
                <option key={t} value={t}>
                  {list.find((s) => s.ticker === t)?.name ?? t}
                </option>
              ))}
            </Select>
          </Field>
          <Button onClick={run} loading={loading} className="w-full">
            백테스트 실행
          </Button>
          {error && <ErrorBox message={error} />}
        </div>
      </Card>

      <div className="space-y-6">
        {!res ? (
          <Empty>좌측에서 종목과 전략을 설정하고 백테스트를 실행하세요.</Empty>
        ) : (
          <>
            <Card title="성과 지표" subtitle={`리밸런싱 ${res.rebalance_count}회 · 종목 ${tickers.length}개`}>
              <MetricsGrid m={res.metrics} />
            </Card>

            <Card title="누적 수익 곡선" subtitle="초기 자본 1.0 기준">
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={thin} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
                    <CartesianGrid stroke="#1e293b" vertical={false} />
                    <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 11 }} minTickGap={48} />
                    <YAxis tick={{ fill: "#64748b", fontSize: 11 }} domain={["auto", "auto"]} />
                    <Tooltip
                      contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, fontSize: 12 }}
                      labelStyle={{ color: "#94a3b8" }}
                      formatter={(v) => num(Number(v), 3)}
                    />
                    <Legend formatter={(v) => <span className="text-xs text-slate-400">{v === "strategy" ? "전략" : "벤치마크"}</span>} />
                    <Line type="monotone" dataKey="strategy" stroke="#38bdf8" dot={false} strokeWidth={2} />
                    {res.benchmark && (
                      <Line type="monotone" dataKey="benchmark" stroke="#a78bfa" dot={false} strokeWidth={1.5} strokeDasharray="4 3" />
                    )}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card title="낙폭 (Drawdown)">
              <div className="h-48 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={thin} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
                    <defs>
                      <linearGradient id="dd" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#f43f5e" stopOpacity={0.05} />
                        <stop offset="100%" stopColor="#f43f5e" stopOpacity={0.5} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="#1e293b" vertical={false} />
                    <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 11 }} minTickGap={48} />
                    <YAxis tick={{ fill: "#64748b", fontSize: 11 }} tickFormatter={(v) => pct(v, 0)} />
                    <Tooltip
                      contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, fontSize: 12 }}
                      labelStyle={{ color: "#94a3b8" }}
                      formatter={(v) => pct(Number(v))}
                    />
                    <Area type="monotone" dataKey="drawdown" stroke="#f43f5e" fill="url(#dd)" strokeWidth={1.5} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </Card>

            {res.benchmark && (
              <Card title="벤치마크 대비">
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <Stat label="전략 총수익" value={signed(res.metrics.total_return)} tone={res.metrics.total_return >= 0 ? "pos" : "neg"} />
                  <Stat label="벤치 총수익" value={signed(res.benchmark.metrics.total_return)} tone={res.benchmark.metrics.total_return >= 0 ? "pos" : "neg"} />
                  <Stat label="전략 샤프" value={num(res.metrics.sharpe)} />
                  <Stat label="벤치 샤프" value={num(res.benchmark.metrics.sharpe)} />
                </div>
              </Card>
            )}

            {latestWeights && (
              <Card title="최근 리밸런싱 비중" subtitle={latestWeights[0]}>
                <WeightBars weights={latestWeights[1]} nameOf={(t) => list.find((s) => s.ticker === t)?.name ?? t} />
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export function MetricsGrid({ m }: { m: Metrics }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Stat label="총수익" value={signed(m.total_return)} tone={m.total_return >= 0 ? "pos" : "neg"} />
      <Stat label="CAGR" value={signed(m.cagr)} tone={m.cagr >= 0 ? "pos" : "neg"} />
      <Stat label="변동성" value={pct(m.volatility)} />
      <Stat label="샤프" value={num(m.sharpe)} />
      <Stat label="소르티노" value={num(m.sortino)} />
      <Stat label="MDD" value={pct(m.max_drawdown)} tone="neg" />
      <Stat label="칼마" value={num(m.calmar)} />
      <Stat label="승률" value={pct(m.win_rate)} />
    </div>
  );
}

export function WeightBars({
  weights,
  nameOf,
}: {
  weights: Record<string, number>;
  nameOf: (t: string) => string;
}) {
  const entries = Object.entries(weights).sort((a, b) => b[1] - a[1]);
  const maxW = Math.max(...entries.map(([, w]) => w), 0.0001);
  return (
    <div className="space-y-2">
      {entries.map(([t, w]) => (
        <div key={t} className="flex items-center gap-3">
          <span className="w-32 shrink-0 truncate text-xs text-slate-300" title={nameOf(t)}>
            {nameOf(t)}
          </span>
          <div className="h-3 flex-1 overflow-hidden rounded bg-slate-800">
            <div className="h-full rounded bg-sky-500" style={{ width: `${(w / maxW) * 100}%` }} />
          </div>
          <span className="w-14 shrink-0 text-right text-xs tabular-nums text-slate-400">{pct(w)}</span>
        </div>
      ))}
    </div>
  );
}
