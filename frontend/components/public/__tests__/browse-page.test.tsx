import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowsePage } from "@/components/public/browse-page";

// ---------------------------------------------------------------------------
// Mocks — forward all exports so components like SaveToLibrary still work
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
  genresQuery: vi.fn(),
  catalogQuery: vi.fn(),
  pushFn: vi.fn(),
  refreshFn: vi.fn(),
}));

vi.mock("@/hooks/public", async () => {
  const actual = await vi.importActual<typeof import("@/hooks/public")>("@/hooks/public");
  return {
    ...actual,
    useCatalog: () => mocks.catalogQuery(),
    useGenres: () => mocks.genresQuery(),
  };
});

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
      { slug: "fantasy", name_ja: "ファンタジー", name_en: "Fantasy", is_adult: false },
      { slug: "romance", name_ja: "恋愛", name_en: "Romance", is_adult: false },
      { slug: "adult", name_ja: "成人向け", name_en: null, is_adult: true },
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
  const btn = screen.getByRole("button", { name: /advanced search/i });
  act(() => {
    btn.click();
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("BrowsePage genre filter UI", () => {
  it("renders genre list from API", () => {
    renderPage();
    openAdvancedSearch();

    const allFantasy = screen.getAllByText("Fantasy");
    expect(allFantasy.length).toBe(2);
  });

  it("shows loading state when genres are pending", () => {
    mocks.genresQuery.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
    });
    renderPage();
    openAdvancedSearch();

    expect(screen.getByText("Loading genres…")).toBeInTheDocument();
  });

  it("shows unavailable message when genre fetch fails", () => {
    mocks.genresQuery.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
    });
    renderPage();
    openAdvancedSearch();

    expect(screen.getByText("Genres temporarily unavailable.")).toBeInTheDocument();
  });

  it("shows empty state when no genres returned", () => {
    mocks.genresQuery.mockReturnValue({
      data: [],
      isPending: false,
      isError: false,
    });
    renderPage();
    openAdvancedSearch();

    expect(screen.getByText("No genres available.")).toBeInTheDocument();
  });

  it("selecting include genre pushes genre_include param", () => {
    renderPage();
    openAdvancedSearch();

    const includeGroup = screen.getByRole("group", { name: /include genres/i });
    const fantasyBtn = includeGroup.querySelector("button")!;
    act(() => { fantasyBtn.click(); });

    expect(mocks.pushFn).toHaveBeenCalledTimes(1);
    const url = mocks.pushFn.mock.calls[0][0] as string;
    expect(url).toContain("genre_include=fantasy");
    expect(url).not.toContain("page=");
  });

  it("selecting exclude genre pushes genre_exclude param", () => {
    renderPage();
    openAdvancedSearch();

    const excludeGroup = screen.getByRole("group", { name: /exclude genres/i });
    const fantasyBtn = excludeGroup.querySelector("button")!;
    act(() => { fantasyBtn.click(); });

    expect(mocks.pushFn).toHaveBeenCalledTimes(1);
    const url = mocks.pushFn.mock.calls[0][0] as string;
    expect(url).toContain("genre_exclude=fantasy");
  });

  it("clearing filters removes genre params", () => {
    searchParamsMock.mockReturnValue(new URLSearchParams("genre_include=fantasy"));
    mocks.catalogQuery.mockReturnValue({
      data: { novels: [], total: 0, page: 1, page_size: 20 },
      isPending: false,
      isError: false,
      error: null,
    });

    renderPage();

    // There are two "Clear filters" buttons (header + empty state). Pick the first.
    const clearBtns = screen.getAllByText("Clear filters");
    act(() => { clearBtns[0].click(); });

    const url = mocks.pushFn.mock.calls[0][0] as string;
    expect(url).not.toContain("genre_include");
    expect(url).not.toContain("genre_exclude");
  });

  it("changing genre filter resets page to 1", () => {
    searchParamsMock.mockReturnValue(new URLSearchParams("page=3"));
    renderPage();
    openAdvancedSearch();

    const includeGroup = screen.getByRole("group", { name: /include genres/i });
    const fantasyBtn = includeGroup.querySelector("button")!;
    act(() => { fantasyBtn.click(); });

    const url = mocks.pushFn.mock.calls[0][0] as string;
    expect(url).not.toContain("page=");
    expect(url).toContain("genre_include=fantasy");
  });

  it("Browse still works when genres fail to load", () => {
    mocks.genresQuery.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
    });

    renderPage();
    openAdvancedSearch();

    expect(screen.getByText("Genres temporarily unavailable.")).toBeInTheDocument();
    expect(screen.queryByText("Fantasy")).not.toBeInTheDocument();
    expect(screen.getByText("No matching novels found")).toBeInTheDocument();
  });

  it("Browse still works when genres are empty", () => {
    mocks.genresQuery.mockReturnValue({
      data: [],
      isPending: false,
      isError: false,
    });

    renderPage();
    openAdvancedSearch();

    expect(screen.getByText("No genres available.")).toBeInTheDocument();
    expect(screen.queryByText("Fantasy")).not.toBeInTheDocument();
  });

  it("genre filter indicator shows in results header when genres are included", () => {
    searchParamsMock.mockReturnValue(new URLSearchParams("genre_include=fantasy"));
    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [
          {
            novel_id: "n001",
            slug: "n001",
            title: "Novel One",
            author: "Author",
            language: "ja",
            status: "Ongoing",
            chapter_count: 10,
            translated_count: 5,
            added_at: null,
            genres: ["fantasy"],
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

    renderPage();

    expect(screen.getByText(/1 genre incl\./)).toBeInTheDocument();
  });

  it("genre filter indicator shows in results header when genres are excluded", () => {
    searchParamsMock.mockReturnValue(new URLSearchParams("genre_exclude=romance"));
    mocks.catalogQuery.mockReturnValue({
      data: {
        novels: [
          {
            novel_id: "n001",
            slug: "n001",
            title: "Novel One",
            author: "Author",
            language: "ja",
            status: "Ongoing",
            chapter_count: 10,
            translated_count: 5,
            added_at: null,
            genres: ["fantasy"],
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

    renderPage();

    expect(screen.getByText(/1 genre excl\./)).toBeInTheDocument();
  });

  it("opens advanced search automatically when genre filters are in URL", () => {
    searchParamsMock.mockReturnValue(new URLSearchParams("genre_include=fantasy"));
    renderPage();

    expect(screen.getByText("Must include")).toBeInTheDocument();
  });
});