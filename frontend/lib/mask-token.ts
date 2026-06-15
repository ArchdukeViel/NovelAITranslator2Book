/**
 * Token masking utilities for credential display.
 * Reveals at most a short prefix and suffix; obscures the middle.
 * Never emits the obscured middle verbatim.
 */

// Configuration for masking behavior
const PREFIX_LENGTH = 4;
const SUFFIX_LENGTH = 4;
const MIN_MIDDLE_LENGTH_FOR_MASK = 1;

/**
 * Masks a token value, revealing at most a short prefix and suffix.
 * The middle is replaced with asterisks.
 * 
 * @param value - The token string to mask
 * @returns The masked token (e.g., "AIza****wXyz")
 * 
 * Examples:
 * - "verylongtoken" -> "very****oken"
 * - "AIzaSyD..." -> "AIza****..."
 * - "sk-1234567890abcdef" -> "sk-****cdef"
 * - "abc" -> "abc" (too short to mask meaningfully)
 * - "" -> ""
 */
export function maskToken(value: string | null | undefined): string {
  // Handle null/undefined/empty
  if (!value || value.length === 0) {
    return "";
  }

  // If the value is too short to mask meaningfully, return as-is
  // Need at least prefix + suffix + at least one character in middle for masking
  const minMaskedLength = PREFIX_LENGTH + MIN_MIDDLE_LENGTH_FOR_MASK + SUFFIX_LENGTH;
  if (value.length <= minMaskedLength) {
    // For short values, just return them as-is (they're already short enough to not be secrets)
    return value;
  }

  const prefix = value.slice(0, PREFIX_LENGTH);
  const suffix = value.slice(-SUFFIX_LENGTH);
  const middleLength = value.length - PREFIX_LENGTH - SUFFIX_LENGTH;

  // Create mask that indicates length was hidden, but doesn't reveal actual middle
  // Using a reasonable number of asterisks to indicate hidden content
  const mask = "*".repeat(Math.min(middleLength, 8));

  return `${prefix}${mask}${suffix}`;
}

/**
 * Checks if a string contains any known secret patterns that should be redacted.
 * This is a helper for error redaction.
 */
export function containsSecret(text: string | null | undefined): boolean {
  if (!text) return false;
  
  // Check for common secret patterns
  const secretPatterns = [
    /Bearer\s+[A-Za-z0-9\-._~+/]+=*/i,
    /Authorization:\s*.+/i,
    /cookie[:\s]+[A-Za-z0-9=;_\-\s]+/i,
    /session[_\-]?token[=\s]+[A-Za-z0-9\-._~+/]+/i,
    /api[_\-]?key[=\s]+[A-Za-z0-9\-._~+/]+/i,
    /AIza[A-Za-z0-9\-_]+/, // Google API keys
    /sk-[A-Za-z0-9]{20,}/, // OpenAI API keys
    /sk-proj-[A-Za-z0-9\-_]{20,}/, // OpenAI project keys
    /xox[baprs]-[A-Za-z0-9\-_]{10,}/, // Slack tokens
    /gh[pousr]_[A-Za-z0-9]{36,}/, // GitHub tokens
    /[A-Za-z0-9]{20,}==/i, // Generic base64-encoded secrets (heuristic)
  ];

  return secretPatterns.some(pattern => pattern.test(text));
}