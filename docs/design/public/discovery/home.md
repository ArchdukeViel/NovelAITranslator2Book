# Discovery — Home Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | public |
| Domain | discovery |
| Routes | `/`, `/home` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(public)/home/page.tsx`, `frontend/components/public/home-page-client.tsx`, `frontend/components/public/spotlight-hero.tsx`, `frontend/components/public/novel-rail.tsx` |

## Purpose
Main public landing surface showcasing featured novel spotlights, reading progress, and curated horizontal novel rails.

## User Goal
Discover new novels to read, quickly resume reading active titles, and explore catalog recommendations.

## Audience and Permissions
- **Guests:** Access featured spotlight, new releases, recently updated, genre rails, and surprise me tile.
- **Authenticated Users:** Access personalized "Continue Reading" rail.

## Primary Action
Spotlight Hero "Start Reading" CTA button.

## Information Hierarchy
1. Hero Spotlight (Featured novel title, cover art, synopsis excerpt, primary action button)
2. Continue Reading Rail (Personalized progress for signed-in users; sign-in prompt tile for guests)
3. New Releases Rail (Latest novel additions)
4. Recently Updated Rail (Novels with recently translated chapters)
5. Top Genre Rails (Catalog-derived top genre selections)
6. Surprise Me Tile (Direct shortcut link to `/random`)

## Page Anatomy
- **Header:** Global `PublicHeader`.
- **Spotlight Banner:** Large visual card featuring single admin-curated novel.
- **Horizontal Rails:** Labeled scrolling sections (`role="region"`), maximum 5 rails above footer.
- **Footer:** Global `PublicFooter`.

## Desktop Layout
Hero banner occupies full container width (1280px max). Rails display 4–5 compact cards horizontally with scroll controls.

## Mobile Layout
Hero collapses vertically. Rails display 2–3 cards with horizontal touch swipe overflow visible.

## Interaction Flow
- Clicking Hero "Start Reading" opens the first chapter of the featured novel.
- Tapping rail card navigates to novel detail page (`/novels/[slug]`).
- Tapping rail "See all" header link opens pre-filtered catalog browse page.

## Authentication or Authorization Behavior
- Guests viewing "Continue Reading" see a quiet card inviting them to sign in.
- Authenticated users see their most recently read novels with exact chapter progress.

## States

### Initial
Page skeleton loader matching hero card and rail dimensions.

### Loading
Pulse animation on spotlight card and compact rail card placeholders.

### Empty
If catalog is empty, hero displays default bookplate and rails display "No novels available yet."

### Pending
Not applicable (read-only surface).

### Settled
Fully loaded hero spotlight and populated horizontal rails.

### Recoverable Error
Inline error banner with "Retry loading home page" button.

### Unavailable
Global system maintenance banner if backend is unreachable.

### Unauthorized or Forbidden
Not applicable (public access).

### Success
Not applicable.

## Components
- `SpotlightHero`
- `NovelRail`
- `CompactNovelCard`
- `Button`

## Content and Copy
- Hero CTA: "Start Reading"
- Guest Continue Reading tile: "Sign in to pick up where you left off"
- Surprise Me tile: "🎲 Surprise Me"

## Accessibility
- Each rail enclosed in `<section role="region" aria-label="...">`.
- Keyboard arrow keys navigate rail scroll regions.
- High contrast focus rings around cards and CTA buttons.

## Responsive Behavior
- Rails reflow smoothly across 320px, 768px, 1024px, 1440px viewports without horizontal page overflow.

## Data Requirements
- Featured novel metadata, top recent updates, latest releases, top genre counts, user reading history.

## Privacy, Safety, and Security
- Public surface; exposes no user data, private paths, or internal IDs.

## Acceptance Criteria
- At most 5 rails rendered above footer.
- Hero CTA links directly to novel chapter.
- No duplicate generic "browse everything" CTA outside rail headers.

## Implementation Mapping
- `frontend/app/(public)/home/page.tsx`
- `frontend/components/public/spotlight-hero.tsx`
- `frontend/components/public/novel-rail.tsx`
