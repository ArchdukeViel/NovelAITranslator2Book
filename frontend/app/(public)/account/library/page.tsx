"use client";

import Link from "next/link";
import { ArrowLeft, BookOpen, Bookmark, Loader2 } from "lucide-react";

import { LoginPrompt } from "@/components/public/login-prompt";
import { useHistory, useLibrary, useRemoveFromLibrary, usePublicAuth } from "@/hooks/public";

function formatAddedAt(value: string): string {
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
    case "reading":
      return "Reading";
    case "completed":
      return "Completed";
    case "paused":
      return "Paused";
    default:
      return status;
  }
}

export default function LibraryPage() {
  const { isAuthenticated, isPending: authPending } = usePublicAuth();
  const library = useLibrary();
  const history = useHistory({ limit: 50 });

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <Link
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
        href="/browse-novels"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Browse
      </Link>

      <header className="mt-6 mb-4">
        <h1 className="text-2xl font-semibold">My Library</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Novels you have saved for later.
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
      ) : library.isPending ? (
        <section className="rounded-md border border-border bg-muted/40 p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading library
          </div>
        </section>
      ) : library.isError ? (
        <section className="rounded-md border border-border bg-muted/40 p-4">
          <p className="text-sm text-destructive">
            Could not load your library.
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Try refreshing the page, or return to browse.
          </p>
        </section>
      ) : (
        <div className="space-y-6">
          <LibrarySection
            emptyDescription="Save a novel from its detail page and it will appear here."
            emptyTitle="No currently reading novels yet."
            items={library.data.filter((item) => item.status !== "paused")}
            title="Currently Reading"
          />

          <section>
            <h2 className="mb-2 text-sm font-medium">Reading History</h2>
            {history.isPending ? (
              <div className="flex items-center gap-2 rounded-md border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading reading history
              </div>
            ) : history.isError ? (
              <div className="rounded-md border border-border bg-muted/40 p-4">
                <p className="text-sm text-destructive">
                  Could not load reading history.
                </p>
              </div>
            ) : history.data.items.length === 0 ? (
              <EmptyLibraryState
                description="Open a chapter while signed in and it will appear here."
                title="No reading history yet."
              />
            ) : (
              <div className="divide-y rounded-md border border-border">
                {history.data.items.map((entry) => {
                  const chapterHref = entry.chapter_id
                    ? `/novels/${encodeURIComponent(entry.slug)}/chapter/${encodeURIComponent(entry.chapter_id)}`
                    : null;
                  const novelHref = `/novels/${encodeURIComponent(entry.slug)}`;
                  return (
                    <div className="flex items-center justify-between gap-3 px-4 py-3" key={entry.id}>
                      <div className="min-w-0">
                        <Link href={chapterHref ?? novelHref} className="truncate text-sm font-medium hover:underline">
                          {entry.chapter_id ? `${entry.slug} - Ch. ${entry.chapter_id}` : entry.slug}
                        </Link>
                        <div className="mt-0.5 text-xs text-muted-foreground">
                          {formatAddedAt(entry.read_at)}
                        </div>
                      </div>
                      <Link
                        className="inline-flex h-8 shrink-0 items-center justify-center gap-1.5 rounded-md border px-2.5 text-xs font-medium transition-colors hover:bg-muted"
                        href={chapterHref ?? novelHref}
                      >
                        <BookOpen className="h-3.5 w-3.5" />
                        Open
                      </Link>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          <LibrarySection
            emptyDescription="Paused or dropped novels will appear here when the backend marks them that way."
            emptyTitle="No dropped novels yet."
            items={library.data.filter((item) => item.status === "paused")}
            title="Dropped"
          />

          <section>
            <h2 className="mb-2 text-sm font-medium">Updates</h2>
            <EmptyLibraryState
              description="Update alerts are not connected to a public backend feed yet."
              title="No update feed available yet."
            />
          </section>
        </div>
      )}
    </main>
  );
}

function EmptyLibraryState({
  description,
  title,
}: {
  description: string;
  title: string;
}) {
  return (
    <section className="rounded-md border border-border bg-muted/40 p-6 text-center">
      <Bookmark className="mx-auto h-8 w-8 text-muted-foreground" />
      <p className="mt-3 text-sm font-medium">{title}</p>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      <Link
        href="/browse-novels"
        className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium underline hover:opacity-80"
      >
        Browse novels
      </Link>
    </section>
  );
}

function LibrarySection({
  emptyDescription,
  emptyTitle,
  items,
  title,
}: {
  emptyDescription: string;
  emptyTitle: string;
  items: { slug: string; status: string; added_at: string }[];
  title: string;
}) {
  return (
    <section>
      <h2 className="mb-2 text-sm font-medium">{title}</h2>
      {items.length === 0 ? (
        <EmptyLibraryState description={emptyDescription} title={emptyTitle} />
      ) : (
        <div className="divide-y rounded-md border border-border">
          {items.map((item) => (
            <LibraryRow key={item.slug} item={item} />
          ))}
        </div>
      )}
    </section>
  );
}

function LibraryRow({ item }: { item: { slug: string; status: string; added_at: string } }) {
  const removeFromLibrary = useRemoveFromLibrary(item.slug);
  const novelHref = `/novels/${encodeURIComponent(item.slug)}`;

  return (
    <div className="flex items-center justify-between gap-3 px-4 py-3">
      <div className="min-w-0">
        <Link href={novelHref} className="truncate text-sm font-medium hover:underline">
          {item.slug}
        </Link>
        <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
          <span className="rounded bg-muted px-1.5 py-0.5 text-xs font-medium">
            {statusLabel(item.status)}
          </span>
          <span>{formatAddedAt(item.added_at)}</span>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Link
          className="inline-flex h-8 items-center justify-center gap-1.5 rounded-md border px-2.5 text-xs font-medium transition-colors hover:bg-muted"
          href={novelHref}
        >
          <BookOpen className="h-3.5 w-3.5" />
          View
        </Link>
        <button
          className="inline-flex h-8 items-center justify-center rounded-md border border-destructive/40 px-2.5 text-xs font-medium text-destructive transition-colors hover:bg-destructive/10"
          disabled={removeFromLibrary.isPending}
          onClick={() => removeFromLibrary.mutate()}
          type="button"
        >
          {removeFromLibrary.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            "Remove"
          )}
        </button>
      </div>
    </div>
  );
}
