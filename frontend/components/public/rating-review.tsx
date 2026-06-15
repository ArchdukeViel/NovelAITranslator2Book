"use client";

import { useState } from "react";
import { Loader2, Star, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { LoginPrompt } from "@/components/public/login-prompt";
import { useDeleteReview, usePublicAuth, useUpsertReview } from "@/hooks/public";
import type { ReviewResponse } from "@/lib/public-types";

interface RatingReviewProps {
  slug: string;
}

function validateReview(rating: number, body: string): string | null {
  if (!Number.isInteger(rating) || rating < 1 || rating > 5) {
    return "Choose a rating from 1 to 5.";
  }
  if (body.length > 5000) {
    return "Review text must be 5000 characters or fewer.";
  }
  return null;
}

export function RatingReview({ slug }: RatingReviewProps) {
  const { isAuthenticated, isPending: authPending } = usePublicAuth();
  const [rating, setRating] = useState(0);
  const [body, setBody] = useState("");
  const [clientError, setClientError] = useState<string | null>(null);
  const [savedReview, setSavedReview] = useState<ReviewResponse | null>(null);
  const upsertReview = useUpsertReview(slug);
  const deleteReview = useDeleteReview(slug);

  if (authPending) {
    return (
      <section className="rounded-md border border-border bg-muted/40 p-4">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Checking session
        </div>
      </section>
    );
  }

  if (!isAuthenticated) {
    return (
      <section className="space-y-3 rounded-md border border-border bg-muted/40 p-4">
        <h3 className="text-sm font-medium">Review this novel</h3>
        <LoginPrompt />
      </section>
    );
  }

  const submitReview = () => {
    const trimmed = body.trim();
    const validation = validateReview(rating, trimmed);
    setClientError(validation);
    if (validation) {
      return;
    }
    upsertReview.mutate(
      { rating, body: trimmed || null },
      {
        onSuccess: (review) => {
          setSavedReview(review);
          setBody(review.body ?? "");
          setRating(review.rating ?? 0);
        },
      }
    );
  };

  const removeReview = () => {
    deleteReview.mutate(undefined, {
      onSuccess: () => {
        setSavedReview(null);
        setRating(0);
        setBody("");
      },
    });
  };

  const isBusy = upsertReview.isPending || deleteReview.isPending;

  return (
    <section className="space-y-3 rounded-md border border-border bg-muted/40 p-4">
      <h3 className="text-sm font-medium">Review this novel</h3>
      <div className="flex items-center gap-1">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            aria-label={`Rate ${star} star${star === 1 ? "" : "s"}`}
            className="text-muted-foreground transition-colors hover:text-amber-500 disabled:opacity-60"
            disabled={isBusy}
            key={star}
            onClick={() => setRating(star)}
            type="button"
          >
            <Star
              className={`h-5 w-5 ${rating >= star ? "fill-amber-400 text-amber-500" : ""}`}
            />
          </button>
        ))}
      </div>
      <textarea
        className="min-h-24 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
        maxLength={5000}
        onChange={(event) => setBody(event.target.value)}
        placeholder="Optional review"
        value={body}
      />
      {clientError && <p className="text-sm text-destructive">{clientError}</p>}
      {upsertReview.error && (
        <p className="text-sm text-destructive">Review could not be saved.</p>
      )}
      {deleteReview.error && (
        <p className="text-sm text-destructive">Review could not be deleted.</p>
      )}
      {savedReview && (
        <p className="text-sm text-muted-foreground">
          Review saved with status: {savedReview.status}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button disabled={isBusy || !slug} onClick={submitReview} type="button">
          {upsertReview.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
          Submit Review
        </Button>
        <Button
          disabled={isBusy || !slug}
          onClick={removeReview}
          type="button"
          variant="outline"
        >
          {deleteReview.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Trash2 className="h-4 w-4" />
          )}
          Delete Review
        </Button>
      </div>
    </section>
  );
}
