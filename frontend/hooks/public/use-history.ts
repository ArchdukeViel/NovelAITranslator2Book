"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { userApi } from "@/lib/public-api";
import { ApiError } from "@/lib/api";

const AUTH_ME_KEY = ["auth", "me"] as const;

export function useHistory(enabled: boolean) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: ["user", "history"],
    queryFn: () => userApi.listHistory(),
    enabled,
    retry: (failureCount, error) => {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        queryClient.invalidateQueries({ queryKey: AUTH_ME_KEY });
        return false;
      }
      return failureCount < 3;
    },
  });
}

export function useRecordHistory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ slug, chapterId }: { slug: string; chapterId: string }) =>
      userApi.recordHistory(slug, chapterId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user", "history"] });
    },
    onError: (error) => {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        queryClient.invalidateQueries({ queryKey: AUTH_ME_KEY });
      }
    },
  });
}
