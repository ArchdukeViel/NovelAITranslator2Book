"use client";

import { Loader2 } from "lucide-react";

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

  // While auth state is loading, show a calm spinner.
  if (isPending) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Checking session
      </div>
    );
  }

  if (isAuthenticated) {
    return <>{children}</>;
  }

  return <>{fallback ?? <LoginPrompt />}</>;
}
