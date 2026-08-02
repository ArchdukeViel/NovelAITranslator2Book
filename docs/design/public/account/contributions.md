# Account — Contributions Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | public |
| Domain | account |
| Routes | `/account/contributions` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(public)/account/contributions/page.tsx` |

## Purpose
View provider API-key contribution program status.

## User Goal
Inspect API contribution status and guidelines.

## Audience and Permissions
- **Guests:** Displays `LoginPrompt`.
- **Authenticated Users:** Access contribution status page.

## Primary Action
Read contribution status guidelines.

## Information Hierarchy
1. Page Header ("API Contributions", Subtitle)
2. Warning Banner (Styled with `--warning-text` explaining current contribution availability)
3. Guidelines Container

## Page Anatomy
- Informational notice container.

## Desktop Layout
Centered panel layout (960px max width).

## Mobile Layout
Full width mobile panel.

## Interaction Flow
- Read-only informational surface.

## Authentication or Authorization Behavior
- Requires authenticated session.

## States

### Initial
Loading state.

### Loading
Skeleton indicator.

### Empty
Not applicable.

### Pending
Not applicable.

### Settled
Informational banner rendered.

### Recoverable Error
"Failed to load contribution status."

### Unavailable
Backend offline.

### Unauthorized or Forbidden
`LoginPrompt` displayed.

### Success
Not applicable.

## Components
- `Panel`
- `Badge`

## Content and Copy
- Banner copy: "API-key contributions are currently disabled."

## Accessibility
- High contrast warning banner using semantic tokens.

## Responsive Behavior
- Reflows cleanly across viewports.

## Data Requirements
- User contribution status API.

## Privacy, Safety, and Security
- Does not expose raw keys or private credentials.

## Acceptance Criteria
- Banner consumes semantic `--warning-text` tokens.

## Implementation Mapping
- `frontend/app/(public)/account/contributions/page.tsx`
