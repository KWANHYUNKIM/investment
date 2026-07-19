import type { NextConfig } from "next";

// 백엔드 주소(서버 사이드 프록시 대상). 기본은 로컬 FastAPI.
const BACKEND = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // 브라우저는 프론트엔드와 '같은 출처'로 /api/* 를 호출하고, Next 가 이를
  // 백엔드로 프록시한다. 덕분에 터널(공개 URL) 하나만 열어도 외부에서 동작하고
  // CORS 문제도 없다. (프론트엔드에서 NEXT_PUBLIC_API_BASE="" 로 상대경로 사용)
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND}/api/:path*` }];
  },
};

export default nextConfig;
