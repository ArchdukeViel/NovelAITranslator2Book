"use client";

import { useState } from "react";
import { LogIn, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLogin, useStartGoogleOAuth } from "@/hooks/public/use-auth";

interface LoginViewProps {
  onClose: () => void;
  onSuccess?: () => void;
}

type LoginMode = "google" | "owner";

/**
 * Login panel with Google OAuth sign-in and owner bootstrap login.
 * Shows benefit bullet list to give guests a clear reason to sign in.
 */
export function LoginView({ onClose, onSuccess }: LoginViewProps) {
  const [mode, setMode] = useState<LoginMode>("google");
  const [secret, setSecret] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [googleUnavailable, setGoogleUnavailable] = useState(false);

  const startGoogleOAuth = useStartGoogleOAuth();
  const loginMutation = useLogin();

  const handleGoogleLogin = async () => {
    setError(null);
    try {
      // Preflight check: does Google OAuth exist?
      const response = await fetch("/api/auth/google/start", {
        method: "HEAD",
        redirect: "manual",
      });
      if (response.status === 503) {
        setGoogleUnavailable(true);
        return;
      }
      // Proceed with Google OAuth redirect
      startGoogleOAuth();
    } catch {
      // Network error — still try the redirect, browser will handle it
      startGoogleOAuth();
    }
  };

  const handleOwnerLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!secret.trim()) {
      setError("Please enter your owner secret.");
      return;
    }
    try {
      await loginMutation.mutateAsync(secret);
      // Clear secret from memory
      setSecret("");
      // Notify parent of successful login
      onSuccess?.();
    } catch (err) {
      // Don't leak details about whether the secret exists
      setError("Invalid credentials. Please try again.");
    }
  };

  return (
    <div className="w-full max-w-sm rounded-lg border border-border bg-background p-6 shadow-lg">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Sign in to Dokushodo</h2>
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
        Sign in to unlock reader features:
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

      {/* Mode toggle */}
      <div className="mb-4 flex gap-2 text-xs">
        <button
          type="button"
          onClick={() => setMode("google")}
          className={`px-3 py-1 rounded ${
            mode === "google"
              ? "bg-primary text-primary-foreground"
              : "bg-muted hover:bg-muted/80"
          }`}
        >
          Google
        </button>
        <button
          type="button"
          onClick={() => setMode("owner")}
          className={`px-3 py-1 rounded ${
            mode === "owner"
              ? "bg-primary text-primary-foreground"
              : "bg-muted hover:bg-muted/80"
          }`}
        >
          Owner
        </button>
      </div>

      {mode === "google" && (
        <div className="flex flex-col gap-2">
          {googleUnavailable && (
            <p className="text-sm text-destructive">
              Google sign-in is not configured on this server.
            </p>
          )}
          <Button
            type="button"
            onClick={handleGoogleLogin}
            className="w-full"
            disabled={googleUnavailable}
          >
            <LogIn className="h-4 w-4" />
            Continue with Google
          </Button>
        </div>
      )}

      {mode === "owner" && (
        <form onSubmit={handleOwnerLogin} className="flex flex-col gap-3">
          <div>
            <label
              htmlFor="owner-secret"
              className="block text-sm font-medium mb-1"
            >
              Owner secret
            </label>
            <input
              id="owner-secret"
              type="password"
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
              className="w-full rounded border border-border bg-background px-3 py-2 text-sm"
              autoComplete="current-password"
              disabled={loginMutation.isPending}
            />
          </div>
          {error && (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          )}
          <Button
            type="submit"
            className="w-full"
            disabled={loginMutation.isPending}
          >
            {loginMutation.isPending ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      )}

      <Button
        type="button"
        variant="outline"
        onClick={onClose}
        className="w-full mt-2"
      >
        Close
      </Button>
    </div>
  );
}
