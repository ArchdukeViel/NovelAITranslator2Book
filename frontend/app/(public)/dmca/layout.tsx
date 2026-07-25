import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "DMCA",
  description: "DMCA and takedown policy for Dokushodo.",
  robots: { index: false, follow: false },
};

export default function DmcaLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
