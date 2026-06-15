"use client";

import { useState, type FormEvent } from "react";
import { X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useLogin } from "@/hooks/public/use-auth";
import { ApiError } from "@/lib/api";

interface LoginViewProps {
  onClose: () => void;
  onSuccess?: () => void;
}

/**
 * Credential login form for the public reader.
 * - Fields: email (optional), secret (required password/token)
 * - On 401: shows "Invalid credentials" without echoing the submitted secret
 * - No OAuth-specific controls (Req 8.8)
 * - Has a close/cancel control
 */
export function LoginView({ onClose, onSuccess }: LoginViewProps) {
  const [email, setEmail] = useState("");
  const [secret, setSecret] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loginMutation = useLogin();

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setErrorMessage(null);

    if (!secret.trim()) {
      setErrorMessage("A secret or password is required.");
      return;
    }

    loginMutation.mutate(
      { email: email.trim() || undefined, secret: secret },
      {
        onSuccess: () => {
          onSuccess?.();
          onClose();
        },
        onError: (error) => {
          // Req 8.4: on 401, show "Invalid credentials" without echoing the secret
          if (error instanceof ApiError && error.status === 401) {
            setErrorMessage("Invalid credentials. Please try again.");
          } else {
            setErrorMessage("Login failed. Please try again later.");
          }
        },
      }
    );
  }

  return (
    <div className="w-full max-w-sm rounded-lg border border-border bg-background p-6 shadow-lg">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Sign In</h2>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Close login"
          onClick={onClose}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="login-email" className="text-sm font-medium">
            Email <span className="text-muted-foreground">(optional)</span>
          </label>
          <Input
            id="login-email"
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="login-secret" className="text-sm font-medium">
            Password / Token
          </label>
          <Input
            id="login-secret"
            type="password"
            placeholder="Enter your secret"
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            required
            autoComplete="current-password"
          />
        </div>

        {errorMessage && (
          <p className="text-sm text-destructive" role="alert">
            {errorMessage}
          </p>
        )}

        <div className="flex items-center gap-2 pt-1">
          <Button
            type="submit"
            disabled={loginMutation.isPending}
            className="flex-1"
          >
            {loginMutation.isPending && (
              <Loader2 className="h-4 w-4 animate-spin" />
            )}
            Sign In
          </Button>
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
}
