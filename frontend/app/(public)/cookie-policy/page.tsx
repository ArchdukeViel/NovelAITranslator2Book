import { StaticPage } from "@/components/public/static-page";

export default function CookiePolicyPage() {
  return (
    <StaticPage
      title="Cookie Policy"
      description="Cookie policy content is pending final legal copy."
      sections={[{ title: "Current status", body: "This scaffold does not add cookie consent or tracking behavior." }]}
    />
  );
}
