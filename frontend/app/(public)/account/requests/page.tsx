"use client";

import { useAuthMe, useRequests } from "@/hooks/public";
import { AuthGate } from "@/components/public/auth-gate";
import { RequestControl } from "@/components/public/request-control";

/**
 * User requests page — shows submitted requests and the request form.
 * Guarded behind AuthGate so only authenticated users can submit.
 *
 * Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6
 */
export default function RequestsPage() {
  const { data: authUser } = useAuthMe();
  const isUser = authUser?.role === "user";
  const { data: requests, isPending, isError } = useRequests(isUser);

  return (
    <div className="mx-auto max-w-2xl space-y-6 px-4 py-8">
      <h1 className="text-lg font-semibold">My Requests</h1>

      {/* Request form — behind AuthGate */}
      <AuthGate>
        <RequestControl />
      </AuthGate>

      {/* Requests list */}
      {isUser && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">
            Submitted Requests
          </h2>

          {isPending && (
            <p className="text-sm text-muted-foreground">Loading…</p>
          )}

          {isError && (
            <p className="text-sm text-red-600" role="alert">
              Failed to load requests.
            </p>
          )}

          {requests && requests.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No requests submitted yet.
            </p>
          )}

          {requests && requests.length > 0 && (
            <ul className="space-y-2">
              {requests.map((req) => (
                <li
                  key={req.id}
                  className="rounded-md border border-border px-3 py-2 text-sm"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium capitalize">
                      {req.request_type}
                    </span>
                    <span className="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                      {req.status}
                    </span>
                  </div>
                  {req.source_url && (
                    <p className="mt-1 truncate text-xs text-muted-foreground">
                      {req.source_url}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
