# Account — Overview Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | public |
| Domain | account |
| Routes | `/account` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(public)/account/page.tsx`, `frontend/components/public/account-shell.tsx` |

## Purpose
Account summary dashboard for authenticated readers, serving as the main entry point to personal user features.

## User Goal
View reading activity summary, check unread notifications, and navigate to account sub-pages.

## Audience and Permissions
- **Guests:** Redirected to `/login?next=/account`.
- **Authenticated Users:** Full dashboard access.

## Primary Action
Navigate to Library Board or Resume Reading.

## Information Hierarchy
1. Reader Welcome Header (Display name / Email)
2. Reading Stats Summary Cards (Saved titles count, read chapters count, unread notification count)
3. Recent Activity Widget (Last read novel shortcut)
4. Navigation Grid / Hub (Shortcuts to Library, History, Notifications, Requests, Reviews, Settings)

## Page Anatomy
- Desktop: Left Account Sidebar + Dashboard Summary Cards.
- Mobile: Account/More Hub layout with profile header, library shortcuts, and More list.

## Desktop Layout
Main content container (960px max width) with persistent left sidebar navigation.

## Mobile Layout
Single column scrollable hub list.

## Interaction Flow
- Tapping shortcut cards opens corresponding `/account/*` page.

## Authentication or Authorization Behavior
- Requires authenticated session (`usePublicAuth`). Unauthenticated visits land on sign-in form.

## States

### Initial
Dashboard skeleton cards.

### Loading
Loading indicator for user stats.

### Empty
If user has zero activity, displays onboarding card: "Welcome to Dokushodo! Explore the catalog to start your library."

### Pending
Not applicable.

### Settled
Populated dashboard with recent activity and stats summary.

### Recoverable Error
"Could not load account details." with Retry button.

### Unavailable
Backend offline.

### Unauthorized or Forbidden
Redirects to login page.

### Success
Not applicable.

## Components
- `AccountShell`
- `Panel`
- `Button`

## Content and Copy
- Header: "Account Overview"
- Welcome: "Welcome back, {username}"

## Accessibility
- Proper landmark structure and visible focus states across account links.

## Responsive Behavior
- Mobile transforms account navigation into the thumb-reachable Account/More hub.

## Data Requirements
- Authenticated user profile, reading history count, library items count, unread notifications count.

## Privacy, Safety, and Security
- Accessible only to session owner; user identity derived strictly from session cookie.

## Acceptance Criteria
- Unauthenticated visitors are safely redirected to sign-in.
- Mobile Account tab doubles as the navigation hub.

## Implementation Mapping
- `frontend/app/(public)/account/page.tsx`
- `frontend/components/public/account-shell.tsx`
