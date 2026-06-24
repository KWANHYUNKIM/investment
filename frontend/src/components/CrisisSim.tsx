"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine,
} from "recharts";
import { api, CrisisSim as Sim, CrisisMeta, CrisisSeries } from "@/lib/api";
import { Card, Empty, Spinner } from "@/components/ui";

const RED = "#c92a2a";
const BLUE = "#1971c2";

// 기본 선택: 데이터가 가장 촘촘하고 잘 알려진 두 위기.
const DEFAULT_CRISES = ["2008_gfc", "2020_covid"];

function seriesKey(s: { crisis: string; code: string }) {
  return `${s.crisis}__${s.code}`;
}
function depthColor(v: number | null, dir: "down" | "up") {
  if (v == null) return "#888";
  // 붕괴 방향이면 빨강(악화), 회복 방향이면 파랑.
  const bad = dir === "down" ? v < 0 : v > 0;
  return bad ? RED : BLUE;
}
function fmtDepth(v: number | null) {
  if (v == null) return "—";
  return `${v > 0 ? "+" : ""}${v}%`;
}

export function CrisisSim() {
  const [meta, setMeta] = useState<CrisisMeta | null>(null);
  const [metric, setMetric] = useState("fx");
  const [picked, setPicked] = useState<string[]>(DEFAULT_CRISES);
  const [sim, setSim] = useState<Sim | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  // 애니메이션 상태
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [focus, setFocus] = useState<string | null>(null); // 강조할 series key

  // 메타 1회 로드
  useEffect(() => {
    api.crisisMeta().then(setMeta).catch((e) => setErr(e?.message ?? "메타를 불러오지 못했습니다."));
  }, []);

  // 지표·위기 변경 시 시뮬레이션 로드
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setPlaying(false);
    api
      .crisisSim(metric, picked)
      .then((r) => {
        if (!alive) return;
        setSim(r);
        setErr("");
        setFrame(r.axis.max_day); // 처음엔 전체 곡선을 보여준다
      })
      .catch((e) => alive && setErr(e?.message ?? "시뮬레이션을 불러오지 못했습니다."))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [metric, picked]);

  const maxDay = sim?.axis.max_day ?? 0;
  const minDay = sim?.axis.min_day ?? 0;

  // 재생 루프
  useEffect(() => {
    if (!playing) return;
    if (frame >= maxDay) {
      setPlaying(false);
      return;
    }
    const range = Math.max(1, maxDay - minDay);
    const step = Math.max(1, Math.round((range / 160) * speed));
    const id = setTimeout(() => setFrame((f) => Math.min(maxDay, f + step)), 45);
    return () => clearTimeout(id);
  }, [playing, frame, maxDay, minDay, speed]);

  // 병합 데이터셋 (day → {day, seriesKey: v, __current: v})
  const data = useMemo(() => {
    if (!sim) return [];
    const byDay = new Map<number, Record<string, number>>();
    const row = (d: number) => {
      let r = byDay.get(d);
      if (!r) {
        r = { day: d };
        byDay.set(d, r);
      }
      return r;
    };
    for (const s of sim.series) {
      const k = seriesKey(s);
      for (const p of s.points) row(p.day)[k] = p.v;
    }
    if (sim.current) for (const p of sim.current.points) row(p.day)["__current"] = p.v;
    return Array.from(byDay.values()).sort((a, b) => a.day - b.day);
  }, [sim]);

  // 애니메이션: frame 이하만 보여준다 (x 도메인은 고정)
  const shown = useMemo(() => data.filter((r) => r.day <= frame), [data, frame]);

  const dir = (sim?.metric.direction ?? "down") as "down" | "up";

  if (err && !sim) return <div className="py-20 text-center text-sm text-rose-600">{err}</div>;

  return (
    <div className="space-y-4">
      {/* ── 헤더 / 컨트롤 ─────────────────────────────────────── */}
      <Card
        title="금융위기 시뮬레이터 — 며칠에 걸쳐 어떻게 무너졌나"
        subtitle={meta?.note}
      >
        <div className="space-y-3">
          {/* 지표 선택 */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-[#555]">지표</span>
            {meta?.metrics.map((m) => (
              <button
                key={m.key}
                onClick={() => setMetric(m.key)}
                title={m.desc}
                className={`rounded border px-3 py-1.5 text-xs font-semibold transition ${
                  metric === m.key
                    ? "border-[#217346] bg-[#217346] text-white"
                    : "border-[#cdcdcd] bg-white text-[#444] hover:bg-[#eef6f0]"
                }`}
              >
                {m.label}
              </button>
            ))}
            <span className="ml-2 text-[11px] text-[#888]">
              {dir === "down" ? "↓ 내려갈수록 붕괴" : "↑ 올라갈수록 붕괴(신용경색)"}
            </span>
          </div>

          {/* 위기 선택 */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-[#555]">위기</span>
            {meta?.crises.map((c) => {
              const on = picked.includes(c.key);
              return (
                <button
                  key={c.key}
                  onClick={() =>
                    setPicked((p) => (on ? p.filter((k) => k !== c.key) : [...p, c.key]))
                  }
                  title={`${c.trigger} (${c.day0}) — ${c.desc}`}
                  className={`rounded-full border px-3 py-1 text-xs font-semibold transition ${
                    on ? "text-white" : "bg-white text-[#666] hover:bg-[#f0f0f0]"
                  }`}
                  style={on ? { background: c.color, borderColor: c.color } : { borderColor: "#cdcdcd" }}
                >
                  {c.label}
                </button>
              );
            })}
          </div>

          {/* 재생 컨트롤 */}
          <div className="flex flex-wrap items-center gap-3 border-t border-[#eee] pt-3">
            <button
              onClick={() => {
                if (frame >= maxDay) setFrame(minDay);
                setPlaying((p) => !p);
              }}
              className="inline-flex items-center gap-1.5 rounded bg-[#217346] px-3 py-1.5 text-xs font-bold text-white hover:bg-[#1b5e3a]"
            >
              {playing ? "❚❚ 일시정지" : "▶ 재생"}
            </button>
            <button
              onClick={() => {
                setPlaying(false);
                setFrame(minDay);
              }}
              className="rounded border border-[#cdcdcd] bg-white px-2.5 py-1.5 text-xs font-semibold text-[#444] hover:bg-[#f0f0f0]"
            >
              ↺ 처음
            </button>
            <div className="flex items-center gap-1">
              {[1, 2, 4].map((sp) => (
                <button
                  key={sp}
                  onClick={() => setSpeed(sp)}
                  className={`rounded border px-2 py-1 text-[11px] font-semibold ${
                    speed === sp ? "border-[#217346] bg-[#eef6f0] text-[#217346]" : "border-[#cdcdcd] text-[#666]"
                  }`}
                >
                  {sp}x
                </button>
              ))}
            </div>
            <div className="flex flex-1 items-center gap-2">
              <input
                type="range"
                min={minDay}
                max={maxDay}
                value={frame}
                onChange={(e) => {
                  setPlaying(false);
                  setFrame(Number(e.target.value));
                }}
                className="h-1.5 flex-1 cursor-pointer accent-[#217346]"
              />
              <span className="w-28 shrink-0 text-right text-xs font-bold tabular-nums text-[#217346]">
                {frame < 0 ? `위기 ${-frame}일 전` : frame === 0 ? "Day 0 (방아쇠)" : `위기 후 ${frame}일`}
              </span>
            </div>
          </div>
        </div>
      </Card>

      {loading && !sim ? (
        <div className="flex items-center justify-center gap-2 py-24 text-sm text-[#888]">
          <Spinner /> 시계열을 불러오는 중…
        </div>
      ) : !sim || sim.series.length === 0 ? (
        <Empty>이 지표·위기 조합에 표시할 데이터가 없습니다. 다른 위기를 선택해 보세요.</Empty>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {/* ── 메인 차트 ─────────────────────────────────────── */}
          <Card title="위기 후 N일 — 정렬 비교 (Day0=100)" className="lg:col-span-2">
            <div className="h-[420px] w-full">
              <ResponsiveContainer>
                <LineChart data={shown} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                  <XAxis
                    dataKey="day"
                    type="number"
                    domain={[minDay, maxDay]}
                    tick={{ fontSize: 11, fill: "#888" }}
                    tickFormatter={(d) => `${d}일`}
                  />
                  <YAxis
                    domain={["auto", "auto"]}
                    tick={{ fontSize: 11, fill: "#888" }}
                    width={44}
                    tickFormatter={(v) => `${v}`}
                  />
                  <Tooltip
                    contentStyle={{ fontSize: 12, borderRadius: 6, border: "1px solid #ddd" }}
                    labelFormatter={(d) => (Number(d) < 0 ? `위기 ${-Number(d)}일 전` : `위기 후 ${d}일`)}
                    formatter={(val: number, name: string) => [Number(val).toFixed(1), name]}
                  />
                  <ReferenceLine x={0} stroke="#c92a2a" strokeDasharray="4 3" label={{ value: "Day 0", fontSize: 10, fill: "#c92a2a", position: "top" }} />
                  <ReferenceLine y={100} stroke="#bbb" strokeDasharray="2 2" />
                  {sim.series.map((s) => {
                    const k = seriesKey(s);
                    const isFocus = focus === k;
                    const dim = focus !== null && !isFocus;
                    return (
                      <Line
                        key={k}
                        type="monotone"
                        dataKey={k}
                        name={s.label}
                        stroke={s.color}
                        strokeWidth={isFocus ? 3 : 1.6}
                        strokeOpacity={dim ? 0.18 : 0.9}
                        dot={false}
                        isAnimationActive={false}
                        connectNulls
                      />
                    );
                  })}
                  {sim.current && (
                    <Line
                      type="monotone"
                      dataKey="__current"
                      name={sim.current.label}
                      stroke="#111"
                      strokeWidth={3.2}
                      strokeDasharray="6 3"
                      dot={false}
                      isAnimationActive={false}
                      connectNulls
                    />
                  )}
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-2 text-[11px] text-[#999]">
              검은 점선 = <b>{sim.current?.label ?? "현재"}</b>. 각 색선 = 과거 위기 당시 각국 궤적. 범례/선에 마우스를 올리면 강조됩니다.
            </p>
          </Card>

          {/* ── 유사도 패널 ───────────────────────────────────── */}
          <Card title="지금은 어느 위기와 닮았나" subtitle="현재 한국 궤적 vs 과거 위기 곡선 (모양·수준 비교)">
            {!sim.current ? (
              <Empty>현재 궤적을 만들 데이터가 없습니다.</Empty>
            ) : sim.similarity.length === 0 ? (
              <Empty>비교할 과거 곡선이 없습니다.</Empty>
            ) : (
              <div className="space-y-2.5">
                <div className="rounded border border-[#e6e6e6] bg-[#f9f9f9] px-3 py-2 text-xs text-[#555]">
                  현재 기준점 <b>{sim.current.anchor_date}</b> 이후 <b>{sim.current.days_elapsed}거래일</b> 경과 ·
                  현재 낙폭{" "}
                  <b style={{ color: depthColor(sim.current.depth_pct, dir) }}>{fmtDepth(sim.current.depth_pct)}</b>
                </div>
                {sim.similarity.slice(0, 7).map((m) => (
                  <button
                    key={`${m.crisis}__${m.code}`}
                    onMouseEnter={() => setFocus(`${m.crisis}__${m.code}`)}
                    onMouseLeave={() => setFocus(null)}
                    className="block w-full rounded border border-[#e6e6e6] bg-white px-3 py-2 text-left transition hover:border-[#217346] hover:bg-[#f6fbf8]"
                  >
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1.5 text-xs font-bold text-[#333]">
                        <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: m.color }} />
                        {m.name}
                      </span>
                      <span className="text-xs font-bold tabular-nums" style={{ color: m.score >= 60 ? RED : "#666" }}>
                        {m.score.toFixed(0)}점 · {m.verdict}
                      </span>
                    </div>
                    <div className="mt-1 text-[11px] text-[#888]">{m.crisis_label}</div>
                    <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-[#eee]">
                      <div className="h-full rounded-full" style={{ width: `${m.score}%`, background: m.color }} />
                    </div>
                  </button>
                ))}
                <p className="text-[11px] leading-relaxed text-[#999]">
                  점수 = 모양 유사도(상관계수) 70% + 수준 근접도 30%. 높을수록 현재 궤적이 그 위기 초기와 닮았다는 뜻이며,
                  미래를 예측하지는 않습니다.
                </p>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* ── 위기별 붕괴 요약 표 ──────────────────────────────── */}
      {sim && sim.series.length > 0 && (
        <Card title="위기별·국가별 붕괴 깊이" subtitle="Day0 대비 최저점(또는 금리 최고점)과 도달 일수">
          <CrisisTable series={sim.series} dir={dir} onFocus={setFocus} />
        </Card>
      )}
    </div>
  );
}

function CrisisTable({
  series,
  dir,
  onFocus,
}: {
  series: CrisisSeries[];
  dir: "down" | "up";
  onFocus: (k: string | null) => void;
}) {
  const sorted = [...series].sort((a, b) => {
    const av = a.depth_pct ?? 0;
    const bv = b.depth_pct ?? 0;
    return dir === "down" ? av - bv : bv - av; // 더 심한 붕괴가 위로
  });
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-[#e0e0e0] text-[#888]">
            <th className="px-2 py-1.5 text-left font-semibold">국가 / 위기</th>
            <th className="px-2 py-1.5 text-right font-semibold">{dir === "down" ? "최대 낙폭" : "최대 상승"}</th>
            <th className="px-2 py-1.5 text-right font-semibold">도달 일수</th>
            <th className="px-2 py-1.5 text-right font-semibold">주기</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((s) => {
            const k = seriesKey(s);
            return (
              <tr
                key={k}
                onMouseEnter={() => onFocus(k)}
                onMouseLeave={() => onFocus(null)}
                className="border-b border-[#f0f0f0] hover:bg-[#f6fbf8]"
              >
                <td className="px-2 py-1.5">
                  <span className="inline-block h-2.5 w-2.5 rounded-full align-middle" style={{ background: s.color }} />{" "}
                  <span className="font-semibold text-[#333]">{s.name}</span>
                  <span className="ml-1.5 text-[#aaa]">{s.label.split("·")[1]}</span>
                </td>
                <td className="px-2 py-1.5 text-right font-bold tabular-nums" style={{ color: depthColor(s.depth_pct, dir) }}>
                  {fmtDepth(s.depth_pct)}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums text-[#555]">
                  {s.extreme_day != null ? `${s.extreme_day}일` : "—"}
                </td>
                <td className="px-2 py-1.5 text-right text-[#999]">{s.freq}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
