"use client";

import { useState } from "react";
import { Loader2, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import { LoginPrompt } from "@/components/public/login-prompt";
import { useCreateRequest, usePublicAuth } from "@/hooks/public";
import type { PublicRequestInput, PublicRequest } from "@/lib/public-types";

type RequestType = "novel" | "chapter";

interface RequestControlProps {
  slug?: string;
  chapterId?: string;
}

function validateRequest(
  requestType: RequestType,
  sourceUrl: string,
  slug?: string
): string | null {
  if (requestType === "novel") {
    if (!sourceUrl.trim()) {
      return "Source URL is required for novel requests.";
    }
    try {
      const parsed = new URL(sourceUrl);
      if (!["http:", "https:"].includes(parsed.protocol)) {
        return "Use an http or https source URL.";
      }
    } catch {
      return "Enter a valid source URL.";
    }
  }
  if (requestType === "chapter" && !slug) {
    return "Chapter requests require a novel page.";
  }
  return null;
}

function statusLabel(status: string): string {
  switch (status) {
    case "pending":
      return "Pending";
    case "approved":
      return "Approved";
    case "rejected":
      return "Rejected";
    case "completed":
      return "Completed";
    default:
      return status;
  }
}

export function RequestControl({ slug, chapterId }: RequestControlProps) {
  const { isAuthenticated, isPending: authPending } = usePublicAuth();
  const [requestType, setRequestType] = useState<RequestType>(
    slug ? "chapter" : "novel"
  );
  const [sourceUrl, setSourceUrl] = useState("");
  const [details, setDetails] = useState("");
  const [clientError, setClientError] = useState<string | null>(null);
  const [createdRequest, setCreatedRequest] = useState<PublicRequest | null>(null);
  const [justSubmitted, setJustSubmitted] = useState(false);
  const createRequest = useCreateRequest();

  if (authPending) {
    return (
      <section className="space-y-3 rounded-md border border-border bg-muted/40 p-4">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Checking session
        </div>
      </section>
    );
  }

  if (!isAuthenticated) {
    return (
      <section className="space-y-3 rounded-md border border-border bg-muted/40 p-4">
        <h3 className="text-sm font-medium">Request a Novel or Chapter</h3>
        <p className="text-xs text-muted-foreground">
          Sign in to request translations or new novels.
        </p>
        <LoginPrompt />
      </section>
    );
  }

  const submitRequest = () => {
    const validation = validateRequest(requestType, sourceUrl, slug);
    setClientError(validation);
    setJustSubmitted(false);
    if (validation) {
      return;
    }
    const payload: PublicRequestInput =
      requestType === "novel"
        ? {
            request_type: "novel",
            source_url: sourceUrl.trim(),
            details: details.trim() || null,
          }
        : {
            request_type: "chapter",
            slug: slug ?? null,
            chapter_id: chapterId ?? null,
            details: details.trim() || null,
          };
    createRequest.mutate(payload, {
      onSuccess: (request) => {
        setCreatedRequest(request);
        setDetails("");
        setSourceUrl("");
        setJustSubmitted(true);
      },
    });
  };

  return (
    <section className="space-y-3 rounded-md border border-border bg-muted/40 p-4">
      <div>
        <h3 className="text-sm font-medium">Request a Novel or Chapter</h3>
        <p className="text-xs text-muted-foreground">
          {slug
            ? "Request a missing or untranslated chapter for this novel."
            : "Request a new novel to be added to the catalog."}
        </p>
      </div>

      {/* Request type toggle */}
      <div className="flex flex-wrap gap-2">
        <Button
          onClick={() => {
            setRequestType("novel");
            setJustSubmitted(false);
          }}
          size="sm"
          type="button"
          variant={requestType === "novel" ? "secondary" : "outline"}
        >
          New Novel
        </Button>
        <Button
          onClick={() => {
            setRequestType("chapter");
            setJustSubmitted(false);
          }}
          size="sm"
          type="button"
          variant={requestType === "chapter" ? "secondary" : "outline"}
        >
          Chapter
        </Button>
      </div>

      {/* Source URL (novel requests only) */}
      {requestType === "novel" && (
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">
            Source URL <span className="text-destructive">*</span>
          </label>
          <input
            className="h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
            onChange={(event) => {
              setSourceUrl(event.target.value);
              setJustSubmitted(false);
            }}
            placeholder="https://example.com/novel"
            type="url"
            value={sourceUrl}
          />
          <p className="text-xs text-muted-foreground">
            Link to the original novel page you want translated.
          </p>
        </div>
      )}

      {/* Contextual message (chapter requests) */}
      {requestType === "chapter" && (
        <p className="rounded-md border border-border bg-background px-3 py-2 text-xs text-muted-foreground">
          This will create a pending chapter request for{" "}
          <span className="font-medium text-foreground">{slug ?? "this novel"}</span>.
        </p>
      )}

      {/* Details textarea */}
      <div className="space-y-1">
        <label className="text-xs font-medium text-muted-foreground">
          Details <span className="text-xs font-normal">(optional)</span>
        </label>
        <textarea
          className="min-h-20 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
          maxLength={2000}
          onChange={(event) => {
            setDetails(event.target.value);
            setJustSubmitted(false);
          }}
          placeholder="Add any additional context or notes"
          value={details}
        />
      </div>

      {/* Error messages */}
      {clientError && <p className="text-sm text-destructive">{clientError}</p>}
      {createRequest.error && (
        <p className="text-sm text-destructive">
          Could not submit your request. Try again later.
        </p>
      )}

      {/* Success confirmation */}
      {justSubmitted && createdRequest && (
        <p className="text-sm text-green-600 dark:text-green-400">
          ✓ Request submitted — {statusLabel(createdRequest.status)}.
        </p>
      )}

      <Button
        disabled={createRequest.isPending}
        onClick={submitRequest}
        type="button"
      >
        {createRequest.isPending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Send className="h-4 w-4" />
        )}
        Submit Request
      </Button>
    </section>
  );
}
