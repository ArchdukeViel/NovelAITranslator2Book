"use client";

import { LoginPrompt } from "@/components/public/login-prompt";

interface AuthGateProps {
  /** The user-only content to render when authenticated. */
  children: React.ReactNode;
  /** Optional custom fallback to show Guests (defaults to LoginPrompt). */
  fallback?: React.ReactNode;
}

/**
 * Public user accounts are not available yet, so user-only content stays inert.
 */
export function AuthGate({ children: _children, fallback }: AuthGateProps) {
  return <>{fallback ?? <LoginPrompt />}</>;
}
