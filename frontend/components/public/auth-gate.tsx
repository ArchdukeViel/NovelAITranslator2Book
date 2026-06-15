"use client";

import { usePublicAuth } from "@/hooks/public/use-auth";
import { LoginPrompt } from "@/components/public/login-prompt";

interface AuthGateProps {
  /** The user-only content to render when authenticated. */
  children: React.ReactNode;
  /** Optional custom fallback to show guests (defaults to LoginPrompt). */
  fallback?: React.ReactNode;
}

/**
 * Conditionally renders children for authenticated users or
 * a fallback prompt for guests. Eliminates repeated login prompts
 * by using a single shared LoginPrompt overlay.
 */
export function AuthGate({ children, fallback }: AuthGateProps) {
  const { isAuthenticated, isPending } = usePublicAuth();

  // While auth state is loading, render nothing to avoid layout thrash.
  if (isPending) {
    return null;
  }

  if (isAuthenticated) {
    return <>{children}</>;
  }

  return <>{fallback ?? <LoginPrompt />}</>;
}
