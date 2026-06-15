"use client";

import { useState } from "react";
import { Star } from "lucide-react";

import { usePostReview } from "@/hooks/public";
import { toReaderError } from "@/lib/public-format";

interface RatingReviewProps {
  slug: string;
}

/**
 * Star rating selector (1–5) with optional text feedback.
 * Validates rating client-side before calling the endpoint.
 * Requirements: 13.1, 13.2, 13.3, 13.4, 13.5
 */
export function RatingReview({ slug }: RatingReviewProps) {
  const [rating, setRating] = useState<number>(0);
  const [hoveredStar, setHoveredStar] = useState<number>(0);
  const [body, setBody] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const postReview = usePostReview();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setValidationError(null);
    setSuccessMessage(null);

    // Client-side validation: rating must be in [1, 5]
    if (rating < 1 || rating > 5) {
      setValidationError("Please select a rating between 1 and 5 stars.");
      return;
    }

    postReview.mutate(
      { slug, review: { rating, body: body.trim() || undefined } },
      {
        onSuccess: () => {
          setSuccessMessage("Review submitted!");
          setRating(0);
          setBody("");
        },
      }
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <h3 className="text-sm font-medium">Rate this novel</h3>

      {/* Star rating selector */}
      <div className="flex items-center gap-1" role="radiogroup" aria-label="Rating">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            type="button"
            role="radio"
            aria-checked={rating === star}
            aria-label={`${star} star${star > 1 ? "s" : ""}`}
            className="rounded p-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onClick={() => {
              setRating(star);
              setValidationError(null);
            }}
            onMouseEnter={() => setHoveredStar(star)}
            onMouseLeave={() => setHoveredStar(0)}
          >
            <Star
              className={`h-6 w-6 transition-colors ${
                star <= (hoveredStar || rating)
                  ? "fill-yellow-400 text-yellow-400"
                  : "text-muted-foreground"
              }`}
            />
          </button>
        ))}
        {rating > 0 && (
          <span className="ml-2 text-sm text-muted-foreground">
            {rating}/5
          </span>
        )}
      </div>

      {/* Optional text area for written feedback */}
      <textarea
        className="w-full rounded-md border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        placeholder="Write a review (optional)"
        rows={3}
        value={body}
        onChange={(e) => setBody(e.target.value)}
      />

      {/* Validation error */}
      {validationError && (
        <p className="text-sm text-red-600" role="alert">
          {validationError}
        </p>
      )}

      {/* API error */}
      {postReview.isError && (
        <p className="text-sm text-red-600" role="alert">
          {toReaderError(postReview.error)}
        </p>
      )}

      {/* Success message */}
      {successMessage && (
        <p className="text-sm text-green-600" role="status">
          {successMessage}
        </p>
      )}

      {/* Submit button */}
      <button
        type="submit"
        disabled={postReview.isPending}
        className="inline-flex h-9 items-center justify-center rounded-md bg-foreground px-4 text-sm font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-50"
      >
        {postReview.isPending ? "Submitting…" : "Submit Review"}
      </button>
    </form>
  );
}
