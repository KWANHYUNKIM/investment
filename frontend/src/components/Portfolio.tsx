"use client";

import { useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { api, ApiError, Coverage, PortfolioResponse } from "@/lib/api";
import { TickerPicker, useSecurities } from "./securities";
import { Button, Card, Empty, ErrorBox, Field, Select, Input } from "./ui";
import { MetricsGrid, WeightBars } from "./Backtest";
import { colorFor, pct } from "@/lib/format";

const SCHEMES = [
  { v: "max_sharpe", l: "최대샤프 (Max Sharpe)" },
  { v: "min_variance", l: "최소분산 (Min Variance)" },
  { v: "inverse_vol", l: "역변동성 (Inverse Vol)" },
  { v: "equal", l: "동일가중 (Equal)" },
];

export function Portfolio({ coverage }: { coverage: Coverage[] }) {
  const market = coverage[0]?.market;
  const { list } = useSecurities(market);
  const [tickers, setTickers] = useState<string[]>([]);
  const [scheme, setScheme] = useState("max_sharpe");
  const [start, setStart] = useState("");

  const [res, setRes] = useState<PortfolioResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const nameOf = (t: string) => list.find((s) => s.ticker === t)?.name ?? t;

  async function run() {
    if (tickers.length < 2) {
      setError("종목을 2개 이상 선택하세요.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const r = await api.portfolio({ tickers, market, scheme, start: start || null });
      setRes(r);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "포트폴리오 구성 실패");
      setRes(null);
    } finally {
      setLoading(false);
    }
  }

  const pieData = res
    ? Object.entries(res.weights)
        .map(([t, w]) => ({ name: nameOf(t), ticker: t, value: w }))
        .sort((a, b) => b.value - a.value)
    : [];

  return (
    <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
      <Card title="포트폴리오 설정">
        <div className="space-y-4">
          <div>
            <span className="mb-1.5 block text-xs font-semibold text-[#555]">종목 선택 (≥2)</span>
            <TickerPicker market={market} selected={tickers} onChange={setTickers} />
          </div>
          <Field label="최적화 방식">
            <Select value={scheme} onChange={(e) => setScheme(e.target.value)}>
              {SCHEMES.map((s) => (
                <option key={s.v} value={s.v}>
                  {s.l}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="시작일 (선택)">
            <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </Field>
          <Button onClick={run} loading={loading} className="w-full">
            비중 계산
          </Button>
          {error && <ErrorBox message={error} />}
        </div>
      </Card>

      <div className="space-y-6">
        {!res ? (
          <Empty>좌측에서 종목과 최적화 방식을 선택하고 비중을 계산하세요.</Empty>
        ) : (
          <>
            <Card title="제안 비중" subtitle={`방식: ${res.scheme}`}>
              <div className="grid items-center gap-6 sm:grid-cols-2">
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={95} paddingAngle={2}>
                        {pieData.map((d, i) => (
                          <Cell key={d.ticker} fill={colorFor(d.ticker, i)} stroke="#ffffff" />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{ background: "#fff", border: "1px solid #d0d0d0", borderRadius: 6, fontSize: 12 }}
                        formatter={(v, _n, p) => [pct(Number(v)), (p.payload as { name: string }).name]}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <WeightBars weights={res.weights} nameOf={nameOf} />
              </div>
            </Card>

            <Card title="인-샘플 위험/수익 지표" subtitle="제안 비중을 과거 구간에 적용했을 때">
              <MetricsGrid m={res.metrics} />
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
