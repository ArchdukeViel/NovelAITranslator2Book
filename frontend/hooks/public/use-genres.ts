"use client";

import { useQuery } from "@tanstack/react-query";
import { publicApi } from "@/lib/public-api";
import type { PublicGenreResponse } from "@/lib/public-types";

export function useGenres() {
  return useQuery<PublicGenreResponse[]>({
    queryKey: ["public", "genres"],
    queryFn: () => publicApi.genres(),
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });
}