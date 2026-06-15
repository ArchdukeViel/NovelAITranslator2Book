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

export function RequestControl({ slug, chapterId }: RequestControlProps) {
  const { isAuthenticated, isPending: authPending } = usePublicAuth();
  const [requestType, setRequestType] = useState<RequestType>(
    slug ? "chapter" : "novel"
  );
  const [sourceUrl, setSourceUrl] = useState("");
  const [details, setDetails] = useState("");
  const [clientError, setClientError] = useState<string | null>(null);
  const [createdRequest, setCreatedRequest] = useState<PublicRequest | null>(null);
  const createRequest = useCreateRequest();

  if (authPending) {
    return (
      <section className="rounded-md border border-border bg-muted/40 p-4">
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
        <h3 className="text-sm font-medium">Request a novel or chapter</h3>
        <LoginPrompt />
      </section>
    );
  }

  const submitRequest = () => {
    const validation = validateRequest(requestType, sourceUrl, slug);
    setClientError(validation);
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
      },
    });
  };

  return (
    <section className="space-y-3 rounded-md border border-border bg-muted/40 p-4">
      <h3 className="text-sm font-medium">Request a novel or chapter</h3>
      <div className="flex flex-wrap gap-2">
        <Button
          onClick={() => setRequestType("novel")}
          size="sm"
          type="button"
          variant={requestType === "novel" ? "secondary" : "outline"}
        >
          Novel
        </Button>
        <Button
          onClick={() => setRequestType("chapter")}
          size="sm"
          type="button"
          variant={requestType === "chapter" ? "secondary" : "outline"}
        >
          Chapter
        </Button>
      </div>
      {requestType === "novel" && (
        <input
          className="h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
          onChange={(event) => setSourceUrl(event.target.value)}
          placeholder="https://example.com/novel"
          type="url"
          value={sourceUrl}
        />
      )}
      {requestType === "chapter" && (
        <p className="text-sm text-muted-foreground">
          This will create a pending chapter request for {slug ?? "this novel"}.
        </p>
      )}
      <textarea
        className="min-h-20 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
        maxLength={2000}
        onChange={(event) => setDetails(event.target.value)}
        placeholder="Optional details"
        value={details}
      />
      {clientError && <p className="text-sm text-destructive">{clientError}</p>}
      {createRequest.error && (
        <p className="text-sm text-destructive">Request could not be submitted.</p>
      )}
      {createdRequest && (
        <p className="text-sm text-muted-foreground">
          Request #{createdRequest.id} is {createdRequest.status}.
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
