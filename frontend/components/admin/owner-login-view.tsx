"use client";

import { useState, type FormEvent } from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { adminAuth } from "@/lib/api";
import { ApiError } from "@/lib/api";

interface OwnerLoginViewProps {
  onSuccess: () => void;
}

/**
 * Owner login view for the Admin_Workspace.
 * - Collects the owner login secret (bootstrap secret)
 * - Calls POST /api/auth/login via adminAuth.ownerBootstrapLogin()
 * - On invalid secret: renders Error_State, establishes no session
 * - Never persists a token in JS-accessible storage
 * - Session is carried by HTTP-only cookie set by backend
 */
export function OwnerLoginView({ onSuccess }: OwnerLoginViewProps) {
  const [secret, setSecret] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isPending, setIsPending] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setErrorMessage(null);

    if (!secret.trim()) {
      setErrorMessage("Login secret is required.");
      return;
    }

    setIsPending(true);
    try {
      await adminAuth.ownerBootstrapLogin(secret);
      onSuccess();
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setErrorMessage("Invalid login secret. Please try again.");
      } else {
        setErrorMessage("Owner login failed. Please try again later.");
      }
    } finally {
      setIsPending(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-8">
      <Panel className="w-full max-w-md">
        <PanelHeader>
          <PanelTitle>Admin Sign In</PanelTitle>
        </PanelHeader>
        <PanelBody className="space-y-4">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="owner-secret" className="text-sm font-medium">
                Owner Login Secret
              </label>
              <Input
                id="owner-secret"
                type="password"
                placeholder="Enter owner bootstrap secret"
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
                required
                autoComplete="current-password"
                disabled={isPending}
              />
            </div>

            {errorMessage && (
              <p className="text-sm text-destructive" role="alert">
                {errorMessage}
              </p>
            )}

            <Button type="submit" className="w-full" disabled={isPending}>
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Sign In
            </Button>
          </form>
        </PanelBody>
      </Panel>
    </div>
  );
}
