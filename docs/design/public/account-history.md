# Dokushodo - Reading History

## Design Task
Design the reading history list of chapters opened while signed in.

## Product Context
History is recorded only for signed-in reading sessions.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface uses a restrained warm-light aesthetic: washi paper, near-black ink, vermillion for the primary action, and muted teal for secondary surfaces. The desktop shell is a fixed 56px header with the brand mark, search, notifications, account controls, and a collapsible navigation panel up to 320px wide; navigation reflects the current Home, News, Library, Browse Novels, Ranking, Random Novel, Request Novels, Contributions, and FAQ surfaces. Mobile uses a compact header and fixed bottom tabs for Home, Browse, Search, Library, and Account. Cards use quiet paper surfaces, thin borders, six-pixel corners, and restrained elevation. Covers use deterministic bookplate or gradient treatments; illustrations are reserved for empty, error, and maintenance states. Serif typography carries titles and reading matter, sans-serif handles interface text, and monospace is reserved for metadata. Motion is brief and functional. The platform presents truthful ranking periods, loading, unavailable, and no-data states, while contribution settings show masked credential lifecycle and usage states without exposing key material. The settled state is calm, legible, tactile, and free of digital clutter.

## Page Goal
Let a reader return to any previously opened chapter in one click.

## Audience and Access
Signed-in readers only.

## Primary Action
Reopening a chapter from the list.

## Information Hierarchy
- Page heading Reading History
- Description line
- Chronological list of chapters
- Back to Browse link

## Desktop Composition
- Description under the heading
- List rows with novel title, chapter title, and opened timestamp
- Row click opens the chapter

## Mobile Composition
- Same list full width
- Rows with thumbnails omitted to keep density

## Page Anatomy
- Account shell
- Page heading block
- History list
- Public footer

## Key Components
- History row
- Back to Browse link

## Representative Content
- Reading History
- Chapters you have opened while signed in.
- Back to Browse

## Normal Settled State
A quiet chronological list with monospace timestamps and clear row hover.

## Alternate Visual States
- Empty history with the empty illustration and a browse link
- Loading skeleton rows

## Interaction Cues
- Row hover raises border emphasis
- Row click opens the chapter reader

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive element
- Complete keyboard navigation, including the search overlay and the mobile tab bar
- Semantic heading order starting at H1
- Reduced motion honored: no movement when requested
- Tap targets at least 44 px on mobile

## Assets
- empty.png for the empty history

## Preserve Exactly
- The exact description wording
- Chronological order newest first

## Avoid
- Progress percentages not recorded in data
- Grouping by date unless data exists
- Clearing history without confirmation

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
