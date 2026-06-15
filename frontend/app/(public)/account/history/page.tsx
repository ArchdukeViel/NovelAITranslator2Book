"use client";

import Link from "next/link";
import { Loader2 } from "lucide-react";

import { LoginPrompt } from "@/components/public/login-prompt";
import { useHistory, usePublicAuth } from "@/hooks/public";

function formatReadAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export default function HistoryPage() {
  const { isAuthenticated, isPending: authPending } = usePublicAuth();
  const history = useHistory({ limit: 50 });

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="mb-4 text-2xl font-semibold">Reading History</h1>

      {authPending ? (
        <section className="rounded-md border border-border bg-muted/40 p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Checking session
          </div>
        </section>
      ) : !isAuthenticated ? (
        <LoginPrompt />
      ) : history.isPending ? (
        <section className="rounded-md border border-border bg-muted/40 p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading reading history
          </div>
        </section>
      ) : history.isError ? (
        <section className="rounded-md border border-border bg-muted/40 p-4">
          <p className="text-sm text-destructive">
            Could not load reading history.
          </p>
        </section>
      ) : history.data.items.length === 0 ? (
        <section className="rounded-md border border-border bg-muted/40 p-4">
          <p className="text-sm font-medium">No reading history yet.</p>
          <p className="mt-2 text-sm text-muted-foreground">
            Open a chapter while signed in and it will appear here.
          </p>
        </section>
      ) : (
        <section className="divide-y rounded-md border border-border">
          {history.data.items.map((entry) => (
            <Link
              className="block px-4 py-3 transition-colors hover:bg-muted/50"
              href={
                entry.chapter_id
                  ? `/novel/${encodeURIComponent(entry.slug)}/chapter/${encodeURIComponent(entry.chapter_id)}`
                  : `/novel/${encodeURIComponent(entry.slug)}`
              }
              key={entry.id}
            >
              <div className="text-sm font-medium">{entry.slug}</div>
              <div className="mt-1 text-xs text-muted-foreground">
                {entry.chapter_id ? `Chapter ${entry.chapter_id} - ` : ""}
                {formatReadAt(entry.read_at)}
              </div>
            </Link>
          ))}
        </section>
      )}
    </div>
  );
}
