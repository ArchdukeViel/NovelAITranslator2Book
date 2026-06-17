import { StaticPage } from "@/components/public/static-page";

export default function PrivacyPage() {
  return (
    <StaticPage
      title="Privacy"
      description="Privacy policy content is pending final legal copy."
      sections={[{ title: "Current status", body: "Final privacy details are being prepared. This page does not introduce additional tracking." }]}
    />
  );
}
