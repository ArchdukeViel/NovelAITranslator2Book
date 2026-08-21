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
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & {
    children: React.ReactNode;
  }) => <a {...props}>{children}</a>,
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
  const actual =
    await vi.importActual<typeof import("@/hooks/public")>("@/hooks/public");
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
          genres: [
            { slug: "fantasy", name_ja: "ファンタジー", name_en: "Fantasy" },
            {
              slug: "slice-of-life",
              name_ja: "日常",
              name_en: "Slice of Life",
            },
          ],
          tags: [
            { name: "magic", name_ja: "魔法" },
            { name: "healing", name_ja: null },
          ],
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
          genres: [
            { slug: "adventure", name_ja: "冒険", name_en: "Adventure" },
          ],
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
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Home page — no fake metrics
// ---------------------------------------------------------------------------

describe("Home page visual honesty", () => {
  it("renders without crashing", () => {
    renderHome();
    expect(screen.getByText("New Novels")).toBeInTheDocument();
    expect(screen.getByText("Recent Updates")).toBeInTheDocument();
  });

  it("uses labeled rails instead of the old grouped date stack", () => {
    renderHome();
    expect(
      screen.getByRole("region", { name: "New releases" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Recently updated" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Today")).not.toBeInTheDocument();
  });

  it("does not display a Preview Feature badge", () => {
    renderHome();
    expect(screen.queryByText("Preview Feature")).not.toBeInTheDocument();
  });

  it("does not display Trending Now as a marketing label", () => {
    renderHome();
    // "trending" appears as the current widget title ("Trending"),
    // but never as a fake marketing claim like "Trending Now"
    expect(screen.queryByText("Trending Now")).not.toBeInTheDocument();
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

  it("shows honest random novel entry instead of ranking placeholder", () => {
    renderHome();
    // The old "Ranking data is not live yet" placeholder is removed.
    expect(
      screen.queryByText(/ranking data is not live/i),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /random novel/i })).toHaveAttribute(
      "href",
      "/random",
    );
  });

  it("does not display a fake library stats label", () => {
    renderHome();
    expect(screen.queryByText(/library stats/i)).not.toBeInTheDocument();
  });

  it("never makes an unsupported Featured claim", () => {
    renderHome();
    expect(screen.queryByText("Featured")).not.toBeInTheDocument();
  });

  it("renders New Novels and Recent Updates sections", () => {
    renderHome();
    expect(screen.getByText("New Novels")).toBeInTheDocument();
    expect(screen.getByText("Recent Updates")).toBeInTheDocument();
    expect(screen.queryByText("Recently Added")).not.toBeInTheDocument();
    expect(screen.queryByText("Latest Updates")).not.toBeInTheDocument();
  });

  it("does not show the old Browse the library section header", () => {
    renderHome();
    expect(screen.queryByText("Browse the library")).not.toBeInTheDocument();
  });
});
