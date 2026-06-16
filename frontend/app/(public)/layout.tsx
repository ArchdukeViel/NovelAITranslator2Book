import type { Metadata } from "next";

import { PublicShell } from "@/components/public/public-shell";

export const metadata: Metadata = {
  title: "Dokushodo",
  description: "Read translated Japanese web novels with clean navigation, progress tracking, and source-aware metadata.",
};

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return <PublicShell>{children}</PublicShell>;
}
