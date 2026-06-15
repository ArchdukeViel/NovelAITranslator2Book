"use client";

import { useState } from "react";
import { LogIn, LogOut, Loader2, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LoginView } from "@/components/public/login-view";
import { useLogout, usePublicAuth } from "@/hooks/public/use-auth";

interface CurrentUserIndicatorProps {
  /** Callback after a navigation action (used by mobile menu to close). */
  onNavigate?: () => void;
}

/**
 * Current User Indicator for the Public Header.
 * Shows email + sign-out when authenticated, sign-in button when guest.
 * Login panel uses a center-screen overlay with backdrop instead of
 * absolute-position dropdown to avoid overflow/clipping on mobile.
 */
export function CurrentUserIndicator({ onNavigate }: CurrentUserIndicatorProps) {
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
    <>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setShowLogin(true)}
        aria-label="Sign in"
      >
        <LogIn className="h-4 w-4" />
        <span>Sign in</span>
      </Button>

      {/* Center-screen overlay with backdrop — mobile-safe, no overflow risk */}
      {showLogin && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowLogin(false);
          }}
        >
          <LoginView
            onClose={() => setShowLogin(false)}
            onSuccess={() => {
              setShowLogin(false);
              onNavigate?.();
            }}
          />
        </div>
      )}
    </>
  );
}
