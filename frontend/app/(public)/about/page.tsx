import { StaticPage } from "@/components/public/static-page";

export default function AboutPage() {
  return (
    <StaticPage
      title="About Novel AI"
      description="Novel AI is a public reader for translated web novels with owner-controlled ingestion and translation workflows."
      sections={[
        {
          title: "FAQ",
          body: "Public catalog, reader, login, library, and request surfaces are being aligned first. Community and contribution features remain gated until their backend contracts are ready.",
        },
        {
          title: "Reader accounts",
          body: "Signed-in users can use existing library, reading history, progress, review, and request features where the backend supports them.",
        },
      ]}
    />
  );
}
