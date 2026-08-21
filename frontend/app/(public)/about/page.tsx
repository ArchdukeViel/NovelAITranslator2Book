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
          body: "Dokushodo is a public reading platform for translated web novels.",
        },
        {
          title: "FAQ",
          body: "The public catalog, reader, sign-in, library, request, ranking, and contributor credential features are available now. Community editing remains outside the current product scope.",
        },
        {
          title: "Reader accounts",
          body: "Signed-in users can use existing library, reading history, progress, review, and request features where the backend supports them.",
        },
      ]}
    />
  );
}
