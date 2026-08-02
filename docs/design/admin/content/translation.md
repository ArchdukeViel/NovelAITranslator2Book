# Admin Content — Translation Jobs Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | admin |
| Domain | content |
| Routes | `/admin/translation` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(admin)/admin/translation/page.tsx` |

## Purpose
Orchestration dashboard for dispatching and monitoring AI translation batch jobs.

## User Goal
Queue novel chapters for translation, select AI provider/model, adjust concurrency, and observe live job progress.

## Audience and Permissions
- **Owners (`role="owner"`):** Authorized access.

## Primary Action
"Dispatch Translation Batch" button.

## Information Hierarchy
1. Page Header ("Translation Jobs", Subtitle)
2. Queue Configuration Card (Target novel select, chapter range input, provider select, prompt version, concurrency slider)
3. Active Translation Jobs Table (Job ID, novel title, progress bar, active provider, status, Pause/Cancel actions)

## Page Anatomy
- Configuration form card + Active jobs data table.

## Desktop Layout
Configuration card (top) + full width jobs table (bottom).

## Mobile Layout
Full width layout.

## Interaction Flow
- Submitting configuration queues translation job and adds row to active jobs table.

## Authentication or Authorization Behavior
- Requires owner role.

## States

### Initial
Loading skeletons.

### Loading
Active job polling loader.

### Empty
"No active translation jobs."

### Pending
Dispatch mutation in flight.

### Settled
Active translation batch running.

### Recoverable Error
"Failed to queue translation job."

### Unavailable
Translation worker service offline.

### Unauthorized or Forbidden
403 Forbidden.

### Success
Toast confirmation on job dispatch.

## Components
- `Panel`
- `Table`
- `Button`
- `Progress`

## Content and Copy
- Header: "AI Translation Orchestration"

## Accessibility
- Form sliders and selects fully keyboard accessible.

## Responsive Behavior
- Reflows cleanly across viewports.

## Data Requirements
- Active translation jobs list and available AI provider models.

## Privacy, Safety, and Security
- Owner-only access. Masked credential usage.

## Acceptance Criteria
- Live progress bar updates dynamically as chapters settle.

## Implementation Mapping
- `frontend/app/(admin)/admin/translation/page.tsx`
