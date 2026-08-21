# Dokushodo - Account Overview

## Design Task
Design the account home with a sub-navigation and quick links.

## Product Context
The account area is signed-in only, indexed noindex, and rendered inside the account shell.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface uses a restrained warm-light aesthetic: washi paper, near-black ink, vermillion for the primary action, and muted teal for secondary surfaces. The desktop shell is a fixed 56px header with the brand mark, search, notifications, account controls, and a collapsible navigation panel up to 320px wide; navigation reflects the current Home, News, Library, Browse Novels, Ranking, Random Novel, Request Novels, Contributions, and FAQ surfaces. Mobile uses a compact header and fixed bottom tabs for Home, Browse, Search, Library, and Account. Cards use quiet paper surfaces, thin borders, six-pixel corners, and restrained elevation. Covers use deterministic bookplate or gradient treatments; illustrations are reserved for empty, error, and maintenance states. Serif typography carries titles and reading matter, sans-serif handles interface text, and monospace is reserved for metadata. Motion is brief and functional. The platform presents truthful ranking periods, loading, unavailable, and no-data states, while contribution settings show masked credential lifecycle and usage states without exposing key material. The settled state is calm, legible, tactile, and free of digital clutter.

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
- More links: Ranking, Request Novels, Contributions, FAQ, News, About, Support, Legal

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
- Ranking, Request Novels, Contributions, FAQ, News, About, Support, Legal

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
