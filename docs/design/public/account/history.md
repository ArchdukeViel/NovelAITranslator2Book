# Account — Reading History Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | public |
| Domain | account |
| Routes | `/account/history` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(public)/account/history/page.tsx` |

## Purpose
Reverse-chronological reading log displaying previously read novel chapters.

## User Goal
Review past reading history, check timestamps, and jump back to previous chapters.

## Audience and Permissions
- **Guests:** Displays `LoginPrompt`.
- **Authenticated Users:** Access full reading history log.

## Primary Action
Resume chapter from history log entry.

## Information Hierarchy
1. Header ("Reading History", Clear History button)
2. History Log List (Grouped by date: Today, Yesterday, Earlier)
3. Log Entry Row (Novel title, chapter number, timestamp, Resume Reading CTA)

## Page Anatomy
- Date-grouped list container.
- Individual log entry rows with clear text link to target chapter.

## Desktop Layout
Single column list container (960px max width).

## Mobile Layout
Full width mobile list rows.

## Interaction Flow
- Clicking log entry row navigates to chapter reader.
- Clicking "Clear History" opens confirmation dialog.

## Authentication or Authorization Behavior
- Requires authenticated session.

## States

### Initial
Loading list skeletons.

### Loading
Pulse animation on history rows.

### Empty
"No reading history recorded yet. Start reading a novel to build your log!" with link to `/browse-novels`.

### Pending
Clear history mutation in flight.

### Settled
Populated reading history log.

### Recoverable Error
"Failed to load history." with Retry button.

### Unavailable
Backend offline.

### Unauthorized or Forbidden
`LoginPrompt` displayed.

### Success
Toast confirmation on clearing history.

## Components
- `AccountShell`
- `Button`

## Content and Copy
- Header: "Reading History"
- Empty: "No reading history recorded yet."

## Accessibility
- Grouped list using semantic `<ul>` and date heading landmarks.

## Responsive Behavior
- Reflows cleanly down to 320px mobile viewports.

## Data Requirements
- Authenticated user reading history array (`useHistory`).

## Privacy, Safety, and Security
- Private reading log; accessible only to account owner.

## Acceptance Criteria
- Log entries display exact read chapter numbers and formatted timestamps.

## Implementation Mapping
- `frontend/app/(public)/account/history/page.tsx`
