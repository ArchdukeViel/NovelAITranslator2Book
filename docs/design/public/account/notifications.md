# Account — Notifications Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | public |
| Domain | account |
| Routes | `/account/notifications` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(public)/account/notifications/page.tsx`, `frontend/components/public/notification-list.tsx` |

## Purpose
Alerts and notification center for system announcements, new chapter releases, and request status updates.

## User Goal
Read alerts, clear unread notifications, and jump to target updates.

## Audience and Permissions
- **Guests:** Displays `LoginPrompt`.
- **Authenticated Users:** Manage notifications.

## Primary Action
Mark notifications as read and navigate to target link.

## Information Hierarchy
1. Page Header ("Notifications", "Mark all as read" button)
2. Notification List (Unread items highlighted, severity indicator, message text, timestamp, link)

## Page Anatomy
- List container with semantic status tokens (`--info-text`, `--success-text`, `--warning-text`).

## Desktop Layout
Single column list container (960px max width).

## Mobile Layout
Full width list rows.

## Interaction Flow
- Clicking notification row marks it as read and navigates to target route.
- Clicking "Mark all as read" updates all items.

## Authentication or Authorization Behavior
- Requires authenticated session (`useNotifications`).

## States

### Initial
Loading list skeletons.

### Loading
Pulse loading state for notifications.

### Empty
"No notifications right now. You're all caught up!"

### Pending
Mark read mutation in flight.

### Settled
Populated notifications list.

### Recoverable Error
"Could not load notifications." with Retry button.

### Unavailable
Backend offline.

### Unauthorized or Forbidden
`LoginPrompt` displayed.

### Success
State updated to read.

## Components
- `NotificationList`
- `Badge`
- `Button`

## Content and Copy
- Header: "Notifications"
- Action: "Mark all as read"

## Accessibility
- Live announcements for unread alert updates.

## Responsive Behavior
- Reflows cleanly across viewports.

## Data Requirements
- Authenticated user notifications array (`useNotifications`).

## Privacy, Safety, and Security
- Private alerts scoped to logged-in user.

## Acceptance Criteria
- Uses semantic status text tokens (`--{status}-text`) without hardcoded Tailwind color overrides.

## Implementation Mapping
- `frontend/app/(public)/account/notifications/page.tsx`
- `frontend/components/public/notification-list.tsx`
