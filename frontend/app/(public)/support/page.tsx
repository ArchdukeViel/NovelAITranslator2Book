import type { Metadata } from "next";

import { StaticPage } from "@/components/public/static-page";

export const metadata: Metadata = {
  title: "Support",
  description: "Support information for Dokushodo public reader.",
  robots: { index: false, follow: false },
};

export default function SupportPage() {
  return (
    <StaticPage
      title="Support"
      description="Frequently asked questions and guidance for using Dokushodo."
      sections={[
        {
          title: "What is Dokushodo?",
          body: "Dokushodo is a public reader for translated Japanese web novels. It provides a clean reading interface, reading progress tracking, library management, reviews, and novel request features.",
        },
        {
          title: "Do I need an account?",
          body: "No. You can browse the catalog and read published chapters without signing in. An account (Google OAuth or email/password) is needed for library, reading progress, history, reviews, and requests.",
        },
        {
          title: "How do I request a novel?",
          body: "Signed-in readers can submit novel or chapter requests from the request page. Requests are reviewed by the owner and may or may not be fulfilled depending on source availability and translation capacity.",
        },
        {
          title: "Translations look wrong or incomplete",
          body: "Content is machine-translated and may contain errors, awkward phrasing, or incomplete passages. Quality varies by source, chapter length, and translation provider. The owner may revise translations over time.",
        },
        {
          title: "How do I report a problem?",
          body: "Use the Contact page to send a message to the owner. Include the novel title, chapter number (if applicable), and a clear description of the issue. For copyright concerns, use the DMCA page.",
        },
        {
          title: "Can I contribute translations?",
          body: "Community editing and credential contribution features are not yet available. The current product does not accept public translation edits or provider API keys.",
        },
        {
          title: "Browser or device issues",
          body: "Dokushodo targets modern browsers with JavaScript enabled. If you experience display, navigation, or reading issues, try refreshing, clearing the site's session data, or checking with a different browser. If the problem persists, use the Contact page.",
        },
      ]}
    />
  );
}
