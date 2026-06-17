/**
 * Visual-atmosphere honesty tests.
 *
 * Confirms that public pages do not render fake metric labels, fake
 * trending copy, fake ratings/views, or unsupported filter behavior.
 *
 * Feature: visual-atmosphere-polish
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import HomePage from "@/app/(public)/home/page";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("next/link", () => ({
  default: ({
    children,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { children: React.ReactNode }) => (
    <a {...props}>{children}</a>
  ),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/home",
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(""),
}));

vi.mock("@/hooks/public", async () => {
  const actual = await vi.importActual<typeof import("@/hooks/public")>(
    "@/hooks/public"
  );
  return {
    ...actual,
    usePublicAuth: () => ({
      isAuthenticated: false,
      isPending: false,
      isPublicUser: false,
      isOwner: false,
      authState: null,
      user: null,
    }),
    useLibraryItem: () => ({ data: undefined, isPending: false }),
    useAddToLibrary: () => ({ mutate: vi.fn(), isPending: false }),
    useRemoveFromLibrary: () => ({ mutate: vi.fn(), isPending: false }),
    useLogout: () => vi.fn(),
  };
});

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

let queryClient: QueryClient;

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function renderHome() {
  return render(
    <QueryClientProvider client={queryClient}>
      <HomePage />
    </QueryClientProvider>
  );
}

// ---------------------------------------------------------------------------
// Home page — no fake metrics
// ---------------------------------------------------------------------------

describe("Home page visual honesty", () => {
  it("renders without crashing", () => {
    renderHome();
    expect(screen.getByText("Latest Updates")).toBeInTheDocument();
  });

  it("shows grouped dates in the latest updates section", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    renderHome();

    expect(screen.getByText("Today")).toBeInTheDocument();
    expect(screen.getByText("Yesterday")).toBeInTheDocument();
    expect(screen.getByText("1 week ago")).toBeInTheDocument();
  });

  it("does not display a Preview Feature badge", () => {
    renderHome();
    expect(screen.queryByText("Preview Feature")).not.toBeInTheDocument();
  });

  it("does not display Trending Now as a marketing label", () => {
    renderHome();
    // "trending" may appear in honest disclaimers about data gaps,
    // but never as "Trending Now" or "Trending" section header
    expect(screen.queryByText("Trending Now")).not.toBeInTheDocument();
    const trendingHeaders = screen.queryAllByRole("heading", { name: /trending/i });
    expect(trendingHeaders.length).toBe(0);
  });

  it("does not display fake views or ratings labels", () => {
    renderHome();
    // Check for fake-metric patterns, not bare words which appear in disclaimers
    expect(screen.queryByText(/^\d+ views$/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^\d+ ratings?$/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/popularity score/i)).not.toBeInTheDocument();
  });

  it("does not display Ranking Preview section with fake numbered ranks", () => {
    renderHome();
    expect(screen.queryByText("Ranking Preview")).not.toBeInTheDocument();
  });

  it("shows honest ranking message instead of fake ranking data", () => {
    renderHome();
    expect(
      screen.getByText(/ranking data is not live/i)
    ).toBeInTheDocument();
  });

  it("shows Browse the library section linking to catalog", () => {
    renderHome();
    expect(screen.getByText("Browse the library")).toBeInTheDocument();
    expect(screen.getByText("Browse novels")).toBeInTheDocument();
  });

  it("does not display Backend trending metrics are pending text", () => {
    renderHome();
    expect(
      screen.queryByText(/backend trending metrics are pending/i)
    ).not.toBeInTheDocument();
  });

  it("does not display a fake library stats label", () => {
    renderHome();
    expect(screen.queryByText(/library stats/i)).not.toBeInTheDocument();
  });

  it("displays Editor's Pick not Featured - Editor's Pick", () => {
    renderHome();
    expect(screen.getByText("Editor's Pick")).toBeInTheDocument();
    expect(
      screen.queryByText(/Featured.*Editor/i)
    ).not.toBeInTheDocument();
  });
});
