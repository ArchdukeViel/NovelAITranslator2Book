# Dokushodo - Account Overview

## Design Task
Design the account home with a sub-navigation and quick links.

## Product Context
The account area is signed-in only, indexed noindex, and rendered inside the account shell.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface favors a restrained warm-light aesthetic: a washi paper background with near-black ink text, vermillion reserved for the single primary action on a card or screen, and soft teal used only for secondary surfaces. The desktop shell is a slim header with the brand mark on the left, inline navigation, a search overlay trigger, a theme toggle, and a user menu, above a persistent footer with catalog, help, legal, and account links. Mobile replaces the header with a compact bar and a fixed bottom tab bar offering Home, Browse, Search, Library, and Account. Cards are quiet: white paper, thin borders, six pixel corners, no shadow. Imagery is limited to the brand mark, gradient book covers generated from title and author, and three restrained illustrations for empty, error, and maintenance states. Serif typography is reserved for novel titles and reading matter; sans-serif covers interface text; monospace marks metadata such as identifiers and timestamps. Motion is subtle and short, never decorative. The platform tells the truth: unavailable features state that they are unavailable, ranking shows a quiet not-live notice, and empty states point to a clear next step. The settled state is calm, legible, and free of noise.

## Page Goal
Give the reader a clear map of their account and fast paths to the main areas.

## Audience and Access
Signed-in readers only; unsigned visitors are redirected to login.

## Primary Action
Choosing a destination from the account navigation.

## Information Hierarchy
- Page heading Account
- User identity line
- Account sub-navigation: Library, History, Notifications, Requests, Contributions, Settings
- More links: Ranking, Request Novel, Contribute, FAQ, News, About, Support, Legal

## Desktop Composition
- Account shell with a persistent left sidebar for the sub-navigation
- Main column with the identity line and More link groups
- Quiet link list styling with clear hover states

## Mobile Composition
- Sidebar collapses to a horizontal scrollable tab row
- Main column stacks identity then links
- Bottom tab bar remains

## Page Anatomy
- Public header
- Account shell
- Sub-navigation
- Main column
- Public footer

## Key Components
- Account sub-navigation
- More link group
- User identity line

## Representative Content
- Account
- Library, History, Notifications, Requests, Contributions, Settings
- Ranking, Request Novel, Contribute, FAQ, News, About, Support, Legal

## Normal Settled State
A quiet two-column account home: navigation on the left, link groups on the right, no cards, no imagery.

## Alternate Visual States
- New account with no activity
- Redirect state when signed out

## Interaction Cues
- Active navigation item is highlighted
- All links are plain text links with underline on hover

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive element
- Complete keyboard navigation, including the search overlay and the mobile tab bar
- Semantic heading order starting at H1
- Reduced motion honored: no movement when requested
- Tap targets at least 44 px on mobile

## Assets

## Preserve Exactly
- Sub-navigation labels exactly as listed
- More link labels exactly as listed
- Noindex behavior

## Avoid
- Avatars or decorative identity cards
- Unverified account stats
- Newsletters or marketing panels

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
