import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "@/app/(public)/home/page";

const mocks = vi.hoisted(() => ({
  catalogQuery: vi.fn(),
  historyQuery: vi.fn(),
  catalogParams: vi.fn(),
  isAuthenticated: false,
}));

vi.mock("@/hooks/public", async () => {
  const actual = await vi.importActual<typeof import("@/hooks/public")>("@/hooks/public");
  return {
    ...actual,
    useCatalog: (params: unknown) => {
      mocks.catalogParams(params);
      return mocks.catalogQuery();
    },
    useGenreLabelMap: () => new Map<string, string>(),
    useHistory: () => mocks.historyQuery(),
    usePublicAuth: () => ({
      isAuthenticated: mocks.isAuthenticated,
      isPending: false,
      isPublicUser: mocks.isAuthenticated,
      isOwner: false,
      user: mocks.isAuthenticated ? { user_id: 1, email: "reader@example.com" } : null,
    }),
  };
});

vi.mock("next/link", () => ({
  default: ({ children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => <a {...props}>{children}</a>,
}));

function novel(overrides: Record<string, unknown> = {}) {
  return {
    novel_id: "n1",
    slug: "dragon",
    title: "Dragon Road",
    source_title: "竜の道",
    author: "Author",
    language: "ja",
    synopsis: "A complete synopsis.",
    publication_status: "ongoing",
    chapter_count: 10,
    translated_count: 5,
    added_at: "2026-07-01T00:00:00Z",
    latest_chapter_id: "chapter-5",
    latest_chapter_updated_at: "2026-07-10T00:00:00Z",
    genres: [{ slug: "fantasy", name_ja: "ファンタジー", name_en: "Fantasy" }],
    tags: [],
    ...overrides,
  };
}

let queryClient: QueryClient;

beforeEach(() => {
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.clearAllMocks();
  mocks.isAuthenticated = false;
  mocks.historyQuery.mockReturnValue({ data: undefined, isPending: false, isError: false });
  mocks.catalogQuery.mockReturnValue({
    data: { novels: [novel()], total: 1, page: 1, page_size: 8 },
    isPending: false,
    isError: false,
    refetch: vi.fn(),
  });
});

afterEach(cleanup);

function renderHome() {
  return render(<QueryClientProvider client={queryClient}><HomePage /></QueryClientProvider>);
}

describe("HomePage states", () => {
  it("renders catalog-shaped loading state", () => {
    mocks.catalogQuery.mockReturnValue({ data: undefined, isPending: true, isError: false, refetch: vi.fn() });
    renderHome();
    expect(screen.getByLabelText("Loading featured novel")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Loading catalog");
  });

  it("renders retryable error state", () => {
    const refetch = vi.fn();
    mocks.catalogQuery.mockReturnValue({ data: undefined, isPending: false, isError: true, refetch });
    renderHome();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(refetch).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("link", { name: /browse the catalog/i })).toHaveAttribute("href", "/browse-novels");
  });

  it("renders honest empty state", () => {
    mocks.catalogQuery.mockReturnValue({ data: { novels: [], total: 0, page: 1, page_size: 8 }, isPending: false, isError: false, refetch: vi.fn() });
    renderHome();
    expect(screen.getByText("No novels in the catalog yet")).toBeInTheDocument();
  });
});

describe("HomePage honest spotlight", () => {
  it("shows one Start Reading CTA for an eligible spotlight", () => {
    renderHome();
    const hero = screen.getByLabelText("Dokushodo spotlight novel");
    expect(within(hero).getByText("Spotlight")).toBeInTheDocument();
    expect(within(hero).getByRole("link", { name: /start reading/i })).toHaveAttribute("href", "/novels/dragon/chapter/chapter-5");
    expect(within(hero).queryByText("Featured")).not.toBeInTheDocument();
    expect(within(hero).queryByRole("link", { name: /view details/i })).not.toBeInTheDocument();
  });

  it("does not claim a spotlight when eligibility is missing", () => {
    mocks.catalogQuery.mockReturnValue({ data: { novels: [novel({ synopsis: null, latest_chapter_id: null })], total: 1, page: 1, page_size: 8 }, isPending: false, isError: false, refetch: vi.fn() });
    renderHome();
    expect(screen.queryByText("Spotlight")).not.toBeInTheDocument();
  });
});

describe("HomePage rails", () => {
  it("renders labeled New Novels grid and Recent Updates list with real See More links", () => {
    renderHome();
    const newNovels = screen.getByRole("region", { name: "New releases" });
    expect(
      within(newNovels).getByRole("link", { name: "See More" })
    ).toHaveAttribute("href", "/browse-novels?sort_by=added_at&order=desc");
    const updated = screen.getByRole("region", { name: "Recently updated" });
    expect(
      within(updated).getByRole("link", { name: "See More" })
    ).toHaveAttribute("href", "/browse-novels?sort_by=updated_at&order=desc");
  });

  it("hides the Continue reading region for guests", () => {
    renderHome();
    expect(screen.queryByRole("region", { name: "Continue reading" })).not.toBeInTheDocument();
  });

  it("uses existing history for signed-in Continue Reading", () => {
    mocks.isAuthenticated = true;
    mocks.historyQuery.mockReturnValue({ data: { items: [{ id: 1, slug: "dragon", chapter_id: "chapter-5", chapter_number: 5, read_at: "2026-07-10" }], next_cursor: null }, isPending: false, isError: false });
    renderHome();
    const continuation = screen.getByRole("region", { name: "Continue reading" });
    expect(within(continuation).getByRole("link", { name: "See all" })).toHaveAttribute("href", "/account/history");
  });

  it("derives genre rails from translated catalog composition", () => {
    mocks.catalogQuery.mockReturnValue({ data: { novels: [novel(), novel({ novel_id: "n2", slug: "magic", title: "Magic", genres: [{ slug: "fantasy", name_ja: "ファンタジー", name_en: "Fantasy" }] }), novel({ novel_id: "n3", slug: "love", title: "Love", genres: [{ slug: "romance", name_ja: "恋愛", name_en: "Romance" }] })], total: 3, page: 1, page_size: 8 }, isPending: false, isError: false, refetch: vi.fn() });
    renderHome();
    const fantasy = screen.getByRole("region", { name: "Fantasy novels" });
    expect(within(fantasy).getByRole("link", { name: "See all" })).toHaveAttribute("href", "/genres/fantasy");
  });

  it("links Surprise Me and the discovery tiles to real routes", () => {
    renderHome();
    expect(screen.getByRole("link", { name: /surprise me/i })).toHaveAttribute("href", "/random");
    expect(screen.getByRole("link", { name: /random novel/i })).toHaveAttribute("href", "/random");
    expect(screen.getByRole("link", { name: /request novel/i })).toHaveAttribute("href", "/request-novel");
  });

  it("renders honest catalog-derived sidebar widgets", () => {
    renderHome();
    expect(screen.getByText("Novel Ranking")).toBeInTheDocument();
    expect(screen.getByText("Longest Series")).toBeInTheDocument();
    expect(screen.getByText("Most Chapters")).toBeInTheDocument();
  });

  it("removes Reading Paths and duplicate browse utility boxes", () => {
    renderHome();
    expect(screen.queryByText("Reading Paths")).not.toBeInTheDocument();
    expect(screen.queryByText("Browse Library")).not.toBeInTheDocument();
    expect(screen.queryByText("Catalog Notes")).not.toBeInTheDocument();
  });

  it("never opts into adult catalog content", () => {
    renderHome();
    expect(mocks.catalogParams).toHaveBeenCalledWith(expect.not.objectContaining({ include_adult: true }));
  });
});
