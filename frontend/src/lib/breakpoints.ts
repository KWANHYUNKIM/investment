/**
 * 화면 폭 기준 세 단계.
 *
 * 하나로 합치지 않는 이유: 셋은 각각 다른 물리적 제약에서 나왔다.
 *   phone  — 그리드 열이 더는 안 들어가는 폭(글자 크기가 정한다)
 *   nav    — 사이드바 208px 를 본문에서 뺄 수 없게 되는 폭
 *   detail — 종목 상세 400px 패널을 본문에서 뺄 수 없게 되는 폭
 *
 * 값은 Tailwind 의 sm / lg / xl 과 같게 맞춰 두었다. CSS 는 변형(`sm:`)으로,
 * JS 는 아래 `mq` 로 읽는다 — 숫자를 양쪽에 따로 적으면 언젠가 어긋난다.
 */
export const BP = {
  phone: 640,
  nav: 1024,
  detail: 1280,
} as const;

export const mq = {
  /** 폰: 그리드 열을 줄이고 표의 높이 캡을 푼다. */
  phone: `(max-width: ${BP.phone - 1}px)`,
  /** 사이드바가 문서 흐름 안에 있는 폭. 이 아래에서는 시트탭이 내비게이션을 맡는다. */
  nav: `(min-width: ${BP.nav}px)`,
  /** 종목 상세가 문서 흐름 안에 있는 폭. 이 아래에서는 덮는 시트로 열린다. */
  detail: `(min-width: ${BP.detail}px)`,
} as const;
