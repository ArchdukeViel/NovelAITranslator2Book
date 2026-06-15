"use client";

import Link from "next/link";
import { ArrowLeft, BookOpen, Loader2 } from "lucide-react";

import { LoginPrompt } from "@/components/public/login-prompt";
import { useHistory, usePublicAuth } from "@/hooks/public";

function formatReadAt(value: string): string {
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

export default function HistoryPage() {
  const { isAuthenticated, isPending: authPending } = usePublicAuth();
  const history = useHistory({ limit: 50 });

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
        <h1 className="text-2xl font-semibold">Reading History</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Chapters you have opened while signed in.
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
          <p className="mt-1 text-xs text-muted-foreground">
            Try refreshing the page, or return to browse.
          </p>
        </section>
      ) : history.data.items.length === 0 ? (
        <section className="rounded-md border border-border bg-muted/40 p-6 text-center">
          <BookOpen className="mx-auto h-8 w-8 text-muted-foreground" />
          <p className="mt-3 text-sm font-medium">No reading history yet.</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Open a chapter while signed in and it will appear here.
          </p>
          <Link
            href="/"
            className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium underline hover:opacity-80"
          >
            Browse novels
          </Link>
        </section>
      ) : (
        <section className="divide-y rounded-md border border-border">
          {history.data.items.map((entry) => {
            const chapterHref = entry.chapter_id
              ? `/novel/${encodeURIComponent(entry.slug)}/chapter/${encodeURIComponent(entry.chapter_id)}`
              : null;
            const novelHref = `/novel/${encodeURIComponent(entry.slug)}`;

            return (
              <div
                className="flex items-center justify-between gap-3 px-4 py-3"
                key={entry.id}
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">
                    {chapterHref ? (
                      <Link href={chapterHref} className="hover:underline">
                        {entry.slug} — Ch. {entry.chapter_id}
                      </Link>
                    ) : (
                      <Link href={novelHref} className="hover:underline">
                        {entry.slug}
                      </Link>
                    )}
                  </div>
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {formatReadAt(entry.read_at)}
                  </div>
                </div>
                {chapterHref ? (
                  <Link
                    className="inline-flex h-8 items-center justify-center gap-1.5 rounded-md border px-2.5 text-xs font-medium transition-colors hover:bg-muted"
                    href={chapterHref}
                  >
                    <BookOpen className="h-3.5 w-3.5" />
                    Open
                  </Link>
                ) : (
                  <Link
                    className="inline-flex h-8 items-center justify-center gap-1.5 rounded-md border px-2.5 text-xs font-medium transition-colors hover:bg-muted"
                    href={novelHref}
                  >
                    View novel
                  </Link>
                )}
              </div>
            );
          })}
        </section>
      )}

      {isAuthenticated && (
        <div className="mt-6 text-center">
          <Link
            href="/account/library"
            className="text-sm text-muted-foreground underline hover:text-foreground transition-colors"
          >
            View My Library
          </Link>
        </div>
      )}
    </main>
  );
}
