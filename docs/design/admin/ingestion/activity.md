# Admin Ingestion — Activity Monitor Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | admin |
| Domain | ingestion |
| Routes | `/admin/activity`, `/admin/activity/[activityId]` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(admin)/admin/activity/page.tsx`, `frontend/app/(admin)/admin/activity/[activityId]/page.tsx` |

## Purpose
Real-time monitoring interface and detailed log viewer for background crawling and fetching activities.

## User Goal
Monitor background crawling progress, inspect error logs, and retry failed crawl operations.

## Audience and Permissions
- **Owners (`role="owner"`):** Authorized access.

## Primary Action
Inspect log output or retry failed job.

## Information Hierarchy
1. Page Header ("Activity Logs", Auto-refresh toggle)
2. Activity Table (Activity ID, task type, target novel, status badge, progress bar, timestamp, view log CTA)
3. Detail Log View (`[activityId]` route: Sanitized terminal log output, raw stats, retry action)

## Page Anatomy
- High-density operator data table + monospaced log terminal block.

## Desktop Layout
Full width data table with auto-refresh toggle.

## Mobile Layout
Horizontal scrolling table container.

## Interaction Flow
- Clicking activity row opens detailed log view (`/admin/activity/[activityId]`).

## Authentication or Authorization Behavior
- Requires owner role.

## States

### Initial
Loading table skeletons.

### Loading
Table pulse loading state.

### Empty
"No activity logs recorded."

### Pending
Not applicable.

### Settled
Populated activity table.

### Recoverable Error
"Failed to load activity log."

### Unavailable
Backend offline.

### Unauthorized or Forbidden
403 Forbidden message.

### Success
Not applicable.

## Components
- `Table`
- `Badge`
- `Button`

## Content and Copy
- Header: "Background Activity Monitor"

## Accessibility
- Data table headers properly bound.

## Responsive Behavior
- Table scrolls horizontally on narrow screens.

## Data Requirements
- Paginated activity log array (`useAdminActivity`).

## Privacy, Safety, and Security
- Log output sanitized; masks internal paths and sensitive headers.

## Acceptance Criteria
- Status badges reflect job states (Pending, Running, Completed, Failed).

## Implementation Mapping
- `frontend/app/(admin)/admin/activity/page.tsx`
