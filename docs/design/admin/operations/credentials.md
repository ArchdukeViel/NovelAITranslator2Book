# Admin Operations — Credentials Management Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | admin |
| Domain | operations |
| Routes | `/admin/credentials` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(admin)/admin/credentials/page.tsx` |

## Purpose
Provider API key and external service credential administration surface.

## User Goal
Configure, update, and test API keys for AI translation providers (Gemini), storage backends (S3/R2), and email (SMTP).

## Audience and Permissions
- **Owners (`role="owner"`):** Authorized access.

## Primary Action
"Save Credential" / "Test Connection" buttons.

## Information Hierarchy
1. Page Header ("Credential Management", Security Notice)
2. Provider Credentials List (Provider name, status badge, masked key preview, updated timestamp, edit form, Test Connection CTA)

## Page Anatomy
- Security-masked credential cards.

## Desktop Layout
Panel grid for credentials management.

## Mobile Layout
Single column panel stack.

## Interaction Flow
- Inputting new key and clicking "Save" encrypts key backend side using `PROVIDER_CREDENTIAL_ENCRYPTION_KEY`.
- Clicking "Test Connection" verifies provider API access.

## Authentication or Authorization Behavior
- Requires owner role (`require_role("owner")`).

## States

### Initial
Loading credential skeletons.

### Loading
Connection test loader.

### Empty
"No external provider credentials configured."

### Pending
Credential save or test mutation in flight.

### Settled
Credential panels rendered with masked keys.

### Recoverable Error
"Failed to update provider credentials."

### Unavailable
Backend offline.

### Unauthorized or Forbidden
403 Forbidden.

### Success
Toast confirmation: "Connection test succeeded."

## Components
- `Panel`
- `Input`
- `Button`
- `Badge`

## Content and Copy
- Header: "External Provider Credentials"

## Accessibility
- Masked inputs use `type="password"`; clear accessibility labels.

## Responsive Behavior
- Reflows cleanly across viewports.

## Data Requirements
- Masked provider credentials list (`useAdminCredentials`).

## Privacy, Safety, and Security
- Credentials masked via `mask-token.ts`; raw secret values are NEVER rendered in HTML or returned in API responses.

## Acceptance Criteria
- Full credential strings are masked completely in UI.

## Implementation Mapping
- `frontend/app/(admin)/admin/credentials/page.tsx`
