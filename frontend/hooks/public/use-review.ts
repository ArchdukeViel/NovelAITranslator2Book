"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { userApi } from "@/lib/public-api";
import { ApiError } from "@/lib/api";
import type { ReviewInput } from "@/lib/public-types";

const AUTH_ME_KEY = ["auth", "me"] as const;

export function usePostReview() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ slug, review }: { slug: string; review: ReviewInput }) =>
      userApi.postReview(slug, review),
    onError: (error) => {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        queryClient.invalidateQueries({ queryKey: AUTH_ME_KEY });
      }
    },
  });
}
