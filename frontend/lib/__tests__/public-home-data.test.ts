import { QueryClient } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  HOME_CATALOG_PARAMS,
  HOME_RANKING_LIMIT,
  HOME_RANKING_PERIOD,
  prefetchHomeQueries,
} from "@/lib/public-home-data";
import { catalogQueryKey, rankingQueryKey } from "@/lib/public-query-keys";

const originalBackendUrl = process.env.BACKEND_API_URL;
const originalBackendHost = process.env.BACKEND_API_HOST;

describe("public home server prefetch", () => {
  beforeEach(() => {
    process.env.BACKEND_API_URL = "http://backend:8000";
    process.env.BACKEND_API_HOST = "localhost";
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/catalog?")) {
          return new Response(
            JSON.stringify({ novels: [], total: 0, page: 1, page_size: 24 }),
            { status: 200 },
          );
        }
        return new Response(
          JSON.stringify({
            period: "weekly",
            metric: "unique_novel_views",
            available: false,
            reason: "no_data",
            retention_days: 30,
            generated_at: "2026-08-20T00:00:00Z",
            items: [],
          }),
          { status: 200 },
        );
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    if (originalBackendUrl === undefined) delete process.env.BACKEND_API_URL;
    else process.env.BACKEND_API_URL = originalBackendUrl;
    if (originalBackendHost === undefined) delete process.env.BACKEND_API_HOST;
    else process.env.BACKEND_API_HOST = originalBackendHost;
  });

  it("prefetches only the guest-visible catalog and weekly ranking", async () => {
    const queryClient = new QueryClient();

    await prefetchHomeQueries(queryClient);

    expect(HOME_CATALOG_PARAMS.page_size).toBe(24);
    expect(queryClient.getQueryData(catalogQueryKey(HOME_CATALOG_PARAMS))).toEqual({
      novels: [],
      total: 0,
      page: 1,
      page_size: 24,
    });
    expect(
      queryClient.getQueryData(rankingQueryKey(HOME_RANKING_PERIOD, HOME_RANKING_LIMIT)),
    ).toMatchObject({ period: "weekly", items: [] });
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
