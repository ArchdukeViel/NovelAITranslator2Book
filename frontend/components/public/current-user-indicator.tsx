"use client";

import { useState } from "react";
import { LogIn } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LoginView } from "@/components/public/login-view";

/**
 * Current User Indicator for the Public_Header.
 * Public accounts are unavailable, so this opens an informational dialog only.
 */
export function CurrentUserIndicator() {
  const [showLogin, setShowLogin] = useState(false);

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setShowLogin(true)}
        aria-label="Public accounts unavailable"
      >
        <LogIn className="h-4 w-4" />
        <span>Accounts Unavailable</span>
      </Button>

      {showLogin && (
        <div className="absolute right-0 top-full z-50 mt-2">
          <LoginView onClose={() => setShowLogin(false)} />
        </div>
      )}
    </div>
  );
}
