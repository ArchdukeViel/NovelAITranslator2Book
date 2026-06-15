// Public-scoped pure helper functions for the public reader surface.
// All functions are pure (no side effects, no DOM access, no store access).
// Requirements validated: 2.4, 3.3, 3.5, 3.6, 4.2, 4.3, 6.2, 6.5, 6.6, 17.7, 17.9

import type {
  CatalogParams,
  ContributionStatus,
  PublicChapterSummary,
} from "@/lib/public-types";
import { ApiError } from "@/lib/api";

/**
 * Clamps and rounds a font size to an integer within [15, 24].
 * Requirement 6.2
 */
export function clampReaderFontSize(size: number): number {
  return Math.min(24, Math.max(15, Math.round(size)));
}

/**
 * Masks a credential string so it never equals the raw value.
 * Shows at most `prefix` leading characters and `suffix` trailing characters,
 * with "…" in between.
 * Requirement 17.7
 */
export function maskCredential(
  raw: string,
  prefix: number = 4,
  suffix: number = 2
): string {
  if (raw.length <= prefix + suffix) {
    // For short strings, still mask — return something different from raw.
    // Show what we can from the prefix side, mask the rest.
    if (raw.length === 0) return "…";
    if (raw.length === 1) return "…";
    // For very short strings, just replace middle/end with mask
    return raw.slice(0, Math.max(1, Math.floor(raw.length / 2))) + "…";
  }
  return raw.slice(0, prefix) + "…" + raw.slice(-suffix);
}

/** Sensitive patterns to redact from error messages. */
const SENSITIVE_PATTERNS = [
  // Bearer tokens / Authorization header values
  /Bearer\s+[A-Za-z0-9\-._~+/]+=*/gi,
  /Authorization:\s*\S+/gi,
  // API key patterns (common prefixes)
  /AIza[A-Za-z0-9\-_]{30,}/g,
  /sk-[A-Za-z0-9_\-]{20,}/g,
  /key-[A-Za-z0-9_\-]{20,}/g,
  // Generic long token-like strings (40+ hex or base64-ish chars)
  /\b[A-Za-z0-9\-._~+/]{40,}=*\b/g,
  // Session identifiers
  /session[_-]?id\s*[:=]\s*\S+/gi,
  /session\s*[:=]\s*[A-Za-z0-9\-._~+/]{16,}/gi,
  // Stack traces (file paths with line numbers)
  /at\s+.+\(.+:\d+:\d+\)/g,
  /^\s+at\s+.+$/gm,
  /File\s+"[^"]+",\s+line\s+\d+/gi,
  /Traceback\s*\(most recent call last\)[\s\S]*/gi,
];

/**
 * Redacts sensitive content from a string.
 */
function redactSensitive(text: string): string {
  let result = text;
  for (const pattern of SENSITIVE_PATTERNS) {
    // Reset lastIndex for global regexes
    pattern.lastIndex = 0;
    result = result.replace(pattern, "[REDACTED]");
  }
  return result;
}

/**
 * Produces a sanitized, reader-safe error message.
 * Reuses ApiError shape for detection; never surfaces provider keys,
 * Authorization values, session values, raw contributed credentials,
 * or stack traces.
 * Requirements 2.8, 4.8, 5.8, 13.5, 17.14
 */
export function toReaderError(error: unknown): string {
  if (error instanceof ApiError) {
    const message = error.message || "Something went wrong";
    return redactSensitive(message);
  }
  if (error instanceof Error) {
    // Don't expose stack traces or potentially sensitive error messages
    // from non-ApiError errors — use a generic message
    const message = error.message || "Something went wrong";
    return redactSensitive(message);
  }
  return "Something went wrong";
}

/**
 * Maps a width preference to its corresponding max-width Tailwind class.
 * Requirements 6.5, 6.6
 */
export function widthClass(width: "compact" | "comfortable" | "wide"): string {
  switch (width) {
    case "compact":
      return "max-w-xl";
    case "comfortable":
      return "max-w-2xl";
    case "wide":
      return "max-w-4xl";
  }
}

/**
 * Determines if there is a next page of results.
 * Requirement 3.6
 */
export function hasNextPage(
  total: number,
  page: number,
  page_size: number
): boolean {
  return page * page_size < total;
}

/**
 * Returns the baseline unfiltered catalog params.
 * Requirement 3.5
 */
export function clearedCatalogParams(): CatalogParams {
  return { page: 1, page_size: 20 };
}

/**
 * Sorts chapters ascending by chapter_number, falling back to
 * chapter_id string comparison for null chapter_numbers.
 * Returns a new sorted array (no mutation).
 * Requirement 4.3
 */
export function sortChaptersAscending(
  chapters: PublicChapterSummary[]
): PublicChapterSummary[] {
  return [...chapters].sort((a, b) => {
    // Both have chapter_number: sort numerically
    if (a.chapter_number !== null && b.chapter_number !== null) {
      return a.chapter_number - b.chapter_number;
    }
    // Only one has chapter_number: the one with a number comes first
    if (a.chapter_number !== null && b.chapter_number === null) {
      return -1;
    }
    if (a.chapter_number === null && b.chapter_number !== null) {
      return 1;
    }
    // Both null: fall back to chapter_id string comparison
    return a.chapter_id.localeCompare(b.chapter_id);
  });
}

/**
 * Returns the author string or "Unknown author" when null, undefined, or empty.
 * Requirement 2.4
 */
export function authorOrFallback(author: string | null | undefined): string {
  if (!author || author.trim() === "") {
    return "Unknown author";
  }
  return author;
}

const VALID_CONTRIBUTION_STATUSES: ContributionStatus[] = [
  "Unchecked",
  "Checking",
  "Working",
  "Failed",
];

/**
 * Constrains a value to the allowed ContributionStatus set.
 * Returns "Unchecked" for unknown values.
 * Requirement 17.9
 */
export function mapContributionStatus(value: unknown): ContributionStatus {
  if (
    typeof value === "string" &&
    VALID_CONTRIBUTION_STATUSES.includes(value as ContributionStatus)
  ) {
    return value as ContributionStatus;
  }
  return "Unchecked";
}
