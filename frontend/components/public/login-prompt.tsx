"use client";

import { useState } from "react";
import { LogIn } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LoginView } from "@/components/public/login-view";

/**
 * Public-account prompt shown in place of user-only controls until public auth exists.
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
      <span>Public accounts are not available yet.</span>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setShowLogin(true)}
        className="ml-auto"
      >
        Details
      </Button>
    </div>
  );
}
