import type { Metadata } from "next";

import { StaticPage } from "@/components/public/static-page";

export const metadata: Metadata = {
  title: "Legal",
  description: "Legal notices for Dokushodo public reader.",
  robots: { index: false, follow: false },
};

export default function LegalPage() {
  return (
    <StaticPage
      title="Legal"
      description="Legal information and policies for Dokushodo."
      sections={[
        {
          title: "DMCA",
          body: "Dokushodo respects intellectual property rights. If you believe material on the site infringes your copyright, submit a takedown notice through the DMCA page. The owner will respond to valid notices promptly.",
        },
        {
          title: "Terms of Service",
          body: 'Use of Dokushodo is governed by the Terms of Service page. The terms cover account responsibilities, acceptable use, reader content policies, moderation, availability, and disclaimers.',
        },
        {
          title: "Privacy Policy",
          body: 'The Privacy Policy page explains what personal data Dokushodo collects, how it is used, and your rights. This includes sign-in data, session cookies, reader records, and technical data.',
        },
        {
          title: "Cookie Notice",
          body: 'Dokushodo uses HTTP-only session cookies for signed-in functionality and CSRF tokens for state-changing actions. Guest novel-detail views may also receive a first-party signed anonymous viewer token for distinct-view rankings; no IP address is stored. No third-party advertising or analytics cookies are used. See the Cookie Policy page for full details.',
        },
        {
          title: "Disclaimer",
          body: "Dokushodo is an owner-operated translation aggregation reader. Content is provided for reading access only. The service is provided without warranty of accuracy, completeness, or uninterrupted availability.",
        },
      ]}
    />
  );
}
