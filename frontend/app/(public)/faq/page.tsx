import type { Metadata } from "next";

import { StaticPage } from "@/components/public/static-page";

export const metadata: Metadata = {
  title: "FAQ",
  description: "Frequently asked questions about Dokushodo.",
};

export default function FaqPage() {
  return (
    <StaticPage
      title="Frequently Asked Questions"
      description="Answers to common questions about reading on Dokushodo."
      sections={[
        {
          title: "What is Dokushodo?",
          body: "Dokushodo is a public reader for translated Japanese web novels. It offers a clean reading interface, browsing and search, reading progress tracking, a personal library, reviews, and novel requests.",
        },
        {
          title: "Do I need an account to read?",
          body: "No. You can browse the catalog and read published chapters without signing in. An account (Google OAuth or email/password) is needed for library, reading progress, history, reviews, and requests.",
        },
        {
          title: "How does reading progress work?",
          body: "Signed-in readers get account-backed progress that syncs across devices. Guests get the same percentage saved locally in the browser, so they pick up where they left off on the same device.",
        },
        {
          title: "How do I save a novel to my library?",
          body: "Signed-in readers can save any novel from its detail page. The library page groups saved novels by status, with search and sorting, so you can keep track of what you are reading.",
        },
        {
          title: "How do I leave a review or rating?",
          body: "Open a novel's detail page and switch to the Reviews tab. Signed-in readers can rate from 1 to 5 stars and optionally write a short review. Your own reviews appear under Account → Reviews, where you can edit or remove them.",
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
