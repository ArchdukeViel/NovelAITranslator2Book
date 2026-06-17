import { StaticPage } from "@/components/public/static-page";

export default function TermsPage() {
  return (
    <StaticPage
      title="Terms"
      description="Terms of service content is pending final legal copy."
      sections={[{ title: "Current status", body: "Final terms are being prepared for this public reader." }]}
    />
  );
}
