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

const mocks = vi.hoisted(() => ({
  catalogQuery: vi.fn(),
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
    useCatalog: () => mocks.catalogQuery(),
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
  vi.clearAllMocks();
  mocks.catalogQuery.mockReturnValue({
    data: {
      novels: [
        {
          novel_id: "n1",
          slug: "test-novel-1",
          title: "Test Novel One",
          author: "Author One",
          language: "ja",
          status: "Ongoing",
          chapter_count: 42,
          translated_count: 15,
          added_at: "2026-06-17T08:00:00Z",
          genres: ["fantasy", "slice-of-life"],
          tags: ["magic", "healing"],
        },
        {
          novel_id: "n2",
          slug: "test-novel-2",
          title: "Test Novel Two",
          author: "Author Two",
          language: "ja",
          status: "Completed",
          chapter_count: 120,
          translated_count: 120,
          added_at: "2026-06-16T10:00:00Z",
          genres: ["adventure"],
          tags: [],
        },
        {
          novel_id: "n3",
          slug: "test-novel-3",
          title: "Test Novel Three",
          author: "Author Three",
          language: "en",
          status: "Ongoing",
          chapter_count: 5,
          translated_count: 2,
          added_at: "2026-06-12T09:00:00Z",
          genres: [],
          tags: [],
        },
      ],
      total: 3,
      page: 1,
      page_size: 8,
    },
    isPending: false,
    isError: false,
    error: null,
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
    expect(screen.getByText("Recently Added")).toBeInTheDocument();
  });

  it("shows grouped dates in the Recently Added section", () => {
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

  it("shows honest catalog CTA instead of ranking placeholder", () => {
    renderHome();
    // The old "Ranking data is not live yet" placeholder is removed.
    expect(
      screen.queryByText(/ranking data is not live/i)
    ).not.toBeInTheDocument();
    // Replaced by "Browse the catalog" CTA
    const browseLinks = screen.getAllByText("Browse the catalog");
    expect(browseLinks.length).toBeGreaterThanOrEqual(1);
  });

  it("does not display a fake library stats label", () => {
    renderHome();
    expect(screen.queryByText(/library stats/i)).not.toBeInTheDocument();
  });

  it("displays Latest Release eyebrow on hero section", () => {
    renderHome();
    expect(screen.getByText("Latest Release")).toBeInTheDocument();
  });

  it("renders Recently Added section (renamed from Latest Updates)", () => {
    renderHome();
    expect(screen.getByText("Recently Added")).toBeInTheDocument();
    // Old "Latest Updates" header should not appear
    expect(screen.queryByText("Latest Updates")).not.toBeInTheDocument();
  });

  it("does not show the old Browse the library section header", () => {
    renderHome();
    expect(screen.queryByText("Browse the library")).not.toBeInTheDocument();
  });
});
