# Admin Operations — System Settings Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | admin |
| Domain | operations |
| Routes | `/admin/settings` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(admin)/admin/settings/page.tsx` |

## Purpose
Global system configuration and operational parameter administration page.

## User Goal
Configure dynamic application settings such as default translation provider, system rate limits, and request thresholds.

## Audience and Permissions
- **Owners (`role="owner"`):** Authorized access.

## Primary Action
"Save Configuration" button.

## Information Hierarchy
1. Page Header ("System Settings", Subtitle)
2. Settings Sections (Default Translation Provider, Rate Limits, Maintenance Windows)
3. Save Action Bar

## Page Anatomy
- Configuration forms panel.

## Desktop Layout
Centered configuration container (720px max width).

## Mobile Layout
Full width panel container.

## Interaction Flow
- Updating settings inputs and clicking "Save" updates system settings backend side.

## Authentication or Authorization Behavior
- Requires owner role (`require_role("owner")`).

## States

### Initial
Loading settings form.

### Loading
Form loading state.

### Empty
Not applicable.

### Pending
Save settings mutation in flight.

### Settled
Form populated with active settings.

### Recoverable Error
"Failed to update system settings."

### Unavailable
Backend offline.

### Unauthorized or Forbidden
403 Forbidden.

### Success
Toast confirmation: "System settings updated."

## Components
- `Panel`
- `Input`
- `Select`
- `Button`

## Content and Copy
- Header: "Global Application Settings"

## Accessibility
- Form inputs properly labeled.

## Responsive Behavior
- Reflows cleanly across viewports.

## Data Requirements
- System settings object (`useAdminSettings`).

## Privacy, Safety, and Security
- Accessible strictly to system owners.

## Acceptance Criteria
- Configuration updates apply dynamically without requiring backend server restarts.

## Implementation Mapping
- `frontend/app/(admin)/admin/settings/page.tsx`
