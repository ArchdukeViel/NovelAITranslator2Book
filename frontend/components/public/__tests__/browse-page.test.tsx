import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowsePage } from "@/components/public/browse-page";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
  genresQuery: vi.fn(),
  catalogQuery: vi.fn(),
  pushFn: vi.fn(),
  refreshFn: vi.fn(),
  searchTags: vi.fn(),
}));

vi.mock("@/hooks/public", async () => {
  const actual = await vi.importActual<typeof import("@/hooks/public")>("@/hooks/public");
  return {
    ...actual,
    useCatalog: () => mocks.catalogQuery(),
    useGenres: () => mocks.genresQuery(),
  };
});

vi.mock("@/lib/public-api", () => ({
  publicApi: {
    searchTags: (...args: unknown[]) => mocks.searchTags(...args),
  },
}));

const searchParamsMock = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParamsMock(),
  useRouter: () => ({
    push: mocks.pushFn,
    refresh: mocks.refreshFn,
  }),
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
  searchParamsMock.mockReturnValue(new URLSearchParams(""));
  mocks.genresQuery.mockReturnValue({
    data: [
      { slug: "fantasy", name_ja: "ファンタジー", name_en: "Fantasy" },
    ],
    isPending: false,
    isError: false,
  });
  mocks.catalogQuery.mockReturnValue({
    data: { novels: [], total: 0, page: 1, page_size: 20 },
    isPending: false,
    isError: false,
    error: null,
  });
  mocks.searchTags.mockResolvedValue([]);
});

afterEach(() => cleanup());

function renderPage() {
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowsePage basePath="/browse-novels" title="Browse" description="Find novels" />
    </QueryClientProvider>
  );
}

function openAdvancedSearch() {
  const btn = screen.getByRole("button", { name: /filters/i });
  act(() => { btn.click(); });
}

/** Helper: type into a tag search input and wait for debounce + query to settle. */
async function typeTagQuery(index: 0 | 1, text: string) {
  const inputs = screen.getAllByPlaceholderText("Type to search tags…") as HTMLInputElement[];
  fireEvent.input(inputs[index], { target: { value: text } });
  // Wait for debounce (300ms) + query to resolve
  await waitFor(() => {
    // The searchTags mock should have been called at least once
    // (at minimum after debounce settles).
    // We just wait for any visible change.
  }, { timeout: 500 });
}

// ---------------------------------------------------------------------------
// Genre filter tests (regression)
// ---------------------------------------------------------------------------

describe("BrowsePage visual honesty", () => {
  it("does not render fake metric labels", () => {
    renderPage();
    expect(screen.queryByText(/^popular$/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^trending$/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Top Rated")).not.toBeInTheDocument();
    expect(screen.queryByText("Library Stats")).not.toBeInTheDocument();
    expect(screen.queryByText("Metrics")).not.toBeInTheDocument();
    // "view" in "View details" is legitimate — check word-level
    expect(screen.queryByText(/ratings?/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/reviews?/i)).not.toBeInTheDocument();
  });

  it("renders honest catalog header with Japanese eyebrow", () => {
    renderPage();
    expect(screen.getByText("探索")).toBeInTheDocument();
    // h1 renders title prop; renderPage passes title="Browse"
    expect(screen.getByRole("heading", { level: 1, name: "Browse" })).toBeInTheDocument();
  });

  it("does not display unsupported metric filter controls", () => {
    renderPage();
    // Rating/views/reviews filter buttons should not exist
    expect(screen.queryByRole("button", { name: /rating/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /popular/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /trending/i })).not.toBeInTheDocument();
  });

  it("sort options do not include unsupported metric labels", () => {
    renderPage();
    const sortSelect = screen.getByLabelText("Sort by") as HTMLSelectElement;
    const options = Array.from(sortSelect.options).map((o) => o.textContent?.trim() ?? "");
    // Allowed: "Recently added", "Title", "Chapter count"
    expect(options).not.toContain("Popular");
    expect(options).not.toContain("Top Rated");
    expect(options).not.toContain("Most Viewed");
    expect(options).not.toContain("Trending");
    expect(options).not.toContain("Addition date");
  });

  it("clear filters resets all visible filter indicators", () => {
    searchParamsMock.mockReturnValue(
      new URLSearchParams("q=test&status=Ongoing&min_chapters=5&max_chapters=50")
    );
    renderPage();
    // Verify filter indicators are present
    expect(screen.getByText(/“test”/)).toBeInTheDocument();
    expect(screen.getAllByText("Ongoing").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/5[-–]50 ch\.?/)).toBeInTheDocument();
    // Click clear
    const clearBtns = screen.getAllByText("Clear filters");
    act(() => { clearBtns[0].click(); });
    // Verify pushParams cleared them (only sort/order/page survive)
    const url = mocks.pushFn.mock.calls[0][0] as string;
    expect(url).not.toContain("q=");
    expect(url).not.toContain("status=");
    expect(url).not.toContain("min_chapters");
    expect(url).not.toContain("max_chapters");
  });
});

describe("BrowsePage genre filter UI", () => {
  it("renders genre list from API", () => {
    renderPage();
    openAdvancedSearch();
    expect(screen.getAllByText("Fantasy").length).toBe(2);
  });

  it("shows loading/error/empty states", () => {
    mocks.genresQuery.mockReturnValue({ data: undefined, isPending: true, isError: false });
    renderPage();
    openAdvancedSearch();
    expect(screen.getByText("Loading genres…")).toBeInTheDocument();
  });

  it("selecting include genre pushes genre_include param", () => {
    renderPage();
    openAdvancedSearch();
    const includeGroup = screen.getByRole("group", { name: /include genres/i });
    act(() => { includeGroup.querySelector("button")!.click(); });
    expect(mocks.pushFn.mock.calls[0][0]).toContain("genre_include=fantasy");
  });

  it("selecting exclude genre pushes genre_exclude param", () => {
    renderPage();
    openAdvancedSearch();
    const excludeGroup = screen.getByRole("group", { name: /exclude genres/i });
    act(() => { excludeGroup.querySelector("button")!.click(); });
    expect(mocks.pushFn.mock.calls[0][0]).toContain("genre_exclude=fantasy");
  });

  it("clearing filters removes genre params", () => {
    searchParamsMock.mockReturnValue(new URLSearchParams("genre_include=fantasy"));
    renderPage();
    const clearBtns = screen.getAllByText("Clear filters");
    act(() => { clearBtns[0].click(); });
    const url = mocks.pushFn.mock.calls[0][0] as string;
    expect(url).not.toContain("genre_include");
    expect(url).not.toContain("genre_exclude");
  });

  it("Browse still works when genres fail to load", () => {
    mocks.genresQuery.mockReturnValue({ data: undefined, isPending: false, isError: true });
    renderPage();
    openAdvancedSearch();
    expect(screen.getByText("Genres temporarily unavailable.")).toBeInTheDocument();
  });

  it("genre filter indicator shows in results header", () => {
    searchParamsMock.mockReturnValue(new URLSearchParams("genre_include=fantasy"));
    renderPage();
    expect(screen.getByText(/1 genre incl\./)).toBeInTheDocument();
  });

  it("opens advanced search automatically when genre filters in URL", () => {
    searchParamsMock.mockReturnValue(new URLSearchParams("genre_include=fantasy"));
    renderPage();
    expect(screen.getAllByText("Must include").length).toBeGreaterThanOrEqual(1);
  });
});

// ---------------------------------------------------------------------------
// Tag filter tests
// ---------------------------------------------------------------------------

describe("BrowsePage tag filter UI", () => {
  it("shows tag search inputs inside advanced search", () => {
    renderPage();
    openAdvancedSearch();
    const inputs = screen.getAllByPlaceholderText("Type to search tags…");
    expect(inputs.length).toBe(2);
  });

  it("search does not fire for < 2 character query", async () => {
    renderPage();
    openAdvancedSearch();

    const inputs = screen.getAllByPlaceholderText("Type to search tags…") as HTMLInputElement[];
    fireEvent.input(inputs[0], { target: { value: "i" } });

    // After a short wait, searchTags should NOT have been called
    await new Promise((r) => setTimeout(r, 450));
    expect(mocks.searchTags).not.toHaveBeenCalled();
  });

  it("search fires for >= 2 character query", async () => {
    mocks.searchTags.mockResolvedValue([
      { name: "isekai", name_ja: null },
    ]);

    renderPage();
    openAdvancedSearch();

    const inputs = screen.getAllByPlaceholderText("Type to search tags…") as HTMLInputElement[];
    fireEvent.input(inputs[0], { target: { value: "is" } });

    await waitFor(() => {
      expect(mocks.searchTags).toHaveBeenCalled();
    }, { timeout: 800 });

    // Also verify "isekai" appears in dropdown
    await waitFor(() => {
      expect(screen.getByText("isekai")).toBeInTheDocument();
    }, { timeout: 500 });
  });

  it("matching tags appear in typeahead", async () => {
    mocks.searchTags.mockResolvedValue([
      { name: "isekai", name_ja: null },
      { name: "magic", name_ja: "魔法" },
    ]);

    renderPage();
    openAdvancedSearch();

    const inputs = screen.getAllByPlaceholderText("Type to search tags…") as HTMLInputElement[];
    fireEvent.input(inputs[0], { target: { value: "is" } });

    await waitFor(() => {
      expect(screen.getByText("isekai")).toBeInTheDocument();
    }, { timeout: 800 });
    expect(screen.getByText("magic")).toBeInTheDocument();
  });

  it("selecting include tag pushes tag_include param and resets page", async () => {
    mocks.searchTags.mockResolvedValue([
      { name: "isekai", name_ja: null },
    ]);

    renderPage();
    openAdvancedSearch();

    const inputs = screen.getAllByPlaceholderText("Type to search tags…") as HTMLInputElement[];
    fireEvent.input(inputs[0], { target: { value: "is" } });

    await waitFor(() => {
      expect(screen.getByText("isekai")).toBeInTheDocument();
    }, { timeout: 800 });

    act(() => { screen.getByText("isekai").click(); });

    const lastCall = mocks.pushFn.mock.calls[mocks.pushFn.mock.calls.length - 1][0] as string;
    expect(lastCall).toContain("tag_include=isekai");
    expect(lastCall).not.toContain("page=");
  });

  it("selecting exclude tag pushes tag_exclude param", async () => {
    mocks.searchTags.mockResolvedValue([
      { name: "action", name_ja: null },
    ]);

    renderPage();
    openAdvancedSearch();

    const inputs = screen.getAllByPlaceholderText("Type to search tags…") as HTMLInputElement[];
    fireEvent.input(inputs[1], { target: { value: "ac" } });

    await waitFor(() => {
      expect(screen.getByText("action")).toBeInTheDocument();
    }, { timeout: 800 });

    act(() => { screen.getByText("action").click(); });

    const lastCall = mocks.pushFn.mock.calls[mocks.pushFn.mock.calls.length - 1][0] as string;
    expect(lastCall).toContain("tag_exclude=action");
  });

  it("selected tags render as removable chips", () => {
    searchParamsMock.mockReturnValue(new URLSearchParams("tag_include=isekai"));
    renderPage();
    // Advanced search opens auto when tag params in URL

    expect(screen.getByText("isekai")).toBeInTheDocument();
    expect(screen.getByLabelText("Remove tag isekai")).toBeInTheDocument();
  });

  it("already-selected tags are hidden from dropdown results", async () => {
    searchParamsMock.mockReturnValue(new URLSearchParams("tag_include=isekai"));

    mocks.searchTags.mockResolvedValue([
      { name: "isekai", name_ja: null },
      { name: "isekai-romance", name_ja: null },
    ]);

    renderPage();
    // Advanced search opens auto when tag params in URL

    const inputs = screen.getAllByPlaceholderText("Type to search tags…") as HTMLInputElement[];
    fireEvent.input(inputs[0], { target: { value: "is" } });

    await waitFor(() => {
      // "isekai-romance" should appear
      expect(screen.getByText("isekai-romance")).toBeInTheDocument();
    }, { timeout: 800 });

    // "isekai" should appear exactly once (the chip, not the dropdown result)
    expect(screen.getAllByText("isekai").length).toBe(1);
  });

  it("clearing filters removes tag params", () => {
    searchParamsMock.mockReturnValue(new URLSearchParams("tag_include=isekai"));
    renderPage();
    const clearBtns = screen.getAllByText("Clear filters");
    act(() => { clearBtns[0].click(); });
    const url = mocks.pushFn.mock.calls[0][0] as string;
    expect(url).not.toContain("tag_include");
    expect(url).not.toContain("tag_exclude");
  });

  it("changing tag filter resets page to 1", async () => {
    searchParamsMock.mockReturnValue(new URLSearchParams("page=3"));

    mocks.searchTags.mockResolvedValue([
      { name: "isekai", name_ja: null },
    ]);

    renderPage();
    openAdvancedSearch();

    const inputs = screen.getAllByPlaceholderText("Type to search tags…") as HTMLInputElement[];
    fireEvent.input(inputs[0], { target: { value: "is" } });

    await waitFor(() => {
      expect(screen.getByText("isekai")).toBeInTheDocument();
    }, { timeout: 800 });

    act(() => { screen.getByText("isekai").click(); });

    const lastCall = mocks.pushFn.mock.calls[mocks.pushFn.mock.calls.length - 1][0] as string;
    expect(lastCall).not.toContain("page=");
    expect(lastCall).toContain("tag_include=isekai");
  });

  it("advanced search opens automatically when tag params in URL", () => {
    searchParamsMock.mockReturnValue(new URLSearchParams("tag_include=isekai"));
    renderPage();
    expect(screen.getByText("Tag filters")).toBeInTheDocument();
  });

  it("shows no-matching-tags state when search returns empty", async () => {
    mocks.searchTags.mockResolvedValue([]);

    renderPage();
    openAdvancedSearch();

    const inputs = screen.getAllByPlaceholderText("Type to search tags…") as HTMLInputElement[];
    fireEvent.input(inputs[0], { target: { value: "xy" } });

    await waitFor(() => {
      expect(screen.getByText("No matching tags.")).toBeInTheDocument();
    }, { timeout: 800 });
  });

  it("tag filter indicator shows in results header for included tags", () => {
    searchParamsMock.mockReturnValue(new URLSearchParams("tag_include=isekai"));
    renderPage();
    expect(screen.getByText(/1 tag incl\./)).toBeInTheDocument();
  });

  it("tag filter indicator shows in results header for excluded tags", () => {
    searchParamsMock.mockReturnValue(new URLSearchParams("tag_exclude=action"));
    renderPage();
    expect(screen.getByText(/1 tag excl\./)).toBeInTheDocument();
  });

  it("removing a tag chip updates URL params", () => {
    searchParamsMock.mockReturnValue(new URLSearchParams("tag_include=isekai&tag_exclude=action"));
    renderPage();
    // Advanced search opens auto when tag params in URL

    const removeBtn = screen.getByLabelText("Remove tag isekai");
    act(() => { removeBtn.click(); });

    const lastCall = mocks.pushFn.mock.calls[mocks.pushFn.mock.calls.length - 1][0] as string;
    expect(lastCall).toContain("tag_exclude=action");
    // isekai was the only include tag, so tag_include should be absent
    expect(lastCall).not.toContain("tag_include");
  });
});

// ---------------------------------------------------------------------------
// Genre/tag pass-through from API to NovelCard
// ---------------------------------------------------------------------------

describe("BrowsePage genre/tag pass-through", () => {
  it("passes genres and tags from API response through to NovelCard", () => {
    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [
          {
            novel_id: "n1",
            slug: "n1",
            title: "Novel One",
            author: "Author One",
            language: "ja",
            status: "Ongoing",
            chapter_count: 10,
            translated_count: 3,
            added_at: null,
            genres: ["fantasy", "isekai"],
            tags: ["magic", "hero"],
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
      isPending: false,
      isError: false,
      error: null,
    });

    render(
      <QueryClientProvider client={queryClient}>
        <BrowsePage
          basePath="/browse-novels"
          title="Browse"
          description="Find novels"
        />
      </QueryClientProvider>
    );

    expect(screen.getByText("fantasy")).toBeInTheDocument();
    expect(screen.getByText("isekai")).toBeInTheDocument();
    expect(screen.getByText("magic")).toBeInTheDocument();
    expect(screen.getByText("hero")).toBeInTheDocument();
  });

  it("renders no genre/tag chips when API returns empty arrays", () => {
    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [
          {
            novel_id: "n1",
            slug: "n1",
            title: "Novel One",
            author: "Author One",
            language: "ja",
            status: "Ongoing",
            chapter_count: 10,
            translated_count: 3,
            added_at: null,
            genres: [],
            tags: [],
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
      isPending: false,
      isError: false,
      error: null,
    });

    render(
      <QueryClientProvider client={queryClient}>
        <BrowsePage
          basePath="/browse-novels"
          title="Browse"
          description="Find novels"
        />
      </QueryClientProvider>
    );

    expect(screen.queryByText("fantasy")).not.toBeInTheDocument();
    expect(screen.queryByText("magic")).not.toBeInTheDocument();
  });

  it("renders no genre/tag chips when API returns undefined fields", () => {
    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [
          {
            novel_id: "n1",
            slug: "n1",
            title: "Novel One",
            author: "Author One",
            language: "ja",
            status: "Ongoing",
            chapter_count: 10,
            translated_count: 3,
            added_at: null,
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
      isPending: false,
      isError: false,
      error: null,
    });

    render(
      <QueryClientProvider client={queryClient}>
        <BrowsePage
          basePath="/browse-novels"
          title="Browse"
          description="Find novels"
        />
      </QueryClientProvider>
    );

    expect(screen.getAllByText("Novel One").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("fantasy")).not.toBeInTheDocument();
  });

  it("does not display hardcoded fallback genres", () => {
    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [
          {
            novel_id: "n1",
            slug: "n1",
            title: "Novel One",
            author: "Author One",
            language: "ja",
            status: "Ongoing",
            chapter_count: 10,
            translated_count: 3,
            added_at: null,
            genres: undefined,
            tags: undefined,
          },
        ],
        total: 1,
        page: 1,
        page_size: 20,
      },
      isPending: false,
      isError: false,
      error: null,
    });

    render(
      <QueryClientProvider client={queryClient}>
        <BrowsePage
          basePath="/browse-novels"
          title="Browse"
          description="Find novels"
        />
      </QueryClientProvider>
    );

    expect(screen.queryByText("Fantasy")).not.toBeInTheDocument();
    expect(screen.queryByText("Isekai")).not.toBeInTheDocument();
    expect(screen.queryByText("Popular")).not.toBeInTheDocument();
    expect(screen.queryByText("Trending")).not.toBeInTheDocument();
    expect(screen.queryByText("Romance")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Catalog search (q param) tests
// ---------------------------------------------------------------------------

describe("BrowsePage catalog search", () => {
  it("initializes search input from URL q param", () => {
    searchParamsMock.mockReturnValue(new URLSearchParams("q=test+query"));

    renderPage();

    const input = screen.getByPlaceholderText("Search by title or author") as HTMLInputElement;
    expect(input.value).toBe("test query");
  });

  it("search input is empty when no q param", () => {
    renderPage();

    const input = screen.getByPlaceholderText("Search by title or author") as HTMLInputElement;
    expect(input.value).toBe("");
  });

  it("shows active search indicator with quoted query", () => {
    searchParamsMock.mockReturnValue(new URLSearchParams("q=test+query"));

    renderPage();

    expect(screen.getByText(/“test query”/)).toBeInTheDocument();
  });

  it("does not show active search indicator when q param absent", () => {
    searchParamsMock.mockReturnValue(new URLSearchParams(""));

    renderPage();

    expect(screen.queryByText(/“/)).not.toBeInTheDocument();
  });

  it("submitting search form pushes q param with page=1", () => {
    renderPage();

    const input = screen.getByPlaceholderText("Search by title or author");
    fireEvent.change(input, { target: { value: "novel" } });
    fireEvent.click(screen.getByRole("button", { name: /search/i }));

    const lastCall = mocks.pushFn.mock.calls[mocks.pushFn.mock.calls.length - 1][0] as string;
    expect(lastCall).toContain("q=novel");
    expect(lastCall).not.toContain("page=");
  });

  it("submitting empty search removes q param", () => {
    searchParamsMock.mockReturnValue(new URLSearchParams("q=old"));

    renderPage();

    const input = screen.getByPlaceholderText("Search by title or author");
    fireEvent.change(input, { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: /search/i }));

    const lastCall = mocks.pushFn.mock.calls[mocks.pushFn.mock.calls.length - 1][0] as string;
    expect(lastCall).not.toContain("q=");
  });

  it("clear filters removes q param", () => {
    searchParamsMock.mockReturnValue(new URLSearchParams("q=test&status=Ongoing"));

    renderPage();

    const clearBtns = screen.getAllByText("Clear filters");
    act(() => { clearBtns[0].click(); });

    const url = mocks.pushFn.mock.calls[0][0] as string;
    expect(url).not.toContain("q=");
    expect(url).not.toContain("status=");
  });

  it("renders honest no-match message when catalog empty with active filters", () => {
    searchParamsMock.mockReturnValue(new URLSearchParams("q=xyz"));

    renderPage();

    expect(
      screen.getByText(/No novels matched this search/)
    ).toBeInTheDocument();
    // Multiple "Clear filters" elements appear (filter bar + empty state)
    const clearButtons = screen.getAllByText("Clear filters");
    expect(clearButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("renders honest empty catalog message when no filters active", () => {
    searchParamsMock.mockReturnValue(new URLSearchParams(""));

    renderPage();

    expect(
      screen.getByText(/catalog is empty right now/)
    ).toBeInTheDocument();
  });

  it("does not pass include_adult=true in URL on search", () => {
    renderPage();

    const input = screen.getByPlaceholderText("Search by title or author");
    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.click(screen.getByRole("button", { name: /search/i }));

    const lastCall = mocks.pushFn.mock.calls[mocks.pushFn.mock.calls.length - 1][0] as string;
    expect(lastCall).not.toContain("include_adult");
  });
});