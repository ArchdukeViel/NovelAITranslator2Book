# Dokushodo - Error

## Design Task
Design the unexpected error page with clear exits.

## Product Context
Shown when a route throws an unexpected error.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface uses a restrained warm-light aesthetic: washi paper, near-black ink, vermillion for the primary action, and muted teal for secondary surfaces. The desktop shell is a fixed 56px header with the brand mark, search, notifications, account controls, and a collapsible navigation panel up to 320px wide; navigation reflects the current Home, News, Library, Browse Novels, Ranking, Random Novel, Request Novels, Contributions, and FAQ surfaces. Mobile uses a compact header and fixed bottom tabs for Home, Browse, Search, Library, and Account. Cards use quiet paper surfaces, thin borders, six-pixel corners, and restrained elevation. Covers use deterministic bookplate or gradient treatments; illustrations are reserved for empty, error, and maintenance states. Serif typography carries titles and reading matter, sans-serif handles interface text, and monospace is reserved for metadata. Motion is brief and functional. The platform presents truthful ranking periods, loading, unavailable, and no-data states, while contribution settings show masked credential lifecycle and usage states without exposing key material. The settled state is calm, legible, tactile, and free of digital clutter.

## Page Goal
Acknowledge the failure and offer a way forward without technical detail.

## Audience and Access
All visitors.

## Primary Action
Return home.

## Information Hierarchy
- Heading Something went wrong
- Quiet explanation line
- Actions: Return home and Browse catalog

## Desktop Composition
- Centered block with heading and two quiet actions

## Mobile Composition
- Same centered block stacked, actions full width

## Page Anatomy
- Public header
- Error block
- Public footer

## Key Components
- Heading
- Action links

## Representative Content
- Something went wrong
- Return home
- Browse catalog

## Normal Settled State
A calm centered heading with two quiet links; no stack traces, no alarm colors.

## Alternate Visual States
- None

## Interaction Cues
- Both actions are clear links

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive element
- Complete keyboard navigation, including the search overlay and the mobile tab bar
- Semantic heading order starting at H1
- Reduced motion honored: no movement when requested
- Tap targets at least 44 px on mobile

## Assets
- AlertTriangle icon capsule / card surface error fallback layout (PNG illustration deleted)

## Preserve Exactly
- The exact heading
- Both exit actions

## Avoid
- Error codes and stack traces
- Blame copy

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
