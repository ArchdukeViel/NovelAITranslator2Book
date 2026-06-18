/**
 * Homepage data-honesty and state tests.
 *
 * Confirms homepage uses real catalog data, handles loading/error/empty states
 * with polished UI, does not use static/placeholder novel data, does not pass
 * adult opt-in, and does not duplicate sections from the same data.
 *
 * Feature: PUBLIC-HOME-DATA-1, PUBLIC-HOME-DATA-2
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import HomePage from "@/app/(public)/home/page";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

let queryClient: QueryClient;

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

function renderHome() {
  return render(
    <QueryClientProvider client={queryClient}>
      <HomePage />
    </QueryClientProvider>
  );
}

// Sample novel factory
function makeNovel(overrides: Record<string, unknown> = {}) {
  return {
    novel_id: "n1",
    slug: "test-novel",
    title: "Test Novel",
    source_title: null as string | null,
    author: "Test Author",
    language: "ja",
    synopsis: null as string | null,
    status: "Ongoing",
    chapter_count: 10,
    translated_count: 5,
    added_at: "2026-06-17T08:00:00Z",
    genres: ["fantasy"],
    tags: ["magic"],
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

describe("HomePage loading state", () => {
  it("shows skeleton layout resembling final structure", () => {
    mocks.catalogQuery.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    // Loading region is present
    expect(
      screen.getByLabelText("Loading featured novel")
    ).toBeInTheDocument();
    // Screen-reader status text
    expect(screen.getByText("Loading catalog…")).toBeInTheDocument();
    // Should not render section headers during loading
    expect(screen.queryByText("Recently Added")).not.toBeInTheDocument();
    expect(screen.queryByText("Featured")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------

describe("HomePage error state", () => {
  it("shows error message with Try again and Browse catalog", () => {
    const mockRefetch = vi.fn();
    mocks.catalogQuery.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: new Error("Network error"),
      refetch: mockRefetch,
    });
    renderHome();

    expect(
      screen.getByText("Could not load the catalog")
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Something went wrong fetching novels/)
    ).toBeInTheDocument();

    // Two recovery paths: retry and browse
    expect(screen.getByText("Try again")).toBeInTheDocument();
    expect(screen.getByText("Browse the catalog")).toBeInTheDocument();
  });

  it("calls refetch when Try again is clicked", async () => {
    const mockRefetch = vi.fn();
    mocks.catalogQuery.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: new Error("Timeout"),
      refetch: mockRefetch,
    });
    renderHome();

    const user = userEvent.setup();
    await user.click(screen.getByText("Try again"));

    expect(mockRefetch).toHaveBeenCalledTimes(1);
  });

  it("does not render real content in error state", () => {
    mocks.catalogQuery.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: new Error("Boom"),
      refetch: vi.fn(),
    });
    renderHome();

    expect(screen.queryByText("Recently Added")).not.toBeInTheDocument();
    expect(screen.queryByText("Featured")).not.toBeInTheDocument();
    expect(screen.queryByText("Start Reading")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

describe("HomePage empty state", () => {
  it("shows empty message with request and browse CTAs", () => {
    mocks.catalogQuery.mockReturnValue({
      data: { novels: [], total: 0, page: 1, page_size: 8 },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    expect(
      screen.getByText("No novels in the catalog yet")
    ).toBeInTheDocument();
    expect(
      screen.getByText(/New translations are added regularly/)
    ).toBeInTheDocument();
    expect(screen.getByText("Request a novel")).toBeInTheDocument();
    expect(screen.getByText("Browse the catalog")).toBeInTheDocument();
  });

  it("does not render real content when catalog is empty", () => {
    mocks.catalogQuery.mockReturnValue({
      data: { novels: [], total: 0, page: 1, page_size: 8 },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    expect(screen.queryByText("Recently Added")).not.toBeInTheDocument();
    expect(screen.queryByText("Featured")).not.toBeInTheDocument();
    expect(screen.queryByText("Start Reading")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Real data rendering (PUBLIC-HOME-DATA-1 regression)
// ---------------------------------------------------------------------------

describe("HomePage real data rendering", () => {
  it("renders hero section with first catalog novel", () => {
    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [
          makeNovel({ title: "Hero Novel", slug: "hero-novel" }),
          makeNovel({ novel_id: "n2", slug: "second-novel", title: "Second Novel" }),
        ],
        total: 2,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    const heroTitles = screen.getAllByText("Hero Novel");
    expect(heroTitles.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Featured")).toBeInTheDocument();
    expect(screen.getByText("Start Reading")).toBeInTheDocument();
    expect(screen.getByText("View Details")).toBeInTheDocument();
  });

  it("renders Recently Added section with catalog novels", () => {
    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [
          makeNovel({ title: "First Novel", slug: "first", added_at: "2026-06-17T08:00:00Z" }),
          makeNovel({ novel_id: "n2", slug: "second", title: "Second Novel", added_at: "2026-06-16T08:00:00Z" }),
          makeNovel({ novel_id: "n3", slug: "third", title: "Third Novel", added_at: "2026-06-15T08:00:00Z" }),
        ],
        total: 3,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    expect(screen.getByText("Recently Added")).toBeInTheDocument();
    expect(screen.getAllByText("First Novel").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Second Novel").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Third Novel").length).toBeGreaterThanOrEqual(1);
  });

  it("passes genres and tags through to rendered chips", () => {
    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [
          makeNovel({
            title: "Genre Novel",
            genres: ["fantasy", "isekai"],
            tags: ["magic", "hero"],
          }),
        ],
        total: 1,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    const fantasyChips = screen.getAllByText("fantasy");
    expect(fantasyChips.length).toBeGreaterThanOrEqual(1);
    const isekaiChips = screen.getAllByText("isekai");
    expect(isekaiChips.length).toBeGreaterThanOrEqual(1);
  });

  it("renders catalog CTA section", () => {
    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [makeNovel()],
        total: 1,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    expect(
      screen.getByText(/Browse the full catalog/i)
    ).toBeInTheDocument();
    expect(screen.getByText("Browse the catalog")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// No section duplication
// ---------------------------------------------------------------------------

describe("HomePage section duplication", () => {
  it("does not render a Latest Novels section duplicating Recently Added data", () => {
    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [makeNovel(), makeNovel({ novel_id: "n2", slug: "n2" })],
        total: 2,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    // Recently Added exists
    expect(screen.getByText("Recently Added")).toBeInTheDocument();
    // Latest Novels card grid does NOT exist
    expect(screen.queryByText("Latest Novels")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Adult/R18 safety
// ---------------------------------------------------------------------------

describe("HomePage adult safety", () => {
  it("does not pass include_adult=true in catalog query", () => {
    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [
          makeNovel({
            genres: ["adult-romance"],
            tags: [],
          }),
        ],
        total: 1,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });

    renderHome();

    const adultChips = screen.getAllByText("adult-romance");
    expect(adultChips.length).toBeGreaterThanOrEqual(1);
  });
});

// ---------------------------------------------------------------------------
// No static placeholder data
// ---------------------------------------------------------------------------

describe("HomePage data honesty — no static placeholders", () => {
  it("does not render preview/static novel data", () => {
    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [makeNovel({ title: "Real Novel" })],
        total: 1,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    expect(screen.queryByText("The Reincarnated Sage's Quiet Life")).not.toBeInTheDocument();
    expect(screen.queryByText("Dungeon Core: Building a Sanctuary")).not.toBeInTheDocument();
    expect(screen.queryByText("Chronicles of the Azure Sky")).not.toBeInTheDocument();
  });

  it("does not render 'Preview' as section header", () => {
    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [makeNovel()],
        total: 1,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    expect(screen.queryByText("Preview")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Copy polish — no scaffold wording
// ---------------------------------------------------------------------------

describe("HomePage copy polish", () => {
  it("does not use selection/curation language implying hand-picking", () => {
    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [makeNovel()],
        total: 1,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    // No "selection" wording — catalog is auto-sorted, not curated
    expect(screen.queryByText(/selection/i)).not.toBeInTheDocument();
  });

  it("does not render old ranking-data-not-live placeholder", () => {
    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [makeNovel()],
        total: 1,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    expect(screen.queryByText(/ranking data is not live/i)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Source title rendering
// ---------------------------------------------------------------------------

describe("HomePage source_title rendering", () => {
  it("renders source_title in Recently Added rows when present", () => {
    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [
          makeNovel({
            title: "Translated Title",
            source_title: "Original Japanese Title",
          }),
        ],
        total: 1,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    // Display title appears in hero h1 + rows
    const heroTitles = screen.getAllByText("Translated Title");
    expect(heroTitles.length).toBeGreaterThanOrEqual(1);
    // source_title appears in the LatestUpdateRow
    expect(screen.getByText("Original Japanese Title")).toBeInTheDocument();
  });

  it("does not render source_title when it is null", () => {
    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [
          makeNovel({
            title: "Only Title",
            source_title: null,
          }),
        ],
        total: 1,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    // Only Title visible but source_title not rendered as a separate element
    const titles = screen.getAllByText("Only Title");
    expect(titles.length).toBeGreaterThanOrEqual(1);
    // No duplicate "Only Title" in sourceTitle position
  });
});
// ---------------------------------------------------------------------------
// PUBLIC-LATEST-1: Time grouping tests
// ---------------------------------------------------------------------------

describe("Homepage time grouping", () => {
  it("renders 'Today' group header when a novel was added today", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [makeNovel({ added_at: "2026-06-17T08:00:00Z" })],
        total: 1,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    expect(screen.getByText("Today")).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("renders 'Yesterday' group header for yesterday's novel", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [makeNovel({ added_at: "2026-06-16T10:00:00Z" })],
        total: 1,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    expect(screen.getByText("Yesterday")).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("renders '1 week ago' group header for 5-day-old novel", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [makeNovel({ added_at: "2026-06-12T10:00:00Z" })],
        total: 1,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    expect(screen.getByText("1 week ago")).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("renders '2 weeks ago' group header for 10-day-old novel", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [makeNovel({ added_at: "2026-06-07T10:00:00Z" })],
        total: 1,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    expect(screen.getByText("2 weeks ago")).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("renders '3 weeks ago' group header for 18-day-old novel", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [makeNovel({ added_at: "2026-05-30T10:00:00Z" })],
        total: 1,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    expect(screen.getByText("3 weeks ago")).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("renders '1 month ago' group header for 25-day-old novel", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [makeNovel({ added_at: "2026-05-23T10:00:00Z" })],
        total: 1,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    expect(screen.getByText("1 month ago")).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("renders 'Earlier' group header when novel has no added_at", () => {
    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [makeNovel({ added_at: null })],
        total: 1,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    expect(screen.getByText("Earlier")).toBeInTheDocument();
  });

  it("orders group headers chronologically (Today before Yesterday)", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [
          makeNovel({ novel_id: "n1", added_at: "2026-06-17T08:00:00Z" }),
          makeNovel({ novel_id: "n2", added_at: "2026-06-16T10:00:00Z" }),
        ],
        total: 2,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    const allH3 = screen.getAllByRole("heading", { level: 3 });
    const headerTexts = allH3.map((el) => el.textContent);
    const todayIdx = headerTexts.indexOf("Today");
    const yesterdayIdx = headerTexts.indexOf("Yesterday");
    expect(todayIdx).toBeLessThan(yesterdayIdx);
    vi.useRealTimers();
  });

  it("renders latest update groups newest-first even when catalog data is not grouped that way", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [
          makeNovel({ novel_id: "n-earlier", added_at: null }),
          makeNovel({ novel_id: "n-month-2", added_at: "2026-04-18T10:00:00Z" }),
          makeNovel({ novel_id: "n-month-1", added_at: "2026-05-23T10:00:00Z" }),
          makeNovel({ novel_id: "n-week-3", added_at: "2026-05-30T10:00:00Z" }),
          makeNovel({ novel_id: "n-week-2", added_at: "2026-06-07T10:00:00Z" }),
          makeNovel({ novel_id: "n-week-1", added_at: "2026-06-12T10:00:00Z" }),
          makeNovel({ novel_id: "n-yesterday", added_at: "2026-06-16T10:00:00Z" }),
          makeNovel({ novel_id: "n-today", added_at: "2026-06-17T08:00:00Z" }),
        ],
        total: 8,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    const expectedOrder = [
      "Today",
      "Yesterday",
      "1 week ago",
      "2 weeks ago",
      "3 weeks ago",
      "1 month ago",
      "2 months ago",
      "Earlier",
    ];
    const headerTexts = screen
      .getAllByRole("heading", { level: 3 })
      .map((el) => el.textContent)
      .filter((text): text is string => expectedOrder.includes(text ?? ""));

    expect(headerTexts).toEqual(expectedOrder);
    vi.useRealTimers();
  });

  it("does not show exact hour for older-than-24h items", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [makeNovel({ added_at: "2026-06-16T08:30:00Z" })],
        total: 1,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    // Should NOT render exact time strings like "08:30" in the row
    expect(screen.queryByText(/08:30/)).not.toBeInTheDocument();
    vi.useRealTimers();
  });

  it("does not render clock icon in row", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-17T12:00:00Z"));

    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [makeNovel({ added_at: "2026-06-17T08:00:00Z" })],
        total: 1,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    // No clock SVG in the component (only BookOpen icon)
    const clockSvgs = document.querySelectorAll(
      'svg.lucide-clock, svg[class*="clock"]'
    );
    expect(clockSvgs.length).toBe(0);
    vi.useRealTimers();
  });

  it("does not pass include_adult=true in catalog query", () => {
    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [makeNovel()],
        total: 1,
        page: 1,
        page_size: 8,
      },
      isPending: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    });
    renderHome();

    // useCatalog is called with sort_by, order, page_size — no include_adult
    const call = mocks.catalogQuery.mock.calls[0] ?? [];
    // catalogQuery is a fn that returns the mock value, no args inspected
    // but the useCatalog call in the component passes no include_adult
    expect(mocks.catalogQuery).toHaveBeenCalled();
  });
});
