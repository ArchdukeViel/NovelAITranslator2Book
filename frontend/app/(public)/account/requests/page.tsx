"use client";

import { useState } from "react";
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
  const [statusFilter, setStatusFilter] = useState("all");

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <Link
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
        href="/browse-novels"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Browse
      </Link>

      <header className="mt-6 mb-8">
        <h1 className="text-3xl font-semibold tracking-normal font-literary">My Requests</h1>
        <p className="mt-2 text-sm text-muted-foreground">
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
        <div className="space-y-8">
          <RequestControl />

          <section className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-xl font-semibold font-literary">Full request history</h2>
              <div className="flex flex-wrap gap-2" role="group" aria-label="Filter requests by status">
                {["all", "pending", "approved", "rejected", "completed"].map((status) => (
                  <button
                    className={`rounded-md border px-3 py-1.5 text-xs font-metadata capitalize transition-colors ${
                      statusFilter === status
                        ? "bg-primary text-primary-foreground"
                        : "bg-background text-muted-foreground hover:bg-muted"
                    }`}
                    key={status}
                    onClick={() => setStatusFilter(status)}
                    type="button"
                    aria-pressed={statusFilter === status}
                  >
                    {status}
                  </button>
                ))}
              </div>
            </div>
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
            ) : requests.data.items.filter((request) => statusFilter === "all" || request.status === statusFilter).length === 0 ? (
              <section className="rounded-md border border-border bg-muted/40 p-6 text-center">
                <MessageSquare className="mx-auto h-8 w-8 text-muted-foreground" />
                <p className="mt-3 text-sm font-medium">No matching requests.</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Use the form above to request a novel or chapter translation, or change the status filter.
                </p>
                <Link
                  href="/browse-novels"
                  className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-accent underline hover:text-foreground"
                >
                  Browse novels
                </Link>
              </section>
            ) : (
              <div className="divide-y rounded-md border border-border bg-card">
                {requests.data.items.filter((request) => statusFilter === "all" || request.status === statusFilter).map((request) => {
                  const novelHref = request.slug
                    ? `/novel/${encodeURIComponent(request.slug)}`
                    : null;
                  return (
                    <div className="px-4 py-4" key={request.id}>
                      <div className="flex items-center justify-between gap-3">
                        <span className="min-w-0 flex-1 text-sm font-medium capitalize">
                          {request.request_type} request
                        </span>
                        <Badge className="shrink-0 font-metadata" tone={statusTone(request.status)}>
                          {statusLabel(request.status)}
                        </Badge>
                      </div>
                      <div className="mt-2 text-xs text-muted-foreground">
                        {request.slug ? (
                          <Link
                            href={novelHref!}
                            className="font-medium text-foreground hover:text-accent hover:underline"
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
                        <span className="font-metadata">{formatCreatedAt(request.created_at)}</span>
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
