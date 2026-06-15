"use client";

import Link from "next/link";
import { ArrowLeft, Loader2, MessageSquare } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { LoginPrompt } from "@/components/public/login-prompt";
import { RequestControl } from "@/components/public/request-control";
import { usePublicAuth, useRequests } from "@/hooks/public";

function formatCreatedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
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

function statusTone(status: string): "amber" | "green" | "red" | "neutral" {
  switch (status) {
    case "pending":
      return "amber";
    case "approved":
      return "green";
    case "rejected":
      return "red";
    case "completed":
      return "green";
    default:
      return "neutral";
  }
}

export default function RequestsPage() {
  const { isAuthenticated, isPending: authPending } = usePublicAuth();
  const requests = useRequests({ limit: 50 });

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <Link
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
        href="/"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Browse
      </Link>

      <header className="mt-6 mb-4">
        <h1 className="text-2xl font-semibold">My Requests</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Novel and chapter translation requests you have submitted.
        </p>
      </header>

      {authPending ? (
        <section className="rounded-md border border-border bg-muted/40 p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Checking session
          </div>
        </section>
      ) : !isAuthenticated ? (
        <LoginPrompt />
      ) : (
        <div className="space-y-6">
          <RequestControl />

          <section className="space-y-3">
            <h2 className="text-sm font-medium">Recent requests</h2>
            {requests.isPending ? (
              <div className="flex items-center gap-2 rounded-md border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading requests
              </div>
            ) : requests.isError ? (
              <div className="rounded-md border border-border bg-muted/40 p-4">
                <p className="text-sm text-destructive">
                  Could not load requests.
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Try refreshing the page, or return to browse.
                </p>
              </div>
            ) : requests.data.items.length === 0 ? (
              <section className="rounded-md border border-border bg-muted/40 p-6 text-center">
                <MessageSquare className="mx-auto h-8 w-8 text-muted-foreground" />
                <p className="mt-3 text-sm font-medium">No requests yet.</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Use the form above to request a novel or chapter translation.
                </p>
                <Link
                  href="/"
                  className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium underline hover:opacity-80"
                >
                  Browse novels
                </Link>
              </section>
            ) : (
              <div className="divide-y rounded-md border border-border">
                {requests.data.items.map((request) => {
                  const novelHref = request.slug
                    ? `/novel/${encodeURIComponent(request.slug)}`
                    : null;
                  return (
                    <div className="px-4 py-3" key={request.id}>
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm font-medium capitalize">
                          {request.request_type} request
                        </span>
                        <Badge tone={statusTone(request.status)}>
                          {statusLabel(request.status)}
                        </Badge>
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {request.slug ? (
                          <Link
                            href={novelHref!}
                            className="font-medium text-foreground hover:underline"
                          >
                            {request.slug}
                          </Link>
                        ) : request.source_url ? (
                          <span className="font-medium text-foreground">
                            {request.source_url}
                          </span>
                        ) : (
                          <span>Request</span>
                        )}
                        <span className="mx-1">·</span>
                        <span>{formatCreatedAt(request.created_at)}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
