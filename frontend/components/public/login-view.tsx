"use client";

import { useEffect, useState } from "react";
import { Loader2, LogIn, UserPlus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  usePasswordLogin,
  useRegister,
  useStartGoogleOAuth,
} from "@/hooks/public/use-auth";

interface LoginViewProps {
  onClose: () => void;
  onSuccess?: () => void;
  initialMode?: EmailMode;
  onModeChange?: (mode: EmailMode) => void;
}

type EmailMode = "signin" | "signup";

const MIN_PASSWORD_LENGTH = 10;

function validateEmail(value: string): string | null {
  const email = value.trim();
  if (!email) {
    return "Enter your email address.";
  }
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    return "Enter a valid email address.";
  }
  return null;
}

function validatePassword(value: string): string | null {
  if (!value) {
    return "Enter your password.";
  }
  if (value.length < MIN_PASSWORD_LENGTH) {
    return `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`;
  }
  if (value.length > 256) {
    return "Password must be 256 characters or fewer.";
  }
  return null;
}

/**
 * Public reader account panel with Google and email/password auth.
 */
export function LoginView({
  onClose,
  onSuccess,
  initialMode = "signin",
  onModeChange,
}: LoginViewProps) {
  const [mode, setMode] = useState<EmailMode>(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [googleUnavailable, setGoogleUnavailable] = useState(false);

  const startGoogleOAuth = useStartGoogleOAuth();
  const passwordLogin = usePasswordLogin();
  const register = useRegister();
  const emailPending = passwordLogin.isPending || register.isPending;

  useEffect(() => {
    setMode(initialMode);
    setError(null);
  }, [initialMode]);

  function switchMode(nextMode: EmailMode) {
    setMode(nextMode);
    setError(null);
    onModeChange?.(nextMode);
  }

  const handleGoogleLogin = async () => {
    setError(null);
    try {
      const response = await fetch("/api/auth/google/start", {
        method: "HEAD",
        redirect: "manual",
      });
      if (response.status === 503) {
        setGoogleUnavailable(true);
        return;
      }
      startGoogleOAuth();
    } catch {
      startGoogleOAuth();
    }
  };

  const handleEmailAuth = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    const emailError = validateEmail(email);
    if (emailError) {
      setError(emailError);
      return;
    }

    const passwordError = validatePassword(password);
    if (passwordError) {
      setError(passwordError);
      return;
    }

    if (mode === "signup" && password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    try {
      if (mode === "signup") {
        await register.mutateAsync({
          email: email.trim(),
          password,
        });
      } else {
        await passwordLogin.mutateAsync({
          email: email.trim(),
          password,
        });
      }
      setPassword("");
      setConfirmPassword("");
      onSuccess?.();
    } catch {
      setError(
        mode === "signup"
          ? "Could not create that account. Check your details and try again."
          : "Invalid email or password."
      );
    }
  };

  return (
    <div className="w-full max-w-sm rounded-lg border border-border bg-background p-6 shadow-lg">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          {mode === "signup" ? "Create your Dokushodo account" : "Sign in to Dokushodo"}
        </h2>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Close login"
          onClick={onClose}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      <p className="mb-3 text-sm text-muted-foreground">
        Sign in to save reading state:
      </p>
      <ul className="mb-5 space-y-1 text-sm text-muted-foreground">
        <li>Save novels to your library</li>
        <li>Continue reading where you left off</li>
        <li>Keep your reading history</li>
        <li>Leave reviews and request new content</li>
      </ul>
      <p className="mb-4 text-xs text-muted-foreground">
        Guest reading is always available without sign-in.
      </p>

      <div className="mb-4 flex flex-col gap-2">
        {googleUnavailable && (
          <p className="text-sm text-muted-foreground">
            Google sign-in is not available right now. You can still use email
            and password.
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

      <form onSubmit={handleEmailAuth} className="flex flex-col gap-3" noValidate>
        <div>
          <label htmlFor="auth-email" className="mb-1 block text-sm font-medium">
            Email
          </label>
          <input
            id="auth-email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="w-full rounded border border-border bg-background px-3 py-2 text-sm"
            autoComplete="email"
            disabled={emailPending}
          />
        </div>

        <div>
          <label
            htmlFor="auth-password"
            className="mb-1 block text-sm font-medium"
          >
            Password
          </label>
          <input
            id="auth-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="w-full rounded border border-border bg-background px-3 py-2 text-sm"
            autoComplete={mode === "signup" ? "new-password" : "current-password"}
            disabled={emailPending}
          />
        </div>

        {mode === "signup" && (
          <div>
            <label
              htmlFor="auth-confirm-password"
              className="mb-1 block text-sm font-medium"
            >
              Confirm password
            </label>
            <input
              id="auth-confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              className="w-full rounded border border-border bg-background px-3 py-2 text-sm"
              autoComplete="new-password"
              disabled={emailPending}
            />
          </div>
        )}

        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}

        <Button type="submit" className="w-full" disabled={emailPending}>
          {emailPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : mode === "signup" ? (
            <UserPlus className="h-4 w-4" />
          ) : (
            <LogIn className="h-4 w-4" />
          )}
          {emailPending
            ? "Submitting..."
            : mode === "signup"
              ? "Create account"
              : "Sign in with email"}
        </Button>
      </form>

      <p className="mt-4 text-center text-xs text-muted-foreground">
        {mode === "signup" ? "Already have an account? " : "No account yet? "}
        <button
          type="button"
          onClick={() => switchMode(mode === "signup" ? "signin" : "signup")}
          className="font-medium text-accent underline-offset-4 hover:underline"
        >
          {mode === "signup" ? "Sign in" : "Create one"}
        </button>
      </p>

      <Button
        type="button"
        variant="outline"
        onClick={onClose}
        className="mt-2 w-full"
      >
        Close
      </Button>
    </div>
  );
}
