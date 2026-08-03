# Account — Library Board Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | public |
| Domain | account |
| Routes | `/account/library` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(public)/account/library/page.tsx`, `frontend/components/public/library-board.tsx` |

## Purpose
Personal saved novel shelf ("Library Shelf") organized by status columns or list rows.

## User Goal
Manage saved web novels, track unread chapter updates, filter by status, and jump directly to reading.

## Audience and Permissions
- **Guests:** Displays `LoginPrompt` inviting user to sign in to access library.
- **Authenticated Users:** Full board and list view access.

## Primary Action
Resume reading saved novel or update reading status.

## Information Hierarchy
1. Page Header ("Library", Subtitle)
2. Controls Bar (Board/List view toggle, Status filter pills, Search library input)
3. Main Content (Board View: 4 Status Columns; List View: Compact Row List)

## Page Anatomy
- **Status Categories ("Lantern Badges"):**
  - Reading (Solid `--primary` fill)
  - Plan to Read (Outlined `--muted-foreground`)
  - Completed (Solid `--info` fill)
  - Dropped (Solid `--muted` fill)
- **Cards/Rows:** Displays cover, title, status pill, progress marker, "+N new" update badge when new chapters arrive.

## Desktop Layout
4-column status board layout on desktop (or dense list view if toggled).

## Mobile Layout
Default compact list view for narrow screens with filter dropdown.

## Interaction Flow
- Tapping view toggle switches between Board and List view.
- Clicking novel card opens detail or resume chapter link.
- Changing status dropdown mutates novel reading status.

## Authentication or Authorization Behavior
- Requires authenticated user session.

## States

### Initial
Library board loading skeletons.

### Loading
Pulse animation on board columns.

### Empty
Centered onboarding banner: "Nothing saved yet — browse the catalog to start your shelf." with CTA button "Browse Novels".

### Pending
Status update mutation in flight.

### Settled
Populated status board/list with active items.

### Recoverable Error
"Could not load library items." with Retry button.

### Unavailable
Backend offline.

### Unauthorized or Forbidden
`LoginPrompt` displayed.

### Success
Toast confirmation on status update.

## Components
- `LibraryBoard`
- `NovelCard`
- `Badge`
- `Button`

## Content and Copy
- Empty state CTA: "Browse catalog to start your shelf"
- Update badge: "+N new"

## Accessibility
- Board columns labeled with heading levels.
- Full keyboard drag/move or dropdown selection for status updates.

## Responsive Behavior
- Desktop defaults to 4-column board; Mobile defaults to dense list view.

## Data Requirements
- Authenticated user saved novels list with progress and unread chapter flags (`useLibrary`).

## Privacy, Safety, and Security
- Private reader data; visible only to account owner.

## Acceptance Criteria
- Card "+N new" badge highlights novels with newly released chapters since last read.
- View toggle selection persists during session.

## Implementation Mapping
- `frontend/app/(public)/account/library/page.tsx`
- `frontend/components/public/library-board.tsx`
