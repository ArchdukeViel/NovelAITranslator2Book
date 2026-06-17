import type { Metadata } from "next";
import { StaticPage } from "@/components/public/static-page";

export const metadata: Metadata = {
  title: "Error",
  description: "Dokushodo public error surface.",
  robots: { index: false, follow: false },
};

export default function ErrorRoutePage() {
  return (
    <StaticPage
      title="Error"
      description="This public route documents the generic error surface. Runtime errors use the app-level error boundary."
    />
  );
}
