// 백엔드 FastAPI 타입드 클라이언트 — 도메인별 모듈의 조립 지점.
//
// 호출부는 예전과 똑같이 `import { api, type Foo } from "@/lib/api"` 로 쓴다.
// 도메인별 부분 객체(<도메인>Api)를 여기서 하나의 api 로 합친다. 백엔드
// backend/src/app/domains/ 의 도메인 구획과 같은 경계로 나눠 뒀다.

export { API_BASE, ApiError, getToken, setToken, authHeader } from "./client";

export * from "./auth";
export * from "./admin";
export * from "./prices";
export * from "./market";
export * from "./briefing";
export * from "./signals";
export * from "./screener";
export * from "./watchlist";
export * from "./dividends";
export * from "./budget";
export * from "./income";
export * from "./wealth";
export * from "./macro";
export * from "./realestate";
export * from "./themes";
export * from "./industry";
export * from "./globalMap";
export * from "./archive";
export * from "./fundamentals";
export * from "./unitEconomics";
export * from "./costmodel";
export * from "./integrity";
export * from "./crisis";
export * from "./quant";

import { authApi } from "./auth";
import { adminApi } from "./admin";
import { pricesApi } from "./prices";
import { marketApi } from "./market";
import { briefingApi } from "./briefing";
import { signalsApi } from "./signals";
import { screenerApi } from "./screener";
import { watchlistApi } from "./watchlist";
import { dividendsApi } from "./dividends";
import { budgetApi } from "./budget";
import { incomeApi } from "./income";
import { wealthApi } from "./wealth";
import { macroApi } from "./macro";
import { realestateApi, poiApi } from "./realestate";
import { themesApi } from "./themes";
import { industryApi } from "./industry";
import { globalMapApi } from "./globalMap";
import { archiveApi } from "./archive";
import { fundamentalsApi } from "./fundamentals";
import { unitEconomicsApi } from "./unitEconomics";
import { costmodelApi } from "./costmodel";
import { integrityApi } from "./integrity";
import { crisisApi } from "./crisis";
import { quantApi } from "./quant";

export const api = {
  ...authApi,
  ...adminApi,
  ...pricesApi,
  ...marketApi,
  ...briefingApi,
  ...signalsApi,
  ...screenerApi,
  ...watchlistApi,
  ...dividendsApi,
  ...budgetApi,
  ...incomeApi,
  ...wealthApi,
  ...macroApi,
  ...realestateApi,
  ...poiApi,
  ...themesApi,
  ...industryApi,
  ...globalMapApi,
  ...archiveApi,
  ...fundamentalsApi,
  ...unitEconomicsApi,
  ...costmodelApi,
  ...integrityApi,
  ...crisisApi,
  ...quantApi,
};
