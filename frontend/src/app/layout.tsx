import type { Metadata } from "next";
import { Carlito } from "next/font/google";
import "./globals.css";

/**
 * 숫자·영문은 Carlito 하나만 받는다. Calibri 와 메트릭이 동일한 클론이라 엑셀 셀의
 * 글자폭·자간이 그대로 재현된다 — 이 앱의 위장이 실제로 걸려 있는 지점은 한글이 아니라
 * 숫자다(화면의 대부분이 시세·등락률·금액이므로).
 *
 * 한글은 웹폰트를 받지 않는다. 각 OS 에 이미 기본 한글 글꼴이 있고(윈도우 맑은 고딕 /
 * iOS Apple SD Gothic Neo / 안드로이드 Noto Sans KR), 특히 윈도우에서는 맑은 고딕이
 * 곧 엑셀이 쓰는 한글 글꼴이다. 폴백 체인은 globals.css 의 --font-sans 에 있다.
 */
const carlito = Carlito({
  weight: ["400", "700"],
  subsets: ["latin"],
  variable: "--font-sheet",
  display: "swap",
});

export const metadata: Metadata = {
  // 회사용 위장: 브라우저 탭에는 엑셀 파일처럼 보이게 한다.
  title: "매출분석_2026_상반기.xlsx - Excel",
  description: "Microsoft Excel Worksheet",
  icons: {
    icon: "/icon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ko"
      className={`${carlito.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      {/* 브라우저 확장(Grammarly·비밀번호 매니저·번역기 등)이 <body>에 속성을 주입해
          SSR HTML과 클라이언트 DOM이 달라지는 것을 무시한다. 이 요소 '자체' 속성에만
          적용되며 트리 내부의 실제 불일치는 그대로 잡힌다. */}
      <body className="min-h-full flex flex-col bg-[#fafafa] text-[#1f1f1f]" suppressHydrationWarning>{children}</body>
    </html>
  );
}
