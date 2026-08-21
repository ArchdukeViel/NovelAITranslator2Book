"use client";

import { useEffect, useState } from "react";
import { BookOpen, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  usePasswordLogin,
  useRegister,
  useStartGoogleOAuth,
} from "@/hooks/public/use-auth";
import { authApi } from "@/lib/public-api";
import { ApiError } from "@/lib/api";

interface LoginViewProps {
  onClose?: () => void;
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

function GoogleIcon() {
  return (
    <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17Z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.25v3.15C3.26 21.36 7.33 24 12 24Z"
      />
      <path
        fill="#FBBC05"
        d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.25C.45 8.18 0 9.99 0 12s.45 3.82 1.25 5.42l4.03-3.15Z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.33 0 3.26 2.64 1.25 6.58l4.03 3.15c.95-2.83 3.6-4.98 6.72-4.98Z"
      />
    </svg>
  );
}

/**
 * Public reader account panel with Google and email/password auth.
 */
export function LoginView({
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
    queueMicrotask(() => {
      setMode(initialMode);
      setError(null);
    });
  }, [initialMode]);

  function switchMode(nextMode: EmailMode) {
    setMode(nextMode);
    setError(null);
    onModeChange?.(nextMode);
  }

  const handleGoogleLogin = async () => {
    setError(null);
    try {
      const result = await authApi.googleStartCheck();
      if (!result.available) {
        setGoogleUnavailable(true);
        return;
      }
      startGoogleOAuth();
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setGoogleUnavailable(true);
        return;
      }
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
          : "Invalid email or password.",
      );
    }
  };

  return (
    <div className="w-full max-w-[440px] rounded-2xl border border-border/80 bg-card p-6 sm:p-8 text-card-foreground shadow-xl">
      {/* Brand Icon & Heading */}
      <div className="mb-8 text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/80 to-primary text-primary-foreground shadow-md shadow-primary/20">
          <BookOpen className="h-8 w-8" aria-hidden="true" />
        </div>
        <h1 className="font-literary text-2xl font-bold tracking-tight text-foreground">
          {mode === "signup"
            ? "Create your Dokushodo account"
            : "Sign in to Dokushodo"}
        </h1>
        <p className="mt-1.5 text-sm text-muted-foreground">
          {mode === "signup"
            ? "Create an account to continue"
            : "Sign in to continue"}
        </p>
      </div>

      {/* OAuth Section */}
      <div className="space-y-3">
        {googleUnavailable ? (
          <p className="rounded-lg border border-border bg-muted/40 p-3 text-center text-xs text-muted-foreground">
            Google sign-in is not available right now. You can still use email
            and password.
          </p>
        ) : (
          <Button
            type="button"
            variant="outline"
            onClick={handleGoogleLogin}
            className="flex h-11 w-full items-center justify-center gap-3 rounded-lg border-border/80 bg-background text-sm font-medium text-foreground transition-all hover:bg-muted/60 hover:shadow-xs"
          >
            <GoogleIcon />
            <span>Continue with Google</span>
          </Button>
        )}
      </div>

      {/* Divider */}
      <div className="relative my-6 text-center">
        <div className="absolute inset-0 flex items-center" aria-hidden="true">
          <div className="w-full border-t border-border/60" />
        </div>
        <span className="relative bg-card px-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Or continue with email
        </span>
      </div>

      {/* Email Form */}
      <form onSubmit={handleEmailAuth} className="space-y-4" noValidate>
        <div>
          <label
            htmlFor="auth-email"
            className="mb-1.5 block text-xs font-medium text-foreground"
          >
            Email
          </label>
          <input
            id="auth-email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="Enter your email address"
            className="h-11 w-full rounded-lg border border-border/80 bg-background px-3.5 text-sm transition-colors placeholder:text-muted-foreground/60 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
            autoComplete="email"
            disabled={emailPending}
          />
        </div>

        <div>
          <label
            htmlFor="auth-password"
            className="mb-1.5 block text-xs font-medium text-foreground"
          >
            Password
          </label>
          <input
            id="auth-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder={
              mode === "signup"
                ? "Create a password (min. 10 chars)"
                : "Enter your password"
            }
            className="h-11 w-full rounded-lg border border-border/80 bg-background px-3.5 text-sm transition-colors placeholder:text-muted-foreground/60 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
            autoComplete={
              mode === "signup" ? "new-password" : "current-password"
            }
            disabled={emailPending}
          />
        </div>

        {mode === "signup" && (
          <div>
            <label
              htmlFor="auth-confirm-password"
              className="mb-1.5 block text-xs font-medium text-foreground"
            >
              Confirm password
            </label>
            <input
              id="auth-confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              placeholder="Re-enter your password"
              className="h-11 w-full rounded-lg border border-border/80 bg-background px-3.5 text-sm transition-colors placeholder:text-muted-foreground/60 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
              autoComplete="new-password"
              disabled={emailPending}
            />
          </div>
        )}

        {error && (
          <p className="text-xs font-medium text-destructive" role="alert">
            {error}
          </p>
        )}

        <Button
          type="submit"
          className="h-11 w-full rounded-lg text-sm font-medium transition-all"
          disabled={emailPending}
        >
          {emailPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : null}
          {emailPending
            ? "Submitting..."
            : mode === "signup"
              ? "Create account"
              : "Sign in with email"}
        </Button>
      </form>

      {/* Switch Mode Footer */}
      <p className="mt-6 text-center text-xs text-muted-foreground">
        {mode === "signup" ? "Already have an account? " : "No account yet? "}
        <button
          type="button"
          onClick={() => switchMode(mode === "signup" ? "signin" : "signup")}
          className="font-medium text-primary underline-offset-4 hover:underline"
        >
          {mode === "signup" ? "Sign in" : "Create one"}
        </button>
      </p>

      <p className="mt-3 text-center text-xs text-muted-foreground/80">
        Guest reading is always available without sign-in.
      </p>
    </div>
  );
}
