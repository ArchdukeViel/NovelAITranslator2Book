import type { Metadata } from "next";
import type { ReactNode } from "react";
import localFont from "next/font/local";

import "./globals.css";

import { QueryProvider } from "@/lib/query-client";

const notoSerifJp = localFont({
  src: "../public/fonts/Noto_Serif_JP.woff2",
  variable: "--font-noto-serif-jp",
});

const dmSans = localFont({
  src: "../public/fonts/DM_Sans.woff2",
  variable: "--font-dm-sans",
});

const dmMono = localFont({
  src: [
    { path: "../public/fonts/DM_Mono_400.woff2", weight: "400" },
    { path: "../public/fonts/DM_Mono_500.woff2", weight: "500" },
  ],
  variable: "--font-dm-mono",
});

export const metadata: Metadata = {
  title: { default: "Dokushodo", template: "%s | Dokushodo" },
  description: "Web novel translation, reading, and management platform.",
  icons: {
    icon: [
      { url: "/assets/dokushodo/brand/icon.svg", type: "image/svg+xml" },
      { url: "/assets/dokushodo/brand/favicon.ico", sizes: "any" },
    ],
    apple: "/assets/dokushodo/brand/apple-touch-icon.png",
  },
  manifest: "/manifest.webmanifest",
  openGraph: {
    type: "website",
    siteName: "Dokushodo",
    title: "Dokushodo",
    description: "Web novel translation, reading, and management platform.",
  },
  twitter: {
    card: "summary",
    title: "Dokushodo",
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
