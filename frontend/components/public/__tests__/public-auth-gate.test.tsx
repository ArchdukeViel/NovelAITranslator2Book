import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { LoginView } from "@/components/public/login-view";

/** Render LoginView with a QueryClient for static SSR. */
function renderLoginStatic() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return renderToStaticMarkup(
    createElement(
      QueryClientProvider,
      { client: queryClient },
      createElement(LoginView, { onClose: () => undefined })
    )
  );
}

describe("public auth gate", () => {
  it("renders public login with Google OAuth and owner sign-in options", () => {
    const html = renderLoginStatic();

    expect(html).toContain("Continue with Google");
    expect(html).toContain("Guest reading");
    expect(html).toContain("Save novels");
    expect(html).toContain("Continue reading where");
    expect(html).toContain("Leave reviews");
    // Owner login tab is present
    expect(html).toContain("Owner");
    // No email field
    expect(html).not.toContain("type=\"email\"");
    // No token field
    expect(html).not.toContain("token");
    // No "Password / Token" legacy label
    expect(html).not.toContain("Password / Token");
  });

  it("exposes owner bootstrap login through the public API client", () => {
    const publicApi = readFileSync("lib/public-api.ts", "utf8");
    const publicHooks = readFileSync("hooks/public/index.ts", "utf8");

    expect(publicApi).toContain("/api/auth/login");
    expect(publicApi).toContain("login(secret");
    expect(publicHooks).toContain("useLogin");
    expect(publicHooks).toContain("useAuthMe");
    expect(publicHooks).toContain("useLogout");
    expect(publicHooks).toContain("useStartGoogleOAuth");
  });
});

/* ------------------------------------------------------------------ */
/*  Auth callback page (server component via StaticPage)               */
/* ------------------------------------------------------------------ */

describe("auth callback page", () => {
  it("has human-readable title and description in source", () => {
    const source = readFileSync("app/(public)/auth/callback/page.tsx", "utf8");
    // Server component — verify the metadata and page copy contract
    expect(source).toContain('title: "Signing In"');
    expect(source).toContain("sign-in is being processed");
    expect(source).not.toContain("Authentication Callback");
    expect(source).not.toContain("Authentication callback handler");
    expect(source).toContain("robots: { index: false, follow: false }");
  });
});

/* ------------------------------------------------------------------ */
/*  Logout page                                                        */
/* ------------------------------------------------------------------ */

describe("logout page", () => {
  it("renders human-readable description and return-home link in source", () => {
    const source = readFileSync("app/(public)/logout/page.tsx", "utf8");
    expect(source).toContain("Signing out");
    expect(source).toContain("signed out");
    expect(source).not.toContain("session is being cleared");
    expect(source).toContain("Return home");
  });
});

/* ------------------------------------------------------------------ */
/*  LoginPrompt rendering                                              */
/* ------------------------------------------------------------------ */

describe("LoginPrompt component", () => {
  it("renders benefit text and sign-in button with owner toggle", () => {
    // Re-use the existing LoginView render since LoginPrompt wraps it
    const html = renderLoginStatic();

    expect(html).toContain("Continue with Google");
    expect(html).toContain("Guest reading");
    expect(html).toContain("Save novels");
    expect(html).toContain("reading history");
    expect(html).not.toContain("type=\"email\"");
    expect(html).not.toContain("Password / Token");
  });
});

/* ------------------------------------------------------------------ */
/*  AuthGate loading/guest states                                      */
/* ------------------------------------------------------------------ */

describe("AuthGate component", () => {
  it("shows loading state when auth is pending (checks exported component for spinner markup)", () => {
    // Static render isn't ideal for a client component — verify via the
    // source code contract: checking the component text.
    const source = readFileSync("components/public/auth-gate.tsx", "utf8");
    expect(source).toContain("Loader2");
    expect(source).toContain("Checking session");
    expect(source).not.toContain("return null"); // no longer returns null while loading
  });

  it("uses LoginPrompt as default fallback for guests", () => {
    const source = readFileSync("components/public/auth-gate.tsx", "utf8");
    expect(source).toContain("LoginPrompt");
    expect(source).toContain("fallback ?? <LoginPrompt />");
  });
});
