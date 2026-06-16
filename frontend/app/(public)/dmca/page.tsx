import { StaticPage } from "@/components/public/static-page";

export default function DmcaPage() {
  return (
    <StaticPage
      title="DMCA"
      description="DMCA and takedown instructions are pending final policy copy."
      sections={[{ title: "Contact", body: "Use the contact page until a dedicated takedown workflow is connected." }]}
    />
  );
}
