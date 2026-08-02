# Reading — Novel Detail Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | public |
| Domain | reading |
| Routes | `/novels/[slug]` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(public)/novels/[slug]/page.tsx`, `frontend/components/public/novel-detail-client.tsx`, `frontend/components/public/community-reviews.tsx` |

## Purpose
Comprehensive landing page for a single novel title featuring metadata, chapter list, and reader reviews.

## User Goal
Read novel synopsis, inspect chapter list, start or resume reading, save to library, and read/submit reviews.

## Audience and Permissions
- **Guests:** Read overview, browse chapters, read published community reviews.
- **Authenticated Users:** Save novel, track chapter progress, submit/edit rate & review.

## Primary Action
Single Start/Continue Reading CTA button ("Start Reading" or "Continue Ch. X").

## Information Hierarchy
1. Desktop Left Column (Sticky Cover, Title, Status Lantern Badge, Primary CTA, Save Button, Rating Summary)
2. Desktop Right Column (URL-synced Tabbed View: Overview, Chapters, Reviews)
3. Mobile Layout (Header metadata -> Segmented Tab Control -> Tab Content -> Sticky Bottom Action Bar)

## Page Anatomy
- **Left Panel:** Cover bookplate/image (2:3 aspect ratio), title, author, status pill, primary CTA, save to library toggle, rating star summary.
- **Overview Tab:** Detailed synopsis text, genre/tag chips, source platform link, publication stats.
- **Chapters Tab:** Volume-grouped chapter list, search input, ascending/descending order toggle, expand/collapse volumes.
- **Reviews Tab:** Rating breakdown summary, user review form (authenticated), list of published community reviews.

## Desktop Layout
Two-column grid (320px left sticky sidebar + main tabbed content area).

## Mobile Layout
Single column flow. Sticky action bar pinned to viewport bottom (small cover, title, single primary button).

## Interaction Flow
- Clicking primary CTA opens target chapter.
- Tapping tabs updates URL query parameter (`?tab=chapters`).
- Tapping volume headers expands/collapses chapter groups.

## Authentication or Authorization Behavior
- Guests clicking "Save to Library" see an inline auth prompt.
- Authenticated users see their saved status (e.g. "Saved in Library") and their prior review pre-filled in the review form.

## States

### Initial
Page skeleton matching left sticky panel and right tab container.

### Loading
Pulse loading state for synopsis and chapter list.

### Empty
If novel has zero published chapters, primary button displays "No Chapters Available" disabled state.

### Pending
Saving to library or submitting review mutation in flight.

### Settled
Fully loaded novel detail page.

### Recoverable Error
"Failed to load novel details." with Retry CTA.

### Unavailable
Novel unavailable or taken down under legal notice (HTTP 451 state).

### Unauthorized or Forbidden
Not applicable.

### Success
Toast notification on saving to library or submitting review.

## Components
- `NovelDetailClient`
- `CommunityReviews`
- `RatingReview`
- `Badge`
- `Button`

## Content and Copy
- Primary CTA: "Start Reading" (if unread) or "Continue Ch. X" (if progress exists).
- Save button: "Save to Library" / "In Library".

## Accessibility
- Tab list has proper `role="tablist"`, `role="tab"`, `aria-selected` attributes.
- Single primary CTA button enforced on screen to prevent decision fatigue.

## Responsive Behavior
- Desktop sticky sidebar transforms into mobile bottom fixed action bar.

## Data Requirements
- Full novel metadata, chapter list manifest, user progress record, published community reviews array.

## Privacy, Safety, and Security
- Exposes no internal DB identifiers; non-published reviews hidden from public API responses.

## Acceptance Criteria
- Exactly one primary CTA button rendered on screen at any time.
- Selected tab reflected in and restorable from URL query parameter (`?tab=...`).

## Implementation Mapping
- `frontend/app/(public)/novels/[slug]/page.tsx`
- `frontend/components/public/community-reviews.tsx`
