import { StaticPage } from "@/components/public/static-page";

export default function MaintenancePage() {
  return (
    <StaticPage
      title="Maintenance"
      description="Novel AI is not currently in maintenance mode."
      sections={[{ title: "Placeholder", body: "This route exists for a future operational maintenance state." }]}
    />
  );
}
