"use client";

import { LogIn, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useStartGoogleOAuth } from "@/hooks/public/use-auth";

interface LoginViewProps {
  onClose: () => void;
  onSuccess?: () => void;
}

/**
 * Login panel with Google OAuth sign-in.
 * Shows benefit bullet list to give guests a clear reason to sign in.
 */
export function LoginView({ onClose }: LoginViewProps) {
  const startGoogleOAuth = useStartGoogleOAuth();

  return (
    <div className="w-full max-w-sm rounded-lg border border-border bg-background p-6 shadow-lg">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Sign in to Novel AI</h2>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Close login"
          onClick={onClose}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      <p className="text-sm text-muted-foreground mb-3">
        Continue with Google to unlock reader features:
      </p>
      <ul className="space-y-1 text-sm text-muted-foreground mb-5">
        <li>Save novels to your library</li>
        <li>Continue reading where you left off</li>
        <li>Keep your reading history</li>
        <li>Leave reviews and request new content</li>
      </ul>
      <p className="text-xs text-muted-foreground mb-4">
        Guest reading is always available without sign-in.
      </p>

      <div className="flex flex-col gap-2">
        <Button
          type="button"
          onClick={() => startGoogleOAuth()}
          className="w-full"
        >
          <LogIn className="h-4 w-4" />
          Continue with Google
        </Button>
        <Button type="button" variant="outline" onClick={onClose}>
          Close
        </Button>
      </div>
    </div>
  );
}
