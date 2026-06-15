"use client";

import { useAuthMe } from "@/hooks/public/use-auth";
import { LoginPrompt } from "@/components/public/login-prompt";

interface AuthGateProps {
  /** The user-only content to render when authenticated. */
  children: React.ReactNode;
  /** Optional custom fallback to show Guests (defaults to LoginPrompt). */
  fallback?: React.ReactNode;
}

/**
 * Role-based gating component.
 * Renders children when the current user has role "user" (authenticated),
 * otherwise renders the LoginPrompt (or a custom fallback).
 *
 * Requirements: 9.1, 9.2, 9.3, 9.4
 */
export function AuthGate({ children, fallback }: AuthGateProps) {
  const { data: authUser } = useAuthMe();

  if (authUser?.role === "user") {
    return <>{children}</>;
  }

  return <>{fallback ?? <LoginPrompt />}</>;
}
