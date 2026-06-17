import type { Metadata } from "next";
import { StaticPage } from "@/components/public/static-page";

export const metadata: Metadata = {
  title: "Signing In",
  description: "Your sign-in is being processed on Dokushodo.",
  robots: { index: false, follow: false },
};

export default function AuthCallbackPage() {
  return (
    <StaticPage
      title="Signing In"
      description="Your sign-in is being processed. If you are not redirected automatically, you can return to the login page and try again."
    />
  );
}
