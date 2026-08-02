# Admin Moderation — DMCA & Takedowns Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | admin |
| Domain | moderation |
| Routes | `/admin/takedowns` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(admin)/admin/takedowns/page.tsx` |

## Purpose
DMCA legal notice management and novel takedown enforcement dashboard.

## User Goal
Log DMCA takedown notices, execute legal novel takedowns, and purge novel content from public distribution.

## Audience and Permissions
- **Owners (`role="owner"`):** Authorized access.

## Primary Action
"Execute Takedown" button.

## Information Hierarchy
1. Page Header ("DMCA Takedown Management", "Log New Notice" button)
2. Takedowns Table (Notice ID, target novel title, complainant organization, status badge, execution date, actions)

## Page Anatomy
- Legal notice log table + Execute takedown modal.

## Desktop Layout
Full width legal notice table.

## Mobile Layout
Horizontal scrolling table container.

## Interaction Flow
- Clicking "Execute Takedown" opens confirmation modal detailing impact (novel state set to HTTP 451, excluded from sitemap/search index, CDN cache purged).

## Authentication or Authorization Behavior
- Requires owner role (`require_role("owner")`).

## States

### Initial
Loading table skeletons.

### Loading
Table loading state.

### Empty
"No legal takedown notices logged."

### Pending
Takedown execution mutation in flight.

### Settled
Populated takedowns table.

### Recoverable Error
"Failed to process takedown notice."

### Unavailable
Backend offline.

### Unauthorized or Forbidden
403 Forbidden.

### Success
Toast confirmation on takedown execution.

## Components
- `Table`
- `Button`
- `Badge`
- `Dialog`

## Content and Copy
- Header: "Legal Takedown Enforcement"

## Accessibility
- Destructive action confirmation modal traps keyboard focus.

## Responsive Behavior
- Reflows cleanly across viewports.

## Data Requirements
- Takedown requests list (`useAdminTakedowns`).

## Privacy, Safety, and Security
- Complainant PII logged for audit but concealed from public APIs.

## Acceptance Criteria
- Executing a takedown immediately forces novel page to respond with HTTP 451 unavailable status.

## Implementation Mapping
- `frontend/app/(admin)/admin/takedowns/page.tsx`
