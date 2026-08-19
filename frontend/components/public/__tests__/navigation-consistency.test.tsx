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
import { PublicSidebar } from "@/components/public/public-sidebar";
import { fireEvent } from "@testing-library/react";

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
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
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
          user: {
            id: 1,
            email: "a@b.c",
            role: "user" as const,
            is_authenticated: true,
          },
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
    "/account/request-novels",
    "/account/library",
    "/ranking",
  ];

  it("every header href resolves to an existing route page", () => {
    for (const href of headerNavHrefs) {
      const pagePath = hrefToPagePath(href);
      expect(
        existsSync(pagePath),
        `Missing page for header href ${href}: ${pagePath}`,
      ).toBe(true);
    }
  });

  it("renders desktop header nav items when authenticated (Home lives in the fixed sidebar)", () => {
    setAuth(true);
    renderWithQuery(<PublicHeader />);

    const primaryNav = screen.getByRole("navigation", { name: /^primary$/i });
    expect(
      within(primaryNav).getByRole("link", { name: /^browse$/i }),
    ).toBeInTheDocument();
    expect(
      within(primaryNav).getByRole("link", { name: /^request$/i }),
    ).toBeInTheDocument();
    expect(
      within(primaryNav).getByRole("link", { name: /^library$/i }),
    ).toBeInTheDocument();
    expect(
      within(primaryNav).getByRole("link", { name: /^ranking$/i }),
    ).toBeInTheDocument();
    // Stitch design: Home is reachable from the fixed sidebar, not the header nav.
    expect(
      within(primaryNav).queryByRole("link", { name: /^home$/i }),
    ).not.toBeInTheDocument();

    // Search field — now a button opening the shared overlay (DESIGN.md — Search contract)
    expect(
      screen.getByRole("button", { name: /search novels/i }),
    ).toBeInTheDocument();

    // Notification bell present
    expect(screen.getByLabelText(/notifications/i)).toBeInTheDocument();

    // Account menu dropdown trigger
    const userMenuButton = screen.getByRole("button", { name: /user menu/i });
    expect(userMenuButton).toBeInTheDocument();

    // Open dropdown to check items
    fireEvent.click(userMenuButton);
    expect(
      screen.getByRole("menuitem", { name: /settings/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: /contributions/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: /sign out/i }),
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole("group", { name: /theme selection/i })[0],
    ).toBeInTheDocument();

    // Hamburger toggle opens the fixed sidebar (Stitch "Fixed Sidebar" design)
    expect(screen.getByLabelText(/open navigation menu/i)).toBeInTheDocument();
  });

  it("renders desktop header nav items when guest (Home lives in the fixed sidebar)", () => {
    setAuth(false);
    renderWithQuery(<PublicHeader />);

    const primaryNav = screen.getByRole("navigation", { name: /^primary$/i });
    expect(
      within(primaryNav).getByRole("link", { name: /^browse$/i }),
    ).toBeInTheDocument();
    expect(
      within(primaryNav).getByRole("link", { name: /^request$/i }),
    ).toBeInTheDocument();
    expect(
      within(primaryNav).getByRole("link", { name: /^library$/i }),
    ).toBeInTheDocument();
    expect(
      within(primaryNav).getByRole("link", { name: /^ranking$/i }),
    ).toBeInTheDocument();
    // Stitch design: Home is reachable from the fixed sidebar, not the header nav.
    expect(
      within(primaryNav).queryByRole("link", { name: /^home$/i }),
    ).not.toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: /search novels/i }),
    ).toBeInTheDocument();

    // Notification bell is hidden for guests (DESIGN.md guest behavior)
    expect(screen.queryByLabelText(/notifications/i)).not.toBeInTheDocument();

    // Account menu dropdown trigger
    const userMenuButton = screen.getByRole("button", {
      name: /user account and theme menu/i,
    });
    expect(userMenuButton).toBeInTheDocument();

    // Open dropdown to check guest items
    fireEvent.click(userMenuButton);
    expect(screen.getByRole("menuitem", { name: /sign in/i })).toHaveAttribute(
      "href",
      "/login?mode=signin",
    );
    expect(
      screen.getAllByRole("group", { name: /theme selection/i })[0],
    ).toBeInTheDocument();

    // No sign-out
    expect(screen.queryByLabelText(/sign out/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/signing out/i)).not.toBeInTheDocument();

    // Hamburger toggle opens the fixed sidebar (Stitch "Fixed Sidebar" design)
    expect(screen.getByLabelText(/open navigation menu/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Fixed sidebar (Stitch "Fixed Sidebar" design)
// ---------------------------------------------------------------------------

describe("Fixed sidebar", () => {
  const sidebarHrefs = [
    "/home",
    "/news",
    "/account/library",
    "/browse-novels",
    "/ranking",
    "/random",
    "/account/request-novels",
    "/account/contributions",
    "/faq",
  ];

  it("every sidebar href resolves to an existing route page", () => {
    for (const href of sidebarHrefs) {
      const pagePath = hrefToPagePath(href);
      expect(
        existsSync(pagePath),
        `Missing page for sidebar href ${href}: ${pagePath}`,
      ).toBe(true);
    }
  });

  it("opens via the hamburger and shows nav links, then closes", () => {
    setAuth(true);
    renderWithQuery(<PublicSidebar />);

    const toggle = screen.getByLabelText(/open navigation menu/i);
    fireEvent.click(toggle);

    const nav = screen.getByRole("navigation", { name: /sidebar/i });
    expect(within(nav).getByRole("link", { name: /home/i })).toHaveAttribute(
      "href",
      "/home",
    );
    expect(within(nav).getByRole("link", { name: /news/i })).toHaveAttribute(
      "href",
      "/news",
    );
    expect(within(nav).getByRole("link", { name: /library/i })).toHaveAttribute(
      "href",
      "/account/library",
    );
    expect(
      within(nav).getByRole("link", { name: /browse novels/i }),
    ).toHaveAttribute("href", "/browse-novels");
    expect(within(nav).getByRole("link", { name: /ranking/i })).toHaveAttribute(
      "href",
      "/ranking",
    );
    expect(
      within(nav).getByRole("link", { name: /random novel/i }),
    ).toHaveAttribute("href", "/random");
    expect(
      within(nav).getByRole("link", { name: /request novels/i }),
    ).toHaveAttribute("href", "/account/request-novels");
    expect(
      within(nav).getByRole("link", { name: /contributions/i }),
    ).toHaveAttribute("href", "/account/contributions");
    expect(within(nav).getByRole("link", { name: /faq/i })).toHaveAttribute(
      "href",
      "/faq",
    );

    fireEvent.click(screen.getByLabelText(/close navigation menu/i));
    // Panel closes by translating off-canvas; assert toggle is collapsed again.
    expect(screen.getByLabelText(/open navigation menu/i)).toHaveAttribute(
      "aria-expanded",
      "false",
    );
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
      expect(
        existsSync(pagePath),
        `Missing page for tab bar href ${href}: ${pagePath}`,
      ).toBe(true);
    }
  });

  it("renders tab bar items and respects guest/auth state", () => {
    // Guest: account + library tabs should route to sign-in
    setAuth(false);
    render(<MobileTabBar />);

    expect(screen.getByRole("link", { name: /^home$/i })).toHaveAttribute(
      "href",
      "/home",
    );
    expect(screen.getByRole("link", { name: /^browse$/i })).toHaveAttribute(
      "href",
      "/browse-novels",
    );
    // Search tab is a button that opens the shared overlay, not a link
    expect(
      screen.getByRole("button", { name: /^search$/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /^search$/i }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^library$/i })).toHaveAttribute(
      "href",
      "/login?mode=signin&callbackUrl=%2Faccount%2Flibrary",
    );
    expect(screen.getByRole("link", { name: /^account$/i })).toHaveAttribute(
      "href",
      "/login?mode=signin&callbackUrl=%2Faccount",
    );

    // Authenticated: library and account tabs point to their real destinations
    cleanup();
    setAuth(true);
    render(<MobileTabBar />);

    expect(screen.getByRole("link", { name: /^library$/i })).toHaveAttribute(
      "href",
      "/account/library",
    );
    expect(screen.getByRole("link", { name: /^account$/i })).toHaveAttribute(
      "href",
      "/account",
    );
  });
});

// ---------------------------------------------------------------------------
// Footer navigation consistency (unchanged)
// ---------------------------------------------------------------------------

describe("Footer navigation consistency", () => {
  const footerReadHrefs = [
    "/about",
    "/support",
    "/faq",
    "/news",
    "/dmca",
    "/cookie-policy",
    "/privacy",
    "/terms",
  ];
  const footerLegalHrefs = [
    "/about",
    "/privacy",
    "/terms",
    "/legal",
    "/dmca",
    "/contact",
    "/cookie-policy",
  ];

  it("every footer Read section href resolves to an existing route page", () => {
    for (const href of footerReadHrefs) {
      const pagePath = hrefToPagePath(href);
      expect(
        existsSync(pagePath),
        `Missing page for footer Read href ${href}: ${pagePath}`,
      ).toBe(true);
    }
  });

  it("every footer legal href resolves to an existing route page", () => {
    for (const href of footerLegalHrefs) {
      const pagePath = hrefToPagePath(href);
      expect(
        existsSync(pagePath),
        `Missing page for footer href ${href}: ${pagePath}`,
      ).toBe(true);
    }
  });

  it("footer does not contain Library link", () => {
    render(<PublicFooter />);
    expect(
      screen.queryByRole("link", { name: /library/i }),
    ).not.toBeInTheDocument();
  });

  it("footer contains essential navigation and legal links", () => {
    render(<PublicFooter />);
    expect(screen.getByText(/about/i)).toBeInTheDocument();
    expect(screen.getByText(/support/i)).toBeInTheDocument();
    expect(screen.getByText(/faq/i)).toBeInTheDocument();
    expect(screen.getByText(/news/i)).toBeInTheDocument();
    expect(screen.getByText(/privacy/i)).toBeInTheDocument();
    expect(screen.getByText(/terms/i)).toBeInTheDocument();
    expect(screen.getByText(/dmca/i)).toBeInTheDocument();
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
    {
      route: "/login",
      reason:
        "Auth is reached from header/sidebar as /login?mode=signin or /login?mode=signup",
    },
    {
      route: "/logout",
      reason:
        "Logout calls API mutation with server-side redirect, not a nav link",
    },
    {
      route: "/auth/callback",
      reason: "OAuth redirect_uri target — never user-facing",
    },
    { route: "/error", reason: "Next.js error boundary fallback" },
    { route: "/not-found", reason: "Next.js 404 fallback" },
    { route: "/maintenance", reason: "Server-side maintenance redirect" },
    {
      route: "/",
      reason: "Root redirects to /home (page.tsx contains redirect())",
    },
  ];

  /**
   * Routes that SHOULD be reachable from navigation. Every route not in
   * knownExcludedRoutes must have at least one nav entry.
   */
  const navLinkedRoutes = new Set([
    "/home",
    "/browse-novels",
    "/ranking",
    "/random",
    "/account/request-novels",
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
    "/account/reviews",
    "/account/notifications",
    "/account/contributions",
    "/account/settings",
    "/faq",
    "/news",
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

    const notCovered = allRoutes.filter(
      (route) => !navLinked.has(route) && !excluded.includes(route),
    );
    // Dynamic routes (with [param]) are covered by card/row components
    const staticNotFound = notCovered.filter(
      (r) => !r.includes("[") && !r.includes("]"),
    );

    expect(
      staticNotFound,
      `Routes without nav link or exclusion doc: ${staticNotFound.join(", ")}`,
    ).toHaveLength(0);
  });
});
