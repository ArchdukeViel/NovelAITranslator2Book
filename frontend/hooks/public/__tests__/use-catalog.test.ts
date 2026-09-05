import { describe, it, expect, vi, beforeEach } from "vitest";
import { waitFor } from "@testing-library/react";
import { useCatalog, catalogQueryKey } from "@/hooks/public/use-catalog";
import { publicApi } from "@/lib/public-api";
import { renderHookWithProviders } from "@/lib/test-utils";
import type { CatalogParams, PublicCatalogResponse } from "@/lib/public-types";

describe("useCatalog query hook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("constructs predictable query keys based on params", () => {
    const params: CatalogParams = { q: "test", page: 1, sort_by: "title" };
    const key = catalogQueryKey(params);
    expect(key).toEqual(["public", "catalog", params]);
  });

  it("fetches catalog successfully and returns data", async () => {
    const mockResponse: PublicCatalogResponse = {
      novels: [
        {
          novel_id: "nov-1",
          slug: "test-slug",
          title: "Test Novel",
          source_title: null,
          author: "Author",
          language: "ja",
          synopsis: "Synopsis text",
          publication_status: "ongoing",
          chapter_count: 10,
          translated_count: 10,
          genres: [],
          tags: [],
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
    };

    const spy = vi
      .spyOn(publicApi, "catalog")
      .mockResolvedValueOnce(mockResponse);

    const params: CatalogParams = { page: 1 };
    const { result } = renderHookWithProviders(() => useCatalog(params));

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockResponse);
    expect(spy).toHaveBeenCalledWith(params, expect.any(AbortSignal));
  });

  it("handles empty query params gracefully", () => {
    const { result } = renderHookWithProviders(() => useCatalog({}));
    expect(result.current.fetchStatus).toBe("fetching");
  });
});
