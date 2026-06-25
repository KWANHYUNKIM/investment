"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
  ReferenceLine, ReferenceDot,
} from "recharts";
import {
  api, CrisisSim as Sim, CrisisMeta, CrisisSeries, CrisisWarning, CrisisKoreaWarning, CrisisCountries,
} from "@/lib/api";
import { Card, Empty, Spinner } from "@/components/ui";

const RED = "#c92a2a";
const BLUE = "#1971c2";

// 조기경보 상태 스타일
const STAT: Record<string, { bg: string; fg: string; t: string }> = {
  ok: { bg: "#eef6f0", fg: "#217346", t: "정상" },
  watch: { bg: "#fff4e5", fg: "#b8860b", t: "주의" },
  alert: { bg: "#fdecec", fg: "#c92a2a", t: "경고" },
};
function levelColor(level: string) {
  return level === "위험" ? "#c92a2a" : level === "경고" ? "#e8590c" : level === "주의" ? "#b8860b" : "#217346";
}
function fmtNum(v: number | null, suffix = "") {
  return v == null ? "—" : `${v}${suffix}`;
}
function fmtGdp(v: number | null) {
  if (v == null) return "—";
  return v >= 1e12 ? `$${(v / 1e12).toFixed(2)}T` : `$${(v / 1e9).toFixed(0)}B`;
}
function fmtPop(v: number | null) {
  if (v == null) return "—";
  return v >= 1e8 ? `${(v / 1e8).toFixed(2)}억` : `${(v / 1e6).toFixed(1)}M`;
}
// 음수면 빨강(경상수지 적자), 부채는 높을수록 빨강
function signColor(v: number | null, kind: "ca" | "debt" | "neutral" = "neutral") {
  if (v == null) return "#999";
  if (kind === "ca") return v < 0 ? RED : "#217346";
  if (kind === "debt") return v >= 100 ? RED : v >= 60 ? "#b8860b" : "#444";
  return "#444";
}

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

  const [warn, setWarn] = useState<CrisisWarning | null>(null);
  const [krWarn, setKrWarn] = useState<CrisisKoreaWarning | null>(null);
  const [countries, setCountries] = useState<CrisisCountries | null>(null);

  // 메타·조기경보·국가비교 1회 로드
  useEffect(() => {
    api.crisisMeta().then(setMeta).catch((e) => setErr(e?.message ?? "메타를 불러오지 못했습니다."));
    api.crisisWarning().then(setWarn).catch(() => {});
    api.crisisKoreaWarning().then(setKrWarn).catch(() => {});
    api.crisisCountries().then(setCountries).catch(() => {});
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

  // 병합 데이터셋 (day → {day, seriesKey: v, __cur_<code>: v})
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
    for (const c of sim.currents) {
      for (const p of c.points) row(p.day)[`__cur_${c.code}`] = p.v;
      for (const p of c.projection) row(p.day)[`__proj_${c.code}`] = p.v;
    }
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
        title="금융위기 예측 시뮬레이터 — 지금이 과거 위기 직전과 닮았나"
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

      {/* ── 위기 선행징후 (조기경보) ──────────────────────────── */}
      {warn && (
        <Card
          title="위기 선행징후 — 조기경보 체크"
          subtitle="거품·과열·신용·심리 등 '위기 전 증상'을 임계값·과거 위기직전 수준과 비교"
        >
          <div className="grid grid-cols-1 gap-4 md:grid-cols-[180px_1fr]">
            {/* 종합 경보 */}
            <div className="flex flex-col items-center justify-center rounded-lg border border-[#eee] bg-[#fafafa] py-4">
              <div className="text-[11px] font-semibold text-[#888]">종합 위기경보</div>
              <div className="text-4xl font-extrabold tabular-nums" style={{ color: levelColor(warn.level) }}>
                {warn.score}
              </div>
              <div
                className="mt-1 rounded-full px-3 py-0.5 text-xs font-bold text-white"
                style={{ background: levelColor(warn.level) }}
              >
                {warn.level}
              </div>
              <div className="mt-1 text-[10px] text-[#aaa]">{warn.as_of} 기준</div>
            </div>

            {/* 지표별 체크 */}
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {warn.signs.map((s) => {
                const st = STAT[s.status] ?? STAT.ok;
                return (
                  <div key={s.key} className="rounded border border-[#eee] bg-white px-3 py-2" title={s.desc}>
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-[#333]">{s.label}</span>
                      <span
                        className="rounded-full px-2 py-0.5 text-[10px] font-bold"
                        style={{ background: st.bg, color: st.fg }}
                      >
                        {st.t}
                      </span>
                    </div>
                    <div className="mt-1 flex items-baseline gap-2">
                      <span className="text-lg font-bold tabular-nums" style={{ color: st.fg }}>
                        {s.value}
                        <span className="ml-0.5 text-[11px] font-normal text-[#999]">{s.unit}</span>
                      </span>
                      {s.pre_crisis_avg != null && (
                        <span className="text-[10px] text-[#aaa]">위기직전 평균 {s.pre_crisis_avg}{s.unit}</span>
                      )}
                    </div>
                    {s.extra && <div className="mt-0.5 text-[10px] font-semibold text-rose-600">⚠ {s.extra}</div>}
                  </div>
                );
              })}
            </div>
          </div>
          <p className="mt-3 text-[11px] leading-relaxed text-[#999]">{warn.note}</p>
        </Card>
      )}

      {/* ── 한국 외환위기 선행징후 (김대종 교수 프레임) ──────────── */}
      {krWarn && (
        <Card
          title="한국 외환위기 선행징후 — 제2의 IMF?"
          subtitle={krWarn.frame}
        >
          <div className="grid grid-cols-1 gap-4 md:grid-cols-[180px_1fr]">
            <div className="flex flex-col items-center justify-center rounded-lg border border-[#eee] bg-[#fafafa] py-4">
              <div className="text-[11px] font-semibold text-[#888]">외환위기 경보</div>
              <div className="text-4xl font-extrabold tabular-nums" style={{ color: levelColor(krWarn.level) }}>
                {krWarn.score}
              </div>
              <div
                className="mt-1 rounded-full px-3 py-0.5 text-xs font-bold text-white"
                style={{ background: levelColor(krWarn.level) }}
              >
                {krWarn.level}
              </div>
              <div className="mt-1 text-[10px] text-[#aaa]">{krWarn.as_of} 기준</div>
            </div>

            <div className="space-y-2">
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {krWarn.signs.map((s) => {
                  const st = STAT[s.status] ?? STAT.ok;
                  return (
                    <div key={s.key} className="rounded border border-[#eee] bg-white px-3 py-2" title={s.desc}>
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-[#333]">{s.label}</span>
                        <span className="rounded-full px-2 py-0.5 text-[10px] font-bold" style={{ background: st.bg, color: st.fg }}>
                          {st.t}
                        </span>
                      </div>
                      <div className="mt-1 flex items-baseline gap-2">
                        <span className="text-lg font-bold tabular-nums" style={{ color: st.fg }}>
                          {s.value.toLocaleString()}
                          <span className="ml-0.5 text-[11px] font-normal text-[#999]">{s.unit}</span>
                        </span>
                        {s.benchmark != null && (
                          <span className="text-[10px] text-[#aaa]">교수 기준선 {s.benchmark}{s.unit}</span>
                        )}
                      </div>
                      {(s.as_of || s.source) && (
                        <div className="mt-0.5 text-[10px] text-[#aaa]">
                          {s.as_of} {s.source ? `· ${s.source}` : ""}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              {/* 통화스와프 */}
              <div className="flex flex-wrap gap-2">
                {krWarn.swaps.map((sw) => {
                  const st = STAT[sw.status] ?? STAT.ok;
                  return (
                    <span
                      key={sw.label}
                      title={sw.note}
                      className="rounded border px-2 py-1 text-[11px] font-semibold"
                      style={{ background: st.bg, color: st.fg, borderColor: st.bg }}
                    >
                      {sw.label}: {st.t}
                    </span>
                  );
                })}
              </div>
            </div>
          </div>
          <p className="mt-3 text-[11px] leading-relaxed text-[#c0392b]">⚠ {krWarn.note}</p>
        </Card>
      )}

      {/* ── 주요국 거시지표 비교표 ────────────────────────────── */}
      {countries && countries.countries.length > 0 && (
        <Card title="주요국 거시지표 비교" subtitle="한국 vs 주요 경제국 — GDP·성장률·금리·물가·실업·부채·경상수지·인구">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[#e0e0e0] text-[#888]">
                  <th className="px-2 py-1.5 text-left font-semibold">국가</th>
                  <th className="px-2 py-1.5 text-right font-semibold">GDP</th>
                  <th className="px-2 py-1.5 text-right font-semibold">성장률</th>
                  <th className="px-2 py-1.5 text-right font-semibold">금리</th>
                  <th className="px-2 py-1.5 text-right font-semibold">물가</th>
                  <th className="px-2 py-1.5 text-right font-semibold">실업률</th>
                  <th className="px-2 py-1.5 text-right font-semibold">부채/GDP</th>
                  <th className="px-2 py-1.5 text-right font-semibold">경상수지</th>
                  <th className="px-2 py-1.5 text-right font-semibold">인구</th>
                </tr>
              </thead>
              <tbody>
                {countries.countries.map((r) => {
                  const isKR = r.iso === "KR";
                  return (
                    <tr
                      key={r.iso}
                      className={`border-b border-[#f0f0f0] ${isKR ? "bg-[#f6fbf8] font-semibold" : "hover:bg-[#fafafa]"}`}
                    >
                      <td className="px-2 py-1.5 text-left">
                        {isKR && <span className="mr-1 text-[#217346]">★</span>}
                        {r.country}
                      </td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{fmtGdp(r.gdp_usd)}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums" style={{ color: signColor(r.gdp_growth) }}>
                        {fmtNum(r.gdp_growth, "%")}
                      </td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{fmtNum(r.rate, "%")}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{fmtNum(r.cpi, "%")}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{fmtNum(r.unemployment, "%")}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums" style={{ color: signColor(r.debt_gdp, "debt") }}>
                        {fmtNum(r.debt_gdp, "%")}
                      </td>
                      <td className="px-2 py-1.5 text-right tabular-nums" style={{ color: signColor(r.current_account, "ca") }}>
                        {r.current_account == null ? "—" : `${r.current_account > 0 ? "+" : ""}${r.current_account}%`}
                      </td>
                      <td className="px-2 py-1.5 text-right tabular-nums text-[#666]">{fmtPop(r.population)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-[#999]">{countries.note}</p>
        </Card>
      )}

      {loading && !sim ? (
        <div className="flex items-center justify-center gap-2 py-24 text-sm text-[#888]">
          <Spinner /> 시계열을 불러오는 중…
        </div>
      ) : !sim || sim.series.length === 0 ? (
        <Empty>이 지표·위기 조합에 표시할 데이터가 없습니다. 다른 위기를 선택해 보세요.</Empty>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {/* ── 메인 차트 ─────────────────────────────────────── */}
          <Card title="현재 위치 + 예상 시나리오 — 과거 위기에 포개기 (Day0=발발)" className="lg:col-span-2">
            <div className="h-[420px] w-full">
              <ResponsiveContainer>
                <LineChart data={shown} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                  <XAxis
                    dataKey="day"
                    type="number"
                    domain={[minDay, maxDay]}
                    tick={{ fontSize: 11, fill: "#888" }}
                    tickFormatter={(d) => (d === 0 ? "위기" : d < 0 ? `${-d}일전` : `+${d}일`)}
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
                    formatter={(val, name) => [Number(val).toFixed(1), String(name)]}
                  />
                  <ReferenceLine x={0} stroke="#c92a2a" strokeWidth={1.5} label={{ value: "⚠ 위기 발발", fontSize: 11, fill: "#c92a2a", position: "insideTopRight" }} />
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
                  {sim.currents.map((c) => (
                    <Line
                      key={`cur_${c.code}`}
                      type="monotone"
                      dataKey={`__cur_${c.code}`}
                      name={`${c.name} (현재)`}
                      stroke={c.color}
                      strokeWidth={3}
                      dot={false}
                      isAnimationActive={false}
                      connectNulls
                    />
                  ))}
                  {sim.currents.map((c) => (
                    <Line
                      key={`proj_${c.code}`}
                      type="monotone"
                      dataKey={`__proj_${c.code}`}
                      name={`${c.name} (예상 시나리오)`}
                      stroke={c.color}
                      strokeWidth={2}
                      strokeDasharray="3 4"
                      strokeOpacity={0.5}
                      dot={false}
                      isAnimationActive={false}
                      connectNulls
                    />
                  ))}
                  {/* '오늘' 마커 — 현재 시점이 위기선(0)에서 얼마나 떨어져 있는지 */}
                  {sim.currents.map((c) => {
                    const last = c.points[c.points.length - 1];
                    if (!last || last.day > frame) return null;
                    const lead = c.best?.lead_days ?? 0;
                    const tag = lead > 0 ? `오늘 · 위기 D-${lead}` : "오늘";
                    return (
                      <ReferenceDot
                        key={`now_${c.code}`}
                        x={last.day}
                        y={last.v}
                        r={4.5}
                        fill={c.color}
                        stroke="#fff"
                        strokeWidth={1.5}
                        label={{ value: tag, fontSize: 10, fill: c.color, position: "top" }}
                      />
                    );
                  })}
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-2 text-[11px] text-[#999]">
              굵은 실선 = 현재 궤적을 <b>가장 닮은 과거 위기의 같은 시점</b>에 포갠 것. 점선 = 그 위기가 그 뒤
              간 길(<b>예상 시나리오</b>). Day 0 = 위기 발발. 0 왼쪽이면 아직 위기 전.
            </p>
          </Card>

          {/* ── 위기 예측(아날로그) 패널 ─────────────────────────── */}
          <Card title="위기 시계 — 지금은 어느 위기의 며칠 전과 닮았나" subtitle="현재 패턴을 과거 위기 타임라인에 맞춰 '위기까지 남은 거리'를 추정">
            {sim.currents.length === 0 ? (
              <Empty>현재 궤적을 만들 데이터가 없습니다.</Empty>
            ) : (
              <div className="space-y-4">
                {sim.currents.map((c) => {
                  const b = c.best;
                  const warning = !!b && b.lead_days > 0; // 아직 위기 전 = 경고
                  return (
                    <div key={c.code} className="space-y-2">
                      <div className="flex items-center gap-1.5 text-xs font-bold text-[#333]">
                        <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: c.color }} />
                        {c.name}
                        {!c.same_instrument && (
                          <span className="rounded-full bg-[#f0f0f0] px-2 py-0.5 text-[10px] font-bold text-[#888]">교차</span>
                        )}
                      </div>

                      {!b ? (
                        <div className="rounded border border-dashed border-[#ddd] bg-[#fafafa] px-3 py-2 text-[11px] text-[#999]">
                          비교할 과거 위기 곡선이 없습니다.
                        </div>
                      ) : (
                        <>
                          <button
                            onMouseEnter={() => setFocus(`${b.crisis}__${c.code}`)}
                            onMouseLeave={() => setFocus(null)}
                            className={`block w-full rounded border px-3 py-2 text-left transition ${
                              warning ? "border-[#f1aeae] bg-[#fdf3f3]" : "border-[#e6e6e6] bg-white"
                            } hover:border-[#217346]`}
                          >
                            <div className="flex items-center justify-between">
                              <span
                                className="rounded px-2 py-0.5 text-xs font-extrabold tabular-nums"
                                style={{
                                  background: warning ? "#fdecec" : "#eef2f7",
                                  color: warning ? RED : "#5a6b7b",
                                }}
                              >
                                {warning ? `위기까지 D-${b.lead_days}` : "회복기 구간"}
                              </span>
                              <span className="text-[11px] tabular-nums text-[#888]">상관 {b.corr.toFixed(2)}</span>
                            </div>
                            <div className="mt-1 text-[11px] text-[#666]">
                              {b.phase} · 가장 닮은 위기 <b>{b.crisis_label}</b>
                            </div>
                            {b.expected_pct != null && (
                              <div className="mt-1 text-[11px]">
                                역사 반복 시 향후 {b.horizon}일{" "}
                                <b style={{ color: depthColor(b.expected_pct, dir) }}>{fmtDepth(b.expected_pct)}</b>
                              </div>
                            )}
                          </button>
                          {/* 다른 후보 위기들 */}
                          <div className="flex flex-wrap gap-1">
                            {c.analogs.slice(1, 4).map((a) => (
                              <span
                                key={a.crisis}
                                onMouseEnter={() => setFocus(`${a.crisis}__${c.code}`)}
                                onMouseLeave={() => setFocus(null)}
                                className="cursor-default rounded border border-[#eee] bg-[#fafafa] px-1.5 py-0.5 text-[10px] text-[#888]"
                              >
                                {a.crisis_label.split(" ")[0]} {a.phase} ({a.corr.toFixed(2)})
                              </span>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  );
                })}
                <p className="text-[11px] leading-relaxed text-[#999]">
                  현재 최근 구간을 과거 위기 타임라인 위로 밀어 가장 잘 겹치는 위치를 찾습니다.
                  <b className="text-rose-600">“위기 N일 전”</b>이면 그 위기 직전과 닮았다는 뜻(경고),
                  “위기 후”면 회복기 모양에 가깝습니다. <b>과거 패턴 반복을 가정한 참고치이며 미래를 단정하지 않습니다.</b>
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
