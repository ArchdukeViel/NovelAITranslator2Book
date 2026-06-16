import { StaticPage } from "@/components/public/static-page";

export default function ErrorRoutePage() {
  return (
    <StaticPage
      title="Error"
      description="This public route documents the generic error surface. Runtime errors use the app-level error boundary."
    />
  );
}
