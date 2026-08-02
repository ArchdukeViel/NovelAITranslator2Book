# Authentication — Login & Signup Page / Modal

## Contract Metadata

| Field | Value |
|---|---|
| Surface | public |
| Domain | authentication |
| Routes | `/login` (Standalone page) & Modal/Sheet wrapper |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(public)/login/page.tsx`, `frontend/components/public/login-prompt.tsx`, `frontend/components/public/public-auth-dialog.tsx` |

## Purpose
Primary user sign-in and new account registration interface.

## User Goal
Sign in with existing credentials/Google OAuth or register a new reader account.

## Audience and Permissions
- **Guests:** Access form to authenticate.
- **Authenticated Users:** Redirected to `/account` or `next` parameter URL.

## Primary Action
"Sign In" or "Create Account" submit button.

## Information Hierarchy
1. Form Mode Toggle (Tab switcher: "Sign In" vs "Create Account")
2. OAuth Section (Google OAuth button)
3. Divider ("or continue with email")
4. Email & Password Input Fields
5. Form Error Announcements
6. Submit Button
7. Modal Close Icon (Top-right X button, when rendered in modal dialog)

## Page Anatomy
- Card container (`LoginPrompt`) rendered standalone or inside modal dialog.

## Desktop Layout
Centered 400px card. When invoked as modal, centered dialog with dark backdrop.

## Mobile Layout
Full width card. When invoked as modal, full-screen bottom sheet.

## Interaction Flow
- Tapping mode toggle switches between sign-in and sign-up fields.
- Submitting form validates inputs, sends auth API request, and redirects to target destination on success.

## Authentication or Authorization Behavior
- Sets secure session cookie on success. Preserves `next` URL parameter destination.

## States

### Initial
Empty login form ready for input.

### Loading
Input controls disabled; submit button shows spinner loader.

### Empty
Not applicable.

### Pending
Auth API request in flight.

### Settled
Not applicable (redirects on success).

### Recoverable Error
- Login Error: Generic copy *"Invalid email or password."* (prevents username enumeration).
- Signup Error: Reason-specific copy (e.g., *"Email already registered"*, *"Password must be at least 8 characters"*).

### Unavailable
Google OAuth probe offline: shows explicit unavailable notice rather than looping fallback.

### Unauthorized or Forbidden
Not applicable.

### Success
Redirect to target destination (`next` parameter).

## Components
- `LoginPrompt`
- `PublicAuthDialog`
- `Button`
- `Input`

## Content and Copy
- Form title: "Welcome to Dokushodo"
- Login error: "Invalid email or password"

## Accessibility
- Single modal close affordance (X icon).
- Inputs bound to `<label>` tags. Error messages announced via live regions.

## Responsive Behavior
- Renders as dialog on desktop and full-screen sheet on mobile.

## Data Requirements
- Auth credentials (email, password) or OAuth code.

## Privacy, Safety, and Security
- Password inputs masked. Never logs passwords or secret tokens.

## Acceptance Criteria
- Generic error copy enforced for login failures.
- Reason-specific error copy enforced for signup failures.

## Implementation Mapping
- `frontend/app/(public)/login/page.tsx`
- `frontend/components/public/login-prompt.tsx`
