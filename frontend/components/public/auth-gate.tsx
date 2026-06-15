"use client";

import { LoginPrompt } from "@/components/public/login-prompt";

interface AuthGateProps {
  /** The user-only content to render when authenticated. */
  children: React.ReactNode;
  /** Optional custom fallback to show Guests (defaults to LoginPrompt). */
  fallback?: React.ReactNode;
}

/**
 * Public auth is available, but user-owned features stay inert until B4/B5.
 */
export function AuthGate({ children: _children, fallback }: AuthGateProps) {
  return <>{fallback ?? <LoginPrompt />}</>;
}
