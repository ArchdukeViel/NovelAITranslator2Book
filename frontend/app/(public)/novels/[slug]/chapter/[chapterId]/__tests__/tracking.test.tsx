import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ChapterPage from "../page";

const mocks = vi.hoisted(() => ({
  updateProgressMutate: vi.fn(),
  recordHistoryMutate: vi.fn(),
  usePublicAuthMock: vi.fn(),
  useChapterMock: vi.fn(),
  useProgressMock: vi.fn(),
  pushMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ slug: "demo", chapterId: "7" }),
  useRouter: () => ({ push: mocks.pushMock }),
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

// Mock lucide-react icons to simple spans (avoid SVG rendering noise)
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
  useRecordHistory: () => ({ mutate: mocks.recordHistoryMutate }),
  useUpdateProgress: () => ({ mutate: mocks.updateProgressMutate }),
}));

// Chapter data factory
function makeChapterData(overrides: Record<string, unknown> = {}) {
  return {
    novel_id: "demo",
    chapter_id: "7",
    novel_title: "Demo Novel",
    title: "Chapter Seven",
    text: "Chapter text",
    previous_chapter_id: null,
    next_chapter_id: null,
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

beforeEach(() => {
  localStorage.clear();
  Object.defineProperty(window, "scrollY", { configurable: true, value: 0 });
  mocks.updateProgressMutate.mockClear();
  mocks.recordHistoryMutate.mockClear();
  mocks.useChapterMock.mockReturnValue({
    data: makeChapterData(),
    isPending: false,
    isError: false,
    error: null,
  });
  mocks.useProgressMock.mockReturnValue({ data: undefined, isPending: false, isError: false, error: null });
});

describe("reader progress and history tracking", () => {
  it("does not record progress or history for guests", async () => {
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: false });

    render(<ChapterPage />);

    await waitFor(() => {
      expect(mocks.updateProgressMutate).not.toHaveBeenCalled();
      expect(mocks.recordHistoryMutate).not.toHaveBeenCalled();
    });
  });

  it("restores guest progress from local storage", async () => {
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: false });
    localStorage.setItem("reader-position:demo:7", "50");
    Object.defineProperty(document.documentElement, "scrollHeight", { configurable: true, value: 1200 });
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 200 });
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);

    render(<ChapterPage />);

    await waitFor(() => expect(scrollTo).toHaveBeenCalledWith(0, 500));
  });

  it("restores signed-in account progress", async () => {
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: true });
    mocks.useProgressMock.mockReturnValue({ data: { chapter_id: "7", progress_percent: 25 }, isPending: false, isError: false, error: null });
    Object.defineProperty(document.documentElement, "scrollHeight", { configurable: true, value: 1200 });
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 200 });
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);

    render(<ChapterPage />);

    await waitFor(() => expect(scrollTo).toHaveBeenCalledWith(0, 250));
  });

  it("updates the visible progress bar while scrolling", async () => {
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: false });
    Object.defineProperty(document.documentElement, "scrollHeight", { configurable: true, value: 1200 });
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 200 });
    Object.defineProperty(window, "scrollY", { configurable: true, value: 400 });
    render(<ChapterPage />);

    fireEvent.scroll(window);

    await waitFor(() => expect(screen.getByRole("progressbar", { name: "Reading progress" })).toHaveAttribute("aria-valuenow", "40"));
    expect(localStorage.getItem("reader-position:demo:7")).toBe("40");
  });

  it("records progress and history once for authenticated users", async () => {
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: true });

    render(<ChapterPage />);

    await waitFor(() => {
      expect(mocks.updateProgressMutate).toHaveBeenCalledWith({
        chapter_id: "7",
        progress_percent: 0,
      });
      expect(mocks.recordHistoryMutate).toHaveBeenCalledWith({
        slug: "demo",
        chapter_id: "7",
      });
    });
  });
});

describe("reader navigation", () => {
  it("uses arrow-key navigation outside text inputs", () => {
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: false });
    mocks.useChapterMock.mockReturnValue({ data: makeChapterData({ previous_chapter_id: "6", next_chapter_id: "8" }), isPending: false, isError: false, error: null });
    render(<ChapterPage />);
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(mocks.pushMock).toHaveBeenCalledWith("/novels/demo/chapter/8");
  });
  it("renders previous and next links when IDs exist", () => {
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: false });
    mocks.useChapterMock.mockReturnValue({
      data: makeChapterData({
        previous_chapter_id: "6",
        next_chapter_id: "8",
      }),
      isPending: false,
      isError: false,
      error: null,
    });

    const { container } = render(<ChapterPage />);

    // Should have two navigation blocks (top + bottom)
    const navBlocks = container.querySelectorAll("nav");
    expect(navBlocks.length).toBeGreaterThanOrEqual(2);

    // Previous link
    const prevLinks = container.querySelectorAll("a[href*='/chapter/6']");
    expect(prevLinks.length).toBeGreaterThanOrEqual(1);

    // Next link
    const nextLinks = container.querySelectorAll("a[href*='/chapter/8']");
    expect(nextLinks.length).toBeGreaterThanOrEqual(1);

    // All chapters link
    const allChaptersLinks = container.querySelectorAll("a[href='/novels/demo']");
    expect(allChaptersLinks.length).toBeGreaterThanOrEqual(2);
  });

  it("renders disabled state labels when first chapter (no previous)", () => {
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: false });
    mocks.useChapterMock.mockReturnValue({
      data: makeChapterData({
        previous_chapter_id: null,
        next_chapter_id: "8",
      }),
      isPending: false,
      isError: false,
      error: null,
    });

    const { container } = render(<ChapterPage />);

    // "First chapter" disabled label appears
    const disabledLabels = container.querySelectorAll("span");
    const firstChapterLabels = Array.from(disabledLabels).filter(
      (el) => el.textContent?.includes("First chapter")
    );
    expect(firstChapterLabels.length).toBeGreaterThanOrEqual(1);
  });

  it("renders disabled state labels when latest chapter (no next)", () => {
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: false });
    mocks.useChapterMock.mockReturnValue({
      data: makeChapterData({
        previous_chapter_id: "6",
        next_chapter_id: null,
      }),
      isPending: false,
      isError: false,
      error: null,
    });

    const { container } = render(<ChapterPage />);

    // "Latest chapter" disabled label appears
    const disabledLabels = container.querySelectorAll("span");
    const latestChapterLabels = Array.from(disabledLabels).filter(
      (el) => el.textContent?.includes("Latest chapter")
    );
    expect(latestChapterLabels.length).toBeGreaterThanOrEqual(1);
  });
});

describe("reader controls and layout", () => {
  it("renders reader controls", () => {
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: false });

    const { getByTestId } = render(<ChapterPage />);
    expect(getByTestId("reader-controls")).toBeInTheDocument();
  });

  it("shows novel title in breadcrumb", () => {
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: false });

    const { container } = render(<ChapterPage />);

    // Novel title appears in breadcrumb link
    const breadcrumbLinks = container.querySelectorAll("a[href='/novels/demo']");
    const hasNovelTitle = Array.from(breadcrumbLinks).some(
      (el) => el.textContent?.includes("Demo Novel")
    );
    expect(hasNovelTitle).toBe(true);
  });

  it("shows chapter title in header", () => {
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: false });

    const { container } = render(<ChapterPage />);

    const h1 = container.querySelector("h1");
    expect(h1?.textContent).toContain("Chapter Seven");
  });

  it("shows loading spinner when chapter is pending", () => {
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: false });
    mocks.useChapterMock.mockReturnValue({
      data: null,
      isPending: true,
      isError: false,
      error: null,
    });

    const { container } = render(<ChapterPage />);

    // Loading spinner (the spinning circle)
    const spinner = container.querySelector(".animate-spin");
    expect(spinner).toBeInTheDocument();
  });
});
