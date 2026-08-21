"use client";

import { useQuery } from "@tanstack/react-query";
import { publicApi } from "@/lib/public-api";
import { rankingQueryKey } from "@/lib/public-query-keys";
import type { PublicRankingPeriod } from "@/lib/public-types";

export { rankingQueryKey } from "@/lib/public-query-keys";

export function usePublicRankings(
  period: PublicRankingPeriod,
  limit = 5,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: rankingQueryKey(period, limit),
    queryFn: ({ signal }) => publicApi.rankings(period, limit, signal),
    enabled: options.enabled ?? true,
    retry: false,
  });
}
