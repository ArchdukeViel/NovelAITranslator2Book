"use client";

import { useState } from "react";

import { useCreateRequest } from "@/hooks/public";
import { toReaderError } from "@/lib/public-format";
import { ApiError } from "@/lib/api";
import type { NovelRequestType } from "@/lib/public-types";

/**
 * Standalone form for submitting novel/chapter requests.
 * Frames submission as a request for the site owner to review —
 * does NOT represent it as triggering translation.
 *
 * Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6
 */
export function RequestControl() {
  const [requestType, setRequestType] = useState<NovelRequestType>("novel");
  const [details, setDetails] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [rateLimitMessage, setRateLimitMessage] = useState<string | null>(null);

  const createRequest = useCreateRequest();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSuccessMessage(null);
    setRateLimitMessage(null);

    createRequest.mutate(
      {
        request_type: requestType,
        details: details.trim() || undefined,
        source_url: sourceUrl.trim() || undefined,
      },
      {
        onSuccess: () => {
          setSuccessMessage("Request submitted!");
          setDetails("");
          setSourceUrl("");
        },
        onError: (error) => {
          if (error instanceof ApiError && error.status === 429) {
            setRateLimitMessage(
              "Rate limit exceeded. Please try again later."
            );
          }
        },
      }
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <h3 className="text-sm font-medium">Submit a Request</h3>
      <p className="text-xs text-muted-foreground">
        Submit a request for the site owner to review. This does not guarantee
        or trigger any translation.
      </p>

      {/* Request type select */}
      <label className="block text-sm">
        <span className="mb-1 block font-medium">Type</span>
        <select
          value={requestType}
          onChange={(e) => setRequestType(e.target.value as NovelRequestType)}
          className="w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="novel">Novel</option>
          <option value="chapter">Chapter</option>
        </select>
      </label>

      {/* Details text area */}
      <label className="block text-sm">
        <span className="mb-1 block font-medium">Details</span>
        <textarea
          className="w-full rounded-md border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          placeholder="Describe what you'd like to request"
          rows={3}
          value={details}
          onChange={(e) => setDetails(e.target.value)}
        />
      </label>

      {/* Source URL (optional) */}
      <label className="block text-sm">
        <span className="mb-1 block font-medium">
          Source URL <span className="text-muted-foreground">(optional)</span>
        </span>
        <input
          type="url"
          className="w-full rounded-md border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          placeholder="https://..."
          value={sourceUrl}
          onChange={(e) => setSourceUrl(e.target.value)}
        />
      </label>

      {/* Rate-limit error */}
      {rateLimitMessage && (
        <p className="text-sm text-red-600" role="alert">
          {rateLimitMessage}
        </p>
      )}

      {/* API error (non-rate-limit) */}
      {createRequest.isError &&
        !rateLimitMessage && (
          <p className="text-sm text-red-600" role="alert">
            {toReaderError(createRequest.error)}
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
        disabled={createRequest.isPending}
        className="inline-flex h-9 items-center justify-center rounded-md bg-foreground px-4 text-sm font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-50"
      >
        {createRequest.isPending ? "Submitting…" : "Submit Request"}
      </button>
    </form>
  );
}
