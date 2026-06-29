/**
 * Chapter reader page honesty and UX tests.
 *
 * Confirms the /novels/[slug]/chapter/[chapterId] page renders real API data
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
    chapter_number: 7,
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
    const backLink = document.querySelector('a[href="/novels/demo"]');
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

  it("does not render internal translation protocol markers", () => {
    mocks.useChapterMock.mockReturnValue({
      data: makeChapterData({
        text: "[CHAPTER 7]\n[P p0001] First translated paragraph.\n\n[P p0002]\nSecond translated paragraph.",
      }),
      isPending: false,
      isError: false,
      error: null,
    });

    const { container } = renderPage();
    const body = document.body.textContent ?? "";
    expect(body).not.toContain("[CHAPTER 7]");
    expect(body).not.toContain("[P p0001]");
    expect(body).not.toContain("[P p0002]");
    expect(body).toContain("First translated paragraph.");
    expect(body).toContain("Second translated paragraph.");
    const paragraphs = Array.from(container.querySelectorAll(".reader-source-paragraph"));
    expect(paragraphs.map((paragraph) => paragraph.textContent)).toEqual([
      "First translated paragraph.",
      "Second translated paragraph.",
    ]);
  });

  it("joins consecutive API reader line blocks into one English paragraph", () => {
    mocks.useChapterMock.mockReturnValue({
      data: makeChapterData({
        text: "Fallback text should not drive block rendering.",
        reader_blocks: [
          { type: "line", text: "Narration line." },
          { type: "line", text: "Short narration line." },
          { type: "line", text: "Another source unit." },
        ],
      }),
      isPending: false,
      isError: false,
      error: null,
    });

    const { container } = renderPage();
    const paragraphs = Array.from(container.querySelectorAll(".reader-source-paragraph"));
    expect(paragraphs).toHaveLength(1);
    expect(paragraphs.map((paragraph) => paragraph.textContent)).toEqual([
      "Narration line. Short narration line. Another source unit.",
    ]);
    expect(paragraphs[0]).toHaveClass("reader-source-paragraph--narration");
    expect(container.querySelector(".reader-source-line")).toBeNull();
    expect(container.querySelector(".reader-source-break")).toBeNull();
  });

  it("renders dialogue lines as standalone left-aligned paragraphs", () => {
    mocks.useChapterMock.mockReturnValue({
      data: makeChapterData({
        text: "Fallback text should not drive block rendering.",
        reader_blocks: [
          { type: "line", text: "\"Ugh... I'm so thirsty...\"" },
          { type: "break" },
          { type: "line", text: "Several days had passed since I became a sapling." },
          { type: "line", text: "Since there had been no rain and the scorching heat continued." },
          { type: "line", text: "I was in an uninhabited forest." },
          { type: "break" },
          { type: "line", text: "「I wonder if that boy will come back to water me.」" },
          { type: "break" },
          { type: "line", text: "Still, having him build me a fence was more than enough." },
          { type: "line", text: "It would be unreasonable to expect that much from the boy." },
        ],
      }),
      isPending: false,
      isError: false,
      error: null,
    });

    const { container } = renderPage();
    const paragraphs = Array.from(container.querySelectorAll(".reader-source-paragraph"));
    expect(paragraphs.map((paragraph) => paragraph.textContent)).toEqual([
      "\"Ugh... I'm so thirsty...\"",
      "Several days had passed since I became a sapling. Since there had been no rain and the scorching heat continued. I was in an uninhabited forest.",
      "「I wonder if that boy will come back to water me.」",
      "Still, having him build me a fence was more than enough. It would be unreasonable to expect that much from the boy.",
    ]);
    expect(paragraphs[0]).toHaveClass("reader-source-paragraph--dialogue");
    expect(paragraphs[1]).toHaveClass("reader-source-paragraph--narration");
    expect(paragraphs[2]).toHaveClass("reader-source-paragraph--dialogue");
    expect(paragraphs[3]).toHaveClass("reader-source-paragraph--narration");
  });

  it("renders API reader break blocks as paragraph separation", () => {
    mocks.useChapterMock.mockReturnValue({
      data: makeChapterData({
        text: "Fallback text should not drive block rendering.",
        reader_blocks: [
          { type: "line", text: "First group line." },
          { type: "line", text: "Still first group." },
          { type: "break" },
          { type: "line", text: "Second group line." },
        ],
      }),
      isPending: false,
      isError: false,
      error: null,
    });

    const { container } = renderPage();
    const children = Array.from(container.querySelector(".reader-text")?.children ?? []);
    expect(children).toHaveLength(2);
    expect(children[0]).toHaveClass("reader-source-paragraph");
    expect(children[1]).toHaveClass("reader-source-paragraph");
    expect(container.querySelector(".reader-source-break")).toBeNull();
    const paragraphs = Array.from(container.querySelectorAll(".reader-source-paragraph"));
    expect(paragraphs.map((paragraph) => paragraph.textContent)).toEqual([
      "First group line. Still first group.",
      "Second group line.",
    ]);
    expect(paragraphs[0]).toHaveClass("reader-source-paragraph--narration");
    expect(paragraphs[1]).toHaveClass("reader-source-paragraph--narration");
  });

  it("collapses repeated API reader breaks without noisy empty groups", () => {
    mocks.useChapterMock.mockReturnValue({
      data: makeChapterData({
        text: "Fallback text should not drive block rendering.",
        reader_blocks: [
          { type: "break" },
          { type: "line", text: "First group." },
          { type: "break" },
          { type: "break" },
          { type: "line", text: "Second group." },
          { type: "break" },
        ],
      }),
      isPending: false,
      isError: false,
      error: null,
    });

    const { container } = renderPage();
    const paragraphs = Array.from(container.querySelectorAll(".reader-source-paragraph"));
    expect(paragraphs).toHaveLength(2);
    expect(paragraphs.map((paragraph) => paragraph.textContent)).toEqual([
      "First group.",
      "Second group.",
    ]);
    expect(container.querySelector(".reader-source-break")).toBeNull();
  });

  it("falls back to splitting clean text blocks when reader_blocks is absent", () => {
    mocks.useChapterMock.mockReturnValue({
      data: makeChapterData({
        text: "First display block.\nStill first block.\n\nSecond display block.",
      }),
      isPending: false,
      isError: false,
      error: null,
    });

    const { container } = renderPage();
    const paragraphs = Array.from(container.querySelectorAll(".reader-source-paragraph"));
    expect(paragraphs).toHaveLength(2);
    expect(paragraphs.map((paragraph) => paragraph.textContent)).toEqual([
      "First display block. Still first block.",
      "Second display block.",
    ]);
    expect(container.querySelector(".reader-source-break")).toBeNull();
  });

  it("renders novel title from API data", () => {
    renderPage();
    const body = document.body.textContent ?? "";
    expect(body).toContain("Demo Novel");
  });

  it("handles null chapter title by falling back to chapter_number", () => {
    mocks.useChapterMock.mockReturnValue({
      data: makeChapterData({ title: null, chapter_number: 5 }),
      isPending: false,
      isError: false,
      error: null,
    });
    renderPage();
    const h1 = document.querySelector("h1");
    expect(h1?.textContent).toContain("Chapter 5");
  });

  it("handles null title and null chapter_number with neutral fallback", () => {
    mocks.useChapterMock.mockReturnValue({
      data: makeChapterData({ title: null, chapter_number: null }),
      isPending: false,
      isError: false,
      error: null,
    });
    renderPage();
    const h1 = document.querySelector("h1");
    expect(h1?.textContent).toContain("Untitled chapter");
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

  it("renders chapter_number in the header subtitle", () => {
    mocks.useChapterMock.mockReturnValue({
      data: makeChapterData({ chapter_number: 7 }),
      isPending: false,
      isError: false,
      error: null,
    });
    renderPage();
    const body = document.body.textContent ?? "";
    expect(body).toContain("Chapter 7");
  });

  it("does not display raw chapter UUID as primary label", () => {
    // The mock chapterId is "7" — with chapter_number available,
    // the visible label should be "Chapter 7" not the raw ID.
    renderPage();
    const body = document.body.textContent ?? "";
    // "Chapter 7" is fine; check no raw longer UUID pattern appears as chapter label
    const subtitleElement = document.querySelector(".reader-muted ~ .reader-chrome p");
    // The subtitle paragraph should use chapter_number, not UUID
    const chromeParagraphs = document.querySelectorAll(".reader-chrome p");
    for (const p of chromeParagraphs) {
      const text = p.textContent ?? "";
      // Should not contain anything that looks like a UUID
      expect(text).not.toMatch(
        /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i
      );
    }
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

  it("shows unavailable next state without an active next href", () => {
    mocks.useChapterMock.mockReturnValue({
      data: makeChapterData({
        previous_chapter_id: "6",
        next_chapter_id: null,
        next_chapter_unavailable: true,
      }),
      isPending: false,
      isError: false,
      error: null,
    });

    const { container } = renderPage();
    expect(container.querySelectorAll('a[href*="/chapter/6"]').length).toBeGreaterThanOrEqual(1);
    expect(container.querySelectorAll('a[href*="/chapter/8"]').length).toBe(0);
    expect(container.textContent).toContain("Next unavailable");
  });

  it("All chapters link goes to novel detail page", () => {
    renderPage();
    const allChaptersLinks = document.querySelectorAll('a[href="/novels/demo"]');
    expect(allChaptersLinks.length).toBeGreaterThanOrEqual(2);
  });

  it("Back to Novel link goes to correct novel", () => {
    renderPage();
    const backLink = document.querySelector('a[href="/novels/demo"]');
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
