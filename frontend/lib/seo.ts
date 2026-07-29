/**
 * SEO utilities for public reader pages.
 * Pure functions — safe to test without framework mocks.
 * Zero dependencies on Next.js internals (testable in vitest/jsdom).
 */

// ---------------------------------------------------------------------------
// Config (reads from env at function call time — testable via mock)
// ---------------------------------------------------------------------------

/** Get configured public site URL. Falls back to localhost. */
export function getSiteUrl(): string {
  return process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FALLBACK_TITLE = "Untitled Novel";
const FALLBACK_CHAPTER_TITLE = "Untitled Chapter";
const FALLBACK_DESCRIPTION =
  "Read translated Japanese web novels on Dokushodo.";
const MAX_DESCRIPTION_LENGTH = 160;

// ---------------------------------------------------------------------------
// Canonical URL
// ---------------------------------------------------------------------------

/**
 * Build absolute canonical URL from a relative pathname.
 * Always strips query strings, hash, and trailing slash.
 */
export function buildCanonicalUrl(pathname: string): string {
  const base = getSiteUrl().replace(/\/+$/, "");
  const path = pathname.startsWith("/") ? pathname : `/${pathname}`;
  return `${base}${path}`;
}

// ---------------------------------------------------------------------------
// Page titles
// ---------------------------------------------------------------------------

/**
 * Build `<title>` for a novel detail page.
 * Pattern: `{Novel Title} | Dokushodo`
 */
export function buildNovelPageTitle(
  novelTitle: string | null | undefined,
): string {
  const safe = novelTitle?.trim() || FALLBACK_TITLE;
  return `${safe} | Dokushodo`;
}

/**
 * Build `<title>` for a chapter reader page.
 * Pattern: `{Chapter Title} - {Novel Title} | Dokushodo`
 */
export function buildChapterPageTitle(
  chapterTitle: string | null | undefined,
  novelTitle: string | null | undefined,
): string {
  const safeChapter = chapterTitle?.trim() || FALLBACK_CHAPTER_TITLE;
  const safeNovel = novelTitle?.trim() || FALLBACK_TITLE;
  return `${safeChapter} - ${safeNovel} | Dokushodo`;
}

// ---------------------------------------------------------------------------
// Meta descriptions
// ---------------------------------------------------------------------------

/**
 * Build safe meta description from raw text.
 * Strips HTML tags, collapses whitespace, truncates to 160 chars.
 * Falls back to site description when text is empty/null.
 */
export function buildDescription(
  text: string | null | undefined,
): string {
  if (!text?.trim()) return FALLBACK_DESCRIPTION;
  const stripped = text
    .trim()
    .replace(/<[^>]*>/g, "")
    .replace(/\s+/g, " ");
  if (stripped.length <= MAX_DESCRIPTION_LENGTH) return stripped;
  return stripped.slice(0, MAX_DESCRIPTION_LENGTH - 1) + "\u2026";
}

// ---------------------------------------------------------------------------
// Escaping helpers
// ---------------------------------------------------------------------------

/**
 * Escape text for safe HTML attribute insertion.
 */
export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/**
 * Escape text for safe insertion into JSON-LD (JSON string).
 */
export function escapeJson(text: string): string {
  return text
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"')
    .replace(/\n/g, "\\n")
    .replace(/\r/g, "\\r")
    .replace(/\t/g, "\\t");
}

// ---------------------------------------------------------------------------
// SEO policy
// ---------------------------------------------------------------------------

/** Whether a published novel is indexable. */
export function isNovelIndexable(publicationStatus: string): boolean {
  return publicationStatus === "published";
}

/** Whether a published translated chapter is indexable. */
export function isChapterIndexable(
  novelPublicationStatus: string,
  chapterTranslated: boolean,
): boolean {
  return novelPublicationStatus === "published" && chapterTranslated;
}

/** Robots meta tag value string. */
export function robotsDirective(indexable: boolean): string {
  return indexable ? "index,follow" : "noindex,nofollow";
}

// ---------------------------------------------------------------------------
// JSON-LD structured data
// ---------------------------------------------------------------------------

/**
 * Build Book JSON-LD for a novel detail page.
 * Only public-safe fields — no IDs, prompts, diagnostics, or private notes.
 */
export function buildNovelJsonLd(
  name: string,
  description?: string | null,
  canonicalUrl?: string,
  author?: string | null,
): Record<string, unknown> {
  const ld: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "Book",
    name: name.trim() || FALLBACK_TITLE,
  };
  if (description?.trim()) ld.description = description.trim();
  if (canonicalUrl) ld.url = canonicalUrl;
  if (author?.trim()) ld.author = author.trim();
  return ld;
}

/**
 * Build Chapter JSON-LD for a chapter reader page.
 * Only public-safe fields.
 */
export function buildChapterJsonLd(
  chapterName: string,
  novelName: string,
  description?: string | null,
  canonicalUrl?: string,
): Record<string, unknown> {
  const ld: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "Chapter",
    name: chapterName.trim() || FALLBACK_CHAPTER_TITLE,
    isPartOf: {
      "@type": "Book",
      name: novelName.trim() || FALLBACK_TITLE,
    },
  };
  if (description?.trim()) ld.description = description.trim();
  if (canonicalUrl) ld.url = canonicalUrl;
  return ld;
}

/**
 * Serialize a JSON-LD object to a `<script type="application/ld+json">` HTML string.
 */
export function serializeJsonLd(
  data: Record<string, unknown>,
): string {
  return `<script type="application/ld+json">${JSON.stringify(data)}</script>`;
}
