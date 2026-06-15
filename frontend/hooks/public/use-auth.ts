"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { authApi } from "@/lib/public-api";
import type { LoginInput } from "@/lib/public-types";

const AUTH_ME_KEY = ["auth", "me"] as const;

export function useAuthMe() {
  return useQuery({
    queryKey: AUTH_ME_KEY,
    queryFn: () => authApi.me(),
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: LoginInput) => authApi.login(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: AUTH_ME_KEY });
    },
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
