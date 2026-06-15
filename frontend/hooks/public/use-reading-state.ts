"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { userReadingApi } from "@/lib/public-api";
import type {
  HistoryListParams,
  HistoryRecordInput,
  ProgressInput,
} from "@/lib/public-types";
import { usePublicAuth } from "./use-auth";

const libraryKeys = {
  all: ["user-reading", "library"] as const,
  item: (slug: string) => ["user-reading", "library", slug] as const,
};

const progressKeys = {
  item: (slug: string) => ["user-reading", "progress", slug] as const,
};

const historyKeys = {
  all: ["user-reading", "history"] as const,
};

function useCanUseReadingState() {
  const { isAuthenticated, isPending } = usePublicAuth();
  return {
    canUseReadingState: isAuthenticated,
    authPending: isPending,
  };
}

export function useLibrary() {
  const { canUseReadingState } = useCanUseReadingState();
  return useQuery({
    queryKey: libraryKeys.all,
    queryFn: () => userReadingApi.getLibrary(),
    enabled: canUseReadingState,
  });
}

export function useLibraryItem(slug: string) {
  const { canUseReadingState } = useCanUseReadingState();
  return useQuery({
    queryKey: libraryKeys.item(slug),
    queryFn: () => userReadingApi.getLibraryItem(slug),
    enabled: canUseReadingState && !!slug,
    retry: false,
  });
}

export function useAddToLibrary(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => userReadingApi.addToLibrary(slug),
    onSuccess: (item) => {
      queryClient.setQueryData(libraryKeys.item(slug), item);
      queryClient.invalidateQueries({ queryKey: libraryKeys.all });
    },
  });
}

export function useRemoveFromLibrary(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => userReadingApi.removeFromLibrary(slug),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: libraryKeys.item(slug) });
      queryClient.invalidateQueries({ queryKey: libraryKeys.all });
    },
  });
}

export function useProgress(slug: string) {
  const { canUseReadingState } = useCanUseReadingState();
  return useQuery({
    queryKey: progressKeys.item(slug),
    queryFn: () => userReadingApi.getProgress(slug),
    enabled: canUseReadingState && !!slug,
  });
}

export function useUpdateProgress(slug: string) {
  const queryClient = useQueryClient();
  const { canUseReadingState } = useCanUseReadingState();
  return useMutation({
    mutationFn: (input: ProgressInput) => {
      if (!canUseReadingState) {
        return Promise.reject(new Error("Sign in required."));
      }
      return userReadingApi.putProgress(slug, input);
    },
    onSuccess: (progress) => {
      queryClient.setQueryData(progressKeys.item(slug), progress);
    },
  });
}

export function useHistory(params: HistoryListParams = {}) {
  const { canUseReadingState } = useCanUseReadingState();
  return useQuery({
    queryKey: [...historyKeys.all, params],
    queryFn: () => userReadingApi.listHistory(params),
    enabled: canUseReadingState,
  });
}

export function useRecordHistory() {
  const queryClient = useQueryClient();
  const { canUseReadingState } = useCanUseReadingState();
  return useMutation({
    mutationFn: (input: HistoryRecordInput) => {
      if (!canUseReadingState) {
        return Promise.reject(new Error("Sign in required."));
      }
      return userReadingApi.recordHistory(input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: historyKeys.all });
    },
  });
}
