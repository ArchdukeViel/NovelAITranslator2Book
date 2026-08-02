# Admin Operations — Audit Log Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | admin |
| Domain | operations |
| Routes | `/admin/audit` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(admin)/admin/audit/page.tsx` |

## Purpose
Immutable administrative audit log viewer for reviewing system mutations and security events.

## User Goal
Inspect administrative audit records to track who performed specific actions (takedowns, user disables, credential updates).

## Audience and Permissions
- **Owners (`role="owner"`):** Authorized access.

## Primary Action
Filter and search audit log records.

## Information Hierarchy
1. Page Header ("System Audit Log", Action Category Filter)
2. Audit Data Table (Event ID, action name, performing owner ID, target entity, timestamp, IP address)

## Page Anatomy
- Searchable, immutable audit data table.

## Desktop Layout
Full width data table with expandable detail rows.

## Mobile Layout
Horizontal scrolling table container.

## Interaction Flow
- Filtering by action category updates log view.

## Authentication or Authorization Behavior
- Requires owner role (`require_role("owner")`). Audit records are strictly read-only and immutable.

## States

### Initial
Loading table skeletons.

### Loading
Table loading state.

### Empty
"No audit events found."

### Pending
Not applicable.

### Settled
Populated audit log table.

### Recoverable Error
"Failed to load audit records."

### Unavailable
Backend offline.

### Unauthorized or Forbidden
403 Forbidden.

### Success
Not applicable.

## Components
- `Table`
- `Badge`
- `Select`

## Content and Copy
- Header: "Administrative Audit Trail"

## Accessibility
- Data table properly structured for screen readers.

## Responsive Behavior
- Table scrolls horizontally on narrow viewports.

## Data Requirements
- Paginated audit log records (`useAdminAudit`).

## Privacy, Safety, and Security
- Read-only; administrative mutations recorded automatically in DB.

## Acceptance Criteria
- Displays accurate timestamps and target entity identifiers for all administrative actions.

## Implementation Mapping
- `frontend/app/(admin)/admin/audit/page.tsx`
