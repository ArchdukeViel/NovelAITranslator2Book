# Dokushodo - Random

## Design Task
Design the transient random novel resolving surface.

## Product Context
Choosing Surprise Me resolves a random novel; while resolving, this quiet surface is shown, then the reader is redirected to the novel or to browse with a notice.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface uses a restrained warm-light aesthetic: washi paper, near-black ink, vermillion for the primary action, and muted teal for secondary surfaces. The desktop shell is a fixed 56px header with the brand mark, search, notifications, account controls, and a collapsible navigation panel up to 320px wide; navigation reflects the current Home, News, Library, Browse Novels, Ranking, Random Novel, Request Novels, Contributions, and FAQ surfaces. Mobile uses a compact header and fixed bottom tabs for Home, Browse, Search, Library, and Account. Cards use quiet paper surfaces, thin borders, six-pixel corners, and restrained elevation. Covers use deterministic bookplate or gradient treatments; illustrations are reserved for empty, error, and maintenance states. Serif typography carries titles and reading matter, sans-serif handles interface text, and monospace is reserved for metadata. Motion is brief and functional. The platform presents truthful ranking periods, loading, unavailable, and no-data states, while contribution settings show masked credential lifecycle and usage states without exposing key material. The settled state is calm, legible, tactile, and free of digital clutter.

## Page Goal
Borrow a moment of anticipation without noise.

## Audience and Access
All visitors.

## Primary Action
None; automatic redirect.

## Information Hierarchy
- Centered quiet message
- Small spinner
- Automatic redirect

## Desktop Composition
- Centered block with a short line and quiet spinner

## Mobile Composition
- Same centered block

## Page Anatomy
- Public header
- Resolving block
- Public footer

## Key Components
- Resolving block
- Spinner

## Representative Content
- Picking a random novel...

## Normal Settled State
A single quiet line and a small spinner on washi paper.

## Alternate Visual States
- Redirect to a random novel detail page
- Redirect to browse with the notice No novels match your filters when the catalog is empty

## Interaction Cues
- Spinner is quiet
- Redirect is automatic

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive element
- Complete keyboard navigation, including the search overlay and the mobile tab bar
- Semantic heading order starting at H1
- Reduced motion honored: no movement when requested
- Tap targets at least 44 px on mobile

## Assets
- brand-mark.png

## Preserve Exactly
- The exact resolving line
- Automatic redirect behavior

## Avoid
- Slot machine graphics
- Countdowns
- Decorative particles

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
