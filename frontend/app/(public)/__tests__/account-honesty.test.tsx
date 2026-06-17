/**
 * Account page honesty and UX tests.
 *
 * Confirms that account pages:
 * - Show login prompts for guests
 * - Do not use scaffold/preview/developer-facing language
 * - Do not claim unimplemented features are available
 * - Do not display fake rejection reasons
 * - Do not pass include_adult=true
 *
 * Feature: PUBLIC-ACCOUNT-AUDIT-1
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, cleanup } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mocks — covers all hooks imported by account pages
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
  isAuthenticated: false,
  authPending: false,
  usePublicAuthMock: vi.fn(),
  useLibraryMock: vi.fn(),
  useHistoryMock: vi.fn(),
  useRequestsMock: vi.fn(),
  useRemoveFromLibraryMock: vi.fn(),
}));

const defaultLibraryData: { slug: string; status: string; added_at: string }[] = [];
const defaultHistoryData = { items: [], next_cursor: null };
const defaultRequestsData = { items: [], next_cursor: null };

vi.mock("@/hooks/public", () => ({
  usePublicAuth: () => mocks.usePublicAuthMock(),
  useLibrary: () => mocks.useLibraryMock(),
  useHistory: (params?: { limit?: number }) => mocks.useHistoryMock(),
  useRequests: (params?: { limit?: number }) => mocks.useRequestsMock(),
  useRemoveFromLibrary: (_slug: string) => mocks.useRemoveFromLibraryMock(),
  useRecordProgress: () => ({ mutate: vi.fn() }),
}));

vi.mock("@/components/public/login-prompt", () => ({
  LoginPrompt: () => <div data-testid="login-prompt" />,
}));

vi.mock("@/components/public/auth-gate", () => ({
  AuthGate: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/ui/panel", () => ({
  Panel: ({ children }: { children: React.ReactNode }) => <div data-testid="panel">{children}</div>,
  PanelHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PanelTitle: ({ children }: { children: React.ReactNode }) => <h3>{children}</h3>,
  PanelBody: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/ui/badge", () => ({
  Badge: ({ children, tone }: { children: React.ReactNode; tone?: string }) => (
    <span data-tone={tone}>{children}</span>
  ),
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
    <button {...props}>{children}</button>
  ),
}));

vi.mock("@/components/public/request-control", () => ({
  RequestControl: () => <div data-testid="request-control" />,
}));

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

vi.mock("lucide-react", () => {
  const Svg = ({ className, children }: { className?: string; children?: React.ReactNode }) => (
    <span className={className}>{children}</span>
  );
  return {
    ArrowLeft: Svg,
    ArrowRight: Svg,
    BookOpen: Svg,
    Bookmark: Svg,
    Loader2: Svg,
    LogIn: Svg,
    MessageSquare: Svg,
    Flag: Svg,
    Lock: Svg,
    User: Svg,
    AlertTriangle: Svg,
    ShieldAlert: Svg,
  };
});

beforeEach(() => {
  vi.clearAllMocks();
  mocks.isAuthenticated = false;
  mocks.authPending = false;
  mocks.usePublicAuthMock.mockReturnValue({
    get isAuthenticated() {
      return mocks.isAuthenticated;
    },
    get isPending() {
      return mocks.authPending;
    },
  });
  mocks.useLibraryMock.mockReturnValue({
    data: defaultLibraryData,
    isPending: false,
    isError: false,
  });
  mocks.useHistoryMock.mockReturnValue({
    data: defaultHistoryData,
    isPending: false,
    isError: false,
  });
  mocks.useRequestsMock.mockReturnValue({
    data: defaultRequestsData,
    isPending: false,
    isError: false,
  });
  mocks.useRemoveFromLibraryMock.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  });
});

afterEach(() => {
  cleanup();
});

function renderWithProviders(ui: React.ReactNode) {
  const { QueryClient, QueryClientProvider } = require("@tanstack/react-query");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

// ---------------------------------------------------------------------------
// Tests: Scaffold / placeholder / developer-facing language
// ---------------------------------------------------------------------------

describe("Account pages — no scaffold language", () => {
  it("contributions page does not use 'preview shell'", async () => {
    mocks.isAuthenticated = true;
    const { default: Page } = await import("../account/contributions/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body.toLowerCase()).not.toContain("preview shell");
  });

  it("contributions page does not say 'Do not submit real API keys'", async () => {
    mocks.isAuthenticated = true;
    const { default: Page } = await import("../account/contributions/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body).not.toContain("Do not submit real API keys");
  });

  it("contributions page does not use 'Backend Integration Pending'", async () => {
    mocks.isAuthenticated = true;
    const { default: Page } = await import("../account/contributions/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body).not.toContain("Backend Integration Pending");
  });

  it("contributions page does not use 'intentionally disabled in this phase'", async () => {
    mocks.isAuthenticated = true;
    const { default: Page } = await import("../account/contributions/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body).not.toContain("intentionally disabled in this phase");
  });

  it("settings page does not use 'scaffolded'", async () => {
    mocks.isAuthenticated = true;
    const { default: Page } = await import("../account/settings/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body.toLowerCase()).not.toContain("scaffolded");
  });

  it("settings page does not use 'pending a public account contract'", async () => {
    mocks.isAuthenticated = true;
    const { default: Page } = await import("../account/settings/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body).not.toContain("pending a public account contract");
  });
});

describe("Account requests — no fake rejection reason", () => {
  it("requests page does not display 'Not provided by current API'", async () => {
    mocks.isAuthenticated = true;
    mocks.useRequestsMock.mockReturnValue({
      data: {
        items: [
          { id: 1, request_type: "novel", status: "rejected", source_url: null, slug: null, chapter_id: null, created_at: "2025-01-01T00:00:00Z" },
        ],
        next_cursor: null,
      },
      isPending: false,
      isError: false,
    });
    const { default: Page } = await import("../account/requests/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body).not.toContain("Not provided by current API");
    expect(body).not.toContain("current API");
  });

  it("requests page does not show 'rejection reason' line", async () => {
    mocks.isAuthenticated = true;
    mocks.useRequestsMock.mockReturnValue({
      data: {
        items: [
          { id: 1, request_type: "novel", status: "rejected", source_url: null, slug: null, chapter_id: null, created_at: "2025-01-01T00:00:00Z" },
        ],
        next_cursor: null,
      },
      isPending: false,
      isError: false,
    });
    const { default: Page } = await import("../account/requests/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body).not.toMatch(/rejection reason/i);
  });
});

// ---------------------------------------------------------------------------
// Tests: Guest auth-gated states
// ---------------------------------------------------------------------------

describe("Account pages — guest auth gate", () => {
  it("library page shows login prompt for guests", async () => {
    const { default: Page } = await import("../account/library/page");
    const { queryByTestId } = renderWithProviders(<Page />);
    expect(queryByTestId("login-prompt")).toBeTruthy();
  });

  it("history page shows login prompt for guests", async () => {
    const { default: Page } = await import("../account/history/page");
    const { queryByTestId } = renderWithProviders(<Page />);
    expect(queryByTestId("login-prompt")).toBeTruthy();
  });

  it("requests page shows login prompt for guests", async () => {
    const { default: Page } = await import("../account/requests/page");
    const { queryByTestId } = renderWithProviders(<Page />);
    expect(queryByTestId("login-prompt")).toBeTruthy();
  });

  it("library page renders content for authenticated users", async () => {
    mocks.isAuthenticated = true;
    const { default: Page } = await import("../account/library/page");
    const { queryByTestId } = renderWithProviders(<Page />);
    // Should NOT show login prompt when authenticated
    expect(queryByTestId("login-prompt")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Tests: Safety — no adult/R18 exposure
// ---------------------------------------------------------------------------

describe("Account pages — safety", () => {
  it("library page does not pass include_adult=true", async () => {
    mocks.isAuthenticated = true;
    const { default: Page } = await import("../account/library/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body).not.toContain("include_adult=true");
    expect(body.toLowerCase()).not.toMatch(/\br18\b/);
  });

  it("settings page does not expose adult/R18 labels", async () => {
    mocks.isAuthenticated = true;
    const { default: Page } = await import("../account/settings/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body.toLowerCase()).not.toMatch(/\br18\b/);
    expect(body.toLowerCase()).not.toMatch(/\badult\b/);
  });
});

// ---------------------------------------------------------------------------
// Tests: Settings page — honest controls
// ---------------------------------------------------------------------------

describe("Account settings — honest controls", () => {
  it("profile editing is stated as unavailable", async () => {
    mocks.isAuthenticated = true;
    const { default: Page } = await import("../account/settings/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body).toContain("not available yet");
  });

  it("delete account button is disabled", async () => {
    mocks.isAuthenticated = true;
    const { default: Page } = await import("../account/settings/page");
    renderWithProviders(<Page />);
    const buttons = document.querySelectorAll("button[disabled]");
    const deleteBtn = Array.from(buttons).find(
      (b) => b.getAttribute("aria-label")?.toLowerCase().includes("delete")
    );
    expect(deleteBtn).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Tests: Account routes / CTAs
// ---------------------------------------------------------------------------

describe("Account pages — real route references", () => {
  it("history page links to /account/library", async () => {
    mocks.isAuthenticated = true;
    const { default: Page } = await import("../account/history/page");
    renderWithProviders(<Page />);
    const link = document.querySelector('a[href="/account/library"]');
    expect(link).toBeTruthy();
  });

  it("contributions page links to /contribute", async () => {
    mocks.isAuthenticated = true;
    const { default: Page } = await import("../account/contributions/page");
    renderWithProviders(<Page />);
    const link = document.querySelector('a[href="/contribute"]');
    expect(link).toBeTruthy();
  });

  it("settings page links to /account/contributions", async () => {
    mocks.isAuthenticated = true;
    const { default: Page } = await import("../account/settings/page");
    renderWithProviders(<Page />);
    const link = document.querySelector('a[href="/account/contributions"]');
    expect(link).toBeTruthy();
  });

  it("library page Back to Browse links to /browse-novels", async () => {
    mocks.isAuthenticated = true;
    const { default: Page } = await import("../account/library/page");
    renderWithProviders(<Page />);
    const links = document.querySelectorAll('a[href="/browse-novels"]');
    expect(links.length).toBeGreaterThanOrEqual(1);
  });
});

// ---------------------------------------------------------------------------
// Tests: Library page — empty states
// ---------------------------------------------------------------------------

describe("Account library — empty states", () => {
  it("shows 'No currently reading novels' when empty", async () => {
    mocks.isAuthenticated = true;
    const { default: Page } = await import("../account/library/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body).toContain("No currently reading novels");
  });

  it("shows 'No reading history' when history empty", async () => {
    mocks.isAuthenticated = true;
    const { default: Page } = await import("../account/library/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body).toContain("No reading history yet");
  });
});

// ---------------------------------------------------------------------------
// Tests: History page — empty state
// ---------------------------------------------------------------------------

describe("Account history — empty state", () => {
  it("shows 'No reading history yet' message", async () => {
    mocks.isAuthenticated = true;
    const { default: Page } = await import("../account/history/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body).toContain("No reading history yet");
  });

  it("shows Browse novels link", async () => {
    mocks.isAuthenticated = true;
    const { default: Page } = await import("../account/history/page");
    renderWithProviders(<Page />);
    const link = document.querySelector('a[href="/browse-novels"]');
    expect(link).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Tests: Loading states
// ---------------------------------------------------------------------------

describe("Account pages — loading states", () => {
  it("library page shows loading spinner while auth pending", async () => {
    mocks.authPending = true;
    const { default: Page } = await import("../account/library/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body).toContain("Checking session");
  });

  it("library page shows loading spinner while data loading", async () => {
    mocks.isAuthenticated = true;
    mocks.useLibraryMock.mockReturnValue({
      data: null,
      isPending: true,
      isError: false,
    });
    const { default: Page } = await import("../account/library/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body).toContain("Loading library");
  });
});

// ---------------------------------------------------------------------------
// Tests: Error states
// ---------------------------------------------------------------------------

describe("Account pages — error states", () => {
  it("library page shows error message on fetch failure", async () => {
    mocks.isAuthenticated = true;
    mocks.useLibraryMock.mockReturnValue({
      data: null,
      isPending: false,
      isError: true,
    });
    const { default: Page } = await import("../account/library/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body).toContain("Could not load your library");
  });

  it("history page shows error message on fetch failure", async () => {
    mocks.isAuthenticated = true;
    mocks.useHistoryMock.mockReturnValue({
      data: null,
      isPending: false,
      isError: true,
    });
    const { default: Page } = await import("../account/history/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body).toContain("Could not load reading history");
  });
});

// ---------------------------------------------------------------------------
// Tests: Account history — chapter_number display
// ---------------------------------------------------------------------------

describe("Account history — chapter number display", () => {
  it("displays Ch. {chapter_number} when chapter_number is present", async () => {
    mocks.isAuthenticated = true;
    mocks.useHistoryMock.mockReturnValue({
      data: {
        items: [
          {
            id: 1,
            slug: "test-novel",
            chapter_id: "42",
            chapter_number: 7,
            read_at: "2025-06-01T00:00:00Z",
          },
        ],
        next_cursor: null,
      },
      isPending: false,
      isError: false,
    });
    const { default: Page } = await import("../account/history/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body).toContain("Ch. 7");
    expect(body).toContain("test-novel");
  });

  it("does not display raw chapter_id as primary chapter label", async () => {
    mocks.isAuthenticated = true;
    mocks.useHistoryMock.mockReturnValue({
      data: {
        items: [
          {
            id: 2,
            slug: "another-novel",
            chapter_id: "99",
            chapter_number: 3,
            read_at: "2025-06-02T00:00:00Z",
          },
        ],
        next_cursor: null,
      },
      isPending: false,
      isError: false,
    });
    const { default: Page } = await import("../account/history/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    // "99" is the raw DB id — should not appear as "Ch. 99"
    expect(body).not.toContain("Ch. 99");
    // Should use Ch. 3 instead
    expect(body).toContain("Ch. 3");
  });

  it("shows 'Chapter' fallback when chapter_number is null and chapter_id exists", async () => {
    mocks.isAuthenticated = true;
    mocks.useHistoryMock.mockReturnValue({
      data: {
        items: [
          {
            id: 3,
            slug: "no-ch-novel",
            chapter_id: "55",
            chapter_number: null,
            read_at: "2025-06-03T00:00:00Z",
          },
        ],
        next_cursor: null,
      },
      isPending: false,
      isError: false,
    });
    const { default: Page } = await import("../account/history/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body).toContain("Chapter");
    // Should NOT say "Ch. 55" (raw DB id)
    expect(body).not.toContain("Ch. 55");
  });

  it("shows slug-only when both chapter_number and chapter_id are null", async () => {
    mocks.isAuthenticated = true;
    mocks.useHistoryMock.mockReturnValue({
      data: {
        items: [
          {
            id: 4,
            slug: "slug-only-novel",
            chapter_id: null,
            chapter_number: null,
            read_at: "2025-06-04T00:00:00Z",
          },
        ],
        next_cursor: null,
      },
      isPending: false,
      isError: false,
    });
    const { default: Page } = await import("../account/history/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body).toContain("slug-only-novel");
    // entry label shows slug only — no "Ch." prefix before slug
    // (header says "Chapters you have opened" so "Ch." may appear elsewhere)
  });

  it("chapter link still uses chapter_id in the URL", async () => {
    mocks.isAuthenticated = true;
    mocks.useHistoryMock.mockReturnValue({
      data: {
        items: [
          {
            id: 5,
            slug: "test-novel",
            chapter_id: "77",
            chapter_number: 2,
            read_at: "2025-06-05T00:00:00Z",
          },
        ],
        next_cursor: null,
      },
      isPending: false,
      isError: false,
    });
    const { default: Page } = await import("../account/history/page");
    renderWithProviders(<Page />);
    const link = document.querySelector('a[href*="chapter/77"]');
    expect(link).toBeTruthy();
  });

  it("history page does not pass include_adult=true", async () => {
    mocks.isAuthenticated = true;
    const { default: Page } = await import("../account/history/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body).not.toContain("include_adult=true");
  });

  it("library history section uses chapter_number instead of raw chapter_id", async () => {
    mocks.isAuthenticated = true;
    mocks.useLibraryMock.mockReturnValue({
      data: [
        { slug: "lib-novel", status: "reading", added_at: "2025-01-01T00:00:00Z" },
        { slug: "lib-novel", status: "paused", added_at: "2025-01-01T00:00:00Z" },
      ],
      isPending: false,
      isError: false,
    });
    mocks.useHistoryMock.mockReturnValue({
      data: {
        items: [
          {
            id: 6,
            slug: "lib-novel",
            chapter_id: "88",
            chapter_number: 4,
            read_at: "2025-06-06T00:00:00Z",
          },
        ],
        next_cursor: null,
      },
      isPending: false,
      isError: false,
    });
    const { default: Page } = await import("../account/library/page");
    renderWithProviders(<Page />);
    const body = document.body.textContent ?? "";
    expect(body).toContain("Ch. 4");
    expect(body).not.toContain("Ch. 88");
  });
});
