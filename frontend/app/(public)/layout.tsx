import type { Metadata } from "next";

import { PublicShell } from "@/components/public/public-shell";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  title: { default: "Dokushodo", template: "%s | Dokushodo" },
  description: "Read translated Japanese web novels with clean navigation, progress tracking, and source-aware metadata.",
  openGraph: {
    type: "website",
    siteName: "Dokushodo",
    images: [
      {
        url: "/assets/dokushodo/brand/open-graph.png",
        width: 1200,
        height: 630,
        alt: "Dokushodo",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/assets/dokushodo/brand/open-graph.png"],
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return <PublicShell>{children}</PublicShell>;
}
