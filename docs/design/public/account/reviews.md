# Account — Authored Reviews Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | public |
| Domain | account |
| Routes | `/account/reviews` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(public)/account/reviews/page.tsx`, `frontend/components/public/rating-review.tsx` |

## Purpose
Management page for novel reviews authored by the current user.

## User Goal
View, edit, or delete submitted novel ratings and written reviews.

## Audience and Permissions
- **Guests:** Displays `LoginPrompt`.
- **Authenticated Users:** Manage personal authored reviews.

## Primary Action
Edit or delete an existing review.

## Information Hierarchy
1. Page Header ("My Reviews", Subtitle)
2. Review Cards List (Novel title link, publication status badge, star rating, review body text, submission date, Edit/Delete actions)

## Page Anatomy
- Card list container of authored reviews.
- Status badges: Published (`--success`), Pending Moderation (`--warning`), Rejected (`--destructive`).

## Desktop Layout
Single column card list (960px max width).

## Mobile Layout
Full width cards with inline action buttons.

## Interaction Flow
- Clicking "Edit" opens inline edit form.
- Clicking "Delete" displays confirmation prompt and removes review on confirm.
- Clicking novel title opens novel detail page (`/novels/[slug]?tab=reviews`).

## Authentication or Authorization Behavior
- Requires authenticated user session (`useUserReviews`).

## States

### Initial
Loading skeletons.

### Loading
Pulse loading state for review cards.

### Empty
"You haven't written any reviews yet. Visit a novel page to rate and review!"

### Pending
Delete or edit review mutation in flight.

### Settled
List of user's authored reviews.

### Recoverable Error
"Could not load your reviews." with Retry button.

### Unavailable
Backend offline.

### Unauthorized or Forbidden
`LoginPrompt` displayed.

### Success
Toast confirmation on review update or deletion.

## Components
- `RatingReview`
- `Badge`
- `Button`

## Content and Copy
- Header: "My Reviews"
- Empty: "You haven't submitted any reviews yet."

## Accessibility
- Form controls labeled; status badges carry accessible text labels.

## Responsive Behavior
- Reflows cleanly across desktop and mobile viewports.

## Data Requirements
- Authenticated user authored reviews list (`useUserReviews`).

## Privacy, Safety, and Security
- Users can manage only reviews tied to their own session.

## Acceptance Criteria
- Authored review cards display publication moderation status accurately.

## Implementation Mapping
- `frontend/app/(public)/account/reviews/page.tsx`
