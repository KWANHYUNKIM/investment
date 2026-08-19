"use client";

import { useSyncExternalStore } from "react";

/** 관심단지(★) — localStorage 에 남는다. 렌더 중 window 를 직접 읽으면 SSR 과
 *  어긋나므로 ExcelGrid 의 useIsPhone 과 같이 구독 형태로 읽는다. */

const KEY = "re:favs";
const listeners = new Set<() => void>();
const EMPTY: ReadonlySet<string> = new Set<string>();
let cache: Set<string> | null = null;

function read(): Set<string> {
  if (cache) return cache;
  try {
    cache = new Set(JSON.parse(localStorage.getItem(KEY) ?? "[]") as string[]);
  } catch {
    cache = new Set();
  }
  return cache;
}

export function useFavs(): ReadonlySet<string> {
  return useSyncExternalStore(
    (cb) => { listeners.add(cb); return () => { listeners.delete(cb); }; },
    read,
    () => EMPTY,
  );
}

export function toggleFav(key: string): void {
  const next = new Set(read());
  if (next.has(key)) next.delete(key);
  else next.add(key);
  cache = next;
  try {
    localStorage.setItem(KEY, JSON.stringify([...next]));
  } catch {
    /* 저장 실패(사생활 모드·용량)는 이번 세션에서만 유지하고 넘어간다 */
  }
  listeners.forEach((l) => l());
}
