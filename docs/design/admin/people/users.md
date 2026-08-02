# Admin People — User Management Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | admin |
| Domain | people |
| Routes | `/admin/users`, `/admin/users/[userId]` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(admin)/admin/users/page.tsx`, `frontend/app/(admin)/admin/users/[userId]/page.tsx` |

## Purpose
User administration table for managing registered accounts, inspecting user activity, and updating roles or status.

## User Goal
Search registered users, view user activity, toggle account active/disabled status, or update user role.

## Audience and Permissions
- **Owners (`role="owner"`):** Authorized access.

## Primary Action
Toggle account active/disabled status or update role.

## Information Hierarchy
1. Page Header ("User Management", Search Input)
2. Users Data Table (User ID, email, display name, role badge, status badge, created date, actions)
3. User Detail View (`[userId]` route: User profile, session log, requests history, authored reviews)

## Page Anatomy
- Searchable user management data table + user detail inspector pane.

## Desktop Layout
Full width data table with search header.

## Mobile Layout
Horizontal scrolling table container.

## Interaction Flow
- Clicking "Disable" opens confirmation modal; disables account and revokes active sessions.

## Authentication or Authorization Behavior
- Requires owner role (`require_role("owner")`). System prevents disabling the bootstrap owner account.

## States

### Initial
Loading table skeletons.

### Loading
Table pulse loading.

### Empty
"No users found matching search query."

### Pending
Status update mutation in flight.

### Settled
Populated user management table.

### Recoverable Error
"Failed to load user accounts."

### Unavailable
Backend offline.

### Unauthorized or Forbidden
403 Forbidden.

### Success
Toast confirmation on user status change.

## Components
- `Table`
- `Button`
- `Badge`
- `Input`

## Content and Copy
- Header: "User Administration"

## Accessibility
- Destructive status toggles require modal confirmation.

## Responsive Behavior
- Table scrolls horizontally on narrow viewports.

## Data Requirements
- Paginated users list with search filter (`useAdminUsers`).

## Privacy, Safety, and Security
- Password hashes and private session tokens are never rendered.

## Acceptance Criteria
- Disabling a user immediately rejects their active authentication sessions.

## Implementation Mapping
- `frontend/app/(admin)/admin/users/page.tsx`
- `frontend/app/(admin)/admin/users/[userId]/page.tsx`
