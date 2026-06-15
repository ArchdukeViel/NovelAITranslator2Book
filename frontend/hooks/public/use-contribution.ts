"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { userApi } from "@/lib/public-api";
import { ApiError } from "@/lib/api";

const AUTH_ME_KEY = ["auth", "me"] as const;

export function useContribution(enabled: boolean) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: ["user", "contribution"],
    queryFn: () => userApi.getContribution(),
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

export function useSubmitContribution() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (rawKey: string) => userApi.submitContribution(rawKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user", "contribution"] });
    },
    onError: (error) => {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        queryClient.invalidateQueries({ queryKey: AUTH_ME_KEY });
      }
    },
  });
}

export function useRemoveContribution() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => userApi.removeContribution(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user", "contribution"] });
    },
    onError: (error) => {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        queryClient.invalidateQueries({ queryKey: AUTH_ME_KEY });
      }
    },
  });
}
