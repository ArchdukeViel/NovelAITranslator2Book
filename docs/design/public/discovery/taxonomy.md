# Discovery — Taxonomy & Source Pages

## Contract Metadata

| Field | Value |
|---|---|
| Surface | public |
| Domain | discovery |
| Routes | `/tags/[tag]`, `/genres/[genre]`, `/sources/[sourceKey]` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(public)/tags/[tag]/page.tsx`, `frontend/app/(public)/genres/[genre]/page.tsx`, `frontend/app/(public)/sources/[sourceKey]/page.tsx` |

## Purpose
Canonical landing pages for specific tags, genres, or scraping source platforms.

## User Goal
Explore all novels associated with a specific genre, tag, or original scraping platform.

## Audience and Permissions
- **Guests & Authenticated Users:** Open public access.

## Primary Action
Browse filtered novel cards for the specified taxonomy term.

## Information Hierarchy
1. Breadcrumbs (Home -> Browse -> Taxonomy Name)
2. Taxonomy Header (Category title, description, total matching count)
3. Novel Grid (Rich Browse Cards pre-filtered to taxonomy parameter)
4. Pagination Controls

## Page Anatomy
- **Header Section:** Dynamic title based on URL parameter (e.g., "Genre: Isekai", "Source: Kakuyomu").
- **Grid Layout:** Standard novel card grid (`NovelCard`).

## Desktop Layout
Centered 1280px container with 3-4 column grid.

## Mobile Layout
Single column novel card grid.

## Interaction Flow
- Clicking a novel card opens novel detail.
- Pagination buttons switch result pages.

## Authentication or Authorization Behavior
- Open access.

## States

### Initial
Page skeleton matching grid layout.

### Loading
Card grid skeletons.

### Empty
"No novels currently registered under this tag/genre/source." with link to Browse Catalog.

### Pending
Not applicable.

### Settled
Populated taxonomy grid.

### Recoverable Error
"Could not load taxonomy page." with Retry CTA.

### Unavailable
Backend offline.

### Unauthorized or Forbidden
Not applicable.

### Success
Not applicable.

## Components
- `NovelCard`
- `Pagination`
- `Breadcrumbs`

## Content and Copy
- Header labels: "Genre", "Tag", "Source Platform"

## Accessibility
- Page H1 matches taxonomy name.
- Indexable canonical URLs for search engine optimization.

## Responsive Behavior
- Reflows from 1 column on mobile to 4 columns on desktop.

## Data Requirements
- Taxonomy metadata and pre-filtered novel catalog listing.

## Privacy, Safety, and Security
- Public SEO routes; `/tags/[tag]` and `/genres/[genre]` set `index, follow`.

## Acceptance Criteria
- Canonical tags and genres generate unique, indexable pages.
- Correct novel counts displayed in header.

## Implementation Mapping
- `frontend/app/(public)/tags/[tag]/page.tsx`
- `frontend/app/(public)/genres/[genre]/page.tsx`
- `frontend/app/(public)/sources/[sourceKey]/page.tsx`
