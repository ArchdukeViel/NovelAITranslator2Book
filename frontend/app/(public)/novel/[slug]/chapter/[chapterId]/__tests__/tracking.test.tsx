import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ChapterPage from "../page";

const mocks = vi.hoisted(() => ({
  updateProgressMutate: vi.fn(),
  recordHistoryMutate: vi.fn(),
  usePublicAuthMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ slug: "demo", chapterId: "7" }),
}));

vi.mock("@/components/public/reader-controls", () => ({
  ReaderControls: () => <div />,
}));

vi.mock("@/lib/reader-prefs", () => ({
  useReaderPrefsStore: () => ({
    theme: "light",
    fontSize: 18,
    width: "standard",
  }),
}));

vi.mock("@/hooks/public", () => ({
  useChapter: () => ({
    data: {
      novel_id: "demo",
      chapter_id: "7",
      novel_title: "Demo",
      title: "Chapter Seven",
      text: "Chapter text",
      previous_chapter_id: null,
      next_chapter_id: null,
    },
    isPending: false,
    isError: false,
    error: null,
  }),
  usePublicAuth: () => mocks.usePublicAuthMock(),
  useRecordHistory: () => ({ mutate: mocks.recordHistoryMutate }),
  useUpdateProgress: () => ({ mutate: mocks.updateProgressMutate }),
}));

beforeEach(() => {
  mocks.updateProgressMutate.mockClear();
  mocks.recordHistoryMutate.mockClear();
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
