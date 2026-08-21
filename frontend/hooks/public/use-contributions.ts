"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { userContributionApi } from "@/lib/public-api";

const CONTRIBUTIONS_KEY = ["user", "contributions"] as const;

export function useContributions(enabled = true) {
  return useQuery({
    queryKey: CONTRIBUTIONS_KEY,
    queryFn: () => userContributionApi.list(),
    enabled,
  });
}

export function useReplaceContribution() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: userContributionApi.replace,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CONTRIBUTIONS_KEY }),
  });
}

export function useUpdateContributionStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ credentialId, status }: { credentialId: string; status: "active" | "paused" }) =>
      userContributionApi.updateStatus(credentialId, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CONTRIBUTIONS_KEY }),
  });
}

export function useDeleteContribution() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (credentialId: string) => userContributionApi.remove(credentialId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CONTRIBUTIONS_KEY }),
  });
}

export function useContributionUsage(credentialId: string | null) {
  return useQuery({
    queryKey: ["user", "contributions", credentialId, "usage"],
    queryFn: () => userContributionApi.usage(credentialId as string),
    enabled: Boolean(credentialId),
  });
}
