# Discovery — Browse Catalog Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | public |
| Domain | discovery |
| Routes | `/browse-novels` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(public)/browse-novels/page.tsx`, `frontend/components/public/browse-filters.tsx`, `frontend/components/public/novel-card.tsx` |

## Purpose
Comprehensive catalog search and filtering grid page for exploring all available translated web novels.

## User Goal
Search, filter by genre/tag/status, sort, and discover novels matching specific reader preferences.

## Audience and Permissions
- **Guests & Authenticated Users:** Unrestricted catalog access.

## Primary Action
Filter selections and novel card discovery.

## Information Hierarchy
1. Page Header (Title: "Browse Novels", Subtitle)
2. Controls Bar (Result count, Sort dropdown, Grid/List view toggle, Random novel CTA)
3. Active Filter Chips (Removable filter pills + "Clear all" action)
4. Main Layout (Desktop: Left Filter Sidebar + Main Card Grid; Mobile: Filter Sheet Trigger + Single Column Grid)
5. Pagination Controls

## Page Anatomy
- **Filter Controls:** Search query input, Genre include/exclude selectors, Tag selector, Status checkboxes (Ongoing, Completed, Hiatus), Sort options (Recently Updated, Title, Chapter Count, Rating).
- **Novel Grid:** Grid of Rich Browse Cards (`NovelCard`).
- **Pagination:** Numeric page selector.

## Desktop Layout
Left sidebar (280px) for filter controls + right grid container (minmax 3 columns). Sidebar sticky header for reset actions.

## Mobile Layout
Filter controls collapse into bottom sheet triggered by "Filters (N)" button. Grid reflows to single column.

## Interaction Flow
- Selecting a filter instantly updates URL search parameters (`?genre=isekai&sort=updated_at`).
- Clicking filter chip removes specific parameter.
- Tapping card opens novel detail. Tapping save icon toggles library status.

## Authentication or Authorization Behavior
- Open access for all visitors.

## States

### Initial
Catalog loading state with grid skeletons.

### Loading
Grid card skeletons displayed during query refetching.

### Empty
"No novels match your filter criteria. Try clearing filters or searching for another term." with prominent "Clear All Filters" button.

### Pending
Not applicable.

### Settled
Populated grid of novel cards with active pagination.

### Recoverable Error
"Could not load catalog. Check your connection and try again." with Retry CTA.

### Unavailable
Backend catalog service offline error state.

### Unauthorized or Forbidden
Not applicable.

### Success
Not applicable.

## Components
- `BrowseFilters`
- `NovelCard`
- `Pagination`
- `Button`
- `Badge`

## Content and Copy
- Empty state: "No novels matched your filters."
- Reset button: "Clear all filters"

## Accessibility
- Form inputs have associated `<label>` elements.
- Filter drawer traps focus when open on mobile.
- Keyboard navigable pagination and card actions.

## Responsive Behavior
- Reflows from 1 column (mobile < 768px) to 2 columns (tablet) to 3-4 columns (desktop >= 1024px).

## Data Requirements
- Paginated novel catalog items, total item count, available genre/tag facets.

## Privacy, Safety, and Security
- URL parameters sanitized; query inputs escaped.

## Acceptance Criteria
- URL search parameters stay synchronized with active filters.
- Back/Forward browser navigation preserves active filter state.
- Empty search results present recovery CTA.

## Implementation Mapping
- `frontend/app/(public)/browse-novels/page.tsx`
- `frontend/components/public/browse-filters.tsx`
