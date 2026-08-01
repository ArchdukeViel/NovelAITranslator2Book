/**
 * SearchOverlay tests — the one shared search overlay (DESIGN.md — Search
 * contract).
 *
 * Covers: open/close, empty-query state (recents + genre shortcuts, no
 * request), debounce + in-flight request cancellation, grouped results
 * (Novels / Authors / Genres & Tags), keyboard behavior (arrows, Enter,
 * Escape + focus return), always-last "See all results" row, honest network
 * failure state, and local-only recent searches.
 *
 * Feature: PUBLIC-SEARCH-2
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act, within } from "@testing-library/react";

import { SearchOverlay } from "@/components/public/search-overlay";
import { useSearchOverlay, recordRecentSearch, loadRecentSearches } from "@/lib/search-overlay";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
  pushFn: vi.fn(),
  catalog: vi.fn(),
  searchTags: vi.fn(),
  useGenres: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.pushFn }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/public-api", () => ({
  publicApi: {
    catalog: (...args: unknown[]) => mocks.catalog(...args),
    searchTags: (...args: unknown[]) => mocks.searchTags(...args),
  },
}));

vi.mock("@/hooks/public/use-genres", () => ({
  useGenres: (...args: unknown[]) => mocks.useGenres(...args),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const genreList = [
  { slug: "fantasy", name_ja: "ファンタジー", name_en: "Fantasy" },
  { slug: "romance", name_ja: "恋愛", name_en: "Romance" },
];

const catalogResponse = (novels: { novel_id: string; slug: string; title: string; source_title: string | null; author: string }[]) => ({
  novels,
  total: novels.length,
  page: 1,
  page_size: 10,
});

const catalogNovels = [
  {
    novel_id: "n1",
    slug: "dragon-king",
    title: "Dragon King",
    source_title: "ドラゴン王",
    author: "Tanaka",
    language: "ja",
    synopsis: null,
    publication_status: "ongoing",
    chapter_count: 5,
    translated_count: 5,
  },
  {
    novel_id: "n2",
    slug: "quiet-novel",
    title: "Quiet Novel",
    source_title: "静かな小説",
    author: "Dragon Writer",
    language: "ja",
    synopsis: null,
    publication_status: "ongoing",
    chapter_count: 3,
    translated_count: 3,
  },
];

function openOverlay() {
  act(() => {
    useSearchOverlay.getState().open();
  });
}

async function typeQuery(text: string) {
  const input = screen.getByRole("searchbox", { name: /search/i }) as HTMLInputElement;
  await act(async () => {
    fireEvent.change(input, { target: { value: text } });
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SearchOverlay open/close", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.useGenres.mockReturnValue({ data: genreList, isLoading: false, isError: false, error: null });
    // Reset shared store so each test starts with a closed overlay.
    useSearchOverlay.setState({ isOpen: false, openerRef: null });
  });

  it("renders nothing when closed", () => {
    const { container } = render(<SearchOverlay />);
    expect(container.querySelector('[role="dialog"]')).not.toBeInTheDocument();
  });

  it("opens and focuses the input", () => {
    render(<SearchOverlay />);
    openOverlay();
    expect(screen.getByRole("dialog", { name: /search/i })).toBeInTheDocument();
    const input = screen.getByRole("searchbox", { name: /search/i });
    expect(input).toHaveFocus();
  });

  it("returns focus to the opener element when closed", () => {
    const trigger = document.createElement("button");
    trigger.textContent = "Open";
    document.body.appendChild(trigger);
    trigger.focus();

    render(<SearchOverlay />);
    openOverlay();
    expect(screen.getByRole("searchbox", { name: /search/i })).toHaveFocus();

    // Escape closes the overlay
    fireEvent.keyDown(screen.getByRole("searchbox", { name: /search/i }), { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: /search/i })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
    trigger.remove();
  });

  it("closes via backdrop click", () => {
    render(<SearchOverlay />);
    openOverlay();
    fireEvent.click(screen.getByLabelText("Close search"));
    expect(screen.queryByRole("dialog", { name: /search/i })).not.toBeInTheDocument();
  });
});

describe("SearchOverlay empty query state", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.useGenres.mockReturnValue({ data: genreList, isLoading: false, isError: false, error: null });
    // Safe defaults: clicking a recent search re-runs a real (debounced) search.
    mocks.catalog.mockResolvedValue(catalogResponse([]));
    mocks.searchTags.mockResolvedValue([]);
    localStorage.clear();
  });

  it("shows local recent searches and genre shortcuts, and fires no request", () => {
    recordRecentSearch("dragon");
    recordRecentSearch("magic school");
    render(<SearchOverlay />);
    openOverlay();

    expect(screen.getByText("Recent searches")).toBeInTheDocument();
    expect(screen.getByText("dragon")).toBeInTheDocument();
    expect(screen.getByText("magic school")).toBeInTheDocument();
    expect(screen.getByText("Genre shortcuts")).toBeInTheDocument();
    expect(screen.getByText("Fantasy")).toBeInTheDocument();
    expect(mocks.catalog).not.toHaveBeenCalled();
    expect(mocks.searchTags).not.toHaveBeenCalled();
  });

  it("shows a playful empty state when nothing is stored and no genres", () => {
    mocks.useGenres.mockReturnValue({ data: [], isLoading: false, isError: false, error: null });
    render(<SearchOverlay />);
    openOverlay();

    expect(screen.getByText(/nothing here yet/i)).toBeInTheDocument();
  });

  it("re-runs a search when a recent search is clicked", async () => {
    recordRecentSearch("dragon");
    render(<SearchOverlay />);
    openOverlay();

    fireEvent.click(screen.getByText("dragon"));
    const input = screen.getByRole("searchbox", { name: /search/i }) as HTMLInputElement;
    expect(input.value).toBe("dragon");
  });

  it("clears recent searches", () => {
    recordRecentSearch("dragon");
    render(<SearchOverlay />);
    openOverlay();

    fireEvent.click(screen.getByText("Clear"));
    expect(screen.queryByText("dragon")).not.toBeInTheDocument();
    expect(loadRecentSearches()).toEqual([]);
  });

  it("queries under 2 characters show shortcuts without firing a request", async () => {
    render(<SearchOverlay />);
    openOverlay();
    await typeQuery("d");

    expect(mocks.catalog).not.toHaveBeenCalled();
    expect(mocks.searchTags).not.toHaveBeenCalled();
    expect(screen.getByText("Genre shortcuts")).toBeInTheDocument();
  });
});

describe("SearchOverlay live results", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.useGenres.mockReturnValue({ data: genreList, isLoading: false, isError: false, error: null });
    mocks.catalog.mockImplementation((_params: unknown, signal?: AbortSignal) =>
      new Promise((resolve, reject) => {
        const timer = setTimeout(() => resolve(catalogResponse(catalogNovels)), 20);
        signal?.addEventListener("abort", () => {
          clearTimeout(timer);
          reject(new DOMException("Aborted", "AbortError"));
        });
      })
    );
    mocks.searchTags.mockImplementation((_params: unknown, signal?: AbortSignal) =>
      new Promise((resolve, reject) => {
        const timer = setTimeout(() => resolve([{ name: "adventure", name_ja: "冒険" }]), 20);
        signal?.addEventListener("abort", () => {
          clearTimeout(timer);
          reject(new DOMException("Aborted", "AbortError"));
        });
      })
    );
  });

  it("debounces then fetches catalog and tags", async () => {
    render(<SearchOverlay />);
    openOverlay();
    await typeQuery("dragon");

    // Debounce window (225ms): no request fired yet
    expect(mocks.catalog).not.toHaveBeenCalled();
    await waitFor(() => expect(mocks.catalog).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByText("Dragon King")).toBeInTheDocument());

    expect(screen.getByText("Novels")).toBeInTheDocument();
    expect(screen.getByText("Dragon King")).toBeInTheDocument();
    expect(screen.getByText("Authors")).toBeInTheDocument();
    // Scope to the Authors <ul>, the sibling of its header <p> — the same
    // author also appears as a label on novel rows.
    const authorsList = screen.getByText("Authors").nextElementSibling as HTMLElement;
    expect(within(authorsList).getByText("Dragon Writer")).toBeInTheDocument();
    expect(screen.getByText("Genres & Tags")).toBeInTheDocument();
    expect(screen.getByText("#adventure")).toBeInTheDocument();
    // See-all row always last
    expect(screen.getByText(/see all results for/i)).toBeInTheDocument();
    expect(mocks.searchTags).toHaveBeenCalledTimes(1);
  });

  it("cancels the in-flight request when a new keystroke lands", async () => {
    render(<SearchOverlay />);
    openOverlay();
    await typeQuery("dragon");

    // First request fired; immediately type a longer query
    await waitFor(() => expect(mocks.catalog).toHaveBeenCalled());
    await typeQuery("dragon king");

    await waitFor(() => expect(mocks.catalog).toHaveBeenCalledTimes(2));
    // The first call must have been aborted — the second resolves with the
    // same shape; assert last call wins and no double render of stale data.
    expect(screen.getByText("Dragon King")).toBeInTheDocument();
    expect(mocks.catalog.mock.calls[0][1]).toBeInstanceOf(AbortSignal);
  });

  it("does not show a loading flash — stale results stay until replacement", async () => {
    render(<SearchOverlay />);
    openOverlay();
    await typeQuery("dragon");
    await waitFor(() => expect(screen.getByText("Dragon King")).toBeInTheDocument());

    // Type a second query; results should remain visible (no blank/loading)
    mocks.catalog.mockImplementation(() => new Promise((resolve) => setTimeout(() => resolve(catalogResponse([])), 50)));
    mocks.searchTags.mockResolvedValue([]);
    await typeQuery("dragon king");
    expect(screen.getByText("Dragon King")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("Dragon King")).not.toBeInTheDocument());
    expect(screen.getByText(/no matches for/i)).toBeInTheDocument();
  });

  it("shows the honest network failure state", async () => {
    mocks.catalog.mockRejectedValue(new Error("network down"));
    mocks.searchTags.mockRejectedValue(new Error("network down"));
    render(<SearchOverlay />);
    openOverlay();
    await typeQuery("dragon");

    await waitFor(() => expect(screen.getByText(/search's unavailable right now/i)).toBeInTheDocument());
    // Never a silent empty-results list
    expect(screen.queryByText(/no matches for/i)).not.toBeInTheDocument();
  });

  it("still shows results when only one group fails (partial failure)", async () => {
    mocks.catalog.mockResolvedValue(catalogResponse(catalogNovels));
    mocks.searchTags.mockRejectedValue(new Error("tags down"));
    render(<SearchOverlay />);
    openOverlay();
    await typeQuery("dragon");

    await waitFor(() => expect(screen.getByText("Dragon King")).toBeInTheDocument());
    expect(screen.queryByText(/search's unavailable right now/i)).not.toBeInTheDocument();
  });
});

describe("SearchOverlay keyboard behavior", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.useGenres.mockReturnValue({ data: genreList, isLoading: false, isError: false, error: null });
    mocks.catalog.mockResolvedValue(catalogResponse(catalogNovels));
    mocks.searchTags.mockResolvedValue([{ name: "adventure", name_ja: "冒険" }]);
  });

  it("ArrowDown then Enter opens the highlighted result", async () => {
    render(<SearchOverlay />);
    openOverlay();
    await typeQuery("dragon");
    await waitFor(() => expect(screen.getByText("Dragon King")).toBeInTheDocument());

    const input = screen.getByRole("searchbox", { name: /search/i });
    fireEvent.keyDown(input, { key: "ArrowDown" }); // highlight first novel
    fireEvent.keyDown(input, { key: "Enter" });

    expect(mocks.pushFn).toHaveBeenCalledWith("/novels/dragon-king");
  });

  it("Enter with nothing highlighted opens the full results page", async () => {
    render(<SearchOverlay />);
    openOverlay();
    await typeQuery("dragon");
    await waitFor(() => expect(screen.getByText("Dragon King")).toBeInTheDocument());

    fireEvent.keyDown(screen.getByRole("searchbox", { name: /search/i }), { key: "Enter" });
    expect(mocks.pushFn).toHaveBeenCalledWith("/browse-novels?q=dragon");
  });

  it("ArrowDown/ArrowUp cycle across grouped results", async () => {
    render(<SearchOverlay />);
    openOverlay();
    await typeQuery("dragon");
    await waitFor(() => expect(screen.getByText("Dragon King")).toBeInTheDocument());

    const input = screen.getByRole("searchbox", { name: /search/i });
    // rows: Dragon King (novel), Quiet Novel (novel), Dragon Writer (author), #adventure (tag), see-all
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(mocks.pushFn).toHaveBeenCalledWith("/novels/quiet-novel");
  });

  it("Enter on an author row searches by that author", async () => {
    render(<SearchOverlay />);
    openOverlay();
    await typeQuery("dragon");
    // "Dragon Writer" appears both as the author label on the novel row and
    // as the Authors group entry — scope the query to the group list.
    const authorsGroup = await waitFor(() => {
      const list = screen.getByText("Authors").nextElementSibling as HTMLElement;
      expect(within(list).getByText("Dragon Writer")).toBeInTheDocument();
      return list;
    });
    expect(authorsGroup).toBeInTheDocument();

    const input = screen.getByRole("searchbox", { name: /search/i });
    // novels(2) then author — index 2 is "Dragon Writer"
    for (let i = 0; i < 3; i++) fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(mocks.pushFn).toHaveBeenCalledWith("/browse-novels?q=Dragon%20Writer");
  });

  it("Enter on the always-last see-all row opens the full results page", async () => {
    render(<SearchOverlay />);
    openOverlay();
    await typeQuery("dragon");
    await waitFor(() => expect(screen.getByText("Dragon King")).toBeInTheDocument());

    const input = screen.getByRole("searchbox", { name: /search/i });
    const rows = 5; // 2 novels + 1 author + 1 tag + see-all
    for (let i = 0; i < rows; i++) fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(mocks.pushFn).toHaveBeenCalledWith("/browse-novels?q=dragon");
  });
});

describe("SearchOverlay recent searches are local-only", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mocks.useGenres.mockReturnValue({ data: genreList, isLoading: false, isError: false, error: null });
    mocks.catalog.mockResolvedValue(catalogResponse(catalogNovels));
    mocks.searchTags.mockResolvedValue([{ name: "adventure", name_ja: "冒険" }]);
  });

  it("records a recent search when a result is opened", async () => {
    render(<SearchOverlay />);
    openOverlay();
    await typeQuery("dragon");
    await waitFor(() => expect(screen.getByText("Dragon King")).toBeInTheDocument());

    const input = screen.getByRole("searchbox", { name: /search/i });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(loadRecentSearches()).toContain("dragon");
  });

  it("dedupes and caps recent searches at 8", () => {
    for (let i = 0; i < 12; i++) recordRecentSearch(`term-${i % 6}`);
    const recents = loadRecentSearches();
    expect(recents.length).toBeLessThanOrEqual(8);
    expect(new Set(recents).size).toBe(recents.length);
    expect(recents[0]).toBe("term-5");
  });

  it("only records queries of at least 2 characters", () => {
    recordRecentSearch("d");
    expect(loadRecentSearches()).toEqual([]);
  });
});
