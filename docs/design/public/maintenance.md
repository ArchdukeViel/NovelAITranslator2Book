# Dokushodo - Maintenance

## Design Task
Design the maintenance status page with honest current state.

## Product Context
Shows maintenance mode status; the default state says maintenance is not active.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface uses a restrained warm-light aesthetic: washi paper, near-black ink, vermillion for the primary action, and muted teal for secondary surfaces. The desktop shell is a fixed 56px header with the brand mark, search, notifications, account controls, and a collapsible navigation panel up to 320px wide; navigation reflects the current Home, News, Library, Browse Novels, Ranking, Random Novel, Request Novels, Contributions, and FAQ surfaces. Mobile uses a compact header and fixed bottom tabs for Home, Browse, Search, Library, and Account. Cards use quiet paper surfaces, thin borders, six-pixel corners, and restrained elevation. Covers use deterministic bookplate or gradient treatments; illustrations are reserved for empty, error, and maintenance states. Serif typography carries titles and reading matter, sans-serif handles interface text, and monospace is reserved for metadata. Motion is brief and functional. The platform presents truthful ranking periods, loading, unavailable, and no-data states, while contribution settings show masked credential lifecycle and usage states without exposing key material. The settled state is calm, legible, tactile, and free of digital clutter.

## Page Goal
State the platform status honestly and quietly.

## Audience and Access
All visitors during or outside maintenance windows.

## Primary Action
None; informational.

## Information Hierarchy
- Eyebrow Dokushodo
- Heading Maintenance
- Status line: Dokushodo is not currently in maintenance mode.
- Numbered explanatory sections

## Desktop Composition
- Centered column with a status line in a quiet callout
- Numbered sections below

## Mobile Composition
- Same column full width

## Page Anatomy
- Public header
- Static content block
- Public footer

## Key Components
- Status callout
- Numbered sections

## Representative Content
- Dokushodo
- Maintenance
- Dokushodo is not currently in maintenance mode.

## Normal Settled State
A quiet status line and plain prose; no alarm styling when nothing is wrong.

## Alternate Visual States
- Active maintenance state with a clear notice and no interactive features

## Interaction Cues
- None in the settled state

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive element
- Complete keyboard navigation, including the search overlay and the mobile tab bar
- Semantic heading order starting at H1
- Reduced motion honored: no movement when requested
- Tap targets at least 44 px on mobile

## Assets
- brand-logo.svg
- Wrench icon capsule / card status grid layout (PNG illustration deleted)

## Preserve Exactly
- The exact default status wording

## Avoid
- Countdown timers
- Fake progress bars
- Alarm colors when idle

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
