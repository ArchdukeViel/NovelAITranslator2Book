"use client";

import { Star } from "lucide-react";

interface RatingReviewProps {
  slug: string;
}

export function RatingReview({ slug: _slug }: RatingReviewProps) {
  return (
    <section className="space-y-3 rounded-md border border-border bg-muted/40 p-4">
      <h3 className="text-sm font-medium">Reviews are not available yet.</h3>
      <div className="flex items-center gap-1 text-muted-foreground" aria-hidden="true">
        {[1, 2, 3, 4, 5].map((star) => (
          <Star key={star} className="h-5 w-5" />
        ))}
      </div>
      <p className="text-sm text-muted-foreground">
        Public accounts are not available yet. Guest reading is still available.
      </p>
      <button
        className="inline-flex h-9 items-center justify-center rounded-md border px-4 text-sm font-medium opacity-60"
        disabled
        type="button"
      >
        Submit Review Unavailable
      </button>
    </section>
  );
}
