# Dokushodo - Logout

## Design Task
Design the sign-out confirmation surface.

## Product Context
Sign-out completes and this page confirms the session ended.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface favors a restrained warm-light aesthetic: a washi paper background with near-black ink text, vermillion reserved for the single primary action on a card or screen, and soft teal used only for secondary surfaces. The desktop shell is a slim header with the brand mark on the left, inline navigation, a search overlay trigger, a theme toggle, and a user menu, above a persistent footer with catalog, help, legal, and account links. Mobile replaces the header with a compact bar and a fixed bottom tab bar offering Home, Browse, Search, Library, and Account. Cards are quiet: white paper, thin borders, six pixel corners, no shadow. Imagery is limited to the brand mark, gradient book covers generated from title and author, and three restrained illustrations for empty, error, and maintenance states. Serif typography is reserved for novel titles and reading matter; sans-serif covers interface text; monospace marks metadata such as identifiers and timestamps. Motion is subtle and short, never decorative. The platform tells the truth: unavailable features state that they are unavailable, ranking shows a quiet not-live notice, and empty states point to a clear next step. The settled state is calm, legible, and free of noise.

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
