import { existsSync } from "node:fs";
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
  const footerLegalHrefs = ["/about", "/privacy", "/terms", "/dmca", "/contact", "/cookie-policy"];

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

  it("footer contains Read section links only (no legal duplication into nav area)", () => {
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
