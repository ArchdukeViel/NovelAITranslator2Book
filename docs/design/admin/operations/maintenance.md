# Admin Operations — Maintenance Status Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | admin |
| Domain | operations |
| Routes | `/admin/maintenance` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(admin)/admin/maintenance/page.tsx` |

## Purpose
Detailed inspector viewer for registered background maintenance tasks, cron schedules, and durable runtime state.

## User Goal
Inspect durable background task schedules, last completion timestamps, sanitized results, and trigger dry-run cleanups.

## Audience and Permissions
- **Owners (`role="owner"`):** Authorized access.

## Primary Action
Inspect task state or execute manual cleanup trigger.

## Information Hierarchy
1. Page Header ("System Maintenance & Scheduler Durability")
2. Registered Tasks Table (Task name, cron expression, timezone, durable state, last execution timestamp, redacted result summary, next eligibility timestamp, manual trigger action)

## Page Anatomy
- Durable task inspector data table.

## Desktop Layout
Full width data table with task execution dialogs.

## Mobile Layout
Horizontal scrolling table container.

## Interaction Flow
- Clicking "Run Task" opens modal dialog with dry-run toggle; executing sends run request to backend.

## Authentication or Authorization Behavior
- Requires owner role (`require_role("owner")`).

## States

### Initial
Loading task skeletons.

### Loading
Table pulse loading.

### Empty
"No maintenance tasks registered."

### Pending
Manual cleanup trigger in flight.

### Settled
Populated maintenance status table.

### Recoverable Error
"Failed to load maintenance status."

### Unavailable
Backend offline.

### Unauthorized or Forbidden
403 Forbidden.

### Success
Toast notification with sanitized task result.

## Components
- `Table`
- `Button`
- `Badge`
- `Dialog`

## Content and Copy
- Header: "Durable Maintenance Schedules"

## Accessibility
- Dialog traps focus; action buttons clearly labeled.

## Responsive Behavior
- Table scrolls horizontally on narrow viewports.

## Data Requirements
- Maintenance runtime states list (`useAdminMaintenance`).

## Privacy, Safety, and Security
- Redacts raw DB errors, file paths, hostnames, and lock holder details from displayed result summaries.

## Acceptance Criteria
- Displays every registered task, cron/timezone, durable state, last execution, redacted result, and next eligibility.

## Implementation Mapping
- `frontend/app/(admin)/admin/maintenance/page.tsx`
