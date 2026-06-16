import { StaticPage } from "@/components/public/static-page";

export default function PrivacyPage() {
  return (
    <StaticPage
      title="Privacy"
      description="Privacy policy content is pending final legal copy."
      sections={[{ title: "Current status", body: "This placeholder does not collect new information or add new tracking behavior." }]}
    />
  );
}
