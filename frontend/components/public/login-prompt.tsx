"use client";

import { useState } from "react";
import { LogIn } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LoginView } from "@/components/public/login-view";

/**
 * Public-account prompt shown in place of user-only controls until user features return.
 */
export function LoginPrompt() {
  const [showLogin, setShowLogin] = useState(false);

  if (showLogin) {
    return (
      <div className="flex justify-center">
        <LoginView
          onClose={() => setShowLogin(false)}
          onSuccess={() => setShowLogin(false)}
        />
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 rounded-md border border-border bg-muted/50 px-3 py-2 text-sm text-muted-foreground">
      <LogIn className="h-4 w-4 shrink-0" />
      <span>User features will return in a later phase.</span>
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
