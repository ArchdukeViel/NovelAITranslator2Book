"use client";

import Link from "next/link";
import { LogIn, LogOut, Loader2, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLogout, usePublicAuth } from "@/hooks/public/use-auth";

interface CurrentUserIndicatorProps {
  /** Callback after a navigation action (used by mobile menu to close). */
  onNavigate?: () => void;
}

/**
 * Current User Indicator for the Public Header.
 * Shows email + sign-out when authenticated, sign-in route when guest.
 */
export function CurrentUserIndicator({ onNavigate }: CurrentUserIndicatorProps) {
  const { isAuthenticated, user } = usePublicAuth();
  const logout = useLogout();

  if (isAuthenticated) {
    return (
      <div className="flex items-center gap-2">
        <div className="hidden items-center gap-1 text-sm text-muted-foreground sm:flex">
          <User className="h-4 w-4" />
          <span>{user?.email ?? "Signed in"}</span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => logout.mutate()}
          disabled={logout.isPending}
          aria-label="Sign out"
        >
          {logout.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <LogOut className="h-4 w-4" />
          )}
          <span>{logout.isPending ? "Signing out…" : "Sign out"}</span>
        </Button>
      </div>
    );
  }

  return (
    <Link
      href="/login?mode=signin"
      onClick={onNavigate}
      aria-label="Sign in"
      className="inline-flex h-8 items-center justify-center gap-2 rounded-md px-2.5 text-xs font-medium transition-colors hover:bg-muted"
    >
      <LogIn className="h-4 w-4" />
      <span>Sign in</span>
    </Link>
  );
}
