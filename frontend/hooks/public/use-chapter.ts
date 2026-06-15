"use client";

import { useQuery } from "@tanstack/react-query";
import { publicApi } from "@/lib/public-api";

export function useChapter(slug: string, chapterId: string) {
  return useQuery({
    queryKey: ["public", "chapter", slug, chapterId],
    queryFn: () => publicApi.chapter(slug, chapterId),
    enabled: !!slug && !!chapterId,
  });
}
