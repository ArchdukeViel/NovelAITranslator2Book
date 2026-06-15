"use client";

import { useState } from "react";
import { User, LogOut, LogIn } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuthMe, useLogout } from "@/hooks/public/use-auth";
import { LoginView } from "@/components/public/login-view";

/**
 * Current User Indicator for the Public_Header.
 * - Guest (not authenticated): shows a "Sign In" button that opens the LoginView
 * - User (authenticated): shows the user's email/identity and a "Sign Out" button
 * Requirements: 8.1, 8.2, 8.5, 8.6
 */
export function CurrentUserIndicator() {
  const [showLogin, setShowLogin] = useState(false);
  const { data: authUser, isLoading } = useAuthMe();
  const logoutMutation = useLogout();

  const isAuthenticated = authUser?.is_authenticated === true;

  function handleLogout() {
    logoutMutation.mutate();
  }

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <User className="h-4 w-4" />
        <span>…</span>
      </div>
    );
  }

  if (isAuthenticated && authUser) {
    // Authenticated user: show identity + logout
    return (
      <div className="flex items-center gap-2 text-sm">
        <User className="h-4 w-4 text-muted-foreground" />
        <span className="max-w-[160px] truncate" title={authUser.email ?? undefined}>
          {authUser.email ?? "User"}
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleLogout}
          disabled={logoutMutation.isPending}
          aria-label="Sign out"
        >
          <LogOut className="h-4 w-4" />
          <span className="sr-only sm:not-sr-only">Sign Out</span>
        </Button>
      </div>
    );
  }

  // Guest: show sign-in entry point
  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setShowLogin(true)}
        aria-label="Sign in"
      >
        <LogIn className="h-4 w-4" />
        <span>Sign In</span>
      </Button>

      {showLogin && (
        <div className="absolute right-0 top-full z-50 mt-2">
          <LoginView onClose={() => setShowLogin(false)} />
        </div>
      )}
    </div>
  );
}
