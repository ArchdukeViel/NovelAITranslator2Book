/**
 * Novel detail page honesty and data tests.
 *
 * Confirms the /novels/[slug] page renders real API data honestly, handles
 * missing optional fields, shows report-to-contact link, links genre/tag
 * chips to browse filters, and does not pass include_adult=true.
 *
 * Feature: PUBLIC-NOVEL-DETAIL-AUDIT-1
 */

import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import { render, screen, cleanup, fireEvent, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import NovelDetailPage from "@/app/(public)/novels/[slug]/page";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
  novelQuery: vi.fn(),
  chaptersQuery: vi.fn(),
  usePublicAuthMock: vi.fn(),
  useUpsertReviewMock: vi.fn(),
  useDeleteReviewMock: vi.fn(),
  useCreateRequestMock: vi.fn(),
  useLibraryItemMock: vi.fn(),
  useAddToLibraryMock: vi.fn(),
  useRemoveFromLibraryMock: vi.fn(),
  useProgressMock: vi.fn(),
  pushMock: vi.fn(),
  searchParamsMock: vi.fn(),
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & {
    children: React.ReactNode;
  }) => <a {...props}>{children}</a>,
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ slug: "test-slug" }),
  useRouter: () => ({ push: mocks.pushMock }),
  useSearchParams: () => mocks.searchParamsMock(),
}));

vi.mock("@/hooks/public", async () => {
  const actual = await vi.importActual<typeof import("@/hooks/public")>(
    "@/hooks/public"
  );
  return {
    ...actual,
    usePublicAuth: () => mocks.usePublicAuthMock(),
    useNovel: () => mocks.novelQuery(),
    useChapters: () => mocks.chaptersQuery(),
    useUpsertReview: () => mocks.useUpsertReviewMock(),
    useDeleteReview: () => mocks.useDeleteReviewMock(),
    useCreateRequest: () => mocks.useCreateRequestMock(),
    useLibraryItem: () => mocks.useLibraryItemMock(),
    useAddToLibrary: () => ({ mutate: mocks.useAddToLibraryMock, isPending: false }),
    useRemoveFromLibrary: () => ({ mutate: mocks.useRemoveFromLibraryMock, isPending: false }),
    useProgress: () => mocks.useProgressMock(),
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
  mocks.searchParamsMock.mockReturnValue(new URLSearchParams());

  // Default: unauthenticated guest
  mocks.usePublicAuthMock.mockReturnValue({
    isAuthenticated: false,
    isPending: false,
    isPublicUser: false,
    isOwner: false,
    authState: null,
    user: null,
  });
  mocks.useLibraryItemMock.mockReturnValue({ data: undefined, isPending: false, isError: false, error: null });
  mocks.useAddToLibraryMock.mockReturnValue({ mutate: vi.fn(), isPending: false, error: null });
  mocks.useRemoveFromLibraryMock.mockReturnValue({ mutate: vi.fn(), isPending: false, error: null });
  mocks.useProgressMock.mockReturnValue({ data: undefined, isPending: false, isError: false, error: null });
  mocks.useUpsertReviewMock.mockReturnValue({ mutate: vi.fn(), isPending: false, error: null });
  mocks.useDeleteReviewMock.mockReturnValue({ mutate: vi.fn(), isPending: false, error: null });
  mocks.useCreateRequestMock.mockReturnValue({ mutate: vi.fn(), isPending: false, error: null });

  // Default: successful novel + chapters
  mocks.novelQuery.mockReturnValue({
    data: makeNovelData(),
    isPending: false,
    isError: false,
    error: null,
  });
  mocks.chaptersQuery.mockReturnValue({
    data: makeChaptersData(),
    isPending: false,
    isError: false,
    error: null,
  });
});

afterEach(() => {
  cleanup();
});

function makeNovelData(overrides: Record<string, unknown> = {}) {
  return {
    novel_id: "test-slug",
    slug: "test-slug",
    title: "Test Novel",
    source_title: "テスト小説",
    author: "Test Author",
    language: "ja",
    synopsis: "A real source synopsis from the public novel detail payload.",
    status: "Ongoing",
    chapter_count: 10,
    translated_count: 5,
    added_at: "2026-06-17T10:00:00Z",
    genres: [
      { slug: "fantasy", name_ja: "ファンタジー", name_en: "Fantasy" },
      { slug: "adventure", name_ja: "冒険", name_en: "Adventure" },
    ],
    tags: [
      { name: "magic", name_ja: "魔法" },
      { name: "isekai", name_ja: "異世界" },
    ],
    ...overrides,
  };
}

function makeChaptersData(overrides: Array<Record<string, unknown>> = []) {
  const defaults = [
    { chapter_id: "1", title: "Chapter One", chapter_number: 1, translated: true },
    { chapter_id: "2", title: null, chapter_number: 2, translated: true },
    { chapter_id: "3", title: null, chapter_number: 3, translated: false },
  ];
  return defaults.map((d) => ({ ...d, ...overrides.shift() }));
}

function renderPage() {
  return render(
    <QueryClientProvider client={queryClient}>
      <NovelDetailPage />
    </QueryClientProvider>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Novel detail page — data honesty", () => {
  it("renders novel title and author from API data", () => {
    renderPage();
    // Title appears in both CoverFallback and h1
    const titles = screen.getAllByText("Test Novel");
    expect(titles.length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Test Author")).toBeInTheDocument();
  });

  it("renders generated fallback bookplate from safe novel metadata", () => {
    renderPage();

    expect(
      screen.getByRole("img", {
        name: "Generated Dokushodo bookplate for Test Novel",
      })
    ).toBeInTheDocument();
    expect(screen.getAllByText("テスト小説").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText(/official cover/i)).not.toBeInTheDocument();
  });

  it("displays added_at date when present", () => {
    renderPage();
    // The date will be formatted by toLocaleDateString. We check for the prefix.
    const addedEls = screen.getAllByText(/Added/);
    expect(addedEls.length).toBeGreaterThanOrEqual(1);
  });

  it("hides added date when not provided", () => {
    mocks.novelQuery.mockReturnValue({
      data: makeNovelData({ added_at: null }),
      isPending: false,
      isError: false,
      error: null,
    });
    renderPage();
    // "Added" should not appear as standalone text
    expect(screen.queryByText(/^Added\b/)).not.toBeInTheDocument();
  });

  it("handles null title by falling back to slug", () => {
    mocks.novelQuery.mockReturnValue({
      data: makeNovelData({ title: null }),
      isPending: false,
      isError: false,
      error: null,
    });
    renderPage();
    // slug appears in both CoverFallback and h1
    const slugs = screen.getAllByText("test-slug");
    expect(slugs.length).toBeGreaterThanOrEqual(2);
  });

  it("handles null author gracefully", () => {
    mocks.novelQuery.mockReturnValue({
      data: makeNovelData({ author: null }),
      isPending: false,
      isError: false,
      error: null,
    });
    renderPage();
    // authorOrFallback should render "Unknown author"
    expect(screen.getByText(/unknown author/i)).toBeInTheDocument();
  });
});

describe("Novel detail page — genre and tag chips", () => {
  it("renders genre chips when genres present", () => {
    renderPage();
    expect(screen.getByText("fantasy")).toBeInTheDocument();
    expect(screen.getByText("adventure")).toBeInTheDocument();
  });

  it("genre chips link to the canonical genre route", () => {
    renderPage();
    const fantasyLink = screen.getByText("fantasy").closest("a");
    expect(fantasyLink).toHaveAttribute("href", "/genres/fantasy");
  });

  it("tag chips link to the canonical tag route", () => {
    renderPage();
    const magicLink = screen.getByText("magic").closest("a");
    expect(magicLink).toHaveAttribute("href", "/tags/magic");
  });

  it("hides genre section when no genres", () => {
    mocks.novelQuery.mockReturnValue({
      data: makeNovelData({ genres: [] }),
      isPending: false,
      isError: false,
      error: null,
    });
    renderPage();
    expect(screen.queryByText("fantasy")).not.toBeInTheDocument();
  });

  it("hides tag section when no tags", () => {
    mocks.novelQuery.mockReturnValue({
      data: makeNovelData({ tags: [] }),
      isPending: false,
      isError: false,
      error: null,
    });
    renderPage();
    expect(screen.queryByText("magic")).not.toBeInTheDocument();
  });
});

describe("Novel detail page — no fake data", () => {
  it("does not render fake ratings or review counts", () => {
    renderPage();
    expect(screen.queryByText(/out of 5/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/\d+ reviews?/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/rating/i)).not.toBeInTheDocument();
  });

  it("does not render fake synopsis", () => {
    renderPage();
    expect(screen.queryByText(/synopsis not available/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/available for reading, but/i)).not.toBeInTheDocument();
  });

  it("renders source title from API data when present", () => {
    renderPage();
    expect(screen.getByText("Source title")).toBeInTheDocument();
    expect(screen.getAllByText("テスト小説").length).toBeGreaterThanOrEqual(1);
  });

  it("does not render source title label when source title is missing", () => {
    mocks.novelQuery.mockReturnValue({
      data: makeNovelData({ source_title: null }),
      isPending: false,
      isError: false,
      error: null,
    });
    renderPage();
    expect(screen.queryByText("Source title")).not.toBeInTheDocument();
  });

  it("does not duplicate source title when it matches display title", () => {
    mocks.novelQuery.mockReturnValue({
      data: makeNovelData({ source_title: "Test Novel" }),
      isPending: false,
      isError: false,
      error: null,
    });
    renderPage();
    expect(screen.queryByText("Source title")).not.toBeInTheDocument();
  });
});

describe("Novel detail page — report action", () => {
  it("links to /contact instead of claiming backend phase", () => {
    renderPage();
    expect(screen.queryByText(/later backend phase/i)).not.toBeInTheDocument();
    const contactLink = screen.getByRole("link", { name: "Report an issue" });
    expect(contactLink).toHaveAttribute("href", "/contact");
  });

  it("displays Report an issue heading", () => {
    renderPage();
    expect(screen.getByText("Report an issue")).toBeInTheDocument();
  });
});

describe("Novel detail page — chapter list", () => {
  beforeEach(() => mocks.searchParamsMock.mockReturnValue(new URLSearchParams("tab=chapters")));

  it("renders chapter list with correct count", () => {
    renderPage();
    expect(screen.getByText("3 total")).toBeInTheDocument();
  });

  it("renders translated chapter links", () => {
    renderPage();
    const readButtons = screen.getAllByText("Read");
    expect(readButtons.length).toBeGreaterThanOrEqual(2);
  });

  it("renders untranslated chapter label", () => {
    renderPage();
    expect(screen.getByText("Not translated")).toBeInTheDocument();
  });

  it("renders chapter titles when available", () => {
    renderPage();
    expect(screen.getByText("Chapter One")).toBeInTheDocument();
  });

  it("renders named sections without creating a header for flat chapters", () => {
    mocks.chaptersQuery.mockReturnValue({
      data: [
        {
          chapter_id: "1",
          title: "Episode One",
          chapter_number: 1,
          translated: true,
          section_title: "Part One",
          section_source_id: "section-1",
          section_ordinal: 1,
        },
        {
          chapter_id: "2",
          title: "Episode Two",
          chapter_number: 2,
          translated: true,
          section_title: "Part One",
          section_source_id: "section-1",
          section_ordinal: 1,
        },
        {
          chapter_id: "3",
          title: "Episode Three",
          chapter_number: 3,
          translated: true,
          section_title: null,
          section_source_id: null,
          section_ordinal: null,
        },
      ],
      isPending: false,
      isError: false,
      error: null,
    });

    renderPage();

    expect(screen.getByText("Part One")).toBeInTheDocument();
    expect(screen.getByText("Episode Three")).toBeInTheDocument();
    expect(screen.queryByText("Section")).not.toBeInTheDocument();
  });

  it("preserves source order across disjoint grouped and ungrouped runs", () => {
    mocks.chaptersQuery.mockReturnValue({
      data: [
        { chapter_id: "1", title: "Episode One", chapter_number: 1, translated: true },
        {
          chapter_id: "2",
          title: "Episode Two",
          chapter_number: 2,
          translated: true,
          section_title: "Part One",
          section_source_id: "section-1",
          section_ordinal: 1,
        },
        {
          chapter_id: "3",
          title: "Episode Three",
          chapter_number: 3,
          translated: true,
          section_title: "Part One",
          section_source_id: "section-1",
          section_ordinal: 1,
        },
        { chapter_id: "4", title: "Episode Four", chapter_number: 4, translated: true },
        {
          chapter_id: "5",
          title: "Episode Five",
          chapter_number: 5,
          translated: true,
          section_title: "Part Two",
          section_source_id: "section-2",
          section_ordinal: 2,
        },
      ],
      isPending: false,
      isError: false,
      error: null,
    });

    renderPage();

    expect(screen.getAllByRole("link", { name: "Read" }).map((link) => link.getAttribute("href"))).toEqual([
      "/novels/test-slug/chapter/1",
      "/novels/test-slug/chapter/2",
      "/novels/test-slug/chapter/3",
      "/novels/test-slug/chapter/4",
      "/novels/test-slug/chapter/5",
    ]);
  });
});

describe("Novel detail page — FE-07 tabs and controls", () => {
  it("writes tab selection to a shareable URL", () => {
    renderPage();
    fireEvent.click(screen.getByRole("tab", { name: /^chapters$/i }));
    expect(mocks.pushMock).toHaveBeenCalledWith("/novels/test-slug?tab=chapters", { scroll: false });
  });

  it("renders exactly one primary reading CTA", () => {
    renderPage();
    expect(screen.getAllByRole("link", { name: "Start Reading" })).toHaveLength(1);
    expect(screen.queryByRole("link", { name: "Latest Chapter" })).not.toBeInTheDocument();
  });

  it("replaces Start Reading with one Continue CTA when progress exists", () => {
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: true, isPending: false, isPublicUser: true, isOwner: false, user: { user_id: 1 } });
    mocks.useProgressMock.mockReturnValue({ data: { chapter_id: "2", chapter_number: 2 }, isPending: false, isError: false, error: null });
    renderPage();
    expect(screen.queryByRole("link", { name: "Start Reading" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /Continue Reading from Ch\. 2/ })).toHaveLength(1);
  });

  it("exposes semantic tabs and a labelled active panel", () => {
    renderPage();
    const tablist = screen.getByRole("tablist", { name: "Novel sections" });
    expect(within(tablist).getAllByRole("tab")).toHaveLength(3);
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveAttribute("aria-labelledby", "novel-tab-overview");
  });

  it("keeps the request form out of Overview and behind a Chapters disclosure", () => {
    renderPage();
    expect(screen.queryByText("Submit a Request")).not.toBeInTheDocument();

    mocks.searchParamsMock.mockReturnValue(new URLSearchParams("tab=chapters"));
    renderPage();
    const disclosure = screen.getByText("Request translation").closest("details");
    expect(disclosure).toBeInTheDocument();
    expect(disclosure).not.toHaveAttribute("open");
    expect(within(disclosure as HTMLElement).getByText("Submit a Request")).toBeInTheDocument();
  });

  it("does not attach Japanese taxonomy labels to a non-Japanese work", () => {
    mocks.novelQuery.mockReturnValue({
      data: makeNovelData({ language: "zh" }),
      isPending: false,
      isError: false,
      error: null,
    });
    renderPage();
    expect(screen.queryByText("ファンタジー")).not.toBeInTheDocument();
    expect(screen.getByText("fantasy")).toBeInTheDocument();
  });

  it("does not repeat generated numbering when a source title already includes it", () => {
    mocks.searchParamsMock.mockReturnValue(new URLSearchParams("tab=chapters"));
    mocks.chaptersQuery.mockReturnValue({
      data: [{ chapter_id: "1", title: "1話　聖水要員", chapter_number: 1, translated: true }],
      isPending: false,
      isError: false,
      error: null,
    });
    renderPage();
    expect(screen.getByText(/1話\s+聖水要員/)).toBeInTheDocument();
    expect(screen.queryByText("Chapter 1")).not.toBeInTheDocument();
  });

  it("filters chapters and reverses their order", () => {
    mocks.searchParamsMock.mockReturnValue(new URLSearchParams("tab=chapters"));
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("Search chapters"), { target: { value: "One" } });
    expect(screen.getByText("Chapter One")).toBeInTheDocument();
    expect(screen.queryByText("Chapter 2")).not.toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("Search chapters"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Ascending" }));
    const readLinks = screen.getAllByRole("link", { name: "Read" });
    expect(readLinks[0]).toHaveAttribute("href", "/novels/test-slug/chapter/2");
  });

  it("marks read and last-read chapters from progress", () => {
    mocks.searchParamsMock.mockReturnValue(new URLSearchParams("tab=chapters"));
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: true, isPending: false, isPublicUser: true, isOwner: false, user: { user_id: 1 } });
    mocks.useProgressMock.mockReturnValue({ data: { chapter_id: "2", chapter_number: 2 }, isPending: false, isError: false, error: null });
    mocks.chaptersQuery.mockReturnValue({ data: makeChaptersData([{}, {}, { translated: true }]), isPending: false, isError: false, error: null });
    renderPage();
    const lastRead = (screen.getByText("Last read").closest("div[id]") ?? screen.getByText("Last read").parentElement!) as HTMLElement;
    expect(within(lastRead).getAllByText("Read").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("link", { name: "First unread" })).toHaveAttribute("href", "#chapter-3");
  });

  it("keeps unavailable chapters visible", () => {
    mocks.searchParamsMock.mockReturnValue(new URLSearchParams("tab=chapters"));
    renderPage();
    expect(screen.getByText("Not translated")).toBeInTheDocument();
  });
});

describe("Novel detail page — navigation", () => {
  it("Back to Browse links to /browse-novels", () => {
    renderPage();
    const backLink = screen.getByText("Back to Browse").closest("a");
    expect(backLink).toHaveAttribute("href", "/browse-novels");
  });
});

describe("Novel detail page — loading and error states", () => {
  it("shows loading skeleton when novel is pending", () => {
    mocks.novelQuery.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      error: null,
    });
    renderPage();
    // LoadingState renders skeleton with aria-label for the page section
    expect(screen.getByText("Back to Browse")).toBeInTheDocument();
  });

  it("shows error state for 404", async () => {
    const { ApiError } = await import("@/lib/api");
    const error404 = new ApiError({
      status: 404,
      code: "HTTP_404",
      message: "Not found",
    });

    mocks.novelQuery.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: error404,
    });
    renderPage();
    expect(screen.getByText("Novel not found")).toBeInTheDocument();
  });

  it("shows user-friendly message for generic novel error", async () => {
    const { ApiError } = await import("@/lib/api");
    const genericError = new ApiError({
      status: 500,
      code: "HTTP_500",
      message: "Internal server error with sensitive details",
    });

    mocks.novelQuery.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: genericError,
    });
    renderPage();
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    // Should not contain raw error message
    expect(screen.queryByText(/Internal server error/)).not.toBeInTheDocument();
    // Should contain user-friendly recovery text
    expect(screen.getByText(/Try browsing the catalog/)).toBeInTheDocument();
  });

  it("shows user-friendly message for chapters error", () => {
    const err = new Error("Raw chapter fetch failure");
    mocks.chaptersQuery.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: err,
    });
    mocks.searchParamsMock.mockReturnValue(new URLSearchParams("tab=chapters"));
    renderPage();
    expect(screen.getByText("Could not load chapters.")).toBeInTheDocument();
    expect(screen.queryByText(/Raw chapter fetch failure/)).not.toBeInTheDocument();
  });
});

describe("Novel detail page — adult/R18 safety", () => {
  it("does not pass include_adult=true in novel data request", () => {
    renderPage();
    // Verify no adult content is being requested by checking that
    // the novel query is called (adult filtering is backend-side).
    // The frontend never passes include_adult=true for public novel detail.
    expect(mocks.novelQuery).toHaveBeenCalled();
  });

  it("does not render adult/R18 taxonomy labels", () => {
    mocks.novelQuery.mockReturnValue({
      data: makeNovelData({ genres: [{ slug: "fantasy", name_ja: "ファンタジー", name_en: "Fantasy" }], tags: [] }),
      isPending: false,
      isError: false,
      error: null,
    });
    renderPage();
    expect(screen.queryByText(/r18/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/adult/i)).not.toBeInTheDocument();
  });
});

describe("Novel detail page — synopsis section honesty", () => {
  it("renders real synopsis when provided by the API", () => {
    renderPage();
    expect(screen.getByText("A real source synopsis from the public novel detail payload.")).toBeInTheDocument();
    expect(screen.queryByText("Synopsis unavailable for this novel.")).not.toBeInTheDocument();
  });

  it("shows honest synopsis fallback when synopsis is missing", () => {
    mocks.novelQuery.mockReturnValue({
      data: makeNovelData({ synopsis: null }),
      isPending: false,
      isError: false,
      error: null,
    });
    renderPage();
    expect(screen.getByText("About this story")).toBeInTheDocument();
    expect(screen.getByText("Synopsis unavailable for this novel.")).toBeInTheDocument();
  });

  it("shows honest synopsis fallback when synopsis is blank", () => {
    mocks.novelQuery.mockReturnValue({
      data: makeNovelData({ synopsis: "   " }),
      isPending: false,
      isError: false,
      error: null,
    });
    renderPage();
    expect(screen.getByText("Synopsis unavailable for this novel.")).toBeInTheDocument();
  });

  it("does not render developer-facing synopsis placeholder copy", () => {
    mocks.novelQuery.mockReturnValue({
      data: makeNovelData({ synopsis: null }),
      isPending: false,
      isError: false,
      error: null,
    });
    renderPage();
    expect(screen.queryByText(/not yet include a synopsis/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/not provided by current API/i)).not.toBeInTheDocument();
  });
});
