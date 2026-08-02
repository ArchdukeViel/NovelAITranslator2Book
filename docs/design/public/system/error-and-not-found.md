# System — Error & Not Found Pages

## Contract Metadata

| Field | Value |
|---|---|
| Surface | public |
| Domain | system |
| Routes | 404 (`/not-found`), 500 (`/error`) |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/not-found.tsx`, `frontend/app/error.tsx`, `frontend/app/(public)/not-found.tsx`, `frontend/app/(public)/error.tsx` |

## Purpose
Friendly, accessible error handling surfaces for missing routes or unhandled exceptions.

## User Goal
Understand that a page is missing or an error occurred, and easily navigate back to safety.

## Audience and Permissions
- **Guests & Authenticated Users:** Displayed automatically on 404 or 500 errors.

## Primary Action
"Return Home" or "Browse Catalog" CTA button.

## Information Hierarchy
1. Vector Illustration (`not-found.svg` for 404)
2. Friendly Error Heading ("Page not found - wrong turn in the alley")
3. Subtitle Description
4. Primary Action Button ("Back to Home")

## Page Anatomy
- Centered error container.

## Desktop Layout
Centered container with vector illustration.

## Mobile Layout
Centered container adapted for small screens.

## Interaction Flow
- Clicking primary action button returns user to `/home` or `/browse-novels`.

## Authentication or Authorization Behavior
- Open access.

## States

### Initial
Error page rendered immediately.

### Loading
Not applicable.

### Empty
Not applicable.

### Pending
Not applicable.

### Settled
Error page active.

### Recoverable Error
"An unexpected error occurred." with "Try again" button.

### Unavailable
Backend service offline.

### Unauthorized or Forbidden
Not applicable.

### Success
Not applicable.

## Components
- `Button`
- `Illustration`

## Content and Copy
- 404 Heading: "404 - Page Not Found"
- CTA: "Back to catalog"

## Accessibility
- Page sets `noindex, follow` header to prevent indexing broken URLs.

## Responsive Behavior
- Vector illustrations scale down cleanly on mobile screens.

## Data Requirements
- Static error content.

## Privacy, Safety, and Security
- Never exposes raw backend stack traces or internal server paths.

## Acceptance Criteria
- 404 page renders friendly illustration and working return CTA.

## Implementation Mapping
- `frontend/app/not-found.tsx`
- `frontend/app/(public)/not-found.tsx`
