"use client";

import { useState } from "react";
import { LogIn } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LoginView } from "@/components/public/login-view";

/**
 * Inline login prompt shown to guests in place of authenticated features.
 * Shows benefit summary and sign-in button; expands into LoginView overlay
 * when clicked to avoid repeating multiple login panels on one page.
 */
export function LoginPrompt() {
  const [showLogin, setShowLogin] = useState(false);

  if (showLogin) {
    return (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
        onClick={(e) => {
          if (e.target === e.currentTarget) setShowLogin(false);
        }}
      >
        <LoginView
          onClose={() => setShowLogin(false)}
          onSuccess={() => setShowLogin(false)}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border border-border bg-muted/50 px-3 py-2 text-sm text-muted-foreground">
      <LogIn className="h-4 w-4 shrink-0" />
      <span>
        Sign in to save novels, continue reading, and leave reviews.
      </span>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setShowLogin(true)}
        className="ml-auto"
      >
        Sign in
      </Button>
    </div>
  );
}
