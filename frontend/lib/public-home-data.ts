import type { QueryClient } from "@tanstack/react-query";

import type {
  CatalogParams,
  PublicCatalogResponse,
  PublicRankingResponse,
} from "@/lib/public-types";
import { catalogQueryKey, rankingQueryKey } from "@/lib/public-query-keys";
import { publicServerGet } from "@/lib/public-api";

/** The first home view needs enough rows for its visible rails, not the full catalog. */
export const HOME_CATALOG_PARAMS = {
  sort_by: "added_at",
  order: "desc",
  page_size: 24,
} satisfies CatalogParams;

export const HOME_RANKING_PERIOD = "weekly" as const;
export const HOME_RANKING_LIMIT = 5;
export const HOME_SERVER_PREFETCH_TIMEOUT_MS = 3_000;
export const HOME_QUERY_STALE_TIME_MS = 20_000;

function homeCatalogPath(): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(HOME_CATALOG_PARAMS)) {
    search.set(key, String(value));
  }
  return `/api/public/catalog?${search.toString()}`;
}

function homeRankingPath(): string {
  const search = new URLSearchParams({
    period: HOME_RANKING_PERIOD,
    limit: String(HOME_RANKING_LIMIT),
  });
  return `/api/public/rankings?${search.toString()}`;
}

async function fetchServerPublicJson<T>(path: string): Promise<T> {
  const backendUrl =
    process.env.READER_API_URL?.trim() ||
    process.env.BACKEND_API_URL?.trim() ||
    process.env.NEXT_PUBLIC_API_URL?.trim();
  if (!backendUrl) {
    throw new Error("Server public API base is not configured");
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), HOME_SERVER_PREFETCH_TIMEOUT_MS);
  const backendHost = process.env.BACKEND_API_HOST?.trim() || process.env.SITE_DOMAIN?.trim();

  try {
    return await publicServerGet<T>(path, {
      baseUrl: backendUrl,
      host: backendHost,
      revalidateSeconds: HOME_QUERY_STALE_TIME_MS / 1000,
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeoutId);
  }
}

export function fetchHomeCatalog(): Promise<PublicCatalogResponse> {
  return fetchServerPublicJson<PublicCatalogResponse>(homeCatalogPath());
}

export function fetchHomeWeeklyRanking(): Promise<PublicRankingResponse> {
  return fetchServerPublicJson<PublicRankingResponse>(homeRankingPath());
}

/** Prefetch only the two guest-visible home datasets; personalization stays client-deferred. */
export async function prefetchHomeQueries(queryClient: QueryClient): Promise<void> {
  await Promise.allSettled([
    queryClient.prefetchQuery({
      queryKey: catalogQueryKey(HOME_CATALOG_PARAMS),
      queryFn: () => fetchHomeCatalog(),
      staleTime: HOME_QUERY_STALE_TIME_MS,
    }),
    queryClient.prefetchQuery({
      queryKey: rankingQueryKey(HOME_RANKING_PERIOD, HOME_RANKING_LIMIT),
      queryFn: () => fetchHomeWeeklyRanking(),
      staleTime: HOME_QUERY_STALE_TIME_MS,
    }),
  ]);
}
