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
      <section className="rounded-xl bg-card p-6 shadow-card dark:ring-1 dark:ring-white/5">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          Checking authentication...
        </div>
      </section>
    );
  }

  if (!isAuthenticated) {
    return (
      <section className="rounded-xl bg-card p-6 shadow-card dark:ring-1 dark:ring-white/5 space-y-4">
        <div>
          <h3 className="font-literary text-lg font-semibold text-foreground">Submit a Request</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Sign in to request novel translations or missing chapters from Japanese raw sources.
          </p>
        </div>
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
    <section className="rounded-xl bg-card p-6 shadow-card dark:ring-1 dark:ring-white/5 space-y-5">
      <div>
        <h3 className="font-literary text-lg font-semibold text-foreground">Submit a Request</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          {slug
            ? "Request a missing or untranslated chapter for this novel."
            : "Request a new Japanese web novel to be translated and added to the catalog."}
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
          variant={requestType === "novel" ? "default" : "outline"}
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
          variant={requestType === "chapter" ? "default" : "outline"}
        >
          Chapter
        </Button>
      </div>

      {/* Source URL (novel requests only) */}
      {requestType === "novel" && (
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-foreground">
            Source URL <span className="text-destructive">*</span>
          </label>
          <input
            className="h-10 w-full rounded-md border border-border/40 bg-background px-3.5 text-sm transition-colors focus:border-primary focus:outline-none"
            onChange={(event) => {
              setSourceUrl(event.target.value);
              setJustSubmitted(false);
            }}
            placeholder="https://kakuyomu.jp/works/... or https://ncode.syosetu.com/..."
            type="url"
            value={sourceUrl}
          />
          <p className="text-[11px] text-muted-foreground font-metadata">
            Direct URL from Kakuyomu, Syosetu, or Syosetu18.
          </p>
        </div>
      )}

      {/* Contextual message (chapter requests) */}
      {requestType === "chapter" && (
        <p className="rounded-md border border-border/30 bg-muted/40 px-3.5 py-2.5 text-xs text-muted-foreground">
          Creating chapter request for{" "}
          <span className="font-medium text-foreground">{slug ?? "selected novel"}</span>.
        </p>
      )}

      {/* Details textarea */}
      <div className="space-y-1.5">
        <label className="text-xs font-medium text-foreground">
          Additional Notes <span className="text-xs font-normal text-muted-foreground">(optional)</span>
        </label>
        <textarea
          className="min-h-24 w-full rounded-md border border-border/40 bg-background px-3.5 py-2.5 text-sm transition-colors focus:border-primary focus:outline-none"
          maxLength={2000}
          onChange={(event) => {
            setDetails(event.target.value);
            setJustSubmitted(false);
          }}
          placeholder="Specific chapters, alternative titles, or translator notes..."
          value={details}
        />
      </div>

      {/* Error messages */}
      {clientError && <p className="text-xs font-medium text-destructive">{clientError}</p>}
      {createRequest.error && (
        <p className="text-xs font-medium text-destructive">
          Could not submit your request. Please try again.
        </p>
      )}

      {/* Success confirmation */}
      {justSubmitted && createdRequest && (
        <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">
          ✓ Request submitted — status: {statusLabel(createdRequest.status)}.
        </p>
      )}

      <Button
        disabled={createRequest.isPending}
        onClick={submitRequest}
        type="button"
        className="gap-2"
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
