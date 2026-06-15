"use client";

import { useState } from "react";
import { Loader2, Key, Trash2, AlertCircle } from "lucide-react";

import {
  useContribution,
  useSubmitContribution,
  useRemoveContribution,
} from "@/hooks/public";
import { toReaderError, mapContributionStatus } from "@/lib/public-format";
import { ApiError } from "@/lib/api";

/**
 * Contribution_View — allows a Public_User to submit, view, or remove
 * their translation provider API credential contribution.
 *
 * Security invariants:
 * - Raw credential is ONLY held in local React state and cleared after submit.
 * - NEVER persisted in localStorage, sessionStorage, or Zustand store (Req 17.6).
 * - Displayed credential uses server-returned masked_value (Req 17.7).
 *
 * Requirements validated: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7, 17.8,
 *                         17.9, 17.10, 17.11, 17.12, 17.13, 17.14, 17.15
 */
export function ContributionView() {
  const contribution = useContribution(true);
  const submitContribution = useSubmitContribution();
  const removeContribution = useRemoveContribution();

  // Raw key is ONLY held in component state — never persisted anywhere.
  const [rawKey, setRawKey] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Backend unavailable handling (404 or connection errors)
  if (contribution.isError) {
    const err = contribution.error;
    if (
      err instanceof ApiError &&
      (err.status === 404 || err.status === 0)
    ) {
      return (
        <div className="rounded-md border border-border bg-muted/50 p-6 text-center">
          <AlertCircle className="mx-auto h-8 w-8 text-muted-foreground" />
          <p className="mt-3 text-sm text-muted-foreground">
            This feature is not yet available. Please check back later.
          </p>
        </div>
      );
    }

    // Connection error (TypeError from fetch)
    if (
      !(err instanceof ApiError) &&
      err instanceof Error &&
      (err.message.includes("fetch") || err.message.includes("network"))
    ) {
      return (
        <div className="rounded-md border border-border bg-muted/50 p-6 text-center">
          <AlertCircle className="mx-auto h-8 w-8 text-muted-foreground" />
          <p className="mt-3 text-sm text-muted-foreground">
            This feature is not yet available. Please check back later.
          </p>
        </div>
      );
    }

    // Other errors: sanitized error message
    return (
      <div className="rounded-md border border-destructive/50 bg-destructive/5 p-4">
        <p className="text-sm text-destructive">{toReaderError(err)}</p>
      </div>
    );
  }

  // Loading state
  if (contribution.isPending) {
    return (
      <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span>Loading contribution status…</span>
      </div>
    );
  }

  const data = contribution.data;

  // When a contribution exists: show status, masked value, remove button
  if (data?.present) {
    const status = mapContributionStatus(data.status);

    return (
      <div className="flex flex-col gap-4">
        <div className="rounded-md border border-border p-4">
          <div className="flex flex-col gap-3">
            {/* Masked credential display */}
            <div className="flex items-center gap-2">
              <Key className="h-4 w-4 text-muted-foreground" />
              <span className="font-mono text-sm">
                {data.masked_value ?? "••••••"}
              </span>
            </div>

            {/* Contribution status */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Status:</span>
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                  status === "Working"
                    ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                    : status === "Failed"
                      ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                      : status === "Checking"
                        ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400"
                        : "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400"
                }`}
              >
                {status === "Checking" && (
                  <Loader2 className="h-3 w-3 animate-spin" />
                )}
                {status}
              </span>
            </div>

            {/* Provider info if available */}
            {data.provider && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">Provider:</span>
                <span className="text-xs">{data.provider}</span>
              </div>
            )}
          </div>

          {/* Remove button */}
          <div className="mt-4 border-t border-border pt-4">
            <button
              className="inline-flex items-center gap-1.5 rounded-md border border-destructive/50 px-3 py-1.5 text-sm font-medium text-destructive hover:bg-destructive/10 disabled:opacity-50"
              disabled={removeContribution.isPending}
              onClick={() => {
                setErrorMessage(null);
                removeContribution.mutate(undefined, {
                  onError: (error) => {
                    setErrorMessage(toReaderError(error));
                  },
                });
              }}
              type="button"
            >
              <Trash2 className="h-4 w-4" />
              {removeContribution.isPending ? "Removing…" : "Remove"}
            </button>
          </div>
        </div>

        <p className="text-xs text-muted-foreground">
          Your contributed credential is used to assist translation per platform
          policy. It does not grant access to any other user&apos;s credential or
          to the platform owner&apos;s credential.
        </p>

        {errorMessage && (
          <p className="text-xs text-destructive">{errorMessage}</p>
        )}
      </div>
    );
  }

  // When no contribution exists: show submission form
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Contribute your translation provider API key to help the platform
        translate novels. Your key is sent securely to the server and is never
        stored in your browser.
      </p>

      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (!rawKey.trim()) return;
          setErrorMessage(null);
          submitContribution.mutate(rawKey.trim(), {
            onSuccess: () => {
              // Clear raw key from component state after successful submit
              setRawKey("");
            },
            onError: (error) => {
              setErrorMessage(toReaderError(error));
            },
          });
        }}
      >
        <div className="flex flex-col gap-1.5">
          <label
            className="text-sm font-medium"
            htmlFor="contribution-key-input"
          >
            API Key
          </label>
          <input
            autoComplete="off"
            className="rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            id="contribution-key-input"
            onChange={(e) => setRawKey(e.target.value)}
            placeholder="Enter your provider API key"
            type="password"
            value={rawKey}
          />
        </div>

        <button
          className="inline-flex items-center justify-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          disabled={!rawKey.trim() || submitContribution.isPending}
          type="submit"
        >
          <Key className="h-4 w-4" />
          {submitContribution.isPending ? "Submitting…" : "Submit Credential"}
        </button>
      </form>

      <p className="text-xs text-muted-foreground">
        Your contributed credential is used to assist translation per platform
        policy. It does not grant access to any other user&apos;s credential or
        to the platform owner&apos;s credential.
      </p>

      {errorMessage && (
        <p className="text-xs text-destructive">{errorMessage}</p>
      )}
    </div>
  );
}
