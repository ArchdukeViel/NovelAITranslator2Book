import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ChapterPage from "../page";

const mocks = vi.hoisted(() => ({
  prefetchMock: vi.fn(),
  usePublicAuthMock: vi.fn(),
  useChapterMock: vi.fn(),
  useProgressMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ slug: "demo", chapterId: "7" }),
  useRouter: () => ({
    push: vi.fn(),
    prefetch: mocks.prefetchMock,
  }),
}));

vi.mock("@/components/public/reader-controls", () => ({
  ReaderControls: () => <div data-testid="reader-controls" />,
}));

vi.mock("@/lib/reader-prefs", () => ({
  useReaderPrefsStore: () => ({
    theme: "light",
    fontSize: 18,
    width: "standard",
  }),
}));

vi.mock("lucide-react", () => ({
  ArrowLeft: () => <span data-testid="icon-arrow-left" />,
  BookOpen: () => <span data-testid="icon-book-open" />,
  Minus: () => <span data-testid="icon-minus" />,
  Plus: () => <span data-testid="icon-plus" />,
  RotateCcw: () => <span data-testid="icon-reset" />,
  Flag: () => <span data-testid="icon-flag" />,
}));

vi.mock("@/hooks/public", () => ({
  useChapter: () => mocks.useChapterMock(),
  useProgress: () => mocks.useProgressMock(),
  usePublicAuth: () => mocks.usePublicAuthMock(),
  useRecordHistory: () => ({ mutate: vi.fn() }),
  useUpdateProgress: () => ({ mutate: vi.fn() }),
}));

function makeChapterData(overrides: Record<string, unknown> = {}) {
  return {
    novel_id: "demo",
    chapter_id: "7",
    novel_title: "Demo Novel",
    title: "Chapter Seven",
    text: "Chapter body content",
    previous_chapter_id: "6",
    next_chapter_id: "8",
    slug: "demo",
    ...overrides,
  };
}

describe("Reader next-chapter scroll prefetching contract", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    mocks.prefetchMock.mockClear();
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: false });
    mocks.useProgressMock.mockReturnValue({ data: null, isLoading: false });
    mocks.useChapterMock.mockReturnValue({
      data: makeChapterData(),
      isLoading: false,
      isError: false,
    });

    Object.defineProperty(document.documentElement, "scrollHeight", {
      configurable: true,
      value: 1000,
    });
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 200,
    });
    Object.defineProperty(window, "scrollY", {
      configurable: true,
      value: 0,
      writable: true,
    });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("does not prefetch when scroll progress is below 70%", async () => {
    const prefetchSpy = vi.spyOn(queryClient, "prefetchQuery");

    render(
      <QueryClientProvider client={queryClient}>
        <ChapterPage />
      </QueryClientProvider>
    );

    // Scroll to 50% (maximum scroll = 1000 - 200 = 800; 50% = 400)
    window.scrollY = 400;
    fireEvent.scroll(window);

    expect(prefetchSpy).not.toHaveBeenCalled();
    expect(mocks.prefetchMock).not.toHaveBeenCalled();
  });

  it("triggers queryClient.prefetchQuery and router.prefetch when scroll progress reaches 70%", async () => {
    const prefetchSpy = vi.spyOn(queryClient, "prefetchQuery").mockResolvedValue(undefined);

    render(
      <QueryClientProvider client={queryClient}>
        <ChapterPage />
      </QueryClientProvider>
    );

    // Scroll to 75% (800 * 0.75 = 600)
    window.scrollY = 600;
    fireEvent.scroll(window);

    await waitFor(() => {
      expect(prefetchSpy).toHaveBeenCalledTimes(1);
    });

    expect(prefetchSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ["public", "chapter", "demo", "8"],
      })
    );
    expect(mocks.prefetchMock).toHaveBeenCalledWith("/novels/demo/chapter/8");
  });

  it("does not trigger prefetch if there is no next_chapter_id", async () => {
    mocks.useChapterMock.mockReturnValue({
      data: makeChapterData({ next_chapter_id: null }),
      isLoading: false,
      isError: false,
    });

    const prefetchSpy = vi.spyOn(queryClient, "prefetchQuery");

    render(
      <QueryClientProvider client={queryClient}>
        <ChapterPage />
      </QueryClientProvider>
    );

    // Scroll to 90% (800 * 0.9 = 720)
    window.scrollY = 720;
    fireEvent.scroll(window);

    expect(prefetchSpy).not.toHaveBeenCalled();
    expect(mocks.prefetchMock).not.toHaveBeenCalled();
  });
});
