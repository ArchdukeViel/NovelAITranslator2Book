import type { Metadata } from "next";
import { StaticPage } from "@/components/public/static-page";

export const metadata: Metadata = {
  title: "DMCA",
  description: "DMCA and takedown instructions for Dokushodo.",
};

export default function DmcaPage() {
  return (
    <StaticPage
      title="DMCA"
      description="DMCA and takedown instructions are pending final policy copy."
      sections={[{ title: "Contact", body: "Use the contact page until a dedicated takedown workflow is connected." }]}
    />
  );
}
