import type { Metadata } from "next";

import { PublicShell } from "@/components/public/public-shell";

export const metadata: Metadata = {
  title: { default: "Dokushodo", template: "%s | Dokushodo" },
  description: "Read translated Japanese web novels with clean navigation, progress tracking, and source-aware metadata.",
  openGraph: {
    type: "website",
    siteName: "Dokushodo",
  },
  twitter: {
    card: "summary",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return <PublicShell>{children}</PublicShell>;
}
