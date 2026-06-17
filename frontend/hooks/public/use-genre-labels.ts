"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { publicApi } from "@/lib/public-api";
import type { PublicGenreResponse } from "@/lib/public-types";

/**
 * Returns a Map<slug, display_label> for non-adult genres.
 *
 * Display label = `name_en ?? slug`.
 * Safe for public UI: never includes adult/R18 genre slugs.
 */
export function useGenreLabelMap() {
  const { data } = useQuery<PublicGenreResponse[]>({
    queryKey: ["public", "genres", "label-map"],
    queryFn: () => publicApi.genres({ include_adult: false }),
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });

  return useMemo(() => {
    if (!data) return null;
    const map = new Map<string, string>();
    for (const g of data) {
      map.set(g.slug, g.name_en ?? g.slug);
    }
    return map;
  }, [data]);
}
