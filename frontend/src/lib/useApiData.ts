"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * 백엔드에서 값을 하나 받아오는 표준형.
 *
 * 이 저장소의 23개 파일이 `let alive = true` + fetch + setLoading + cleanup 을 42번
 * 복붙하고 있었다. 그 자체도 문제지만, 그 안의 `setLoading(true)` 가
 * react-hooks/set-state-in-effect 를 어겨 lint 에러 39건을 만들고 있었다.
 *
 * 그래서 이 훅은 **이펙트 본문에서 setState 를 절대 하지 않는다.** 상태를 하나로 묶고
 * 거기에 '어떤 요청의 결과인지'(key)를 같이 담아 두는 방식으로 로딩을 표현한다.
 *
 *   담긴 key === 지금 요청의 key   →  최신 결과다 (loading=false)
 *   다르다                        →  아직 안 왔다 (loading=true, data=null)
 *
 * key 가 바뀌면 이전 결과가 자동으로 무효가 되므로, 종목을 바꿨을 때 이전 종목의 값이
 * 잠깐 보이는 문제도 따로 초기화 코드 없이 사라진다.
 *
 * @param fetcher 매 요청마다 호출된다. 매 렌더 새 함수여도 된다(ref 로 최신만 쓴다).
 * @param key     요청을 식별하는 문자열. 보통 종목코드처럼 fetcher 가 의존하는 값.
 *                고정 요청이면 "" 같은 상수를 준다.
 * @param opts.enabled false 면 요청하지 않는다. 아직 종목이 안 골라진 경우 등.
 * @param opts.pollMs  주면 그 간격으로 다시 받는다. 정리는 훅이 책임진다.
 */

/** 어떤 요청 키와도 겹치지 않는 초기값. 실제 키는 아래에서 항상 ":" 를 포함한다. */
const PENDING = "pending";

export function useApiData<T>(
  fetcher: () => Promise<T>,
  key: string,
  opts: { enabled?: boolean; pollMs?: number } = {},
): { data: T | null; error: string | null; loading: boolean; reload: () => void } {
  const { enabled = true, pollMs } = opts;

  // reload() 로 같은 key 를 다시 받을 수 있게 nonce 를 붙인다.
  const [nonce, setNonce] = useState(0);
  const reqKey = `${nonce}:${key}`;

  // key 와 reqKey 를 둘 다 담는 이유:
  //   key   가 같으면  → 같은 대상이므로 보던 값을 계속 보여준다 (새로고침 중 화면이 안 빈다)
  //   reqKey 가 다르면 → 아직 이번 요청이 안 끝났으므로 loading 이다
  // 그래서 종목을 바꾸면 즉시 비고, 같은 종목을 다시 받을 때는 안 빈다.
  const [settled, setSettled] = useState<{ key: string; reqKey: string; data?: T; error?: string }>({
    key: PENDING,
    reqKey: PENDING,
  });

  // fetcher 는 보통 매 렌더 새 함수라 이펙트 의존성에 넣을 수 없다. 최신 것만 참조한다.
  const latest = useRef(fetcher);
  useEffect(() => {
    latest.current = fetcher;
  });

  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    const run = () =>
      latest
        .current()
        .then((d) => {
          if (alive) setSettled({ key, reqKey, data: d });
        })
        .catch((e: unknown) => {
          if (!alive) return;
          const message = e instanceof Error ? e.message : "불러오지 못했습니다.";
          // 같은 요청을 다시 받다가(폴링·reload) 실패한 것이라면 보던 값을 지우지 않는다.
          // 30초·60초 주기로 받는 화면에서 한 번 끊겼다고 패널이 비어 버리면, 실제로는
          // 직전 값이 아직 쓸모 있는데도 다음 성공까지 아무것도 못 보게 된다.
          // key 가 바뀐 경우(다른 종목)는 그대로 비운다 — 남의 값을 보여주면 안 되므로.
          setSettled((prev) => ({
            key,
            reqKey,
            data: prev.key === key ? prev.data : undefined,
            error: message,
          }));
        });
    run();
    if (!pollMs) return () => { alive = false; };
    const id = setInterval(run, pollMs);
    return () => { alive = false; clearInterval(id); };
  }, [reqKey, enabled, pollMs]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  // 저장소 전반이 "없음 = null" 규약이라 undefined 를 밖으로 내보내지 않는다.
  const sameTarget = enabled && settled.key === key;   // 보여줘도 되는 값인가
  const settledNow = enabled && settled.reqKey === reqKey; // 이번 요청이 끝났는가
  return {
    data: sameTarget ? settled.data ?? null : null,
    error: sameTarget ? settled.error ?? null : null,
    loading: enabled && !settledNow,
    reload,
  };
}
