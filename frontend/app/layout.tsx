import type { Metadata } from "next";
import { Noto_Serif_JP, DM_Sans, DM_Mono } from "next/font/google";

import "@/app/globals.css";
import { QueryProvider } from "@/lib/query-client";

const notoSerifJp = Noto_Serif_JP({
  subsets: ["latin"],
  variable: "--font-noto-serif-jp",
});

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
});

const dmMono = DM_Mono({
  weight: ["400", "500"],
  subsets: ["latin"],
  variable: "--font-dm-mono",
});

export const metadata: Metadata = {
  title: "Novel AI",
  description: "Japanese web novel crawler, translation, reader, and admin workspace."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${notoSerifJp.variable} ${dmSans.variable} ${dmMono.variable}`}>
      <body className="font-sans">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
