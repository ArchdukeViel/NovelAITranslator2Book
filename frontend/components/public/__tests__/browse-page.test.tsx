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
      { slug: "fantasy", name_ja: "ファンタジー", name_en: "Fantasy", is_adult: false },
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
  const btn = screen.getByRole("button", { name: /advanced search/i });
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
      { name: "isekai", name_ja: null, is_adult: false },
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
      { name: "isekai", name_ja: null, is_adult: false },
      { name: "magic", name_ja: "魔法", is_adult: false },
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
      { name: "isekai", name_ja: null, is_adult: false },
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
      { name: "action", name_ja: null, is_adult: false },
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
      { name: "isekai", name_ja: null, is_adult: false },
      { name: "isekai-romance", name_ja: null, is_adult: false },
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
      { name: "isekai", name_ja: null, is_adult: false },
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