import { describe, it, expect, vi, beforeEach } from "vitest";
import { waitFor } from "@testing-library/react";
import { useNovel } from "@/hooks/public/use-novel";
import { useChapters } from "@/hooks/public/use-chapters";
import { useChapter } from "@/hooks/public/use-chapter";
import { publicApi } from "@/lib/public-api";
import { renderHookWithProviders } from "@/lib/test-utils";
import type {
  PublicNovelSummary,
  PublicChapterSummary,
  PublicChapterDetail,
} from "@/lib/public-types";

describe("Novel and Chapter Query Hooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("useNovel", () => {
    it("fetches novel metadata by slug", async () => {
      const mockNovel: PublicNovelSummary = {
        novel_id: "nov-123",
        slug: "overlord-test",
        title: "Overlord Test",
        source_title: null,
        author: "Maruyama",
        language: "ja",
        synopsis: "Skeleton king",
        publication_status: "completed",
        chapter_count: 50,
        translated_count: 50,
        genres: [],
        tags: [],
      };

      const spy = vi.spyOn(publicApi, "novel").mockResolvedValueOnce(mockNovel);

      const { result } = renderHookWithProviders(() =>
        useNovel("overlord-test"),
      );

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockNovel);
      expect(spy).toHaveBeenCalledWith(
        "overlord-test",
        expect.any(AbortSignal),
      );
    });

    it("does not fetch when slug is empty string", () => {
      const spy = vi.spyOn(publicApi, "novel");
      const { result } = renderHookWithProviders(() => useNovel(""));

      expect(result.current.fetchStatus).toBe("idle");
      expect(spy).not.toHaveBeenCalled();
    });
  });

  describe("useChapters", () => {
    it("fetches chapter list for novel slug", async () => {
      const mockChapters: PublicChapterSummary[] = [
        {
          chapter_id: "c1",
          chapter_number: 1,
          title: "Chapter 1",
          translated: true,
        },
      ];

      const spy = vi
        .spyOn(publicApi, "chapters")
        .mockResolvedValueOnce(mockChapters);

      const { result } = renderHookWithProviders(() =>
        useChapters("overlord-test"),
      );

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockChapters);
      expect(spy).toHaveBeenCalledWith(
        "overlord-test",
        expect.any(AbortSignal),
      );
    });
  });

  describe("useChapter", () => {
    it("fetches chapter detail by slug and chapterId", async () => {
      const mockDetail: PublicChapterDetail = {
        novel_id: "nov-123",
        chapter_id: "c1",
        chapter_number: 1,
        novel_title: "Overlord Test",
        title: "Chapter 1",
        text: "Hello world",
        previous_chapter_id: null,
        next_chapter_id: "c2",
        slug: "overlord-test",
      };

      const spy = vi
        .spyOn(publicApi, "chapter")
        .mockResolvedValueOnce(mockDetail);

      const { result } = renderHookWithProviders(() =>
        useChapter("overlord-test", "c1"),
      );

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockDetail);
      expect(spy).toHaveBeenCalledWith(
        "overlord-test",
        "c1",
        expect.any(AbortSignal),
      );
    });

    it("does not fetch when slug or chapterId is empty", () => {
      const spy = vi.spyOn(publicApi, "chapter");
      const { result } = renderHookWithProviders(() => useChapter("", ""));

      expect(result.current.fetchStatus).toBe("idle");
      expect(spy).not.toHaveBeenCalled();
    });
  });
});
