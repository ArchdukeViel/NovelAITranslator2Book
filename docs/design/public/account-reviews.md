# Dokushodo - My Reviews

## Design Task
Design the reader's review list with ratings and deletion.

## Product Context
Reviews the reader published on novels, with the ability to delete them.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface uses a restrained warm-light aesthetic: washi paper, near-black ink, vermillion for the primary action, and muted teal for secondary surfaces. The desktop shell is a fixed 56px header with the brand mark, search, notifications, account controls, and a collapsible navigation panel up to 320px wide; navigation reflects the current Home, News, Library, Browse Novels, Ranking, Random Novel, Request Novels, Contributions, and FAQ surfaces. Mobile uses a compact header and fixed bottom tabs for Home, Browse, Search, Library, and Account. Cards use quiet paper surfaces, thin borders, six-pixel corners, and restrained elevation. Covers use deterministic bookplate or gradient treatments; illustrations are reserved for empty, error, and maintenance states. Serif typography carries titles and reading matter, sans-serif handles interface text, and monospace is reserved for metadata. Motion is brief and functional. The platform presents truthful ranking periods, loading, unavailable, and no-data states, while contribution settings show masked credential lifecycle and usage states without exposing key material. The settled state is calm, legible, tactile, and free of digital clutter.

## Page Goal
Show every review the reader wrote and allow removal.

## Audience and Access
Signed-in readers only.

## Primary Action
Deleting a review.

## Information Hierarchy
- Page heading My Reviews
- Review list
- Delete action per review

## Desktop Composition
- Rows with star rating, novel title, review text, and date
- Quiet delete action on each row

## Mobile Composition
- Rows stack with full-width review text
- Delete stays visible but quiet

## Page Anatomy
- Account shell
- Page heading block
- Review list
- Public footer

## Key Components
- Star rating
- Review row
- Delete action

## Representative Content
- My Reviews
- Star ratings filled in accent color
- Delete

## Normal Settled State
A quiet list of review cards with accent-filled stars and one quiet delete action each.

## Alternate Visual States
- Empty state with a browse link
- Delete confirmation state

## Interaction Cues
- Delete requires confirmation
- Star ratings are display only here

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive element
- Complete keyboard navigation, including the search overlay and the mobile tab bar
- Semantic heading order starting at H1
- Reduced motion honored: no movement when requested
- Tap targets at least 44 px on mobile

## Assets
- empty.png for the empty list

## Preserve Exactly
- Accent color for filled stars
- Confirmation before delete

## Avoid
- Edit actions the system does not offer
- Average rating math not present in data

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
