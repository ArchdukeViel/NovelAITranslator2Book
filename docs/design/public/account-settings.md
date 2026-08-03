# Dokushodo - Account Settings

## Design Task
Design the account settings page with profile, login methods, and key contribution.

## Product Context
Account settings currently cover linked login methods; profile and key contribution are not available yet.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface favors a restrained warm-light aesthetic: a washi paper background with near-black ink text, vermillion reserved for the single primary action on a card or screen, and soft teal used only for secondary surfaces. The desktop shell is a slim header with the brand mark on the left, inline navigation, a search overlay trigger, a theme toggle, and a user menu, above a persistent footer with catalog, help, legal, and account links. Mobile replaces the header with a compact bar and a fixed bottom tab bar offering Home, Browse, Search, Library, and Account. Cards are quiet: white paper, thin borders, six pixel corners, no shadow. Imagery is limited to the brand mark, gradient book covers generated from title and author, and three restrained illustrations for empty, error, and maintenance states. Serif typography is reserved for novel titles and reading matter; sans-serif covers interface text; monospace marks metadata such as identifiers and timestamps. Motion is subtle and short, never decorative. The platform tells the truth: unavailable features state that they are unavailable, ranking shows a quiet not-live notice, and empty states point to a clear next step. The settled state is calm, legible, and free of noise.

## Page Goal
Show what can be managed today and state honestly what cannot.

## Audience and Access
Signed-in readers only.

## Primary Action
Managing a linked login method.

## Information Hierarchy
- Page heading Account Settings
- Profile card: not available
- Linked Login Methods card with Google
- API Key Contribution card: not available

## Desktop Composition
- Stacked cards in one column
- Linked Login Methods shows the Google method with a not-available note for management

## Mobile Composition
- Cards stack full width

## Page Anatomy
- Account shell
- Page heading block
- Profile card
- Linked Login Methods card
- API Key Contribution card
- Public footer

## Key Components
- Profile card
- Linked Login Methods card
- API Key Contribution card

## Representative Content
- Account Settings
- Profile
- Linked Login Methods
- Google
- API Key Contribution

## Normal Settled State
Three quiet cards; each unavailable feature states so in plain words.

## Alternate Visual States
- Single login method with no removal option

## Interaction Cues
- Unavailable cards are visibly non-interactive

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive element
- Complete keyboard navigation, including the search overlay and the mobile tab bar
- Semantic heading order starting at H1
- Reduced motion honored: no movement when requested
- Tap targets at least 44 px on mobile

## Assets

## Preserve Exactly
- Card names
- Google as the login method label
- Honest not-available wording

## Avoid
- Password change forms the system does not support
- Fake connected device lists

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
