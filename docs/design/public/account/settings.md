# Account — Settings Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | public |
| Domain | account |
| Routes | `/account/settings` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(public)/account/settings/page.tsx` |

## Purpose
User profile, authentication credentials, content preferences, and session management page.

## User Goal
Update username, change password, toggle content safety (mature content) filters, and manage active sessions.

## Audience and Permissions
- **Guests:** Displays `LoginPrompt`.
- **Authenticated Users:** Manage account settings.

## Primary Action
Save settings or update password.

## Information Hierarchy
1. Page Header ("Account Settings", Subtitle)
2. Profile Settings Section (Display name, Email display)
3. Password Change Section (Current password, new password inputs + Save button)
4. Content Safety Section (Include mature content toggle)
5. Session Management Section (Logout action)

## Page Anatomy
- Panel containers grouping form sections.

## Desktop Layout
Single column panel group (960px max width).

## Mobile Layout
Full width panel group.

## Interaction Flow
- Form inputs update local state; clicking "Save" sends update mutation.

## Authentication or Authorization Behavior
- Requires authenticated user session.

## States

### Initial
Settings form loading skeleton.

### Loading
Form loading state.

### Empty
Not applicable.

### Pending
Password/profile update mutation in flight.

### Settled
Settings form loaded with current user preferences.

### Recoverable Error
"Could not update settings. Check your input and try again."

### Unavailable
Backend offline.

### Unauthorized or Forbidden
`LoginPrompt` displayed.

### Success
Toast confirmation on settings update.

## Components
- `Panel`
- `Button`
- `Input`

## Content and Copy
- Header: "Account Settings"
- Save action: "Save changes"

## Accessibility
- Input elements bound to `<label>` tags. Error messages announced via live regions.

## Responsive Behavior
- Reflows cleanly across viewports.

## Data Requirements
- Authenticated user settings data (`usePublicAuth`).

## Privacy, Safety, and Security
- Password inputs use `type="password"`. Requires current password verification for changes.

## Acceptance Criteria
- User display name updates accurately across account interfaces.

## Implementation Mapping
- `frontend/app/(public)/account/settings/page.tsx`
