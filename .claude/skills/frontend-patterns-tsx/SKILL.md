---
name: frontend-patterns-tsx
description: 이 저장소(Next 16 · React 19 · Tailwind v4)에서 실제로 동작하는 .tsx 프론트 패턴. 컴포넌트 합성, 데이터 로딩, 반응형 셸, 틀 고정 그리드, 성능, 접근성. affaan-m/ECC 의 frontend-patterns 를 이 스택에 맞게 다시 씀.
---

# 프론트 패턴 (.tsx)

원본 `frontend-patterns` 는 스택 중립적인 React 문서라 이 저장소에 그대로 넣으면
**설치되지 않은 라이브러리**를 부르거나 **lint 를 통과하지 못하는** 코드가 된다.
여기 있는 것은 전부 이 저장소에서 실제로 쓰이거나 검증된 형태다.

## 언제 쓰나

- 컴포넌트를 새로 만들거나 쪼갤 때 (합성, 복합 컴포넌트)
- 백엔드에서 데이터를 받아올 때
- 화면 폭에 따라 배치가 달라져야 할 때 (사이드바·상세 패널·목록)
- 표가 길거나 넓어서 성능·가독성이 문제될 때
- 폼 입력과 검증
- 키보드·포커스 접근성

## 개인정보 경계

예제에는 합성 데이터나 도메인 일반 데이터만 쓴다. 자격증명, 액세스 토큰, 주민번호,
건강 정보, 결제 정보, 개인 이메일·전화번호를 수집·기록·저장·표시하지 않는다.
사용자가 명시적으로 요청한 경우에만, 검증·마스킹·접근 제어를 갖춘 범위로 한정해 구현한다.

분석 도구, 트래킹 픽셀, 서드파티 스크립트, 외부 데이터 전송은 승인 없이 추가하지 않는다.
사용자 데이터를 다룰 때는 최소 권한 API, 기록 전 클라이언트 마스킹, 모든 경계에서의
서버 검증을 우선한다.

## 이 저장소의 전제

**있는 것**: `next@16`, `react@19`, `tailwindcss@4`, `recharts`, `leaflet`/`react-leaflet`

**없는 것** — 원본 문서가 부르지만 여기엔 설치되어 있지 않다:
`framer-motion`, `@tanstack/react-virtual`, `zod`, `swr`, `@tanstack/react-query`, `zustand`

없는 것을 쓰려면 먼저 설치 여부를 사용자에게 확인한다. 아래에는 각각의 대체 패턴이 있다.

**코드 펜스는 ` ```tsx `** 를 쓴다. JSX 가 든 코드를 ` ```typescript ` 로 표시하면
하이라이팅이 깨진다 (원본 문서의 15개 블록이 전부 이 문제를 갖고 있다).

---

## 컴포넌트 합성

클래스명은 Tailwind 유틸리티로 쓴다. 이 저장소에는 `card`, `tab-list` 같은 전역 CSS 클래스가 없다.

```tsx
export function Card({ title, subtitle, children, className = "" }: {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`overflow-hidden rounded-md border border-[#d0d0d0] bg-white shadow-sm ${className}`}>
      {title && (
        <div className="border-b border-[#d0d0d0] bg-[#f3f2f1] px-4 py-2">
          <h3 className="text-sm font-bold tracking-tight text-[#217346]">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-[#888]">{subtitle}</p>}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  );
}
```

이미 `@/components/ui` 에 `Card`·`Field`·`Input`·`Select`·`Button`·`Spinner`·`ErrorBox`·`Stat`·`Empty`
가 있다. 새로 만들기 전에 거기부터 본다.

### 복합 컴포넌트 (Context 로 상태 공유)

```tsx
"use client";

import { createContext, useContext, useState } from "react";

type TabsValue = { active: string; setActive: (t: string) => void };
const TabsContext = createContext<TabsValue | null>(null);

export function Tabs({ defaultTab, children }: { defaultTab: string; children: React.ReactNode }) {
  const [active, setActive] = useState(defaultTab);
  return <TabsContext.Provider value={{ active, setActive }}>{children}</TabsContext.Provider>;
}

export function Tab({ id, children }: { id: string; children: React.ReactNode }) {
  const ctx = useContext(TabsContext);
  if (!ctx) throw new Error("Tab 은 Tabs 안에서만 쓴다");
  const on = ctx.active === id;
  return (
    <button
      onClick={() => ctx.setActive(id)}
      className={`shrink-0 whitespace-nowrap border border-b-0 px-4 py-1.5 text-xs ${
        on ? "border-[#d0d0d0] bg-white font-semibold text-[#217346]" : "border-transparent text-[#666] hover:bg-[#e8e8e8]"
      }`}
    >
      {children}
    </button>
  );
}
```

`shrink-0 whitespace-nowrap` 이 중요하다. 없으면 좁은 화면에서 탭이 눌려 **글자가 세로로
쪼개진다**. 탭 줄을 감싸는 쪽에 `overflow-x-auto` 를 준다.

---

## 데이터 로딩

### 이 저장소의 표준형 — `alive` 플래그

30개 파일이 이 형태를 쓴다. 언마운트 후 `setState` 를 막는다.

```tsx
"use client";

import { useEffect, useState } from "react";
import { api, CrossAssetLayer } from "@/lib/api";

export function IndexStrip() {
  const [data, setData] = useState<CrossAssetLayer | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      api.crossAsset()
        .then((d) => { if (alive) setData(d); })
        .catch(() => { /* 직전 값 유지 */ });
    load();
    const id = setInterval(load, 30000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  if (!data) return null;
  return <div>{/* … */}</div>;
}
```

### 원본의 `useQuery` 를 그대로 쓰면 안 되는 이유

원본 문서의 범용 `useQuery` 는 이펙트 안에서 `refetch()` 를 부르고, `refetch` 는
곧바로 `setLoading(true)` 를 호출한다. 이 저장소의 ESLint 는 그걸 **에러로 막는다**:

```
react-hooks/set-state-in-effect
  Avoid calling setState() directly within an effect
```

이미 저장소에 이 규칙 위반이 30건 넘게 쌓여 있다. 새 코드로 더 늘리지 않는다.
비동기 결과는 `.then()` **콜백 안에서** 넣고, 로딩 상태가 꼭 필요하면 초기값을
`useState(true)` 로 두고 이펙트 안에서 켜지 말고 끄기만 한다.

```tsx
// 로딩 플래그가 필요할 때
const [loading, setLoading] = useState(true);   // 켜진 채로 시작
useEffect(() => {
  let alive = true;
  api.screenTable()
    .then((r) => { if (alive) setRows(r); })
    .catch((e) => { if (alive) setErr(e?.message ?? "불러오지 못했습니다."); })
    .finally(() => { if (alive) setLoading(false); });   // 끄기만 한다
  return () => { alive = false; };
}, []);
```

SWR·React Query 는 설치되어 있지 않다. 필요하면 먼저 물어본다.

---

## 커스텀 훅

### 화면 폭 읽기 — 렌더 중 `window` 금지

렌더 도중 `window.matchMedia` 를 읽으면 SSR 결과와 클라이언트 첫 렌더가 어긋난다.
`useSyncExternalStore` 로 구독하고, 서버 스냅샷은 데스크톱으로 고정한다.

```tsx
"use client";

import { useSyncExternalStore } from "react";
import { mq } from "@/lib/breakpoints";

export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (cb) => {
      const m = window.matchMedia(query);
      m.addEventListener("change", cb);
      return () => m.removeEventListener("change", cb);
    },
    () => window.matchMedia(query).matches,
    () => false,        // 서버: 데스크톱으로 가정
  );
}

// 사용
const phone = useMediaQuery(mq.phone);
```

기준값은 **반드시 `@/lib/breakpoints`** 에서 가져온다. `BP.phone/nav/detail` 이
Tailwind 의 `sm`/`lg`/`xl` 과 같은 값으로 맞춰져 있다. 숫자를 컴포넌트에 직접 적으면
CSS 쪽 변형과 언젠가 어긋난다.

**JS 로 읽어야 할 때만** 이 훅을 쓴다. 배치만 바뀐다면 CSS 변형(`lg:` 등)이 낫다 —
훅은 리렌더를 부르고 SSR 불일치 위험이 있다. JS 가 필요한 경우는 열 개수처럼
**렌더 결과의 구조 자체가 달라질 때**다.

### 디바운스

```tsx
export function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setV(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return v;
}
```

---

## 반응형 셸 — 고정폭 패널

고정폭 사이드 패널은 좁은 화면에서 **흐름에서 빼고 덮는 방식**으로 바꾼다.
폭이 각각 다른 제약에서 나오므로 브레이크포인트도 다르다(`@/lib/breakpoints` 참고).

```tsx
// 좌측 네비: <lg 드로어 / ≥lg 상주
<aside
  className={[
    "z-40 flex flex-col border-r border-[#d7ddd9] bg-[#f3f5f4]",
    "transition-transform duration-200 motion-reduce:transition-none",
    "fixed inset-y-0 left-0 w-64 overflow-y-auto py-1.5 shadow-xl",
    open ? "translate-x-0" : "invisible -translate-x-full",
    "lg:visible lg:static lg:z-auto lg:translate-x-0 lg:shadow-none lg:w-52 lg:shrink-0",
  ].join(" ")}
>
```

- `invisible` 을 같이 주는 이유: `-translate-x-full` 만으로는 화면 밖의 링크가 여전히
  **탭 순서에 남는다**.
- 백드롭은 `fixed inset-0 z-30 bg-black/40 lg:hidden`, ESC 로도 닫는다.
- 항목을 고르면 드로어를 닫는다. 안 그러면 고른 화면이 가려진 채로 남는다.

### 목록 + 상세는 좁을 때 위아래로 쌓는다

```tsx
<div className="flex min-h-[70dvh] flex-col lg:flex-row">
  <aside className="flex max-h-[45dvh] w-full shrink-0 flex-col border-b lg:max-h-none lg:w-[330px] lg:border-b-0 lg:border-r">
    …목록(자체 스크롤)…
  </aside>
  <div className="min-w-0 flex-1 overflow-x-auto p-4">…상세…</div>
</div>
```

### 반드시 지킬 두 가지

**`min-w-0`** — 가로 플렉스 안에서 넓은 내용(표·그리드)을 담는 아이템에는 항상 붙인다.
플렉스 아이템 기본값이 `min-width: auto` 라서, 없으면 내용 폭만큼 부풀어 **뷰포트 밖으로
밀려 나가고 바깥 `overflow-hidden` 이 그걸 잘라버린다**. 스크롤로도 볼 수 없게 된다.

**`dvh`** — 높이에는 `vh` 대신 `dvh` 를 쓴다. 모바일 브라우저 주소창이 접히고 펴질 때
`100vh` 는 화면보다 커져서 아래가 잘린다. 셸은 `h-dvh`, 카드 내부 스크롤은
`max-h-[70dvh] sm:max-h-[calc(100dvh-190px)]`.

---

## 성능

### 목록은 잘라 렌더하고 "더보기"

`@tanstack/react-virtual` 은 설치되어 있지 않다. 이 저장소는 `limit` 상태로 자른다.

```tsx
const [limit, setLimit] = useState(200);
const shown = view.slice(0, limit);

{limit < view.length && (
  <button onClick={() => setLimit((l) => l + 400)} className="w-full py-2.5 text-sm text-[#217346]">
    더보기 ({(view.length - limit).toLocaleString("ko-KR")}행 남음)
  </button>
)}
```

정렬·검색·필터를 바꾸면 `setLimit(200)` 으로 되돌린다. 안 그러면 3,000행이 그대로 남는다.

### 파생값은 `useMemo`, 무거운 컴포넌트는 코드 분할

```tsx
const view = useMemo(() => rows.filter(…).sort(…), [rows, q, sortKey, desc]);
```

App Router 에서는 `React.lazy` 대신 `next/dynamic` 을 쓴다. 브라우저 API 를 만지는
라이브러리(leaflet 등)는 `ssr: false` 가 필요하다.

```tsx
import dynamic from "next/dynamic";

const MapInner = dynamic(() => import("@/components/RealEstateMapInner"), {
  ssr: false,
  loading: () => <div className="py-24 text-center text-sm text-[#888]">지도 불러오는 중…</div>,
});
```

### 넓은 표는 첫 열을 고정한다 (틀 고정)

`position: sticky` 로 붙인다. 세 가지를 놓치기 쉽다.

1. **고정 블록은 그룹 헤더 경계와 정확히 일치해야 한다.** 헤더 한 칸이 여러 열을 덮으면
   그 칸을 절반만 고정할 수 없다. 이 저장소는 종목명을 첫 열로 옮기고 자기 전용 그룹을
   줘서 해결했다.
2. **배경이 불투명해야 한다.** 투명하면 밑을 지나가는 셀이 비친다. 반투명 색
   (`${bg}66`)을 쓰던 자리는 흰색에 미리 섞어 불투명 값으로 바꾼다.
3. **행 hover 를 직접 못 받는다.** 자기 배경이 행 배경을 덮기 때문. 행에 `group`,
   고정 셀에 `group-hover:` 를 준다.

```tsx
<div className="group flex hover:bg-[#fff7e6]">
  <div
    style={{ width: 168, left: gutter }}
    className="sticky z-10 flex shrink-0 items-center bg-white px-2 group-hover:bg-[#fff7e6]"
  >
    {row.name}
  </div>
  {/* 나머지 열 */}
</div>
```

폭이 좁을 때 열 자체를 줄이려면 CSS 로 숨기지 말고 **배열에서 뺀다**. 전체 폭과
sticky 오프셋을 JS 로 계산하기 때문에, CSS 로만 숨기면 빈 공간이 남는다.

```tsx
const cols = useMemo(() => (phone ? COLS.filter((c) => !PHONE_HIDDEN.has(c.key)) : COLS), [phone]);
const totalW = gutter + cols.reduce((a, c) => a + colW(c), 0);
```

---

## 폼

Zod 는 설치되어 있지 않다. 검증은 손으로 쓴다.

```tsx
type Form = { name: string; amount: string };
type Errors = Partial<Record<keyof Form, string>>;

export function AddForm({ onDone }: { onDone: () => void }) {
  const [form, setForm] = useState<Form>({ name: "", amount: "" });
  const [errors, setErrors] = useState<Errors>({});
  const [busy, setBusy] = useState(false);

  const validate = (): boolean => {
    const e: Errors = {};
    if (!form.name.trim()) e.name = "이름을 입력하세요";
    if (!/^\d+$/.test(form.amount)) e.amount = "숫자만 입력하세요";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!validate() || busy) return;
    setBusy(true);
    try {
      await api.budgetAdd({ name: form.name, amount: Number(form.amount) });
      onDone();
    } catch (err) {
      setErrors({ name: err instanceof Error ? err.message : "저장하지 못했습니다" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <label className="flex flex-col gap-1.5">
        <span className="text-xs font-semibold text-[#555]">이름</span>
        <input
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          aria-invalid={!!errors.name}
          className="rounded border border-[#bdbdbd] px-3 py-2 text-sm outline-none focus:border-[#217346]"
        />
        {errors.name && <span className="text-xs text-rose-600">{errors.name}</span>}
      </label>
      <button type="submit" disabled={busy} className="rounded bg-[#217346] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
        {busy ? "저장 중…" : "저장"}
      </button>
    </form>
  );
}
```

오류 문구는 무엇이 잘못됐고 어떻게 고치는지 적는다. 사과하지 않고, 모호하게 쓰지 않는다.
버튼 이름은 동작 전후로 같은 말을 쓴다 ("저장" → "저장했습니다", "제출" 아님).

---

## 오류 경계

App Router 에서는 클래스 컴포넌트를 직접 만들지 말고 `error.tsx` 를 쓴다.
Next 가 알아서 경계로 감싼다.

```tsx
// src/app/error.tsx
"use client";

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="flex h-dvh flex-col items-center justify-center gap-3 p-6 text-center">
      <p className="text-sm text-[#333]">화면을 그리지 못했습니다.</p>
      <p className="max-w-md text-xs text-[#888]">{error.message}</p>
      <button onClick={reset} className="rounded bg-[#217346] px-4 py-2 text-sm font-semibold text-white">
        다시 시도
      </button>
    </div>
  );
}
```

한 카드만 실패해도 되는 경우는 경계 대신 컴포넌트 안에서 `err` 상태로 처리한다 —
이 저장소가 쓰는 방식이다.

---

## 애니메이션

`framer-motion` 은 설치되어 있지 않다. Tailwind 전환으로 충분하다.

```tsx
className="transition-transform duration-200 motion-reduce:transition-none"
```

`motion-reduce:` 를 빼지 않는다. 운영체제에서 모션 줄이기를 켠 사용자에게는 전환이
멀미를 유발한다. 이 저장소의 드로어·시트가 전부 이 형태다.

들어오고 나가는 요소를 애니메이션하려면 요소를 DOM 에 남긴 채 `translate` 와
`invisible` 을 토글한다. 조건부 렌더(`{open && …}`)는 나가는 전환을 만들 수 없다.

---

## 접근성

### 키보드

```tsx
const onKeyDown = (e: React.KeyboardEvent) => {
  if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => Math.min(i + 1, items.length - 1)); }
  else if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
  else if (e.key === "Enter") { e.preventDefault(); onSelect(items[active]); }
  else if (e.key === "Escape") { setOpen(false); }
};
```

덮는 요소(드로어·시트·모달)는 ESC 로 닫는다. 이 저장소는 `window` 리스너로 건다.

```tsx
useEffect(() => {
  if (!open) return;
  const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
  window.addEventListener("keydown", onKey);
  return () => window.removeEventListener("keydown", onKey);
}, [open]);
```

### 포커스

열 때 이전 포커스를 저장하고 닫을 때 되돌린다.

```tsx
const prevFocus = useRef<HTMLElement | null>(null);
useEffect(() => {
  if (open) {
    prevFocus.current = document.activeElement as HTMLElement;
    dialogRef.current?.focus();
  } else {
    prevFocus.current?.focus();
  }
}, [open]);
```

토글 버튼에는 `aria-expanded`, 덮는 패널에는 `role="dialog" aria-modal="true" tabIndex={-1}`,
장식용 백드롭에는 `aria-hidden` 을 준다.

---

## 확인 방법

창이 최대화되어 있으면 브라우저 도구로 폭을 줄일 수 없다. 같은 오리진에 **iframe 으로
앱을 띄우면** 그 iframe 폭으로 CSS 미디어쿼리가 평가된다.

```js
const f = document.createElement("iframe");
f.style.cssText = "width:390px;height:700px;border:0";
f.src = "/";
document.body.appendChild(f);
```

주의 두 가지. 둘 다 실제로 재서 확인한 것이다.

**iframe 크기를 바꿔도 `MediaQueryList` 의 change 이벤트는 발화하지 않는다.**
`f.style.width` 를 바꾸면 CSS 는 다시 평가되고(`lg:` 등이 정상 전환되며
`matchMedia(q).matches` 값도 바뀐다) `change` 만 안 온다. 그래서 JS 로 폭을 읽는
쪽(`useSyncExternalStore`·resize 리스너)은 다시 렌더되지 않아 **멀쩡한 코드가 고장난 것처럼
보인다**. 하나를 줄였다 늘리지 말고 **폭마다 iframe 을 새로 띄운다**. 실제 리사이즈 반응은
진짜 창에서 확인한다.

**클릭한 뒤의 측정은 밀린다.** iframe 안에서 `getComputedStyle`·`getBoundingClientRect` 가
전환이 끝난 뒤에도 시작값을 계속 보고할 수 있다. 로드 직후 측정은 믿을 수 있고,
상호작용 후 상태는 스크린샷으로 확인한다.

가로 넘침 검사:

```js
document.documentElement.scrollWidth - document.documentElement.clientWidth   // 0 이어야 정상
```

---

**요약**: 패턴은 프로젝트의 제약에서 나온다. 설치되지 않은 라이브러리를 부르는 예제와
lint 를 통과하지 못하는 예제는 패턴이 아니라 부채다.
