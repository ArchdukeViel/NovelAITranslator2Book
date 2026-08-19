import type { Metadata } from "next";
import { StaticPage } from "@/components/public/static-page";

export const metadata: Metadata = {
  title: "Privacy",
  description: "Privacy policy for Dokushodo public reader accounts and saved reading features.",
};

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
          body: "The site uses an HTTP-only session cookie to keep you signed in and a CSRF token for state-changing actions such as saving library items, updating progress, writing reviews, or creating requests. Guest novel-detail views may use a signed first-party anonymous viewer token so ranking can count distinct viewers without storing IP addresses. The server stores only a one-way digest of that token and applies the configured analytics retention window.",
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
          body: "Authenticated users may optionally contribute one Gemini API key through the Contributions page. The key is encrypted at rest, validated explicitly, isolated from owner credentials, never returned to the browser after submission, and represented by masked metadata. The service records sanitized usage and token accounting, not prompts, authorization headers, or provider responses. Users can pause, replace, or permanently delete their own credential; owners retain emergency revoke controls.",
        },
        {
          title: "Technical data",
          body: "Like most web services, the backend may process technical data needed to operate and protect the site, such as request timing, session state, rate-limit signals, and error information. Public novel-detail rankings use authenticated user ids or anonymous viewer-token digests, never IP addresses. Project guardrails require secrets, cookies, OAuth tokens, provider keys, and raw tracebacks not to be exposed in public responses.",
        },
        {
          title: "Your controls",
          body: "Current account controls include removing saved novels, deleting your own review where available, and managing your contributor credential from the Contributions page. You can pause, resume, replace, or permanently delete that credential. General account deletion and separate analytics preference management are not active public controls; disabling cookies may prevent anonymous ranking identity from working.",
        },
      ]}
    />
  );
}
