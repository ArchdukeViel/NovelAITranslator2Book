"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { userApi } from "@/lib/public-api";
import { ApiError } from "@/lib/api";
import type { NovelRequestInput } from "@/lib/public-types";

const AUTH_ME_KEY = ["auth", "me"] as const;

export function useRequests(enabled: boolean) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: ["user", "requests"],
    queryFn: () => userApi.listRequests(),
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

export function useCreateRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: NovelRequestInput) => userApi.createRequest(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user", "requests"] });
    },
    onError: (error) => {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        queryClient.invalidateQueries({ queryKey: AUTH_ME_KEY });
      }
    },
  });
}
