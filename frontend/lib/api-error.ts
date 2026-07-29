/**
 * Shared API error normalization and safe redaction.
 *
 * Prevents leaking raw backend messages, trace IDs, internal paths,
 * or stack traces to user-facing UI.
 *
 * Use in error boundaries, fallback pages, and data-fetching error handlers.
 */
import { ApiError } from "@/lib/api";

// ---------------------------------------------------------------------------
// Safe defaults
// ---------------------------------------------------------------------------

const GENERIC_SERVER_MESSAGE = "Something went wrong. Please try again.";
const GENERIC_NETWORK_MESSAGE =
  "A network error occurred. Check your connection and try again.";
const GENERIC_ERROR_MESSAGE = "Something went wrong.";

// ---------------------------------------------------------------------------
// Network detection
// ---------------------------------------------------------------------------

function isNetworkError(error: unknown): boolean {
  if (error instanceof TypeError && error.message === "Failed to fetch") {
    return true;
  }
  if (
    error instanceof Error &&
    /network|econnrefused|fetch failed/i.test(error.message)
  ) {
    return true;
  }
  return false;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Returns a safe, user-facing message from any error value.
 * - 4xx ApiError: preserves the message (error code visible but safe)
 * - 5xx ApiError: generic "try again" message
 * - Network Error: connection hint
 * - Everything else: generic fallback
 */
export function safeErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status >= 500) {
      return GENERIC_SERVER_MESSAGE;
    }
    return error.message || GENERIC_ERROR_MESSAGE;
  }
  if (error instanceof Error) {
    if (isNetworkError(error)) {
      return GENERIC_NETWORK_MESSAGE;
    }
    return GENERIC_ERROR_MESSAGE;
  }
  return GENERIC_ERROR_MESSAGE;
}

export interface SafeErrorInfo {
  title: string;
  description: string;
}

/**
 * Converts any error to a safe (title, description) pair suitable for
 * spreading into page-state components (ErrorState, NotFoundState, etc.).
 *
 * Rules:
 * - Known HTTP status codes (404, 401, 403, 503) map to specific titles.
 * - `explanation` from the backend is used when available for those codes.
 * - 5xx never leaks message/raw/details/trace_id.
 * - Network errors get a connection hint.
 * - Unknown errors get generic fallback.
 */
export function errorToProps(error: unknown): SafeErrorInfo {
  if (error instanceof ApiError) {
    // 4xx known codes — use explanation if available, else safe default
    switch (error.status) {
      case 404:
        return {
          title: "Not found",
          description:
            error.explanation ||
            "The resource you requested could not be found.",
        };
      case 401:
        return {
          title: "Sign in required",
          description: error.explanation || "Please sign in to continue.",
        };
      case 403:
        return {
          title: "Permission required",
          description:
            error.explanation ||
            "You do not have permission to view this resource.",
        };
      case 503:
        return {
          title: "Temporarily unavailable",
          description:
            error.explanation ||
            "This service is temporarily unavailable. Please try again later.",
        };
    }

    // 5xx — fully redacted
    if (error.status >= 500) {
      return {
        title: "Something went wrong",
        description: GENERIC_SERVER_MESSAGE,
      };
    }

    // Other 4xx (400, 422, 429, etc.) — use explanation if available only
    return {
      title: "Something went wrong",
      description: error.explanation || GENERIC_ERROR_MESSAGE,
    };
  }

  if (error instanceof Error) {
    return {
      title: "Something went wrong",
      description: isNetworkError(error)
        ? GENERIC_NETWORK_MESSAGE
        : GENERIC_ERROR_MESSAGE,
    };
  }

  return {
    title: "Something went wrong",
    description: GENERIC_ERROR_MESSAGE,
  };
}
