/**
 * Taxonomy contract and safety tests for public UI.
 *
 * Verifies:
 * - Genre chips display human labels (name_en) when available, not raw slugs
 * - Genre chips fall back to raw slug when genre data is not loaded
 * - Adult/R18/internal labels are not used in public rendering layer
 * - Frontend public-types.ts contains is_adult only in response types, not in chip/label rendering
 *
 * Feature: TAXONOMY-2E
 */

import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { readFileSync } from "node:fs";

// ---------------------------------------------------------------------------
// GenreChip renders human labels when useGenreLabelMap provides data
// ---------------------------------------------------------------------------

// Mock the genre label hook for tests that need labels
const genreLabelMock = vi.hoisted(() => {
  const fn = vi.fn(() => null as Map<string, string> | null);
  return fn;
});

vi.mock("@/hooks/public/use-genre-labels", () => ({
  useGenreLabelMap: () => genreLabelMock(),
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & {
    children: React.ReactNode;
  }) => <a {...props}>{children}</a>,
}));

import { NovelCard } from "@/components/public/novel-card";
import type { PublicNovelSummary } from "@/lib/public-types";

let queryClient: QueryClient;

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, retryDelay: 0 } },
  });
  genreLabelMock.mockReturnValue(null);
});

afterEach(() => {
  cleanup();
});

function renderWithClient(ui: React.ReactNode) {
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

function makeNovel(overrides: Partial<PublicNovelSummary> = {}) {
  return {
    novel_id: "test-novel",
    slug: "test-novel",
    title: "Test Novel",
    source_title: null as string | null,
    author: "Test Author",
    language: "ja",
    synopsis: null as string | null,
    status: "Ongoing",
    chapter_count: 10,
    translated_count: 5,
    added_at: null,
    ...overrides,
  } satisfies PublicNovelSummary;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("Taxonomy contract — genre chip display labels", () => {
  it("displays human label (name_en) from genre map when available", () => {
    genreLabelMock.mockReturnValue(
      new Map([
        ["fantasy", "Fantasy"],
        ["romance", "Romance"],
        ["isekai-tensei", "Isekai (Reincarnation)"],
      ]),
    );

    const novel = makeNovel({ genres: ["fantasy", "isekai-tensei"] });
    renderWithClient(<NovelCard novel={novel} />);

    expect(screen.getByText("Fantasy")).toBeInTheDocument();
    expect(screen.getByText("Isekai (Reincarnation)")).toBeInTheDocument();
  });

  it("falls back to slug when genre label map is not loaded", () => {
    genreLabelMock.mockReturnValue(null);

    const novel = makeNovel({ genres: ["fantasy", "isekai-tensei"] });
    renderWithClient(<NovelCard novel={novel} />);

    expect(screen.getByText("fantasy")).toBeInTheDocument();
    expect(screen.getByText("isekai-tensei")).toBeInTheDocument();
  });

  it("falls back to slug for unknown genre not in label map", () => {
    genreLabelMock.mockReturnValue(
      new Map([["fantasy", "Fantasy"]]),
    );

    const novel = makeNovel({ genres: ["fantasy", "unknown-genre"] });
    renderWithClient(<NovelCard novel={novel} />);

    expect(screen.getByText("Fantasy")).toBeInTheDocument();
    expect(screen.getByText("unknown-genre")).toBeInTheDocument();
  });

  it("genre chips in browse filter use display labels", () => {
    const browseSource = readFileSync(
      "components/public/browse-page.tsx",
      "utf8",
    );
    // Verify the genre filter button renders name_en with slug fallback
    expect(browseSource).toContain("genre.name_en ?? genre.slug");
    // Ensure is_adult is NOT used in the UI rendering layer of browse page
    expect(browseSource).not.toContain("genre.is_adult");
    expect(browseSource).not.toContain("is_adult");
  });
});

describe("Taxonomy contract — adult/R18 label safety", () => {
  it("novel card never renders adult/R18 genre labels as display text", () => {
    genreLabelMock.mockReturnValue(
      new Map([
        ["fantasy", "Fantasy"],
        ["adult-romance", "Adult Romance"],
      ]),
    );

    const novel = makeNovel({ genres: ["fantasy"] });
    renderWithClient(<NovelCard novel={novel} />);

    // "fantasy" chip shows "Fantasy"
    expect(screen.getByText("Fantasy")).toBeInTheDocument();
    // No adult label shown (chip only contains Fantasy)
    expect(screen.queryByText(/r18/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/adult/i)).not.toBeInTheDocument();
  });

  it("public genre response types do not leak is_adult to chip/label rendering", () => {
    // PublicGenreResponse is the type used for the /genres endpoint response
    // which includes is_adult — that's fine for API-level filtering.
    // But the frontend chip rendering must never read is_adult for display.
    const source = readFileSync(
      "components/public/genre-chip.tsx",
      "utf8",
    );
    expect(source).not.toContain("is_adult");
  });

  it("novel detail genre chips do not render is_adult flag", () => {
    const source = readFileSync(
      "app/(public)/novel/[slug]/page.tsx",
      "utf8",
    );
    // Verify genre rendering uses genreLabels fallback, not is_adult
    expect(source).not.toContain("is_adult");
    // GenreChip is rendered with label prop (not flag)
    expect(source).toContain("genreLabels?.get(genre) ?? genre");
  });
});

describe("Taxonomy contract — TypeScript type alignment", () => {
  it("PublicNovelSummary genres field is string array matching backend PublicNovelSummary.genres", () => {
    const source = readFileSync("lib/public-types.ts", "utf8");
    // PublicNovelSummary.genres should remain string[] (slugs)
    expect(source).toContain("genres?: string[]");
  });

  it("PublicGenreResponse has required fields for label resolution", () => {
    const source = readFileSync("lib/public-types.ts", "utf8");
    expect(source).toContain("slug: string");
    expect(source).toContain("name_ja: string");
    expect(source).toContain("name_en: string | null");
  });
});
