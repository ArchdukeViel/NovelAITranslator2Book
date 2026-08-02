# Authentication — Session Flows & Callbacks

## Contract Metadata

| Field | Value |
|---|---|
| Surface | public |
| Domain | authentication |
| Routes | `/auth/callback`, `/logout` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(public)/auth/callback/page.tsx`, `frontend/app/(public)/logout/page.tsx` |

## Purpose
OAuth authorization code callback landing and session sign-out processing.

## User Goal
Complete third-party Google OAuth login or safely log out of active session.

## Audience and Permissions
- **Guests / Auth Users:** Access callback page during OAuth flow.
- **Authenticated Users:** Access `/logout` to terminate session.

## Primary Action
Automatic redirect processing.

## Information Hierarchy
1. Processing Spinner
2. Status Message ("Completing sign in..." / "Signing out...")

## Page Anatomy
- Centered status card.

## Desktop Layout
Centered container.

## Mobile Layout
Centered container.

## Interaction Flow
- `/auth/callback` validates OAuth state, establishes cookie, and redirects to target destination.
- `/logout` calls backend logout API, clears local query cache, and redirects to `/home`.

## Authentication or Authorization Behavior
- Backend session validation and revocation.

## States

### Initial
Processing spinner.

### Loading
Active session API call in flight.

### Empty
Not applicable.

### Pending
Callback processing.

### Settled
Redirect to destination page.

### Recoverable Error
"Authentication failed. Return to sign in." with link to `/login`.

### Unavailable
OAuth provider offline.

### Unauthorized or Forbidden
Not applicable.

### Success
Redirect executed.

## Components
- Loader spinner
- `Panel`

## Content and Copy
- Callback message: "Completing sign in..."
- Logout message: "Signing out..."

## Accessibility
- Status messages announced via `aria-live="polite"`.

## Responsive Behavior
- Clean centered presentation across all devices.

## Data Requirements
- OAuth authorization code and state parameter.

## Privacy, Safety, and Security
- Code exchange performed server-side. OAuth tokens masked.

## Acceptance Criteria
- `/logout` invalidates session cookie completely.

## Implementation Mapping
- `frontend/app/(public)/auth/callback/page.tsx`
- `frontend/app/(public)/logout/page.tsx`
