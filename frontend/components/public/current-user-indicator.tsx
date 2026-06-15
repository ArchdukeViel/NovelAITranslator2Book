"use client";

import { useState } from "react";
import { LogIn, LogOut, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LoginView } from "@/components/public/login-view";
import { useLogout, usePublicAuth } from "@/hooks/public/use-auth";

/**
 * Current User Indicator for the Public_Header.
 * Public auth may identify a user session, but admin access remains separate.
 */
export function CurrentUserIndicator() {
  const [showLogin, setShowLogin] = useState(false);
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
          <LogOut className="h-4 w-4" />
          <span>Sign out</span>
        </Button>
      </div>
    );
  }

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setShowLogin(true)}
        aria-label="Sign in"
      >
        <LogIn className="h-4 w-4" />
        <span>Sign in</span>
      </Button>

      {showLogin && (
        <div className="absolute right-0 top-full z-50 mt-2">
          <LoginView onClose={() => setShowLogin(false)} />
        </div>
      )}
    </div>
  );
}
