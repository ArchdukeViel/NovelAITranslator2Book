# Admin Moderation — Review Moderation Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | admin |
| Domain | moderation |
| Routes | `/admin/reviews` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(admin)/admin/reviews/page.tsx` |

## Purpose
Operator interface for reviewing, approving, and moderating public user novel reviews.

## User Goal
Review pending user reviews, check content quality/spoilers, and publish or reject reviews.

## Audience and Permissions
- **Owners (`role="owner"`):** Authorized access.

## Primary Action
"Publish Review" / "Reject Review" buttons.

## Information Hierarchy
1. Page Header ("Review Moderation", Status Filter Tabs: Pending, Published, Rejected)
2. Bulk Actions Bar (Select all checkbox, "Publish Selected", "Reject Selected")
3. Review Data Table (Checkbox, novel title, reviewer rating stars, review body text, status badge, submission date, actions)

## Page Anatomy
- Bulk selection bar + Moderation table.

## Desktop Layout
Full width moderation table with expandable review body text.

## Mobile Layout
Horizontal scrolling table container.

## Interaction Flow
- Clicking "Publish" makes review visible on public novel detail pages.
- Clicking "Reject" suppresses review from public APIs.

## Authentication or Authorization Behavior
- Requires owner role (`require_role("owner")`).

## States

### Initial
Loading table skeletons.

### Loading
Table pulse loading.

### Empty
"No reviews matching selected status filter."

### Pending
Publish/Reject mutation in flight.

### Settled
Populated moderation table.

### Recoverable Error
"Failed to load reviews list."

### Unavailable
Backend offline.

### Unauthorized or Forbidden
403 Forbidden.

### Success
Toast confirmation on review status change.

## Components
- `Table`
- `Button`
- `Badge`

## Content and Copy
- Header: "Community Review Moderation"

## Accessibility
- Checkboxes and bulk actions fully keyboard operable.

## Responsive Behavior
- Reflows cleanly across viewports.

## Data Requirements
- Paginated reviews list with moderation status (`pending`, `published`, `rejected`).

## Privacy, Safety, and Security
- Rejected reviews hidden from public reader APIs. Actions logged in `AuditLog`.

## Acceptance Criteria
- Bulk selection allows batch publishing or rejecting of reviews.

## Implementation Mapping
- `frontend/app/(admin)/admin/reviews/page.tsx`
