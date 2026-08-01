import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, within } from "@testing-library/react";

import { PublicHeader } from "@/components/public/public-header";
import { MobileTabBar } from "@/components/public/mobile-tab-bar";
import { PublicFooter } from "@/components/public/public-footer";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const __root = dirname(fileURLToPath(import.meta.url));
const publicRouteRoot = join(__root, "..", "..", "..", "app", "(public)");

/** Map a nav href like "/account/library" to the expected page.tsx path. */
function hrefToPagePath(href: string): string {
  return join(publicRouteRoot, href, "page.tsx");
}

function renderWithQuery(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("next/navigation", () => ({
  usePathname: () => "/home",
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(""),
}));

vi.mock("@/hooks/public/use-auth", () => ({
  usePublicAuth: vi.fn(),
  useLogout: vi.fn(() => vi.fn()),
}));

import { usePublicAuth } from "@/hooks/public/use-auth";
const mockedUsePublicAuth = vi.mocked(usePublicAuth);

function setAuth(authenticated: boolean) {
  mockedUsePublicAuth.mockReturnValue({
    isAuthenticated: authenticated,
    isPublicUser: authenticated,
    isOwner: false,
    authState: authenticated
      ? {
          status: "authenticated",
          user: { id: 1, email: "a@b.c", role: "user" as const, is_authenticated: true },
        }
      : null,
    user: authenticated
      ? { id: 1, email: "a@b.c", role: "user" as const, is_authenticated: true }
      : null,
    data: authenticated
      ? { id: 1, email: "a@b.c", role: "user" as const, is_authenticated: true }
      : undefined,
    isLoading: false,
    isError: false,
    error: null,
  } as unknown as ReturnType<typeof usePublicAuth>);
}

// ---------------------------------------------------------------------------
// Header navigation consistency (desktop)
// ---------------------------------------------------------------------------

describe("Header navigation consistency", () => {
  const headerNavHrefs = [
    "/home",
    "/browse-novels",
    "/request-novel",
    "/account/library",
  ];

  it("every header href resolves to an existing route page", () => {
    for (const href of headerNavHrefs) {
      const pagePath = hrefToPagePath(href);
      expect(existsSync(pagePath), `Missing page for header href ${href}: ${pagePath}`).toBe(true);
    }
  });

  it("renders desktop header nav items when authenticated", () => {
    setAuth(true);
    renderWithQuery(<PublicHeader />);

    expect(screen.getByRole("link", { name: /^home$/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^browse$/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^request$/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^library$/i })).toBeInTheDocument();

    // Search field (not a link but present)
    expect(screen.getByPlaceholderText(/search novels/i)).toBeInTheDocument();

    // Theme toggle present
    expect(screen.getByLabelText(/switch to (dark|light) theme/i)).toBeInTheDocument();

    // Notification bell present
    expect(screen.getByLabelText(/notifications/i)).toBeInTheDocument();

    // Account indicator (signed-in user email + sign out)
    expect(screen.getByText("a@b.c")).toBeInTheDocument();
    expect(screen.getByLabelText(/sign out/i)).toBeInTheDocument();

    // No hamburger menu button
    expect(screen.queryByLabelText(/open navigation menu/i)).not.toBeInTheDocument();
  });

  it("renders desktop header nav items when guest", () => {
    setAuth(false);
    renderWithQuery(<PublicHeader />);

    expect(screen.getByRole("link", { name: /^home$/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^browse$/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^request$/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^library$/i })).toBeInTheDocument();

    expect(screen.getByPlaceholderText(/search novels/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/switch to (dark|light) theme/i)).toBeInTheDocument();

    // Notification bell is hidden for guests (DESIGN.md guest behavior)
    expect(screen.queryByLabelText(/notifications/i)).not.toBeInTheDocument();

    // Sign-in link
    expect(screen.getByRole("link", { name: /sign in/i })).toHaveAttribute(
      "href",
      "/login?mode=signin"
    );

    // No sign-out
    expect(screen.queryByLabelText(/sign out/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/signing out/i)).not.toBeInTheDocument();

    // No hamburger menu button
    expect(screen.queryByLabelText(/open navigation menu/i)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Mobile tab bar consistency
// ---------------------------------------------------------------------------

describe("Mobile tab bar consistency", () => {
  const tabBarHrefs = [
    "/home",
    "/browse-novels",
    "/account/library",
    "/account",
  ];

  it("every tab bar href resolves to an existing route page", () => {
    for (const href of tabBarHrefs) {
      const pagePath = hrefToPagePath(href);
      expect(existsSync(pagePath), `Missing page for tab bar href ${href}: ${pagePath}`).toBe(true);
    }
  });

  it("renders tab bar items and respects guest/auth state", () => {
    // Guest: account + library tabs should route to sign-in
    setAuth(false);
    render(<MobileTabBar />);

    expect(screen.getByRole("link", { name: /^home$/i })).toHaveAttribute("href", "/home");
    expect(screen.getByRole("link", { name: /^browse$/i })).toHaveAttribute("href", "/browse-novels");
    expect(screen.getByRole("link", { name: /^search$/i })).toHaveAttribute("href", "/browse-novels?focus=search");
    expect(screen.getByRole("link", { name: /^library$/i })).toHaveAttribute(
      "href",
      "/login?mode=signin&next=%2Faccount%2Flibrary"
    );
    expect(screen.getByRole("link", { name: /^account$/i })).toHaveAttribute(
      "href",
      "/login?mode=signin"
    );

    // Authenticated: library and account tabs point to their real destinations
    cleanup();
    setAuth(true);
    render(<MobileTabBar />);

    expect(screen.getByRole("link", { name: /^library$/i })).toHaveAttribute("href", "/account/library");
    expect(screen.getByRole("link", { name: /^account$/i })).toHaveAttribute("href", "/account");
  });
});

// ---------------------------------------------------------------------------
// Footer navigation consistency (unchanged)
// ---------------------------------------------------------------------------

describe("Footer navigation consistency", () => {
  const footerReadHrefs = ["/browse-novels", "/ranking", "/request-novel", "/contribute", "/support"];
  const footerLegalHrefs = ["/about", "/privacy", "/terms", "/legal", "/dmca", "/contact", "/cookie-policy"];

  it("every footer Read section href resolves to an existing route page", () => {
    for (const href of footerReadHrefs) {
      const pagePath = hrefToPagePath(href);
      expect(existsSync(pagePath), `Missing page for footer Read href ${href}: ${pagePath}`).toBe(true);
    }
  });

  it("every footer legal href resolves to an existing route page", () => {
    for (const href of footerLegalHrefs) {
      const pagePath = hrefToPagePath(href);
      expect(existsSync(pagePath), `Missing page for footer href ${href}: ${pagePath}`).toBe(true);
    }
  });

  it("footer does not contain Library link", () => {
    render(<PublicFooter />);
    expect(screen.queryByRole("link", { name: /library/i })).not.toBeInTheDocument();
  });

  it("footer contains Read section links", () => {
    render(<PublicFooter />);
    expect(screen.getByText(/browse novels/i)).toBeInTheDocument();
    expect(screen.getByText(/ranking/i)).toBeInTheDocument();
    expect(screen.getByText(/request novel/i)).toBeInTheDocument();
    expect(screen.getByText(/contribute/i)).toBeInTheDocument();
    expect(screen.getByText(/support/i)).toBeInTheDocument();
  });

  it("footer contains Trust section legal links", () => {
    render(<PublicFooter />);
    expect(screen.getByText(/about/i)).toBeInTheDocument();
    expect(screen.getByText(/privacy/i)).toBeInTheDocument();
    expect(screen.getByText(/terms/i)).toBeInTheDocument();
    expect(screen.getByText(/legal/i)).toBeInTheDocument();
    expect(screen.getByText(/dmca/i)).toBeInTheDocument();
    expect(screen.getByText(/contact/i)).toBeInTheDocument();
    expect(screen.getByText(/cookie policy/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Route inventory completeness (unchanged)
// ---------------------------------------------------------------------------

describe("Route inventory completeness", () => {
  /**
   * Routes that exist but are intentionally not linked from any navigation
   * component. Each entry documents why it's excluded.
   */
  const knownExcludedRoutes: { route: string; reason: string }[] = [
    { route: "/login", reason: "Auth is reached from header/sidebar as /login?mode=signin or /login?mode=signup" },
    { route: "/logout", reason: "Logout calls API mutation with server-side redirect, not a nav link" },
    { route: "/auth/callback", reason: "OAuth redirect_uri target — never user-facing" },
    { route: "/error", reason: "Next.js error boundary fallback" },
    { route: "/not-found", reason: "Next.js 404 fallback" },
    { route: "/maintenance", reason: "Server-side maintenance redirect" },
    { route: "/", reason: "Root redirects to /home (page.tsx contains redirect())" },
  ];

  /**
   * Routes that SHOULD be reachable from navigation. Every route not in
   * knownExcludedRoutes must have at least one nav entry.
   */
  const navLinkedRoutes = new Set([
    "/home",
    "/browse-novels",
    "/ranking",
    "/request-novel",
    "/contribute",
    "/about",
    "/privacy",
    "/terms",
    "/legal",
    "/dmca",
    "/contact",
    "/cookie-policy",
    "/support",
    "/account",
    "/account/library",
    "/account/history",
    "/account/notifications",
    "/account/requests",
    "/account/contributions",
    "/account/settings",
    // dynamic routes are covered by card/row components, not nav links
  ]);

  it("every non-excluded route has at least one nav link", () => {
    function collectRoutes(dir: string, prefix: string): string[] {
      const routes: string[] = [];
      const entries = readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        if (entry.name === "node_modules") continue;
        const full = join(dir, entry.name);
        if (entry.isDirectory()) {
          routes.push(...collectRoutes(full, `${prefix}/${entry.name}`));
        } else if (entry.name === "page.tsx") {
          // Convert the path to a route — strip the (public) base
          const routePath = prefix.replace(/\\/g, "/") || "/";
          // Skip page.tsx at root → route is "/"
          routes.push(routePath || "/");
        }
      }
      return routes;
    }

    const allRoutes = collectRoutes(publicRouteRoot, "");
    const navLinked = navLinkedRoutes;
    const excluded = knownExcludedRoutes.map((r) => r.route);

    const notCovered = allRoutes.filter((route) => !navLinked.has(route) && !excluded.includes(route));
    // Dynamic routes (with [param]) are covered by card/row components
    const staticNotFound = notCovered.filter((r) => !r.includes("[") && !r.includes("]"));

    expect(staticNotFound, `Routes without nav link or exclusion doc: ${staticNotFound.join(", ")}`).toHaveLength(0);
  });
});
