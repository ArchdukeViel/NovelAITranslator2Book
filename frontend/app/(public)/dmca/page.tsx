import type { Metadata } from "next";
import { StaticPage } from "@/components/public/static-page";

export const metadata: Metadata = {
  title: "DMCA",
  description: "DMCA and takedown policy for Dokushodo.",
  robots: { index: false, follow: false },
};

export default function DmcaPage() {
  return (
    <StaticPage
      title="DMCA"
      description="A formal DMCA takedown policy and contact workflow are pending. In the meantime, the owner/admin reviews takedown requests manually. Use the Contact page to submit a notice, and include enough detail for the owner to identify the material in question."
    />
  );
}
