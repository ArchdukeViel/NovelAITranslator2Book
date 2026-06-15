"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { userEngagementApi } from "@/lib/public-api";
import type {
  PublicRequestInput,
  RequestListParams,
  ReviewInput,
  ReviewResponse,
} from "@/lib/public-types";
import { usePublicAuth } from "./use-auth";

const reviewKeys = {
  item: (slug: string) => ["user-engagement", "review", slug] as const,
};

const requestKeys = {
  all: ["user-engagement", "requests"] as const,
};

function useCanUseEngagement() {
  const { isAuthenticated, isPending } = usePublicAuth();
  return {
    canUseEngagement: isAuthenticated,
    authPending: isPending,
  };
}

export function useUpsertReview(slug: string) {
  const queryClient = useQueryClient();
  const { canUseEngagement } = useCanUseEngagement();
  return useMutation({
    mutationFn: (input: ReviewInput) => {
      if (!canUseEngagement) {
        return Promise.reject(new Error("Sign in required."));
      }
      return userEngagementApi.putReview(slug, input);
    },
    onSuccess: (review) => {
      queryClient.setQueryData<ReviewResponse>(reviewKeys.item(slug), review);
    },
  });
}

export function useDeleteReview(slug: string) {
  const queryClient = useQueryClient();
  const { canUseEngagement } = useCanUseEngagement();
  return useMutation({
    mutationFn: () => {
      if (!canUseEngagement) {
        return Promise.reject(new Error("Sign in required."));
      }
      return userEngagementApi.deleteReview(slug);
    },
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: reviewKeys.item(slug) });
    },
  });
}

export function useRequests(params: RequestListParams = {}) {
  const { canUseEngagement } = useCanUseEngagement();
  return useQuery({
    queryKey: [...requestKeys.all, params],
    queryFn: () => userEngagementApi.listRequests(params),
    enabled: canUseEngagement,
  });
}

export function useCreateRequest() {
  const queryClient = useQueryClient();
  const { canUseEngagement } = useCanUseEngagement();
  return useMutation({
    mutationFn: (input: PublicRequestInput) => {
      if (!canUseEngagement) {
        return Promise.reject(new Error("Sign in required."));
      }
      return userEngagementApi.createRequest(input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: requestKeys.all });
    },
  });
}
