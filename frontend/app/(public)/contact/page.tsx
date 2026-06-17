import type { Metadata } from "next";
import { StaticPage } from "@/components/public/static-page";

export const metadata: Metadata = {
  title: "Contact",
  description: "Contact information for Dokushodo.",
};

export default function ContactPage() {
  return (
    <StaticPage
      title="Contact"
      description="Public contact channels are pending."
      sections={[{ title: "Support", body: "For now, this route confirms where contact information will live once approved." }]}
    />
  );
}
