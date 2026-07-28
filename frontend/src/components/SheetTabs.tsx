"use client";

import { useEffect, useRef } from "react";

export type SheetTabItem = { id: string; label: string };

/**
 * 하단 시트탭 = 폰의 내비게이션.
 *
 * 엑셀에서 화면을 옮기는 방법은 원래 하단 시트탭이고, 폰에서 화면을 옮기는 방법도 원래
 * 하단 탭이다. 둘은 같은 물건이라 하나로 합쳤다. 좌상단 햄버거를 쓰지 않는 이유는 셋이다.
 *  1. 엄지가 좌상단에 닿지 않는다. 하단은 닿는다.
 *  2. 시트가 20장이 넘어도 한 세션에 오가는 건 서너 장이라, 자주 쓰는 것에 0탭 접근을 주고
 *     나머지는 우측 ⊞(전체 목록)로 보내는 편이 낫다 — 엑셀이 시트를 다루는 방식 그대로다.
 *  3. 햄버거+드로어는 '앱'의 실루엣이다. 이 앱은 회사에서 열어도 스프레드시트로 보여야 하므로
 *     (layout.tsx 의 제목 참고) 앱처럼 생기는 것 자체가 결함이다.
 */
export function SheetTabs({
  items,
  active,
  onPick,
  onOpenAll,
}: {
  items: SheetTabItem[];
  active: string;
  onPick: (id: string) => void;
  onOpenAll: () => void;
}) {
  const activeRef = useRef<HTMLButtonElement>(null);

  // 시트를 바꾸면 그 탭이 보이도록 가로로 따라간다. 이 앱의 유일한 모션이다 —
  // 엑셀은 애니메이션하지 않으므로 탭 전환·페이드 따위는 전부 뺐다.
  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    activeRef.current?.scrollIntoView({
      block: "nearest",
      inline: "center",
      behavior: reduce ? "auto" : "smooth",
    });
  }, [active]);

  const idx = items.findIndex((i) => i.id === active);
  const step = (d: number) => {
    const next = items[idx + d];
    if (next) onPick(next.id);
  };

  const arrow =
    "flex h-11 w-8 shrink-0 items-center justify-center text-[11px] text-[#5a6b60] disabled:text-[#c4c4c4]";

  return (
    /* 홈 인디케이터가 있는 기기에서 탭이 그 아래 깔리지 않게 안전영역만큼 바닥을 띄운다. */
    <nav
      aria-label="시트"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      className="flex shrink-0 items-stretch border-t border-[#d0d0d0] bg-[#f3f2f1] lg:hidden"
    >
      <button onClick={() => step(-1)} disabled={idx <= 0} aria-label="이전 시트" className={arrow}>
        ◀
      </button>
      <button
        onClick={() => step(1)}
        disabled={idx < 0 || idx >= items.length - 1}
        aria-label="다음 시트"
        className={`${arrow} border-r border-[#d0d0d0]`}
      >
        ▶
      </button>

      <div className="no-scrollbar flex flex-1 items-stretch overflow-x-auto">
        {items.map((it) => {
          const on = it.id === active;
          return (
            <button
              key={it.id}
              ref={on ? activeRef : undefined}
              onClick={() => onPick(it.id)}
              aria-current={on ? "page" : undefined}
              className={`relative h-11 shrink-0 whitespace-nowrap border-r border-[#e2e2e2] px-3.5 text-[12px] ${
                on ? "bg-white font-bold text-[#217346]" : "text-[#4a4a4a]"
              }`}
            >
              {/* 활성 시트의 초록 띠. 엑셀은 탭 아래에 긋지만 여기선 탭이 화면 바닥에 있으므로
                  위에 그어 내용 쪽을 가리키게 한다. */}
              {on && <span aria-hidden className="absolute inset-x-0 top-0 h-[3px] bg-[#217346]" />}
              {it.label}
            </button>
          );
        })}
      </div>

      <button
        onClick={onOpenAll}
        aria-label="모든 시트"
        className="flex h-11 w-11 shrink-0 items-center justify-center border-l border-[#d0d0d0] text-base text-[#5a6b60]"
      >
        ⊞
      </button>
    </nav>
  );
}
