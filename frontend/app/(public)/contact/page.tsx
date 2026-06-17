import type { Metadata } from "next";
import { StaticPage } from "@/components/public/static-page";

export const metadata: Metadata = {
  title: "Contact",
  description: "Contact the Dokushodo owner or admin.",
  robots: { index: false, follow: false },
};

export default function ContactPage() {
  return (
    <StaticPage
      title="Contact"
      description="Dokushodo is operated by a single owner/admin. If you need to report an issue, submit a takedown request, or ask a question, the contact route will be listed here once it is approved."
    />
  );
}
