"use client";

import { Loader2 } from "lucide-react";

import { LoginPrompt } from "@/components/public/login-prompt";
import { RequestControl } from "@/components/public/request-control";
import { usePublicAuth, useRequests } from "@/hooks/public";

function formatCreatedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export default function RequestsPage() {
  const { isAuthenticated, isPending: authPending } = usePublicAuth();
  const requests = useRequests({ limit: 50 });

  return (
    <div className="mx-auto max-w-2xl space-y-6 px-4 py-8">
      <h1 className="text-lg font-semibold">My Requests</h1>

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
        <>
          <RequestControl />
          <section className="space-y-3">
            <h2 className="text-sm font-medium">Recent requests</h2>
            {requests.isPending ? (
              <div className="flex items-center gap-2 rounded-md border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading requests
              </div>
            ) : requests.isError ? (
              <div className="rounded-md border border-border bg-muted/40 p-4 text-sm text-destructive">
                Could not load requests.
              </div>
            ) : requests.data.items.length === 0 ? (
              <div className="rounded-md border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
                No requests yet.
              </div>
            ) : (
              <div className="divide-y rounded-md border border-border">
                {requests.data.items.map((request) => (
                  <div className="px-4 py-3" key={request.id}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm font-medium">
                        {request.request_type}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {request.status}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {request.slug ?? request.source_url ?? "Request"} -{" "}
                      {formatCreatedAt(request.created_at)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
