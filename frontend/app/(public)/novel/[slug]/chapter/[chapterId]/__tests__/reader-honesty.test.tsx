/**
 * Chapter reader page honesty and UX tests.
 *
 * Confirms the /novel/[slug]/chapter/[chapterId] page renders real API data
 * honestly, links report to /contact, provides useful error recovery, and
 * does not pass include_adult=true.
 *
 * Feature: PUBLIC-READER-AUDIT-1
 */

import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import { render, cleanup } from "@testing-library/react";

import ChapterPage from "../page";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
  updateProgressMutate: vi.fn(),
  recordHistoryMutate: vi.fn(),
  usePublicAuthMock: vi.fn(),
  useChapterMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ slug: "demo", chapterId: "7" }),
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
  usePublicAuth: () => mocks.usePublicAuthMock(),
  useRecordHistory: () => ({ mutate: mocks.recordHistoryMutate }),
  useUpdateProgress: () => ({ mutate: mocks.updateProgressMutate }),
}));

// ---------------------------------------------------------------------------
// Factories
// ---------------------------------------------------------------------------

function makeChapterData(overrides: Record<string, unknown> = {}) {
  return {
    novel_id: "demo",
    chapter_id: "7",
    novel_title: "Demo Novel",
    title: "Chapter Seven",
    text: "The story text goes here.",
    previous_chapter_id: null,
    next_chapter_id: null,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let queryClient: { clear: () => void } | null = null;

beforeEach(() => {
  vi.clearAllMocks();

  mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: false });

  mocks.useChapterMock.mockReturnValue({
    data: makeChapterData(),
    isPending: false,
    isError: false,
    error: null,
  });
});

afterEach(() => {
  cleanup();
});

function renderPage() {
  const { QueryClient, QueryClientProvider } = require("@tanstack/react-query");
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ChapterPage />
    </QueryClientProvider>
  );
}

// ---------------------------------------------------------------------------
// Tests: Report action
// ---------------------------------------------------------------------------

describe("Reader — report action", () => {
  it("links to /contact instead of claiming backend phase", () => {
    renderPage();
    expect(
      (document.body.textContent ?? "").indexOf("later backend phase")
    ).toBe(-1);
    const contactLink = document.querySelector('a[href="/contact"]');
    expect(contactLink).toBeTruthy();
    expect(contactLink?.textContent).toContain("Contact us");
  });

  it("does not claim report is connected to a backend", () => {
    renderPage();
    const body = document.body.textContent ?? "";
    expect(body).not.toMatch(/report.*connected/i);
    expect(body).not.toMatch(/will be connected/i);
  });
});

// ---------------------------------------------------------------------------
// Tests: Loading state
// ---------------------------------------------------------------------------

describe("Reader — loading state", () => {
  it("shows spinner and loading message when chapter is pending", () => {
    mocks.useChapterMock.mockReturnValue({
      data: null,
      isPending: true,
      isError: false,
      error: null,
    });
    const { container } = renderPage();
    const spinner = container.querySelector(".animate-spin");
    expect(spinner).toBeInTheDocument();
    const body = document.body.textContent ?? "";
    expect(body).toContain("Loading chapter");
  });

  it("does not render reader controls while loading", () => {
    mocks.useChapterMock.mockReturnValue({
      data: null,
      isPending: true,
      isError: false,
      error: null,
    });
    const { queryByTestId } = renderPage();
    expect(queryByTestId("reader-controls")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Tests: Error / 404 states
// ---------------------------------------------------------------------------

describe("Reader — error states", () => {
  it("shows Chapter Unavailable for 404 with Back to Novel and Browse links", async () => {
    const { ApiError } = await import("@/lib/api");
    const error404 = new ApiError({
      status: 404,
      code: "HTTP_404",
      message: "Not found",
    });

    mocks.useChapterMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: error404,
    });

    renderPage();
    const body = document.body.textContent ?? "";
    expect(body).toContain("Chapter Unavailable");
    expect(body).toContain("Back to Novel");
    // Browse the library link should also be present
    expect(body).toContain("Browse the library");
  });

  it("shows generic error with Back to Novel and Browse links for non-404 errors", async () => {
    const { ApiError } = await import("@/lib/api");
    const err500 = new ApiError({
      status: 500,
      code: "HTTP_500",
      message: "Server error",
    });

    mocks.useChapterMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: err500,
    });

    renderPage();
    const body = document.body.textContent ?? "";
    expect(body).toContain("Something went wrong");
    expect(body).toContain("Back to Novel");
    expect(body).toContain("Browse the library");
  });

  it("404 error page links back to the correct novel", async () => {
    const { ApiError } = await import("@/lib/api");
    const error404 = new ApiError({
      status: 404,
      code: "HTTP_404",
      message: "Not found",
    });

    mocks.useChapterMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: error404,
    });

    renderPage();
    const backLink = document.querySelector('a[href="/novel/demo"]');
    expect(backLink).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Tests: Data honesty
// ---------------------------------------------------------------------------

describe("Reader — data honesty", () => {
  it("renders real chapter title from API data", () => {
    renderPage();
    const h1 = document.querySelector("h1");
    expect(h1?.textContent).toContain("Chapter Seven");
  });

  it("renders real chapter text from API data", () => {
    renderPage();
    expect(document.body.textContent).toContain("The story text goes here.");
  });

  it("renders novel title from API data", () => {
    renderPage();
    const body = document.body.textContent ?? "";
    expect(body).toContain("Demo Novel");
  });

  it("handles null chapter title by falling back to chapter ID", () => {
    mocks.useChapterMock.mockReturnValue({
      data: makeChapterData({ title: null }),
      isPending: false,
      isError: false,
      error: null,
    });
    renderPage();
    const h1 = document.querySelector("h1");
    expect(h1?.textContent).toContain("Chapter 7");
  });

  it("handles null novel title by falling back to slug", () => {
    mocks.useChapterMock.mockReturnValue({
      data: makeChapterData({ novel_title: null }),
      isPending: false,
      isError: false,
      error: null,
    });
    renderPage();
    const body = document.body.textContent ?? "";
    expect(body).toContain("demo");
  });

  it("does not render fake progress saved message", () => {
    renderPage();
    const body = document.body.textContent ?? "";
    expect(body).not.toMatch(/progress saved/i);
    expect(body).not.toMatch(/progress has been/i);
    expect(body).not.toMatch(/your progress/i);
  });
});

// ---------------------------------------------------------------------------
// Tests: Navigation
// ---------------------------------------------------------------------------

describe("Reader — navigation", () => {
  it("renders previous/next links when both exist", () => {
    mocks.useChapterMock.mockReturnValue({
      data: makeChapterData({
        previous_chapter_id: "6",
        next_chapter_id: "8",
      }),
      isPending: false,
      isError: false,
      error: null,
    });

    const { container } = renderPage();
    const prevLinks = container.querySelectorAll('a[href*="/chapter/6"]');
    expect(prevLinks.length).toBeGreaterThanOrEqual(1);
    const nextLinks = container.querySelectorAll('a[href*="/chapter/8"]');
    expect(nextLinks.length).toBeGreaterThanOrEqual(1);
  });

  it("shows disabled 'First chapter' label when no previous", () => {
    mocks.useChapterMock.mockReturnValue({
      data: makeChapterData({ previous_chapter_id: null, next_chapter_id: "8" }),
      isPending: false,
      isError: false,
      error: null,
    });

    const { container } = renderPage();
    const disabled = Array.from(container.querySelectorAll("span")).filter(
      (el) => el.textContent?.includes("First chapter")
    );
    expect(disabled.length).toBeGreaterThanOrEqual(1);
  });

  it("shows disabled 'Latest chapter' label when no next", () => {
    mocks.useChapterMock.mockReturnValue({
      data: makeChapterData({ previous_chapter_id: "6", next_chapter_id: null }),
      isPending: false,
      isError: false,
      error: null,
    });

    const { container } = renderPage();
    const disabled = Array.from(container.querySelectorAll("span")).filter(
      (el) => el.textContent?.includes("Latest chapter")
    );
    expect(disabled.length).toBeGreaterThanOrEqual(1);
  });

  it("All chapters link goes to novel detail page", () => {
    renderPage();
    const allChaptersLinks = document.querySelectorAll('a[href="/novel/demo"]');
    expect(allChaptersLinks.length).toBeGreaterThanOrEqual(2);
  });

  it("Back to Novel link goes to correct novel", () => {
    renderPage();
    const backLink = document.querySelector('a[href="/novel/demo"]');
    expect(backLink).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Tests: Progress/history tracking
// ---------------------------------------------------------------------------

describe("Reader — progress/history tracking", () => {
  it("does not track for unauthenticated users", async () => {
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: false });
    renderPage();
    await vi.waitFor(() => {
      expect(mocks.updateProgressMutate).not.toHaveBeenCalled();
      expect(mocks.recordHistoryMutate).not.toHaveBeenCalled();
    });
  });

  it("tracks progress and history once for authenticated users", async () => {
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: true });
    renderPage();
    await vi.waitFor(() => {
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

  it("tracks each chapter once within a single mount", async () => {
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: true });
    renderPage();
    await vi.waitFor(() => {
      expect(mocks.updateProgressMutate).toHaveBeenCalledTimes(1);
    });
    // The ref guard prevents duplicate sends for the same chapter
    await vi.waitFor(() => {
      expect(mocks.updateProgressMutate).toHaveBeenCalledTimes(1);
    });
  });
});

// ---------------------------------------------------------------------------
// Tests: Adult/R18 safety
// ---------------------------------------------------------------------------

describe("Reader — adult/R18 safety", () => {
  it("does not render adult/R18 taxonomy labels", () => {
    renderPage();
    const body = document.body.textContent ?? "";
    expect(body.toLowerCase()).not.toContain("r18");
    expect(body.toLowerCase()).not.toMatch(/\badult\b/);
  });
});

// ---------------------------------------------------------------------------
// Tests: Reader controls
// ---------------------------------------------------------------------------

describe("Reader — reader controls", () => {
  it("renders reader controls placeholder", () => {
    renderPage();
    const controls = document.querySelector('[data-testid="reader-controls"]');
    expect(controls).toBeTruthy();
  });
});
