"use client";

import { useQuery } from "@tanstack/react-query";
import { publicApi } from "@/lib/public-api";

export function useChapters(slug: string) {
  return useQuery({
    queryKey: ["public", "chapters", slug],
    queryFn: ({ signal }) => publicApi.chapters(slug, signal),
    enabled: !!slug,
    retry: false,
  });
}
