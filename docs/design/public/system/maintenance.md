# System — Maintenance Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | public |
| Domain | system |
| Routes | `/maintenance` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(public)/maintenance/page.tsx` |

## Purpose
Scheduled downtime and system maintenance status surface.

## User Goal
Understand that the service is undergoing scheduled maintenance and when it will return online.

## Audience and Permissions
- **Guests & Authenticated Users:** Displayed during scheduled system maintenance windows.

## Primary Action
Refresh page or return later.

## Information Hierarchy
1. Vector Illustration (`maintenance.svg`)
2. Heading ("Under Scheduled Maintenance")
3. Subtitle Copy ("Dokushodo is briefly offline for updates. We'll be back shortly!")
4. Refresh CTA Button

## Page Anatomy
- Centered shopfront illustration container.

## Desktop Layout
Centered container.

## Mobile Layout
Centered container.

## Interaction Flow
- Clicking "Refresh" re-checks system availability.

## Authentication or Authorization Behavior
- Open access.

## States

### Initial
Maintenance screen active.

### Loading
Not applicable.

### Empty
Not applicable.

### Pending
Not applicable.

### Settled
Maintenance state displayed.

### Recoverable Error
Not applicable.

### Unavailable
Active maintenance window.

### Unauthorized or Forbidden
Not applicable.

### Success
Not applicable.

## Components
- `Button`
- `Illustration`

## Content and Copy
- Heading: "Closed for Maintenance"
- Copy: "We are currently performing scheduled maintenance."

## Accessibility
- High contrast text layout.

## Responsive Behavior
- Vector illustration scales down cleanly on mobile.

## Data Requirements
- Static content.

## Privacy, Safety, and Security
- Suppresses database and API calls completely while active.

## Acceptance Criteria
- Maintenance screen does not trigger database or backend queries.

## Implementation Mapping
- `frontend/app/(public)/maintenance/page.tsx`
