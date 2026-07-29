import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Contact",
  description: "Contact the Dokushodo owner or admin.",
  robots: { index: false, follow: false },
};

export default function ContactLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
