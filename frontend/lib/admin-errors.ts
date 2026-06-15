import { ApiError, apiErrorInlineMessage } from "@/lib/api";

/**
 * Redaction patterns for secret detection.
 * These patterns match common credential formats that should be stripped from error messages.
 */
const SECRET_PATTERNS: Array<{ pattern: RegExp; flags: string; replacement: string }> = [
  // Bearer tokens
  { pattern: /Bearer\s+[A-Za-z0-9\-._~+/]+=*/gi, flags: "gi", replacement: "[BEARER_TOKEN]" },
  // Authorization headers (full line or value)
  { pattern: /(?:Authorization[\s:=]+)[^\r\n]*/gi, flags: "gi", replacement: "[AUTHORIZATION_HEADER]" },
  // Cookie strings
  { pattern: /(?:cookie[:\s]+)[^\r\n;]*/gi, flags: "gi", replacement: "[COOKIE]" },
  // Session tokens
  { pattern: /(?:session[_\-]?token[=\s]+)[^\r\n]*/gi, flags: "gi", replacement: "[SESSION_TOKEN]" },
  // Generic API keys
  { pattern: /(?:api[_\-]?key[=\s]+)[^\r\n]*/gi, flags: "gi", replacement: "[API_KEY]" },
  // Google API keys (AIza...)
  { pattern: /AIza[A-Za-z0-9\-_]{20,}/gi, flags: "gi", replacement: "[GOOGLE_API_KEY]" },
  // OpenAI API keys (sk-...)
  { pattern: /sk-[A-Za-z0-9]{20,}/gi, flags: "gi", replacement: "[OPENAI_KEY]" },
  // OpenAI project keys (sk-proj-...)
  { pattern: /sk-proj-[A-Za-z0-9\-_]{20,}/gi, flags: "gi", replacement: "[OPENAI_PROJECT_KEY]" },
  // Slack tokens
  { pattern: /xox[baprs]-[A-Za-z0-9\-_]{10,}/gi, flags: "gi", replacement: "[SLACK_TOKEN]" },
  // GitHub tokens
  { pattern: /gh[pousr]_[A-Za-z0-9]{36,}/gi, flags: "gi", replacement: "[GITHUB_TOKEN]" },
  // AWS keys (heuristic)
  { pattern: /(?:AKIA|ABIA|ACCA)[A-Z0-9]{16}/gi, flags: "gi", replacement: "[AWS_KEY]" },
  // Generic long base64 secrets (heuristic - avoid false positives)
  { pattern: /[A-Za-z0-9+\/]{40,}={0,2}/g, flags: "g", replacement: "[SECRET]" },
];

/**
 * Multi-line stack trace pattern.
 * Matches common stack trace formats from various environments.
 */
const STACK_TRACE_PATTERN = /(\n\s*at\s+.+\(.*\)|\n\s*at\s+.+\s+\(.+\)|\n\s+File\s+".+",\s+line\s+\d+|\n\s*\^\s*)?(\n(?:Error:|Traceback \(most recent call last\):|Exception:|TypeError:|ReferenceError:|SyntaxError:|RangeError:).*)?/gi;

/**
 * Strips all secret patterns from a string.
 */
function redactSecrets(text: string): string {
  let result = text;

  for (const { pattern, flags, replacement } of SECRET_PATTERNS) {
    // Create new regex with the same pattern but with the 'g' flag
    const regex = new RegExp(pattern.source, flags.includes("g") ? flags : flags + "g");
    result = result.replace(regex, replacement);
  }

  return result;
}

/**
 * Removes multi-line stack traces from text.
 */
function removeStackTrace(text: string): string {
  // Split by newlines and filter out stack trace lines
  const lines = text.split("\n");
  const filteredLines: string[] = [];
  let inStackTrace = false;

  for (const line of lines) {
    // Detect stack trace start
    if (
      /^\s*at\s+/.test(line) ||
      /^Traceback \(most recent call last\):/.test(line) ||
      /^\s*File\s+"/.test(line) ||
      /^\s*\^/.test(line) ||
      /^\s+\d+:\s+/.test(line)
    ) {
      inStackTrace = true;
      continue;
    }

    // If we're in a stack trace and encounter a non-indented line or empty line followed by non-stack content
    if (inStackTrace) {
      if (line.trim() === "" || (!/^\s+/.test(line) && !/^\s*at\s+/.test(line))) {
        inStackTrace = false;
      } else {
        continue; // Skip stack trace lines
      }
    }

    filteredLines.push(line);
  }

  return filteredLines.join("\n").trim();
}

/**
 * Formats an admin error into a safe, human-readable message.
 * This is the single redaction chokepoint - all error display should go through here.
 * 
 * @param error - The error to format (ApiError, Error, string, or object)
 * @param fallback - Fallback message if error cannot be parsed
 * @returns A safe, redacted message suitable for display, plus optional trace_id
 */
export function formatAdminError(
  error: unknown,
  fallback = "Something went wrong."
): { message: string; trace_id?: string } {
  let rawMessage = fallback;
  let traceId: string | undefined;

  // Normalize to a string message
  if (error instanceof ApiError) {
    rawMessage = apiErrorInlineMessage(error);
    traceId = error.trace_id ?? undefined;
    // Also check for explanation field
    if (error.explanation && error.explanation.trim()) {
      rawMessage = `${rawMessage}: ${error.explanation}`;
    }
  } else if (error instanceof Error) {
    rawMessage = error.message;
  } else if (typeof error === "string" && error.trim()) {
    rawMessage = error.trim();
  } else if (error && typeof error === "object") {
    // Try to extract message from object
    const errObj = error as Record<string, unknown>;
    if (typeof errObj.message === "string" && errObj.message.trim()) {
      rawMessage = errObj.message.trim();
    } else if (typeof errObj.error === "string" && errObj.error.trim()) {
      rawMessage = errObj.error.trim();
    } else if (typeof errObj.detail === "string" && errObj.detail.trim()) {
      rawMessage = errObj.detail.trim();
    }
    // Extract trace_id if present
    if (typeof errObj.trace_id === "string") {
      traceId = errObj.trace_id;
    } else if (typeof errObj.request_id === "string") {
      traceId = errObj.request_id;
    }
  }

  // Apply redactions
  let redacted = redactSecrets(rawMessage);
  redacted = removeStackTrace(redacted);

  // Clean up any remaining multiple spaces or odd artifacts
  redacted = redacted.replace(/\s+/g, " ").trim();

  // Ensure we never return raw details/raw from objects
  // The message should only contain the human-readable content
  return {
    message: redacted,
    trace_id: traceId,
  };
}

/**
 * Simple string overload for backward compatibility.
 * Returns just the message string.
 */
export function formatAdminErrorString(error: unknown, fallback = "Something went wrong."): string {
  const result = formatAdminError(error, fallback);
  return result.message;
}
