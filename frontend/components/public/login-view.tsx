"use client";

import { LogIn, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useStartGoogleOAuth } from "@/hooks/public/use-auth";

interface LoginViewProps {
  onClose: () => void;
  onSuccess?: () => void;
}

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

      <div className="space-y-2 text-sm text-muted-foreground">
        <p>Continue with Google to use the public reader account session.</p>
        <p>Guest reading is still available.</p>
        <p>Library, progress, reviews, and requests are available after sign-in.</p>
      </div>

      <div className="mt-5 flex flex-col gap-2">
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
