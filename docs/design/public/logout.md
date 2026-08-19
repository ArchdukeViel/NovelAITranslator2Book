# Dokushodo - Logout

## Design Task
Design the sign-out confirmation surface.

## Product Context
Sign-out completes and this page confirms the session ended.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface uses a restrained warm-light aesthetic: washi paper, near-black ink, vermillion for the primary action, and muted teal for secondary surfaces. The desktop shell is a fixed 56px header with the brand mark, search, notifications, account controls, and a collapsible navigation panel up to 320px wide; navigation reflects the current Home, News, Library, Browse Novels, Ranking, Random Novel, Request Novels, Contributions, and FAQ surfaces. Mobile uses a compact header and fixed bottom tabs for Home, Browse, Search, Library, and Account. Cards use quiet paper surfaces, thin borders, six-pixel corners, and restrained elevation. Covers use deterministic bookplate or gradient treatments; illustrations are reserved for empty, error, and maintenance states. Serif typography carries titles and reading matter, sans-serif handles interface text, and monospace is reserved for metadata. Motion is brief and functional. The platform presents truthful ranking periods, loading, unavailable, and no-data states, while contribution settings show masked credential lifecycle and usage states without exposing key material. The settled state is calm, legible, tactile, and free of digital clutter.

## Page Goal
Confirm the reader is signed out and send them home.

## Audience and Access
Signed-in readers who chose to sign out.

## Primary Action
Return home.

## Information Hierarchy
- Heading Signing out
- Confirmation line
- Return home action

## Desktop Composition
- Centered quiet block
- Return home as the single primary button

## Mobile Composition
- Same centered block, full width button

## Page Anatomy
- Public header
- Confirmation block
- Public footer

## Key Components
- Confirmation block
- Return home button

## Representative Content
- Signing out
- You have been signed out. You are now browsing as a guest.
- Return home

## Normal Settled State
A single quiet confirmation with one vermillion button.

## Alternate Visual States
- Sign-in again link as a secondary quiet action

## Interaction Cues
- Return home navigates to the home page

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
- The exact confirmation wording
- Single primary action

## Avoid
- Confetti or farewell graphics
- Session stats

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
