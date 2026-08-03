# Dokushodo - Library

## Design Task
Design the personal library with reading-status groups and board and list views.

## Product Context
Signed-in readers organize saved novels by reading status.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface favors a restrained warm-light aesthetic: a washi paper background with near-black ink text, vermillion reserved for the single primary action on a card or screen, and soft teal used only for secondary surfaces. The desktop shell is a slim header with the brand mark on the left, inline navigation, a search overlay trigger, a theme toggle, and a user menu, above a persistent footer with catalog, help, legal, and account links. Mobile replaces the header with a compact bar and a fixed bottom tab bar offering Home, Browse, Search, Library, and Account. Cards are quiet: white paper, thin borders, six pixel corners, no shadow. Imagery is limited to the brand mark, gradient book covers generated from title and author, and three restrained illustrations for empty, error, and maintenance states. Serif typography is reserved for novel titles and reading matter; sans-serif covers interface text; monospace marks metadata such as identifiers and timestamps. Motion is subtle and short, never decorative. The platform tells the truth: unavailable features state that they are unavailable, ranking shows a quiet not-live notice, and empty states point to a clear next step. The settled state is calm, legible, and free of noise.

## Page Goal
Show exactly where every saved novel stands and move it between statuses.

## Audience and Access
Signed-in readers only.

## Primary Action
Opening a saved novel or changing its status.

## Information Hierarchy
- Page heading Library
- Search and sort controls
- View toggle: board or list
- Status groups: Reading, Plan to read, Completed, Dropped

## Desktop Composition
- Toolbar with search, sort, and view toggle
- Board view: four columns, one per status group, each with novel cards
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
Four tidy groups with quiet cards; the current view state is clearly selected.

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
- Statuses never invented

## Avoid
- Cover carousels
- Drag and drop as the only way to change status
- Counts that conflict with actual data

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
