import type { Metadata } from "next";
import { StaticPage } from "@/components/public/static-page";

export const metadata: Metadata = {
  title: "Signing In",
  description: "Authentication callback handler for Dokushodo.",
  robots: { index: false, follow: false },
};

export default function AuthCallbackPage() {
  return (
    <StaticPage
      title="Authentication Callback"
      description="Sign-in is completed by the backend. If you arrived here directly, return to login and try again."
    />
  );
}
