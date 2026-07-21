import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
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
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      {/* 브라우저 확장(Grammarly·비밀번호 매니저·번역기 등)이 <body>에 속성을 주입해
          SSR HTML과 클라이언트 DOM이 달라지는 것을 무시한다. 이 요소 '자체' 속성에만
          적용되며 트리 내부의 실제 불일치는 그대로 잡힌다. */}
      <body className="min-h-full flex flex-col bg-[#fafafa] text-[#1f1f1f]" suppressHydrationWarning>{children}</body>
    </html>
  );
}
