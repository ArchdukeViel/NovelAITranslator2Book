"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { publicApi, userEngagementApi } from "@/lib/public-api";
import type {
  PublicRequestInput,
  RequestListParams,
  ReviewInput,
  ReviewResponse,
  UserReviewItem,
} from "@/lib/public-types";
import { usePublicAuth } from "./use-auth";

const reviewKeys = {
  item: (slug: string) => ["user-engagement", "review", slug] as const,
};

const myReviewsKeys = {
  all: ["user-engagement", "my-reviews"] as const,
};

const novelReviewsKeys = {
  novel: (slug: string) => ["public", "novel-reviews", slug] as const,
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
      queryClient.invalidateQueries({ queryKey: novelReviewsKeys.novel(slug) });
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
      queryClient.invalidateQueries({ queryKey: myReviewsKeys.all });
      queryClient.invalidateQueries({ queryKey: novelReviewsKeys.novel(slug) });
    },
  });
}

export function useNovelReviews(slug: string, cursor?: string | null, limit = 20) {
  return useQuery({
    queryKey: [...novelReviewsKeys.novel(slug), { cursor, limit }],
    queryFn: () => publicApi.novelReviews(slug, { limit, cursor: cursor ?? undefined }),
    enabled: !!slug,
  });
}

export function useMyReviews() {
  const { canUseEngagement } = useCanUseEngagement();
  return useQuery<UserReviewItem[]>({
    queryKey: myReviewsKeys.all,
    queryFn: () => userEngagementApi.listMyReviews(),
    enabled: canUseEngagement,
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
