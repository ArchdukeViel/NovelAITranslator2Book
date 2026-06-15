"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { userApi } from "@/lib/public-api";
import { ApiError } from "@/lib/api";

const AUTH_ME_KEY = ["auth", "me"] as const;

export function useProgress(slug: string, enabled: boolean) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: ["user", "progress", slug],
    queryFn: () => userApi.getProgress(slug),
    enabled: enabled && !!slug,
    retry: (failureCount, error) => {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        queryClient.invalidateQueries({ queryKey: AUTH_ME_KEY });
        return false;
      }
      return failureCount < 3;
    },
  });
}

export function usePutProgress() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ slug, chapterId }: { slug: string; chapterId: string }) =>
      userApi.putProgress(slug, chapterId),
    onSuccess: (_data, { slug }) => {
      queryClient.invalidateQueries({ queryKey: ["user", "progress", slug] });
    },
    onError: (error) => {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        queryClient.invalidateQueries({ queryKey: AUTH_ME_KEY });
      }
    },
  });
}
