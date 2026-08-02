"use client";

import Link from "next/link";
import { Loader2, Star, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { LoginPrompt } from "@/components/public/login-prompt";
import { useDeleteReview, useMyReviews, usePublicAuth } from "@/hooks/public";
import { publicNovelHref } from "@/lib/public-routes";

function formatUpdatedAt(value: string): string {
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

function RatingStars({ rating }: { rating: number | null }) {
  if (rating == null) {
    return <span className="text-xs text-muted-foreground">Unrated</span>;
  }
  return (
    <span
      className="inline-flex items-center gap-0.5"
      role="img"
      aria-label={`${rating} star${rating === 1 ? "" : "s"} out of 5`}
    >
      {[1, 2, 3, 4, 5].map((star) => (
        <Star
          aria-hidden="true"
          className={`h-4 w-4 ${rating >= star ? "fill-accent text-accent-foreground" : "text-muted-foreground"}`}
          key={star}
        />
      ))}
    </span>
  );
}

export default function MyReviewsPage() {
  const { isAuthenticated, isPending: authPending } = usePublicAuth();
  const reviews = useMyReviews();

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-8">
        <h1 className="font-literary text-3xl font-semibold tracking-normal">My Reviews</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Reviews and ratings you have written, with links back to each novel.
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
      ) : reviews.isPending ? (
        <section className="rounded-md border border-border bg-muted/40 p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading reviews
          </div>
        </section>
      ) : reviews.isError ? (
        <section className="rounded-md border border-border bg-muted/40 p-4">
          <p className="text-sm text-destructive">Could not load your reviews.</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Try refreshing the page, or return to browse.
          </p>
        </section>
      ) : reviews.data.length === 0 ? (
        <section className="rounded-md border border-border bg-muted/40 p-6 text-center">
          <Star className="mx-auto h-8 w-8 text-muted-foreground" aria-hidden="true" />
          <p className="mt-3 text-sm font-medium">No reviews yet.</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Rate a novel from its detail page and it will show up here.
          </p>
          <Link
            href="/browse-novels"
            className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
          >
            Browse novels
          </Link>
        </section>
      ) : (
        <div className="divide-y rounded-md border border-border bg-card">
          {reviews.data.map((review) => {
            const editHref = `${publicNovelHref(review.slug)}?tab=reviews`;
            return (
              <ReviewRow
                body={review.body}
                editHref={editHref}
                key={review.slug}
                onDeleteSlug={review.slug}
                rating={review.rating}
                status={review.status}
                title={review.title}
                updatedAt={review.updated_at}
              />
            );
          })}
        </div>
      )}
    </main>
  );
}

function ReviewRow({
  body,
  editHref,
  onDeleteSlug,
  rating,
  status,
  title,
  updatedAt,
}: {
  body: string | null;
  editHref: string;
  onDeleteSlug: string;
  rating: number | null;
  status: string;
  title: string;
  updatedAt: string;
}) {
  const deleteReview = useDeleteReview(onDeleteSlug);

  return (
    <div className="px-4 py-4">
      <div className="flex items-center justify-between gap-3">
        <Link
          href={editHref}
          className="min-w-0 flex-1 truncate text-sm font-medium text-foreground hover:text-accent hover:underline"
        >
          {title}
        </Link>
        <div className="flex shrink-0 items-center gap-2">
          <span
            className={`rounded px-2 py-0.5 text-xs font-medium ${
              status === "published"
                ? "bg-success-bg text-success-text"
                : status === "rejected"
                  ? "bg-destructive/10 text-destructive"
                  : "bg-muted text-muted-foreground"
            }`}
          >
            {status === "published" ? "Published" : status === "rejected" ? "Not published" : "Pending review"}
          </span>
          <RatingStars rating={rating} />
          <Button
            aria-label={`Delete review for ${title}`}
            disabled={deleteReview.isPending}
            onClick={() => deleteReview.mutate()}
            size="sm"
            type="button"
            variant="ghost"
          >
            {deleteReview.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Trash2 className="h-4 w-4" aria-hidden="true" />
            )}
            <span className="sr-only">Delete review</span>
          </Button>
        </div>
      </div>
      {body ? (
        <p className="mt-2 text-sm leading-6 text-muted-foreground">{body}</p>
      ) : (
        <p className="mt-2 text-xs italic text-muted-foreground">No written review — rating only.</p>
      )}
      <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
        <Link href={editHref} className="font-medium text-primary hover:underline">
          Edit review
        </Link>
        <span aria-hidden="true">·</span>
        <span className="font-metadata">Updated {formatUpdatedAt(updatedAt)}</span>
      </div>
    </div>
  );
}
