"use client";

import { useQuery } from "@tanstack/react-query";
import { publicApi } from "@/lib/public-api";

export function useChapters(slug: string) {
  return useQuery({
    queryKey: ["public", "chapters", slug],
    queryFn: () => publicApi.chapters(slug),
    enabled: !!slug,
  });
}
