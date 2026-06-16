import { describe, it, expect, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { NovelCard } from "@/components/public/novel-card";
import type { PublicNovelSummary } from "@/lib/public-types";

let queryClient: QueryClient;

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
});

afterEach(() => cleanup());

function renderWithClient(ui: React.ReactElement) {
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

function makeNovel(
  overrides: Partial<PublicNovelSummary> = {}
): PublicNovelSummary & {
  cover_url?: string | null;
  source?: string | null;
  source_title?: string | null;
  synopsis?: string | null;
} {
  return {
    novel_id: "test-novel",
    slug: "test-novel",
    title: "Test Novel",
    author: "Test Author",
    language: "ja",
    status: "Ongoing",
    chapter_count: 10,
    translated_count: 5,
    added_at: null,
    ...overrides,
  };
}

describe("NovelCard genre/tag rendering", () => {
  it("renders genre chips when genres are provided", () => {
    const novel = makeNovel({ genres: ["fantasy", "isekai-tensei"] });
    renderWithClient(<NovelCard novel={novel} />);

    expect(screen.getByText("fantasy")).toBeInTheDocument();
    expect(screen.getByText("isekai-tensei")).toBeInTheDocument();
  });

  it("renders tag chips when tags are provided", () => {
    const novel = makeNovel({ tags: ["\u9b54\u6cd5", "\u52c7\u8005"] });
    renderWithClient(<NovelCard novel={novel} />);

    expect(screen.getByText("\u9b54\u6cd5")).toBeInTheDocument();
    expect(screen.getByText("\u52c7\u8005")).toBeInTheDocument();
  });

  it("renders both genres and tags together", () => {
    const novel = makeNovel({
      genres: ["fantasy"],
      tags: ["magic"],
    });
    renderWithClient(<NovelCard novel={novel} />);

    expect(screen.getByText("fantasy")).toBeInTheDocument();
    expect(screen.getByText("magic")).toBeInTheDocument();
  });

  it("renders no taxonomy section when genres and tags are empty arrays", () => {
    const novel = makeNovel({ genres: [], tags: [] });
    renderWithClient(<NovelCard novel={novel} />);

    const spans = screen.queryAllByText(/fantasy|magic|isekai|romance/);
    expect(spans.length).toBe(0);
  });

  it("renders no taxonomy section when genres and tags are undefined", () => {
    const novel = makeNovel();
    renderWithClient(<NovelCard novel={novel} />);

    const spans = screen.queryAllByText(/fantasy|magic|isekai/);
    expect(spans.length).toBe(0);
  });

  it("limits genres to 3 visible chips with +N overflow indicator", () => {
    const novel = makeNovel({
      genres: ["fantasy", "isekai", "romance", "sf", "horror"],
    });
    renderWithClient(<NovelCard novel={novel} />);

    expect(screen.getByText("fantasy")).toBeInTheDocument();
    expect(screen.getByText("isekai")).toBeInTheDocument();
    expect(screen.getByText("romance")).toBeInTheDocument();
    expect(screen.queryByText("sf")).not.toBeInTheDocument();
    expect(screen.queryByText("horror")).not.toBeInTheDocument();
    expect(screen.getByText("+2")).toBeInTheDocument();
  });

  it("limits tags to 2 visible chips with +N overflow indicator", () => {
    const novel = makeNovel({
      tags: ["magic", "hero", "dragon", "castle"],
    });
    renderWithClient(<NovelCard novel={novel} />);

    expect(screen.getByText("magic")).toBeInTheDocument();
    expect(screen.getByText("hero")).toBeInTheDocument();
    expect(screen.queryByText("dragon")).not.toBeInTheDocument();
    expect(screen.queryByText("castle")).not.toBeInTheDocument();
    expect(screen.getByText("+2")).toBeInTheDocument();
  });

  it("shows no overflow indicator when genres fit within limit", () => {
    const novel = makeNovel({ genres: ["fantasy", "romance"] });
    renderWithClient(<NovelCard novel={novel} />);

    expect(screen.getByText("fantasy")).toBeInTheDocument();
    expect(screen.getByText("romance")).toBeInTheDocument();
    expect(screen.queryByText(/\+\d+/)).not.toBeInTheDocument();
  });

  it("shows no overflow indicator when tags fit within limit", () => {
    const novel = makeNovel({ tags: ["magic"] });
    renderWithClient(<NovelCard novel={novel} />);

    expect(screen.getByText("magic")).toBeInTheDocument();
    expect(screen.queryByText(/\+\d+/)).not.toBeInTheDocument();
  });

  it("renders genre chips as non-interactive spans", () => {
    const novel = makeNovel({ genres: ["fantasy"] });
    renderWithClient(<NovelCard novel={novel} />);

    const chip = screen.getByText("fantasy");
    expect(chip.tagName).toBe("SPAN");
    expect(chip.getAttribute("role")).not.toBe("button");
    expect(chip.getAttribute("tabindex")).toBeNull();
  });

  it("renders tag chips as non-interactive spans", () => {
    const novel = makeNovel({ tags: ["magic"] });
    renderWithClient(<NovelCard novel={novel} />);

    const chip = screen.getByText("magic");
    expect(chip.tagName).toBe("SPAN");
    expect(chip.getAttribute("role")).not.toBe("button");
    expect(chip.getAttribute("tabindex")).toBeNull();
  });
});
