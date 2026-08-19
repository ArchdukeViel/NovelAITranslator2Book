"use client";

import { useQuery } from "@tanstack/react-query";
import { publicApi } from "@/lib/public-api";
import type { PublicRankingPeriod } from "@/lib/public-types";

export function usePublicRankings(period: PublicRankingPeriod, limit = 5) {
  return useQuery({
    queryKey: ["public", "rankings", period, limit],
    queryFn: () => publicApi.rankings(period, limit),
  });
}
