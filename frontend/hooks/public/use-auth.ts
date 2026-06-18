"use client";

import { useCallback, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { authApi } from "@/lib/public-api";
import type {
  EmailPasswordAuthInput,
  PublicAuthState,
  RegisterAuthInput,
} from "@/lib/public-types";

const AUTH_ME_KEY = ["auth", "me"] as const;

export function useAuthMe() {
  return useQuery({
    queryKey: AUTH_ME_KEY,
    queryFn: () => authApi.me(),
  });
}

export function usePublicAuthState(): PublicAuthState | null {
  const { data } = useAuthMe();
  if (!data) {
    return null;
  }
  return {
    status: data.is_authenticated ? "authenticated" : "guest",
    user: data,
  };
}

export function usePublicAuth() {
  const query = useAuthMe();
  const authState = useMemo<PublicAuthState | null>(() => {
    if (!query.data) {
      return null;
    }
    return {
      status: query.data.is_authenticated ? "authenticated" : "guest",
      user: query.data,
    };
  }, [query.data]);

  return {
    ...query,
    authState,
    user: query.data ?? null,
    isAuthenticated: query.data?.is_authenticated === true,
    isPublicUser: query.data?.role === "user",
    isOwner: query.data?.role === "owner",
  };
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => authApi.logout(),
    onSuccess: () => {
      // Invalidate auth state so the UI reflects guest immediately.
      queryClient.invalidateQueries({ queryKey: AUTH_ME_KEY });

      // Remove all user-scoped cached data so stale library/progress/history/
      // reviews/requests don't persist after logout. Using removeQueries
      // (not invalidateQueries) ensures data is fully cleared rather than
      // refetched for a now-unauthenticated user.
      queryClient.removeQueries({ queryKey: ["user-reading"] });
      queryClient.removeQueries({ queryKey: ["user-engagement"] });
    },
  });
}

function invalidateAuthState(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: AUTH_ME_KEY });
}

export function usePasswordLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: EmailPasswordAuthInput) => authApi.passwordLogin(input),
    onSuccess: () => {
      invalidateAuthState(queryClient);
    },
  });
}

export function useRegister() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: RegisterAuthInput) => authApi.register(input),
    onSuccess: () => {
      invalidateAuthState(queryClient);
    },
  });
}

export function useStartGoogleOAuth() {
  return useCallback((returnTo?: string) => {
    const currentPath =
      typeof window !== "undefined"
        ? `${window.location.pathname}${window.location.search}${window.location.hash}`
        : "/";
    const url = authApi.googleStart(returnTo ?? currentPath);
    if (typeof window !== "undefined") {
      window.location.assign(url);
    }
    return url;
  }, []);
}
