import type { CatalogParams, PublicRankingPeriod } from "@/lib/public-types";

export function catalogQueryKey(params: CatalogParams) {
  return ["public", "catalog", params] as const;
}

export function rankingQueryKey(period: PublicRankingPeriod, limit = 5) {
  return ["public", "rankings", period, limit] as const;
}
