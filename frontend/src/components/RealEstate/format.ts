// 네이버 부동산 표기 규칙 — 가격은 "12억 5,000", 면적은 ㎡/평 토글.

import type { RealEstateApartment, TradeKind } from "@/lib/api";

/** 억 단위 실수 → 네이버식 "12억 5,000" / "9,500" (1억 미만) */
export function eok(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  const manwon = Math.round(v * 10000);
  const 억 = Math.floor(manwon / 10000);
  const 나머지 = manwon % 10000;
  if (억 === 0) return 나머지.toLocaleString();
  if (나머지 === 0) return `${억}억`;
  return `${억}억 ${나머지.toLocaleString()}`;
}

/** 마커처럼 좁은 곳에서 쓰는 짧은 표기 — "12.5억" */
export function eokShort(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  if (v >= 100) return `${Math.round(v)}억`;
  return `${Number(v.toFixed(1))}억`;
}

/** 만원 단위 월세 → "150" (만원은 호출부에서 붙인다) */
export function manwon(v: number | null | undefined): string {
  if (!v) return "—";
  return v.toLocaleString();
}

const PYEONG = 3.305785;

/** 전용면적 표기. unit="pyeong"이면 평으로 환산(내림 없이 반올림). */
export function area(m2: number | null | undefined, unit: AreaUnit): string {
  if (m2 == null) return "—";
  return unit === "pyeong" ? `${Math.round(m2 / PYEONG)}평` : `${m2}㎡`;
}

export type AreaUnit = "m2" | "pyeong";

export function toPyeong(m2: number): number {
  return m2 / PYEONG;
}

/** 거래유형별 라벨/색 — 매매 초록, 전세 파랑, 월세 주황(네이버와 같은 위계) */
export const TRADE_META: Record<TradeKind, { label: string; color: string; soft: string }> = {
  sale: { label: "매매", color: "#217346", soft: "#eef6f0" },
  jeonse: { label: "전세", color: "#1a63c4", soft: "#eaf1fb" },
  wolse: { label: "월세", color: "#d9480f", soft: "#fdf0e8" },
};

/** 마커·카드에 찍는 대표 가격 문자열. 월세는 "보증금/월세". */
export function headlinePrice(a: RealEstateApartment, trade: TradeKind): string {
  if (trade === "wolse") {
    return `${eokShort(a.recent_eok)}/${manwon(a.monthly_recent)}`;
  }
  return eokShort(a.recent_eok);
}

/** 목록 카드의 가격 범위 — 최저~최고가 같으면 하나만. */
export function priceRange(a: RealEstateApartment, trade: TradeKind): string {
  if (trade === "wolse") {
    const dep = a.min_eok === a.max_eok ? eok(a.recent_eok) : `${eok(a.min_eok)}~${eok(a.max_eok)}`;
    const m =
      a.monthly_min === a.monthly_max
        ? manwon(a.monthly_recent)
        : `${manwon(a.monthly_min)}~${manwon(a.monthly_max)}`;
    return `${dep} / ${m}`;
  }
  return a.min_eok === a.max_eok ? eok(a.recent_eok) : `${eok(a.min_eok)} ~ ${eok(a.max_eok)}`;
}

/** 준공년도 → "n년차" (네이버 단지 카드 표기) */
export function buildAge(buildYear: string | null | undefined): string | null {
  const y = Number(buildYear);
  if (!y || y < 1900) return null;
  const age = new Date().getFullYear() - y;
  return age <= 0 ? "신축" : `${age}년차`;
}
