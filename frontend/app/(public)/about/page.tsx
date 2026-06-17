import type { Metadata } from "next";
import { StaticPage } from "@/components/public/static-page";

export const metadata: Metadata = {
  title: "About",
  description: "Dokushodo is a public reader for translated web novels with owner-controlled ingestion and translation workflows.",
};

export default function AboutPage() {
  return (
    <StaticPage
      title="About Dokushodo"
      description="Dokushodo is a public reader for translated web novels with owner-controlled ingestion and translation workflows."
      sections={[
        {
          title: "Platform",
          body: "Dokushodo is powered by Novel AI.",
        },
        {
          title: "FAQ",
          body: "The public catalog, reader, sign-in, library, and request features are available now. Community and contribution features are not yet ready and will be announced when their backend support is in place.",
        },
        {
          title: "Reader accounts",
          body: "Signed-in users can use existing library, reading history, progress, review, and request features where the backend supports them.",
        },
      ]}
    />
  );
}
