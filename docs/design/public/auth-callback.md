# Dokushodo - Auth Callback

## Design Task
Design the transient sign-in processing surface.

## Product Context
After external sign-in, the callback page shows a brief processing state before redirecting.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface uses a restrained warm-light aesthetic: washi paper, near-black ink, vermillion for the primary action, and muted teal for secondary surfaces. The desktop shell is a fixed 56px header with the brand mark, search, notifications, account controls, and a collapsible navigation panel up to 320px wide; navigation reflects the current Home, News, Library, Browse Novels, Ranking, Random Novel, Request Novels, Contributions, and FAQ surfaces. Mobile uses a compact header and fixed bottom tabs for Home, Browse, Search, Library, and Account. Cards use quiet paper surfaces, thin borders, six-pixel corners, and restrained elevation. Covers use deterministic bookplate or gradient treatments; illustrations are reserved for empty, error, and maintenance states. Serif typography carries titles and reading matter, sans-serif handles interface text, and monospace is reserved for metadata. Motion is brief and functional. The platform presents truthful ranking periods, loading, unavailable, and no-data states, while contribution settings show masked credential lifecycle and usage states without exposing key material. The settled state is calm, legible, tactile, and free of digital clutter.

## Page Goal
Reassure the reader that sign-in is in progress.

## Audience and Access
All visitors completing an external sign-in.

## Primary Action
None; automatic.

## Information Hierarchy
- Centered static heading Signing In
- Brief processing line
- Automatic redirect

## Desktop Composition
- Centered quiet block with a small spinner

## Mobile Composition
- Same centered block

## Page Anatomy
- Public header
- Processing block
- Public footer

## Key Components
- Processing block
- Spinner

## Representative Content
- Signing In

## Normal Settled State
A calm centered message with a quiet spinner; nothing else on the surface.

## Alternate Visual States
- Error state with a retry action when sign-in fails

## Interaction Cues
- Spinner is quiet and never jittery
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
- The exact heading
- Automatic redirect behavior

## Avoid
- Progress percentages
- Marketing copy during processing

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
