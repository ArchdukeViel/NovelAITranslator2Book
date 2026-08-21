"use client";

import { useQuery } from "@tanstack/react-query";
import { publicApi } from "@/lib/public-api";

export function useNovel(slug: string) {
  return useQuery({
    queryKey: ["public", "novel", slug],
    queryFn: ({ signal }) => publicApi.novel(slug, signal),
    enabled: !!slug,
    retry: false,
  });
}
