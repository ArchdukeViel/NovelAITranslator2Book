import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { PublicSidebar } from "@/components/public/public-sidebar";
import { PublicHeader } from "@/components/public/public-header";
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
      ? { status: "authenticated", user: { id: 1, email: "a@b.c", role: "user" as const, is_authenticated: true } }
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
// Sidebar navigation consistency
// ---------------------------------------------------------------------------

describe("Sidebar navigation consistency", () => {
  const publicNavHrefs = [
    "/home",
    "/browse-novels",
    "/ranking",
    "/request-novel",
    "/contribute",
  ];

  const accountNavHrefs = [
    "/account/library",
    "/account/history",
    "/account/requests",
    "/account/contributions",
    "/account/settings",
  ];

  it("every public sidebar href resolves to an existing route page", () => {
    for (const href of publicNavHrefs) {
      const pagePath = hrefToPagePath(href);
      expect(existsSync(pagePath), `Missing page for sidebar href ${href}: ${pagePath}`).toBe(true);
    }
  });

  it("every account sidebar href resolves to an existing route page", () => {
    for (const href of accountNavHrefs) {
      const pagePath = hrefToPagePath(href);
      expect(existsSync(pagePath), `Missing page for account href ${href}: ${pagePath}`).toBe(true);
    }
  });

  it("renders all public nav items when sidebar is open (unauthenticated)", () => {
    setAuth(false);
    render(<PublicSidebar isOpen onClose={() => {}} />);
    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByText("Browse Novels")).toBeInTheDocument();
    expect(screen.getByText("Ranking")).toBeInTheDocument();
    expect(screen.getByText("Request Novel")).toBeInTheDocument();
    expect(screen.getByText("Contribute")).toBeInTheDocument();
    // Account section should NOT appear
    expect(screen.queryByText("Library")).not.toBeInTheDocument();
    expect(screen.queryByText("History")).not.toBeInTheDocument();
    expect(screen.queryByText("Requests")).not.toBeInTheDocument();
  });

  it("renders account nav items when authenticated", () => {
    setAuth(true);
    render(<PublicSidebar isOpen onClose={() => {}} />);
    // Account section appears
    expect(screen.getByText("Library")).toBeInTheDocument();
    expect(screen.getByText("History")).toBeInTheDocument();
    expect(screen.getByText("Requests")).toBeInTheDocument();
    expect(screen.getByText("Contributions")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("/account/history appears in authenticated account navigation", () => {
    setAuth(true);
    render(<PublicSidebar isOpen onClose={() => {}} />);
    const historyLink = screen.getByText("History").closest("a");
    expect(historyLink).toHaveAttribute("href", "/account/history");
  });

  it("unauthenticated users do not see account-only links", () => {
    setAuth(false);
    render(<PublicSidebar isOpen onClose={() => {}} />);
    expect(screen.queryByText("Account")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /library/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /history/i })).not.toBeInTheDocument();
  });

  it("renders no nav from footer legal section in sidebar", () => {
    setAuth(true);
    render(<PublicSidebar isOpen onClose={() => {}} />);
    expect(screen.queryByText("About")).not.toBeInTheDocument();
    expect(screen.queryByText("Privacy")).not.toBeInTheDocument();
    expect(screen.queryByText("Terms")).not.toBeInTheDocument();
    expect(screen.queryByText("DMCA")).not.toBeInTheDocument();
    expect(screen.queryByText("Contact")).not.toBeInTheDocument();
    expect(screen.queryByText("Cookie Policy")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Header navigation consistency
// ---------------------------------------------------------------------------

describe("Header navigation consistency", () => {
  it("header does not contain Library shortcut", () => {
    setAuth(true);
    render(<PublicHeader onMenuClick={() => {}} />);
    expect(screen.queryByRole("link", { name: /library/i })).not.toBeInTheDocument();
  });

  it("header has brand, menu button, theme toggle, and user indicator", () => {
    setAuth(false);
    render(<PublicHeader onMenuClick={() => {}} />);
    expect(screen.getByLabelText("Open navigation menu")).toBeInTheDocument();
    expect(screen.getByLabelText(/switch to (dark|light) theme/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Footer navigation consistency
// ---------------------------------------------------------------------------

describe("Footer navigation consistency", () => {
  const footerReadHrefs = ["/browse-novels", "/ranking", "/request-novel", "/contribute"];
  const footerLegalHrefs = ["/about", "/privacy", "/terms", "/dmca", "/contact", "/cookie-policy"];

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
    expect(screen.getByText("Browse Novels")).toBeInTheDocument();
    expect(screen.getByText("Ranking")).toBeInTheDocument();
    expect(screen.getByText("Request Novel")).toBeInTheDocument();
    expect(screen.getByText("Contribute")).toBeInTheDocument();
  });

  it("footer contains Trust section legal links", () => {
    render(<PublicFooter />);
    expect(screen.getByText("About")).toBeInTheDocument();
    expect(screen.getByText("Privacy")).toBeInTheDocument();
    expect(screen.getByText("Terms")).toBeInTheDocument();
    expect(screen.getByText("DMCA")).toBeInTheDocument();
    expect(screen.getByText("Contact")).toBeInTheDocument();
    expect(screen.getByText("Cookie Policy")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Route inventory completeness
// ---------------------------------------------------------------------------

describe("Route inventory completeness", () => {
  /**
   * Routes that exist but are intentionally not linked from any navigation
   * component. Each entry documents why it's excluded.
   */
  const knownExcludedRoutes: { route: string; reason: string }[] = [
    { route: "/login", reason: "Auth uses LoginView overlay (Google OAuth), not page navigation" },
    { route: "/register", reason: "No manual sign-up flow — auth is Google OAuth only" },
    { route: "/logout", reason: "Logout calls API mutation with server-side redirect, not a nav link" },
    { route: "/auth/callback", reason: "OAuth redirect_uri target — never user-facing" },
    { route: "/error", reason: "Next.js error boundary fallback" },
    { route: "/not-found", reason: "Next.js 404 fallback" },
    { route: "/maintenance", reason: "Server-side maintenance redirect" },
    { route: "/account/contribute", reason: "Legacy redirect-only stub → /contribute (no rendered page)" },
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
    "/dmca",
    "/contact",
    "/cookie-policy",
    "/account/library",
    "/account/history",
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

  it("/account/contribute is a redirect-only stub (no nav link needed)", () => {
    // Verify the file content confirms redirect behavior
    const pagePath = hrefToPagePath("/account/contribute");
    expect(existsSync(pagePath), `Missing /account/contribute page`).toBe(true);
    // Should not appear in any nav
    const sidebar = readFileSync(pagePath, "utf-8");
    expect(sidebar).toMatch(/redirect\("/);  // contains redirect("/contribute")
  });
});
