# Dokushodo - Contributions

## Design Task
Design the contribution dashboard with honest not-available panels.

## Product Context
Public key contribution is not available yet; the dashboard structure exists with honest unavailable panels.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface favors a restrained warm-light aesthetic: a washi paper background with near-black ink text, vermillion reserved for the single primary action on a card or screen, and soft teal used only for secondary surfaces. The desktop shell is a slim header with the brand mark on the left, inline navigation, a search overlay trigger, a theme toggle, and a user menu, above a persistent footer with catalog, help, legal, and account links. Mobile replaces the header with a compact bar and a fixed bottom tab bar offering Home, Browse, Search, Library, and Account. Cards are quiet: white paper, thin borders, six pixel corners, no shadow. Imagery is limited to the brand mark, gradient book covers generated from title and author, and three restrained illustrations for empty, error, and maintenance states. Serif typography is reserved for novel titles and reading matter; sans-serif covers interface text; monospace marks metadata such as identifiers and timestamps. Motion is subtle and short, never decorative. The platform tells the truth: unavailable features state that they are unavailable, ranking shows a quiet not-live notice, and empty states point to a clear next step. The settled state is calm, legible, and free of noise.

## Page Goal
Present the contribution dashboard structure without implying it is live.

## Audience and Access
Signed-in readers only.

## Primary Action
None; informational until the program is live.

## Information Hierarchy
- Page heading Contribution Dashboard
- Not-available notice
- Panels: Key Health, Usage Stats, Pause, Remove

## Desktop Composition
- Notice callout at top
- Panel grid with Key Health, Usage Stats, Pause, and Remove cards, each showing not available

## Mobile Composition
- Panels stack full width

## Page Anatomy
- Account shell
- Page heading block
- Notice callout
- Panel grid
- Public footer

## Key Components
- Notice callout
- Key Health panel
- Usage Stats panel
- Pause panel
- Remove panel

## Representative Content
- Contribution Dashboard
- Public key contribution is not available yet.
- Key Health, Usage Stats, Pause, Remove

## Normal Settled State
Four quiet panels under one honest notice; no metrics, no toggles.

## Alternate Visual States
- Future live state with real key health and usage numbers

## Interaction Cues
- Panels are non-interactive in the current state

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive element
- Complete keyboard navigation, including the search overlay and the mobile tab bar
- Semantic heading order starting at H1
- Reduced motion honored: no movement when requested
- Tap targets at least 44 px on mobile

## Assets

## Preserve Exactly
- The exact not-available wording
- Panel names
- No fabricated usage numbers

## Avoid
- Fake key health bars
- Enrollment forms
- Success messaging

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
