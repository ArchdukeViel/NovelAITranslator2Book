# Admin Content — Library Management Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | admin |
| Domain | content |
| Routes | `/admin/library` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(admin)/admin/library/page.tsx` |

## Purpose
Operator administration view for managing all novels registered in the system catalog.

## User Goal
Inspect novel stats, edit metadata, launch translations, manage chapters, or delete novels.

## Audience and Permissions
- **Owners (`role="owner"`):** Authorized access.

## Primary Action
Edit novel metadata or launch translation job.

## Information Hierarchy
1. Page Header ("Catalog Library", "Import Document" button)
2. Filter & Search Bar (Source select, Status filter, Search title input)
3. Catalog Data Table (Cover thumbnail, title, source, chapter count, translation status, actions)

## Page Anatomy
- High-density tabular layout.

## Desktop Layout
Full width data table with action drop-down menus per row.

## Mobile Layout
Horizontal scrolling table container.

## Interaction Flow
- Clicking novel row opens detail editor or chapter list.
- Clicking "Delete" opens confirmation modal.

## Authentication or Authorization Behavior
- Requires owner role (`require_role("owner")`).

## States

### Initial
Loading table skeletons.

### Loading
Table pulse loading.

### Empty
"No novels found in catalog."

### Pending
Delete or edit mutation in flight.

### Settled
Populated catalog table.

### Recoverable Error
"Failed to load catalog library."

### Unavailable
Backend offline.

### Unauthorized or Forbidden
403 Forbidden.

### Success
Toast confirmation on metadata save or novel deletion.

## Components
- `Table`
- `Button`
- `Badge`

## Content and Copy
- Header: "Catalog Library Management"

## Accessibility
- Data table headers bound; action buttons labeled.

## Responsive Behavior
- Table scrolls horizontally on narrow viewports.

## Data Requirements
- Paginated catalog novels list.

## Privacy, Safety, and Security
- Destructive actions require modal confirmation.

## Acceptance Criteria
- Displays accurate translated vs untranslated chapter counts.

## Implementation Mapping
- `frontend/app/(admin)/admin/library/page.tsx`
