"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { userApi } from "@/lib/public-api";
import { ApiError } from "@/lib/api";

const AUTH_ME_KEY = ["auth", "me"] as const;

export function useLibraryItem(slug: string, enabled: boolean) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: ["user", "library", slug],
    queryFn: () => userApi.getLibraryItem(slug),
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

export function useAddToLibrary() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) => userApi.addToLibrary(slug),
    onSuccess: (_data, slug) => {
      queryClient.invalidateQueries({ queryKey: ["user", "library", slug] });
    },
    onError: (error) => {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        queryClient.invalidateQueries({ queryKey: AUTH_ME_KEY });
      }
    },
  });
}

export function useRemoveFromLibrary() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) => userApi.removeFromLibrary(slug),
    onSuccess: (_data, slug) => {
      queryClient.invalidateQueries({ queryKey: ["user", "library", slug] });
    },
    onError: (error) => {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        queryClient.invalidateQueries({ queryKey: AUTH_ME_KEY });
      }
    },
  });
}
