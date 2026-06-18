import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, type ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { LoginView } from "@/components/public/login-view";
import { LoginPrompt } from "@/components/public/login-prompt";

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
  it("renders public login with Google OAuth and email options", () => {
    const html = renderLoginStatic();

    expect(html).toContain("Continue with Google");
    expect(html).toContain("Sign in with email");
    expect(html).toContain("No account yet?");
    expect(html).toContain("Create one");
    expect(html).toContain("type=\"email\"");
    expect(html).toContain("Guest reading");
    expect(html).toContain("Save novels");
    expect(html).toContain("Continue reading where");
    expect(html).toContain("Leave reviews");
    expect(html).not.toMatch(/owner|admin|secret|bootstrap/i);
    expect(html).not.toContain("Password / Token");
  });

  it("does not expose owner bootstrap login through the public API client", () => {
    const publicApi = readFileSync("lib/public-api.ts", "utf8");
    const publicHooks = readFileSync("hooks/public/index.ts", "utf8");

    expect(publicApi).not.toContain("/api/auth/login");
    expect(publicApi).not.toContain("login(secret");
    expect(publicHooks).not.toContain("useLogin");
    expect(publicApi).toContain("/api/auth/password/login");
    expect(publicApi).toContain("/api/auth/register");
    expect(publicHooks).toContain("usePasswordLogin");
    expect(publicHooks).toContain("useRegister");
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
  it("renders benefit text and routes sign-in to the login page", () => {
    const html = renderToStaticMarkup(createElement(LoginPrompt));

    expect(html).toContain("Sign in to save novels");
    expect(html).toContain("href=\"/login?mode=signin\"");
    expect(html).not.toContain("Continue with Google");
    expect(html).not.toContain("type=\"email\"");
    expect(html).not.toMatch(/owner|admin|secret|bootstrap/i);
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
