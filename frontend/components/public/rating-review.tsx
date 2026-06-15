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
  const [justSaved, setJustSaved] = useState(false);
  const upsertReview = useUpsertReview(slug);
  const deleteReview = useDeleteReview(slug);

  if (authPending) {
    return (
      <section className="space-y-3 rounded-md border border-border bg-muted/40 p-4">
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
        <h3 className="text-sm font-medium">Rate &amp; Review</h3>
        <p className="text-xs text-muted-foreground">
          Share your thoughts about this novel after reading.
        </p>
        <LoginPrompt />
      </section>
    );
  }

  const submitReview = () => {
    const trimmed = body.trim();
    const validation = validateReview(rating, trimmed);
    setClientError(validation);
    setJustSaved(false);
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
          setJustSaved(true);
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
        setJustSaved(false);
      },
    });
  };

  const isBusy = upsertReview.isPending || deleteReview.isPending;
  const hasSavedReview = !!savedReview;

  return (
    <section className="space-y-3 rounded-md border border-border bg-muted/40 p-4">
      <div>
        <h3 className="text-sm font-medium">Rate &amp; Review</h3>
        <p className="text-xs text-muted-foreground">
          Rate this novel and optionally share your thoughts.
        </p>
      </div>

      {/* Star rating */}
      <div className="flex items-center gap-1">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            aria-label={`Rate ${star} star${star === 1 ? "" : "s"}`}
            className="text-muted-foreground transition-colors hover:text-amber-500 disabled:opacity-60"
            disabled={isBusy}
            key={star}
            onClick={() => {
              setRating(star);
              setJustSaved(false);
            }}
            type="button"
          >
            <Star
              className={`h-6 w-6 ${rating >= star ? "fill-amber-400 text-amber-500" : ""}`}
            />
          </button>
        ))}
        {rating > 0 && (
          <span className="ml-2 text-xs text-muted-foreground">
            {rating} of 5
          </span>
        )}
      </div>

      {/* Review body */}
      <textarea
        className="min-h-24 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
        maxLength={5000}
        onChange={(event) => {
          setBody(event.target.value);
          setJustSaved(false);
        }}
        placeholder="Write your review (optional)"
        value={body}
      />

      {/* Error messages */}
      {clientError && <p className="text-sm text-destructive">{clientError}</p>}
      {upsertReview.error && (
        <p className="text-sm text-destructive">
          Could not save your review. Try again later.
        </p>
      )}
      {deleteReview.error && (
        <p className="text-sm text-destructive">
          Could not delete your review. Try again later.
        </p>
      )}

      {/* Success confirmation */}
      {justSaved && savedReview && (
        <p className="text-sm text-green-600 dark:text-green-400">
          ✓ Review submitted{savedReview.status === "pending" ? " (pending review)" : ""}.
        </p>
      )}

      {/* Action buttons */}
      <div className="flex flex-wrap items-center gap-2">
        <Button disabled={isBusy || !slug} onClick={submitReview} type="button">
          {upsertReview.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : null}
          {hasSavedReview ? "Update Review" : "Submit Review"}
        </Button>
        {hasSavedReview && (
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
            Remove Review
          </Button>
        )}
      </div>
    </section>
  );
}
