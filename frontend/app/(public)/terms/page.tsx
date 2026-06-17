import type { Metadata } from "next";
import { StaticPage } from "@/components/public/static-page";

export const metadata: Metadata = {
  title: "Terms",
  description: "Terms of service for Dokushodo public reader.",
};

export default function TermsPage() {
  return (
    <StaticPage
      title="Terms"
      description="These terms describe the current Dokushodo public reader. Use the site in a way that keeps the library readable, respectful, and safe to operate."
      sections={[
        {
          title: "Accounts",
          body: "Public accounts use Google sign-in. You are responsible for activity from your signed-in session, including saved library items, reading history, reviews, and requests. Do not try to access another reader's account, data, or admin-only tools.",
        },
        {
          title: "Acceptable use",
          body: "Do not abuse, scrape, overload, attack, reverse engineer, or misuse the service. Do not submit spam, misleading requests, harmful content, or anything that interferes with translation, review, moderation, or normal reading.",
        },
        {
          title: "Reader content",
          body: "The catalog may include machine-translated novel content, metadata, and chapter text from supported sources. Translations can be incomplete, delayed, inaccurate, or changed by the owner. The reader is provided for reading access, not as an official source text archive.",
        },
        {
          title: "Reviews and requests",
          body: "If you submit reviews, ratings, or novel and chapter requests, keep them relevant and lawful. The owner may moderate, hide, reject, edit labels for, or remove submitted material to protect the service, readers, source rights, and operational safety.",
        },
        {
          title: "Credential contributions",
          body: "Public provider credential contribution is not available in the current product. Do not submit real API keys through preview screens. If credential contribution is enabled later, only contribute credentials you control and understand may be used for translation work.",
        },
        {
          title: "Availability and changes",
          body: "Dokushodo is an owner-operated public reader and translation platform. Features, pages, catalog entries, translations, accounts, and access may change, pause, or be removed. The service is provided without a promise of uninterrupted availability.",
        },
      ]}
    />
  );
}
