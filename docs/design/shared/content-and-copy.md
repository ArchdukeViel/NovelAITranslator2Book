# Content and Copy Guidelines

Tone, terminology, formatting, and localization standards.

## Tone

- **Public surface:** Warm, welcoming, Bunko-bon shelf / Yokocho Lantern atmosphere. Clear, concise, respectful of the reading experience.
- **Admin surface:** Operational, precise, high-density, action-oriented. No decorative language.

## Locale and Time Zone

- Dates and times: format per visitor browser locale (`toLocaleDateString`, `toLocaleTimeString`)
- No hardcoded date formats — always use `Intl.DateTimeFormat` or equivalent
- Time zones: display in user's local timezone; store as UTC
- Relative time ("3 hours ago") preferred for recent events; absolute date for older events

## Date and Number Formatting

| Data Type | Format | Example |
|---|---|---|
| Date | Browser locale | "August 2, 2026" (en-US) |
| Relative time | Short relative | "3h ago", "2d ago" |
| Chapter count | Numeric, no comma threshold | "127 chapters" |
| Word count | Locale-formatted number | "45,230 words" |
| Rating | 1 decimal place | "4.2" |
| File size | SI units | "1.2 MB" |

## Title Hierarchy

- **Translated title** is always primary (largest, most prominent)
- **Original Japanese title** is secondary, displayed in `font-literary` (Noto Serif JP)
- When both are shown, translated title comes first
- Source title labeled with `font-metadata text-xs uppercase text-muted-foreground` prefix "Source title"
- Titles MUST NOT be truncated on their primary display — only in compact card contexts

## Japanese/English Mixed-Script Behavior

- CJK text: `word-break: break-word` and `overflow-wrap: break-word` for safe wrapping
- Japanese prose in reader: `line-break: strict` for proper kinsoku shori (line-breaking)
- Narration paragraphs: `text-align: justify; text-align-last: left; hyphens: auto` on desktop; `text-align: left; hyphens: manual` on mobile (< 640px)
- Dialogue paragraphs: always `text-align: left`
- Mixed Japanese/English inline: no special treatment — browser handles bidi naturally

## Truncation and Wrapping

- Single-line truncation: `line-clamp-1` or `truncate`
- Multi-line truncation: `line-clamp-2` through `line-clamp-5` as appropriate
- MUST NOT truncate:
  - Legal notices
  - Error messages
  - Accessibility labels
  - Chapter titles on chapter reader page
- Synopsis: `line-clamp-3` on browse cards; full text on novel detail overview

## Terminology Rules

- Use canonical identifiers from `AGENTS.md` in code
- Public copy MUST use user-facing names:

| Internal | Public |
|---|---|
| "Novel AI" (project codename) | "Dokushodo" |
| `source_key` | Source name (e.g., "Syosetu") |
| `activity_id` | Not exposed |
| `job_id` | Not exposed |
| `user_id` | Not exposed |
| `credential_id` | Not exposed |

- MUST NOT leak internal codenames, IDs, or technical identifiers to public surfaces
- Status labels use canonical semantic terms: "Completed", "Ongoing", "Hiatus", "Dropped", "Unknown"

## Status Terminology

Canonical status labels for public surfaces:

| Token | Public Label | Context |
|---|---|---|
| `success` | Completed, Published, Active | Novel status, review status, health |
| `info` | Ongoing, Scheduled, In progress | Translation status, scheduled jobs |
| `warning` | Hiatus, Stale, Partial | Novel status, data freshness |
| `destructive` | Failed, Rejected, Removed | Translation failure, review rejection, takedown |
| `muted` | Dropped, Unavailable, Unknown | Novel status, missing features |

## Accessible Names

- All interactive elements MUST have accessible names via visible label, `aria-label`, or `aria-labelledby`
- Icon-only buttons MUST have `aria-label`
- Decorative icons use `aria-hidden="true"`
- Status badges MUST include text content (not color-only)
- Star ratings MUST announce numeric value (e.g., "4 out of 5 stars")

## Destructive Confirmation Copy

- Confirmation dialog MUST name what is being destroyed: "Remove [novel title] from your library?"
- Confirm button MUST use active verb: "Remove", "Delete", "Reject" — not "OK" or "Yes"
- Cancel button: "Cancel" — always available
- MUST NOT use double negatives ("Don't cancel")

## Safe Public Error Messages

- MUST NOT expose: stack traces, database errors, internal paths, storage keys, IP addresses, user IDs
- Generic fallback: "Something went wrong. Please try again later."
- Network errors: "Could not connect. Check your network connection."
- Not found: "We could not find that page or it is no longer available."
- Rate limited: "Please wait a moment before trying again."
- Unauthorized: "Please sign in to continue."

## Pluralization

- Use count-aware copy: "1 chapter" / "127 chapters"
- Zero state: use descriptive empty message, not "0 chapters"
- SHOULD use `Intl.PluralRules` for locale-aware pluralization when extended locale support is added

## Empty and Unavailable Copy

- Empty states MUST include:
  1. Clear explanation of why content is empty
  2. Recovery action when available (e.g., "Browse novels" CTA)
- Unavailable features: "This feature is not yet available" — never claim it exists or will ship by a date
- Never show blank content areas without explanation
