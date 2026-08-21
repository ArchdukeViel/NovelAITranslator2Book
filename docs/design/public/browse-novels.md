# Dokushodo - Browse Novels

## Design Task
Design the catalog browse page with search, filters, and grid and list views.

## Product Context
The main catalog surface. Genre, tag, and source pages reuse the same layout with a preset filter applied.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface uses a restrained warm-light aesthetic: washi paper, near-black ink, vermillion for the primary action, and muted teal for secondary surfaces. The desktop shell is a fixed 56px header with the brand mark, search, notifications, account controls, and a collapsible navigation panel up to 320px wide; navigation reflects the current Home, News, Library, Browse Novels, Ranking, Random Novel, Request Novels, Contributions, and FAQ surfaces. Mobile uses a compact header and fixed bottom tabs for Home, Browse, Search, Library, and Account. Cards use quiet paper surfaces, thin borders, six-pixel corners, and restrained elevation. Covers use deterministic bookplate or gradient treatments; illustrations are reserved for empty, error, and maintenance states. Serif typography carries titles and reading matter, sans-serif handles interface text, and monospace is reserved for metadata. Motion is brief and functional. The platform presents truthful ranking periods, loading, unavailable, and no-data states, while contribution settings show masked credential lifecycle and usage states without exposing key material. The settled state is calm, legible, tactile, and free of digital clutter.

## Page Goal
Let a reader narrow thousands of novels to a shortlist in a few moves.

## Audience and Access
All visitors, signed in or signed out.

## Primary Action
Selecting a novel card to open its detail page.

## Information Hierarchy
- Page title and result count
- Search field with placeholder Search by title or author
- Filter and sort controls
- View toggle and active preset chip
- Novel results grid or list
- Pagination

## Desktop Composition
- Toolbar row: search field on the left, filter and sort controls and view toggle on the right
- Status filter with options Any status, Ongoing, Completed, Hiatus, Dropped
- Sort controls: Recently added, Recently updated, Title, Chapter count; order Descending or Ascending
- Chapter count min and max inputs; genre include and exclude pickers
- Results as a responsive card grid, or as a compact table-like list when list view is active

## Mobile Composition
- Search field pinned below the header
- Filter and sort open as bottom sheets
- Grid shows two cards per row
- List view shows compact rows with thumbnail, title, and status badge

## Page Anatomy
- Public header
- Page heading block
- Search and toolbar row
- Results area
- Pagination
- Public footer

## Key Components
- Search field
- Status filter
- Sort and order selectors
- Chapter count inputs
- Genre include and exclude pickers
- Grid and list view toggle
- Novel card and list row
- Pagination bar

## Representative Content
- Browse the library
- Search by title or author
- Any status, Ongoing, Completed, Hiatus, Dropped
- Recently added, Recently updated, Title, Chapter count
- Descending, Ascending
- Grid, List

## Normal Settled State
An orderly grid of quiet novel cards on washi paper with a single toolbar row above and pagination below.

## Alternate Visual States
- Empty results with the empty illustration and a clear your filters action
- Loading state with skeleton cards
- Preset pages show the applied genre, tag, or source chip in the toolbar

## Interaction Cues
- Active filters and view state are visibly selected
- Card hover raises border emphasis
- Pagination buttons are quiet text links with clear current page
- Empty results always offer an action to clear filters

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive element
- Complete keyboard navigation, including the search overlay and the mobile tab bar
- Semantic heading order starting at H1
- Reduced motion honored: no movement when requested
- Tap targets at least 44 px on mobile

## Assets
- brand-mark.png from the Dokushodo brand asset pack
- Gradient book covers generated from novel title and author
- empty.png illustration for empty states where listed

## Preserve Exactly
- Exact control labels listed above
- Grid and list view both available at all breakpoints
- Result count next to the page title
- No badges or counts invented on cards

## Avoid
- Infinite scroll without a visible alternative
- Auto-applying filters while typing
- Fake result counts
- Card overlays or hover menus

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
