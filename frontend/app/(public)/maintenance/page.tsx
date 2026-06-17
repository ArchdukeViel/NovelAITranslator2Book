import type { Metadata } from "next";
import { StaticPage } from "@/components/public/static-page";

export const metadata: Metadata = {
  title: "Maintenance",
  description: "Dokushodo maintenance page.",
  robots: { index: false, follow: false },
};

export default function MaintenancePage() {
  return (
    <StaticPage
      title="Maintenance"
      description="Dokushodo is not currently in maintenance mode."
      sections={[{ title: "Placeholder", body: "This route exists for a future operational maintenance state." }]}
    />
  );
}
