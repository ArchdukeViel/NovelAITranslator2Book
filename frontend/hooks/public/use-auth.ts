"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { authApi } from "@/lib/public-api";

const AUTH_ME_KEY = ["auth", "me"] as const;

export function useAuthMe() {
  return useQuery({
    queryKey: AUTH_ME_KEY,
    queryFn: () => authApi.me(),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => authApi.logout(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: AUTH_ME_KEY });
    },
  });
}
