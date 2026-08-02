"use client";

import { useState } from "react";

import { useNovelReviews } from "@/hooks/public";
import type { PublicReviewItem } from "@/lib/public-types";

export function ReviewCard({ review }: { review: PublicReviewItem }) {
  return (
    <article className="rounded-md border border-border bg-muted/40 p-4">
      {review.rating != null && (
        <div className="mb-2 text-xs text-muted-foreground">
          {"★".repeat(review.rating)}
          <span className="text-muted-foreground/40">{"★".repeat(5 - review.rating)}</span>
        </div>
      )}
      {review.body ? (
        <p className="text-sm leading-6 text-foreground">{review.body}</p>
      ) : (
        <p className="text-xs italic text-muted-foreground">Rating only.</p>
      )}
      <p className="mt-2 text-xs text-muted-foreground">
        {new Date(review.created_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}
      </p>
    </article>
  );
}

export function CommunityReviews({ slug }: { slug: string }) {
  const [cursor, setCursor] = useState<string | null>(null);
  const [allItems, setAllItems] = useState<PublicReviewItem[]>([]);
  const page = useNovelReviews(slug, cursor);

  const items = cursor ? [...allItems, ...(page.data?.items ?? [])] : (page.data?.items ?? []);

  return (
    <section className="space-y-4">
      <h3 className="text-sm font-medium">Community Reviews</h3>
      {page.isLoading && <p className="text-xs text-muted-foreground">Loading reviews…</p>}
      {page.isError && !page.isLoading && <p className="text-xs text-destructive">Could not load reviews.</p>}
      {!page.isLoading && !page.isError && items.length === 0 && (
        <p className="text-xs text-muted-foreground">No published reviews yet. Be the first to share your thoughts.</p>
      )}
      {!page.isError && items.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {items.map((review) => (
            <ReviewCard key={review.id} review={review} />
          ))}
        </div>
      )}
      {page.data?.next_cursor && (
        <button
          className="rounded-md border border-border px-4 py-2 text-sm"
          disabled={page.isFetching}
          onClick={() => {
            setAllItems(items);
            setCursor(page.data.next_cursor);
          }}
          type="button"
        >
          {page.isFetching ? "Loading…" : "Load more"}
        </button>
      )}
    </section>
  );
}
