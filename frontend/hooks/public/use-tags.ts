"use client";

import { useQuery } from "@tanstack/react-query";
import { publicApi } from "@/lib/public-api";
import type { PublicTagSearchResult } from "@/lib/public-types";

export function useTags(params?: { include_adult?: boolean }) {
  return useQuery<PublicTagSearchResult[]>({
    queryKey: ["public", "tags", params?.include_adult],
    queryFn: () => publicApi.tags(params),
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });
}
