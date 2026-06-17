import type { Metadata } from "next";
import { StaticPage } from "@/components/public/static-page";

export const metadata: Metadata = {
  title: "Cookie Policy",
  description: "Cookie and session token usage policy for Dokushodo public reader accounts.",
};

export default function CookiePolicyPage() {
  return (
    <StaticPage
      title="Cookie Policy"
      description="Dokushodo uses cookies and session tokens to keep sign-in and reader account features working safely."
      sections={[
        {
          title: "What cookies do",
          body: "Cookies help the site remember your browser during a visit. Guests can read the public catalog and chapters without signing in, but signed-in features need session support so the backend can connect actions to the right account.",
        },
        {
          title: "Session cookie",
          body: "When you sign in, the backend uses a signed HTTP-only session cookie named novelai_session. It stores session state for the app, such as your user identity and role, and is sent with requests so library, progress, history, reviews, and requests can work.",
        },
        {
          title: "CSRF protection",
          body: "For actions that change account data, the frontend asks the backend for a session-bound CSRF token and sends it in an X-CSRF-Token header. This helps protect signed-in actions from unwanted cross-site requests.",
        },
        {
          title: "Google sign-in",
          body: "Public sign-in redirects through Google OAuth. Google may use its own cookies or account state during that sign-in flow. Dokushodo uses the result to create or resume your local reader session.",
        },
        {
          title: "Analytics and ads",
          body: "The current public app does not implement third-party advertising or analytics cookies. If that changes, the policy will be updated before those features are active.",
        },
        {
          title: "Blocking cookies",
          body: "If you block cookies, public reading may still work, but sign-in and saved reader features may fail or log you out. Security checks such as CSRF protection also depend on the session being available.",
        },
        {
          title: "Related privacy information",
          body: "The Privacy Policy explains the account and reader data connected to signed-in use. This Cookie Policy focuses only on browser cookies, session state, and security tokens used by the current app.",
        },
      ]}
    />
  );
}
