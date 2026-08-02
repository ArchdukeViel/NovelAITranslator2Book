# Account Domain

## Contract Metadata

| Field | Value |
|---|---|
| Domain | account |
| Surface | public |
| Routes | `/account`, `/account/library`, `/account/history`, `/account/reviews`, `/account/notifications`, `/account/requests`, `/account/contributions`, `/account/settings` |
| Authority | `docs/DESIGN.md` -> `docs/design/public/account/README.md` |

## Domain Purpose

Authenticated reader dashboard, personal saved library board, reading history log, user-authored review management, notifications center, submitted request tracking, API contribution status, and account settings.

## Contained Routes

- `/account` -> [`overview.md`](overview.md)
- `/account/library` -> [`library.md`](library.md)
- `/account/history` -> [`history.md`](history.md)
- `/account/reviews` -> [`reviews.md`](reviews.md)
- `/account/notifications` -> [`notifications.md`](notifications.md)
- `/account/requests` -> [`requests.md`](requests.md)
- `/account/contributions` -> [`contributions.md`](contributions.md)
- `/account/settings` -> [`settings.md`](settings.md)

## Audience and Permissions

- **Guests:** Accessing any `/account/*` route displays an authentication prompt (`LoginPrompt`) preserving target destination URL (`next` parameter).
- **Authenticated Users (`role="user"` / `role="owner"`):** Full access to personal library, history, notifications, and settings.

## Shared Navigation and Shell Behavior

- **Desktop:** Persistent left Account Sidebar listing account pages + main content pane.
- **Mobile:** Account tab acts as Account/More hub, featuring account shortcuts plus quick links to auxiliary pages (Ranking, Request Novel, FAQ, Legal).

## Shared Data and State Rules

- Requires active session cookie. Session identity derived automatically from backend authentication context.
- User data hooks (`useLibrary`, `useHistory`, `useUserReviews`, `useNotifications`, `useRequests`) maintain local TanStack Query cache.

## Shared Terminology

- `Your Yokocho`: Categorized library board status groups (Reading, Plan to Read, Completed, Dropped).
- `Reading Log`: Reverse-chronological history of read chapters.

## Page Index

| Page | Document | Purpose |
|---|---|---|
| Overview | `overview.md` | Account summary dashboard and mobile nav hub |
| Library Board | `library.md` | Personal saved novel shelf ("Your Yokocho") |
| Reading History | `history.md` | Reverse-chronological chapter reading log |
| Authored Reviews | `reviews.md` | Management page for reviews written by user |
| Notifications | `notifications.md` | System and release alert center |
| Requests History | `requests.md` | Tracking page for user novel/chapter requests |
| Contributions | `contributions.md` | API contribution status banner |
| Settings | `settings.md` | Profile, password, and preference management |

## Cross-Domain Dependencies

- Connects to `discovery` domain for catalog browsing shortcuts.
- Connects to `reading` domain for opening saved novels and resuming chapters.
