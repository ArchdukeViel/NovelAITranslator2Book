"use client";

import { useQuery } from "@tanstack/react-query";
import { publicApi } from "@/lib/public-api";
import type { PublicGenreResponse } from "@/lib/public-types";

export function useGenres(params?: { include_adult?: boolean }) {
  return useQuery<PublicGenreResponse[]>({
    queryKey: ["public", "genres", params?.include_adult],
    queryFn: () => publicApi.genres(params),
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });
}