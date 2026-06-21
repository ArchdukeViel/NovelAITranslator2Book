import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import LibraryPage from "@/app/(admin)/admin/library/page";
import { LibraryRowActions } from "@/components/admin/library/library-row-actions";
import type { NovelSummary } from "@/lib/api-types";

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

function makeNovel(overrides: Partial<NovelSummary> = {}): NovelSummary {
  return {
    novel_id: "sample-novel",
    title: "Sample Novel",
    source: "syosetu_ncode",
    source_url: "https://example.com/sample",
    publication_status: "ongoing",
    chapter_count: 5,
    scraped_count: 5,
    translated_count: 1,
    is_published: false,
    latest_chapter_id: "1",
    latest_chapter_number: 1,
    latest_chapter_title: "Translated Chapter",
    ...overrides,
  };
}

const mockNovels = vi.hoisted(() => vi.fn());
const mockPublishNovel = vi.hoisted(() => vi.fn());
const mockUnpublishNovel = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    get api() {
      return {
        ...actual.api,
        novels: (...args: unknown[]) => mockNovels(...args),
        publishNovel: (...args: unknown[]) => mockPublishNovel(...args),
        unpublishNovel: (...args: unknown[]) => mockUnpublishNovel(...args),
      };
    },
  };
});

afterEach(() => {
  vi.restoreAllMocks();
  cleanup();
});

describe("Library publish controls", () => {
  it("shows Publish for unpublished translated novels", () => {
    const onPublish = vi.fn();

    render(
      <LibraryRowActions
        novel={makeNovel()}
        missingSource={false}
        pending={false}
        translationPending={false}
        onTranslate={() => {}}
        onRecrawl={() => {}}
        onDelete={() => {}}
        onEditTaxonomy={() => {}}
        onPublish={onPublish}
        onUnpublish={() => {}}
      />
    );

    expect(screen.getByText("Unpublished")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Publish" })).toBeEnabled();
    expect(screen.getByText("Latest: Ch. 1 Translated Chapter")).toBeInTheDocument();
  });

  it("shows Unpublish for published novels", () => {
    render(
      <LibraryRowActions
        novel={makeNovel({ is_published: true })}
        missingSource={false}
        pending={false}
        translationPending={false}
        onTranslate={() => {}}
        onRecrawl={() => {}}
        onDelete={() => {}}
        onEditTaxonomy={() => {}}
        onPublish={() => {}}
        onUnpublish={() => {}}
      />
    );

    expect(screen.getByText("Published")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Unpublish" })).toBeEnabled();
  });

  it("disables Publish when no translated chapters exist", () => {
    render(
      <LibraryRowActions
        novel={makeNovel({ translated_count: 0, latest_chapter_id: null, latest_chapter_title: null })}
        missingSource={false}
        pending={false}
        translationPending={false}
        onTranslate={() => {}}
        onRecrawl={() => {}}
        onDelete={() => {}}
        onEditTaxonomy={() => {}}
        onPublish={() => {}}
        onUnpublish={() => {}}
      />
    );

    expect(screen.getByRole("button", { name: "Publish" })).toBeDisabled();
    expect(screen.getByText("Translate at least one chapter before publishing.")).toBeInTheDocument();
  });

  it("updates the library row after successful publish", async () => {
    mockNovels.mockResolvedValue([makeNovel()]);
    mockPublishNovel.mockResolvedValue({
      novel_id: "sample-novel",
      title: "Sample Novel",
      is_published: true,
      chapter_count: 5,
      translated_count: 1,
      latest_chapter_id: "1",
      latest_chapter_number: 1,
      latest_chapter_title: "Translated Chapter",
      publication_status: "ongoing",
      visibility_warnings: [],
    });
    const user = userEvent.setup();

    renderWithQuery(<LibraryPage />);

    const publish = await screen.findByRole("button", { name: "Publish" });
    await user.click(publish);

    await waitFor(() => {
      expect(mockPublishNovel).toHaveBeenCalledWith("sample-novel");
      expect(screen.getByText("Published")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Unpublish" })).toBeInTheDocument();
  });

  it("shows a safe error when publish fails", async () => {
    mockNovels.mockResolvedValue([makeNovel()]);
    mockPublishNovel.mockRejectedValue(new Error("Cannot publish a novel without translated chapters."));
    const user = userEvent.setup();

    renderWithQuery(<LibraryPage />);

    const publish = await screen.findByRole("button", { name: "Publish" });
    await user.click(publish);

    expect(await screen.findByText("Cannot publish a novel without translated chapters.")).toBeInTheDocument();
  });

  it("updates the library row after successful unpublish", async () => {
    mockNovels.mockResolvedValue([makeNovel({ is_published: true })]);
    mockUnpublishNovel.mockResolvedValue({
      novel_id: "sample-novel",
      title: "Sample Novel",
      is_published: false,
      chapter_count: 5,
      translated_count: 1,
      latest_chapter_id: "1",
      latest_chapter_number: 1,
      latest_chapter_title: "Translated Chapter",
      publication_status: "ongoing",
      visibility_warnings: [],
    });
    const user = userEvent.setup();

    renderWithQuery(<LibraryPage />);

    const unpublish = await screen.findByRole("button", { name: "Unpublish" });
    await user.click(unpublish);

    await waitFor(() => {
      expect(mockUnpublishNovel).toHaveBeenCalledWith("sample-novel");
      expect(screen.getByText("Unpublished")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Publish" })).toBeInTheDocument();
  });

  it("shows adult visibility warning returned by publish response", async () => {
    mockNovels.mockResolvedValue([makeNovel()]);
    mockPublishNovel.mockResolvedValue({
      novel_id: "sample-novel",
      title: "Sample Novel",
      is_published: true,
      chapter_count: 5,
      translated_count: 1,
      publication_status: "ongoing",
      visibility_warnings: ["adult_hidden_by_default"],
    });
    const user = userEvent.setup();

    renderWithQuery(<LibraryPage />);

    await user.click(await screen.findByRole("button", { name: "Publish" }));

    expect(await screen.findByText("Published adult novels remain hidden from the default public catalog.")).toBeInTheDocument();
  });
});
