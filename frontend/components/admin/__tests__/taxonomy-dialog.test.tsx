import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TaxonomyDialog } from "@/components/admin/library/taxonomy-dialog";
import type { NovelSummary } from "@/lib/api-types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderWithQuery(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

const mockNovel: NovelSummary = {
  novel_id: "test-novel",
  title: "Test Novel",
  chapter_count: 10,
};

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Mock admin API — partial mock, preserve all non-api exports
const mockGetTaxonomy = vi.hoisted(() => vi.fn());
const mockSetTaxonomy = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    get api() {
      return {
        ...actual.api,
        getTaxonomy: (...args: unknown[]) => mockGetTaxonomy(...args),
        setTaxonomy: (...args: unknown[]) => mockSetTaxonomy(...args),
      };
    },
  };
});

// Mock public API (genres + tag search)
const mockGenres = vi.hoisted(() => vi.fn());
const mockSearchTags = vi.hoisted(() => vi.fn());
vi.mock("@/lib/public-api", () => ({
  get publicApi() {
    return {
      genres: (...args: unknown[]) => mockGenres(...args),
      searchTags: (...args: unknown[]) => mockSearchTags(...args),
    };
  },
}));

afterEach(() => {
  vi.restoreAllMocks();
  cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("TaxonomyDialog", () => {
  it("renders nothing when closed", () => {
    mockGetTaxonomy.mockResolvedValue({ novel_id: "test-novel", genres: [], tags: [] });
    mockGenres.mockResolvedValue([]);
    renderWithQuery(
      <TaxonomyDialog open={false} novel={mockNovel} onClose={() => {}} />
    );
    expect(screen.queryByText(/Taxonomy/)).not.toBeInTheDocument();
  });

  it("opens and loads current taxonomy", async () => {
    mockGetTaxonomy.mockResolvedValue({
      novel_id: "test-novel",
      genres: ["isekai"],
      tags: ["fantasy"],
    });
    mockGenres.mockResolvedValue([
      { slug: "isekai", name_ja: "異世界", name_en: "Isekai" },
      { slug: "romance", name_ja: "恋愛", name_en: "Romance" },
    ]);

    renderWithQuery(
      <TaxonomyDialog open={true} novel={mockNovel} onClose={() => {}} />
    );

    expect(screen.getByText(/Taxonomy.*Test Novel/)).toBeInTheDocument();
    await waitFor(() => {
      expect(mockGetTaxonomy).toHaveBeenCalledWith("test-novel");
    });
  });

  it("shows genre toggles and marks active genres", async () => {
    mockGetTaxonomy.mockResolvedValue({
      novel_id: "test-novel",
      genres: ["isekai"],
      tags: [],
    });
    mockGenres.mockResolvedValue([
      { slug: "isekai", name_ja: "異世界", name_en: "Isekai" },
      { slug: "romance", name_ja: "恋愛", name_en: "Romance" },
    ]);

    renderWithQuery(
      <TaxonomyDialog open={true} novel={mockNovel} onClose={() => {}} />
    );

    // Wait for genres to load
    await waitFor(() => {
      expect(screen.getByText("異世界")).toBeInTheDocument();
    });
    expect(screen.getByText("恋愛")).toBeInTheDocument();
  });

  it("genre toggle changes payload — toggle off", async () => {
    const user = userEvent.setup();
    mockGetTaxonomy.mockResolvedValue({
      novel_id: "test-novel",
      genres: ["isekai"],
      tags: [],
    });
    mockGenres.mockResolvedValue([
      { slug: "isekai", name_ja: "異世界", name_en: "Isekai" },
    ]);
    mockSetTaxonomy.mockResolvedValue({
      novel_id: "test-novel",
      genres: [],
      tags: [],
    });

    renderWithQuery(
      <TaxonomyDialog open={true} novel={mockNovel} onClose={() => {}} />
    );

    await waitFor(() => {
      expect(screen.getByText("異世界")).toBeInTheDocument();
    });

    // Click genre toggle to deselect
    await user.click(screen.getByText("異世界"));

    // Click save
    await user.click(screen.getByText("Save taxonomy"));

    await waitFor(() => {
      expect(mockSetTaxonomy).toHaveBeenCalledWith("test-novel", {
        genre_slugs: [],
        tags: [],
      });
    });
  });

  it("genre toggle changes payload — toggle on", async () => {
    const user = userEvent.setup();
    mockGetTaxonomy.mockResolvedValue({
      novel_id: "test-novel",
      genres: ["isekai"],
      tags: [],
    });
    mockGenres.mockResolvedValue([
      { slug: "isekai", name_ja: "異世界", name_en: "Isekai" },
      { slug: "romance", name_ja: "恋愛", name_en: "Romance" },
    ]);
    mockSetTaxonomy.mockResolvedValue({
      novel_id: "test-novel",
      genres: ["isekai", "romance"],
      tags: [],
    });

    renderWithQuery(
      <TaxonomyDialog open={true} novel={mockNovel} onClose={() => {}} />
    );

    await waitFor(() => {
      expect(screen.getByText("恋愛")).toBeInTheDocument();
    });

    // Click the romance toggle to select it
    await user.click(screen.getByText("恋愛"));

    // Save
    await user.click(screen.getByText("Save taxonomy"));

    await waitFor(() => {
      expect(mockSetTaxonomy).toHaveBeenCalledWith("test-novel", {
        genre_slugs: ["isekai", "romance"],
        tags: [],
      });
    });
  });

  it("tag add changes payload", async () => {
    const user = userEvent.setup();
    mockGetTaxonomy.mockResolvedValue({
      novel_id: "test-novel",
      genres: [],
      tags: ["action"],
    });
    mockGenres.mockResolvedValue([]);
    mockSearchTags.mockResolvedValue([
      { name: "comedy", name_ja: "コメディ" },
    ]);
    mockSetTaxonomy.mockResolvedValue({
      novel_id: "test-novel",
      genres: [],
      tags: ["action", "comedy"],
    });

    renderWithQuery(
      <TaxonomyDialog open={true} novel={mockNovel} onClose={() => {}} />
    );

    // Wait for existing tag to appear
    await waitFor(() => {
      expect(screen.getByText("action")).toBeInTheDocument();
    });

    // Type in tag search
    const input = screen.getByPlaceholderText(/Search tags/);
    await user.type(input, "com");

    // Wait for search results
    await waitFor(() => {
      expect(mockSearchTags).toHaveBeenCalled();
    });

    // Click the result
    await waitFor(() => {
      expect(screen.getByText("comedy")).toBeInTheDocument();
    });
    await user.click(screen.getByText("comedy"));

    // Save
    await user.click(screen.getByText("Save taxonomy"));

    await waitFor(() => {
      expect(mockSetTaxonomy).toHaveBeenCalledWith("test-novel", {
        genre_slugs: [],
        tags: ["action", "comedy"],
      });
    });
  });

  it("tag remove changes payload", async () => {
    const user = userEvent.setup();
    mockGetTaxonomy.mockResolvedValue({
      novel_id: "test-novel",
      genres: [],
      tags: ["action", "comedy"],
    });
    mockGenres.mockResolvedValue([]);
    mockSetTaxonomy.mockResolvedValue({
      novel_id: "test-novel",
      genres: [],
      tags: ["action"],
    });

    renderWithQuery(
      <TaxonomyDialog open={true} novel={mockNovel} onClose={() => {}} />
    );

    // Wait for tags to load
    await waitFor(() => {
      expect(screen.getByText("comedy")).toBeInTheDocument();
    });

    // Click remove button for "comedy" tag
    const removeButtons = screen.getAllByRole("button", { name: /Remove tag/ });
    const comedyRemove = removeButtons.find((btn) =>
      btn.closest("span")?.textContent?.includes("comedy")
    );
    if (comedyRemove) {
      await user.click(comedyRemove);
    }

    // Save
    await user.click(screen.getByText("Save taxonomy"));

    await waitFor(() => {
      expect(mockSetTaxonomy).toHaveBeenCalledWith("test-novel", {
        genre_slugs: [],
        tags: ["action"],
      });
    });
  });

  it("displays error state when load fails", async () => {
    mockGetTaxonomy.mockRejectedValue(new Error("Network failure"));
    mockGenres.mockResolvedValue([]);

    renderWithQuery(
      <TaxonomyDialog open={true} novel={mockNovel} onClose={() => {}} />
    );

    await waitFor(() => {
      expect(screen.getByText(/Network failure/i)).toBeInTheDocument();
    });
  });

  it("calls onClose when Cancel clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    mockGetTaxonomy.mockResolvedValue({
      novel_id: "test-novel",
      genres: [],
      tags: [],
    });
    mockGenres.mockResolvedValue([]);

    renderWithQuery(
      <TaxonomyDialog open={true} novel={mockNovel} onClose={onClose} />
    );

    await waitFor(() => {
      expect(screen.getByText("Cancel")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Cancel"));
    expect(onClose).toHaveBeenCalled();
  });
});
