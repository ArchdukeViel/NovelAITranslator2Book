import type { Metadata } from "next";
import type { ReactNode } from "react";
import localFont from "next/font/local";

import "./globals.css";

import { QueryProvider } from "@/lib/query-client";

const notoSerifJp = localFont({
  src: "../public/fonts/Noto_Serif_JP.ttf",
  variable: "--font-noto-serif-jp",
});

const dmSans = localFont({
  src: "../public/fonts/DM_Sans.ttf",
  variable: "--font-dm-sans",
});

const dmMono = localFont({
  src: [
    { path: "../public/fonts/DM_Mono_400.ttf", weight: "400" },
    { path: "../public/fonts/DM_Mono_500.ttf", weight: "500" },
  ],
  variable: "--font-dm-mono",
});

export const metadata: Metadata = {
  title: { default: "Novel AI", template: "%s | Novel AI" },
  description: "Web novel translation, reading, and management platform.",
  openGraph: {
    type: "website",
    siteName: "Novel AI",
    title: "Novel AI",
    description: "Web novel translation, reading, and management platform.",
  },
  twitter: {
    card: "summary",
    title: "Novel AI",
    description: "Web novel translation, reading, and management platform.",
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="en"
      className={`${notoSerifJp.variable} ${dmSans.variable} ${dmMono.variable}`}
    >
      <body className="font-sans">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}