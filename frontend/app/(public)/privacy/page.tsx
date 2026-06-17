import { StaticPage } from "@/components/public/static-page";

export default function PrivacyPage() {
  return (
    <StaticPage
      title="Privacy"
      description="This page explains the personal data Dokushodo currently uses for public reader accounts and saved reading features."
      sections={[
        {
          title: "Sign-in data",
          body: "Public sign-in uses Google OAuth. When you sign in, the backend uses basic Google identity information needed to create or resume your reader account, such as your email address, display name when available, provider name, and provider account identifier.",
        },
        {
          title: "Sessions and cookies",
          body: "The site uses an HTTP-only session cookie to keep you signed in and a CSRF token for state-changing actions such as saving library items, updating progress, writing reviews, or creating requests. These cookies support account security and are not a promise of anonymous use while signed in.",
        },
        {
          title: "Reader data",
          body: "When you use authenticated features, the service may store your library, reading progress, reading history, reviews, ratings, and novel or chapter requests. Those records are tied to your account so the app can show your saved state and protect each reader's data from other readers.",
        },
        {
          title: "Reviews and requests",
          body: "Reviews, ratings, and requests may be reviewed by the owner for moderation, abuse prevention, catalog work, and translation planning. Do not include private information in reviews or requests that you would not want an owner/admin to see.",
        },
        {
          title: "Credential contributions",
          body: "Public provider/API credential contribution is gated and unavailable in the current product. Preview contribution screens should not receive real API keys. A future credential feature would need separate secure handling, audit, revocation, and usage controls before accepting keys.",
        },
        {
          title: "Technical data",
          body: "Like most web services, the backend may process technical data needed to operate and protect the site, such as request timing, session state, rate-limit signals, and error information. Project guardrails require secrets, cookies, OAuth tokens, provider keys, and raw tracebacks not to be exposed in public responses.",
        },
        {
          title: "Your controls",
          body: "Current account controls are limited. You can use available product controls to remove saved novels or delete your own review where those controls exist. General account deletion, privacy preference management, and contributed-credential deletion are not active public features yet.",
        },
      ]}
    />
  );
}
