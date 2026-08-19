# Dokushodo - Library

## Design Task
Design the personal library with reading-status groups and board and list views.

## Product Context
Signed-in readers organize saved novels by reading status.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface uses a restrained warm-light aesthetic: washi paper, near-black ink, vermillion for the primary action, and muted teal for secondary surfaces. The desktop shell is a fixed 56px header with the brand mark, search, notifications, account controls, and a collapsible navigation panel up to 320px wide; navigation reflects the current Home, News, Library, Browse Novels, Ranking, Random Novel, Request Novels, Contributions, and FAQ surfaces. Mobile uses a compact header and fixed bottom tabs for Home, Browse, Search, Library, and Account. Cards use quiet paper surfaces, thin borders, six-pixel corners, and restrained elevation. Covers use deterministic bookplate or gradient treatments; illustrations are reserved for empty, error, and maintenance states. Serif typography carries titles and reading matter, sans-serif handles interface text, and monospace is reserved for metadata. Motion is brief and functional. The platform presents truthful ranking periods, loading, unavailable, and no-data states, while contribution settings show masked credential lifecycle and usage states without exposing key material. The settled state is calm, legible, tactile, and free of digital clutter.

## Page Goal
Show personal library with tabs (Library, Updates, History, Followed Folders) and move saved novels between reading statuses.

## Audience and Access
Publicly viewable; unauthenticated guests see tabbed header with in-page login banner ("You need to login to use Library features"). Signed-in readers access full saved novel lists.

## Primary Action
Opening a saved novel, switching library tab, or changing reading status.

## Information Hierarchy
- Page heading Library
- Top tabs: Library, Updates, History, Followed Folders
- Unauthenticated banner (if guest) with Sign in CTA
- Search and sort controls
- View toggle: board or list
- Status groups (under Library tab): Reading, Plan to read, Completed, Dropped, Unknown

## Desktop Composition
- Toolbar with search, sort, and view toggle
- Board view: status columns derived from the response, including an explicit Unknown group when needed
- List view: one table-like list with a status column
- Status change via a quiet menu on each card

## Mobile Composition
- Toolbar compacts to search and view toggle
- Board columns stack as labeled sections
- Status change via card actions

## Page Anatomy
- Account shell
- Page heading block
- Toolbar
- Board or list content
- Public footer

## Key Components
- Status group header
- Library card
- Status change menu
- View toggle
- Empty group message

## Representative Content
- Library
- Reading, Plan to read, Completed, Dropped
- Board, List
- Search by title or author

## Normal Settled State
Tidy status groups with quiet cards; the current view state is clearly selected and unknown persisted statuses are not silently discarded.

## Alternate Visual States
- Empty library with the empty illustration and a browse link
- Empty single group
- List view layout

## Interaction Cues
- Status change menu updates the group instantly
- Cards link to novel detail
- View toggle switches layout without data loss

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive element
- Complete keyboard navigation, including the search overlay and the mobile tab bar
- Semantic heading order starting at H1
- Reduced motion honored: no movement when requested
- Tap targets at least 44 px on mobile

## Assets
- empty.png for the empty library

## Preserve Exactly
- Group names exactly as listed
- Board and list views both available
- Unknown statuses remain visibly labeled rather than being invented or dropped

## Avoid
- Cover carousels
- Drag and drop as the only way to change status
- Counts that conflict with actual data

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
