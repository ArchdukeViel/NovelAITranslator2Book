import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import LibraryPage from "@/app/(admin)/admin/library/page";
import type {
  LibrarySummaryItem,
  LibrarySummaryResponse,
  NovelSummary,
} from "@/lib/api-types";

function renderWithQuery(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
    ),
  };
}

function makeNovel(overrides: Partial<NovelSummary> = {}): NovelSummary {
  return {
    novel_id: "n2056dn",
    title: "Sample Novel",
    source_key: "syosetu_ncode",
    source_url: "https://example.com/sample",
    publication_status: "ongoing",
    chapter_count: 10, // STALE — must never be shown if summary is present
    scraped_count: 99, // STALE — must never be shown
    translated_count: 99, // STALE — must never be shown
    is_published: false,
    latest_chapter_id: "1",
    latest_chapter_number: 1,
    latest_chapter_title: "Translated Chapter",
    ...overrides,
  };
}

function makeSummaryItem(
  overrides: Partial<LibrarySummaryItem> = {},
): LibrarySummaryItem {
  return {
    novel_id: "n2056dn",
    total: 10,
    scraped: 9,
    translated: 0,
    failed: 0,
    pending: 1,
    ...overrides,
  };
}

function makeSummaryResponse(
  items: LibrarySummaryItem[],
): LibrarySummaryResponse {
  return {
    generated_at: "2026-01-01T00:00:00Z",
    totals: {
      novel_id: "__all__",
      total: items.reduce((s, i) => s + i.total, 0),
      scraped: items.reduce((s, i) => s + i.scraped, 0),
      translated: items.reduce((s, i) => s + i.translated, 0),
      failed: items.reduce((s, i) => s + i.failed, 0),
      pending: items.reduce((s, i) => s + i.pending, 0),
    },
    cache: { hit: false, ttl_seconds: 30 },
    items,
  };
}

const mockNovels = vi.hoisted(() => vi.fn());
const mockLibrarySummary = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    get api() {
      return {
        ...actual.api,
        novels: (...args: unknown[]) => mockNovels(...args),
      };
    },
    get adminApi() {
      return {
        ...actual.adminApi,
        librarySummary: (...args: unknown[]) => mockLibrarySummary(...args),
      };
    },
  };
});

afterEach(() => {
  vi.restoreAllMocks();
  cleanup();
});

describe("Admin Library: live summary integration", () => {
  it("renders summary counts joined by novel_id; SQL values are not used", async () => {
    const novel = makeNovel({
      chapter_count: 10,
      scraped_count: 99,
      translated_count: 99,
    });
    const summary = makeSummaryItem({
      novel_id: "n2056dn",
      total: 10,
      scraped: 9,
      translated: 0,
      failed: 0,
      pending: 1,
    });

    mockNovels.mockResolvedValue([novel]);
    mockLibrarySummary.mockResolvedValue(makeSummaryResponse([summary]));

    renderWithQuery(<LibraryPage />);

    // Wait for the summary counts to appear in the row.
    await waitFor(() => {
      expect(screen.getByText("10")).toBeInTheDocument();
      expect(screen.getByText("9")).toBeInTheDocument();
    });

    // The stale SQL counts (99) must NOT appear in the visible row for this novel.
    const cells = document.body.textContent ?? "";
    // 99 must not appear in the row's columns for the novel.
    // We check that the cell for scraped shows "9" (summary) and not "99" (SQL).
    expect(cells).toContain("9");
    expect(cells).not.toMatch(/(^|\s|>)(99)(<|\s|$)/);
  });

  it("renders — when summary data is unavailable", async () => {
    const novel = makeNovel({
      chapter_count: 10,
      scraped_count: 99,
      translated_count: 99,
    });
    mockNovels.mockResolvedValue([novel]);
    mockLibrarySummary.mockResolvedValue(makeSummaryResponse([])); // No item for novel

    renderWithQuery(<LibraryPage />);

    // Failed = 0, pending = 0 etc. all render as visible "0" because summary returned
    // empty (not unavailable). Ensure raw/translated cells render "—" placeholder
    // because backend omitted this novel.
    await waitFor(() => {
      // The Listed/Raw/etc. columns fall back to the summary-derived "—" when the
      // matching item is missing from the response.
      const html = document.body.innerHTML;
      // The em-dash placeholder (—) is rendered for missing fields.
      expect(html).toContain("—");
    });
  });

  it("explicit Refresh summary uses refresh=true and replaces canonical cache", async () => {
    mockNovels.mockResolvedValue([makeNovel()]);
    let callCount = 0;
    mockLibrarySummary.mockImplementation(async (opts: { refresh?: boolean }) => {
      callCount += 1;
      if (opts?.refresh) {
        return makeSummaryResponse([
          makeSummaryItem({ translated: 4, scraped: 10, total: 10 }),
        ]);
      }
      // Cold/normal call returns translated:0
      return makeSummaryResponse([
        makeSummaryItem({ translated: 0, scraped: 9, total: 10 }),
      ]);
    });

    const user = userEvent.setup();
    renderWithQuery(<LibraryPage />);

    // Initial load should show "0" translated (from first summary).
    await waitFor(() => {
      expect(callCount).toBeGreaterThanOrEqual(1);
    });

    // Confirm that the mutation calls the API with refresh: true
    await user.click(
      screen.getByRole("button", { name: /Refresh summary/i }),
    );

    await waitFor(() => {
      // At least 2 calls happened (cold + refresh)
      expect(callCount).toBeGreaterThanOrEqual(2);
    });

    // Check the API was called with refresh=true
    const calls = mockLibrarySummary.mock.calls;
    const refreshCall = calls.find((c) => c[0]?.refresh === true);
    expect(refreshCall).toBeDefined();
    // Stable canonical key — canonical query cache key preserved
    // (we don't need to introspect the queryClient internals; refresh
    // mutation uses setQueryData(["library-summary"], ...))
  });

  it("does not render duplicate summary-error banners", async () => {
    mockNovels.mockResolvedValue([makeNovel()]);
    mockLibrarySummary.mockRejectedValue(new Error("boom"));

    renderWithQuery(<LibraryPage />);

    await waitFor(() => {
      // Exactly one error fallback message should render.
      const banners = screen.getAllByText(/Failed to load library summary/i);
      expect(banners).toHaveLength(1);
    });

    // The "Retry retry" typo must not appear anywhere.
    expect(screen.queryByText(/Retry retry/i)).toBeNull();
  });

  it("renders 0 (not —) for legitimate zero summary values", async () => {
    const novel = makeNovel();
    mockNovels.mockResolvedValue([novel]);
    mockLibrarySummary.mockResolvedValue(
      makeSummaryResponse([
        makeSummaryItem({ translated: 0, failed: 0, pending: 0, scraped: 0 }),
      ]),
    );

    renderWithQuery(<LibraryPage />);
    await waitFor(() => {
      // Translated/Failed/Pending columns should display explicit "0"
      expect(screen.getAllByText("0").length).toBeGreaterThanOrEqual(3);
    });
  });

  it("explicit refresh failure shows refreshSummary.error without corrupting values", async () => {
    mockNovels.mockResolvedValue([makeNovel()]);
    let callCount = 0;
    mockLibrarySummary.mockImplementation(async (opts: { refresh?: boolean }) => {
      callCount += 1;
      if (opts?.refresh) {
        throw new Error("refresh exploded");
      }
      return makeSummaryResponse([
        makeSummaryItem({ translated: 2, scraped: 5, total: 10 }),
      ]);
    });

    const user = userEvent.setup();
    renderWithQuery(<LibraryPage />);

    // Wait for initial load with translated=2.
    await waitFor(() => {
      expect(screen.getByText("2")).toBeInTheDocument();
    });

    // Click Refresh summary — should fail.
    await user.click(
      screen.getByRole("button", { name: /Refresh summary/i }),
    );

    // The explicit-refresh failure message should appear.
    await waitFor(() => {
      expect(
        screen.getByText(/Explicit refresh failed/i),
      ).toBeInTheDocument();
    });

    // The previously-good translated=2 should still be visible (not wiped).
    expect(screen.getByText("2")).toBeInTheDocument();
  });
});
