"use client";

import Link from "next/link";
import { ArrowLeft, BookOpen, Loader2 } from "lucide-react";

import { LoginPrompt } from "@/components/public/login-prompt";
import { useHistory, usePublicAuth } from "@/hooks/public";
import { publicChapterHref, publicNovelHref } from "@/lib/public-routes";

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
        className="inline-flex min-h-11 items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary rounded-xs"
        href="/browse-novels"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Browse
      </Link>

      <header className="mt-6 mb-6">
        <h1 className="font-literary text-3xl font-semibold tracking-normal">
          Reading History
        </h1>
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
        <section className="rounded-xl border border-border/70 bg-card/70 p-8 text-center shadow-card">
          <BookOpen className="mx-auto h-8 w-8 text-muted-foreground" />
          <p className="mt-3 font-literary text-base font-medium text-foreground">No reading history yet.</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Open a chapter while signed in and it will appear here.
          </p>
          <Link
            href="/browse-novels"
            className="mt-4 inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-primary underline hover:text-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary rounded-xs"
          >
            Browse novels
          </Link>
        </section>
      ) : (
        <section className="divide-y divide-border/60 rounded-xl border border-border/70 bg-card/70 shadow-card">
          {history.data.items.map((entry) => {
            const chapterHref = entry.chapter_id
              ? publicChapterHref(entry.slug, entry.chapter_id)
              : null;
            const novelHref = publicNovelHref(entry.slug);

            return (
              <div
                className="flex items-center justify-between gap-3 px-5 py-3.5"
                key={entry.id}
              >
                <div className="min-w-0">
                  <div className="truncate font-literary text-base font-medium text-foreground">
                    {chapterHref ? (
                      <Link
                        href={chapterHref}
                        className="transition-colors hover:text-primary focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary rounded-xs"
                      >
                        {entry.chapter_number != null
                          ? `${entry.slug} - Ch. ${entry.chapter_number}`
                          : `${entry.slug} - Chapter`}
                      </Link>
                    ) : (
                      <Link
                        href={novelHref}
                        className="transition-colors hover:text-primary focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary rounded-xs"
                      >
                        {entry.slug}
                      </Link>
                    )}
                  </div>
                  <div className="mt-0.5 font-metadata text-xs text-muted-foreground">
                    {formatReadAt(entry.read_at)}
                  </div>
                </div>
                {chapterHref ? (
                  <Link
                    className="inline-flex min-h-11 shrink-0 items-center justify-center gap-1.5 rounded-lg border border-border/70 bg-card px-4 text-sm font-medium text-foreground transition-colors hover:bg-muted focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary"
                    href={chapterHref}
                  >
                    <BookOpen className="h-4 w-4" />
                    Open
                  </Link>
                ) : (
                  <Link
                    className="inline-flex min-h-11 shrink-0 items-center justify-center gap-1.5 rounded-lg border border-border/70 bg-card px-4 text-sm font-medium text-foreground transition-colors hover:bg-muted focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary"
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
            className="inline-flex min-h-11 items-center text-sm font-medium text-muted-foreground underline transition-colors hover:text-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary rounded-xs"
          >
            View My Library
          </Link>
        </div>
      )}
    </main>
  );
}
