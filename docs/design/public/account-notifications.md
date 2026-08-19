# Dokushodo - Notifications

## Design Task
Design the notification center with activity and delivery preferences.

## Product Context
Notifications cover translation updates and review requests for the reader's novels.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface uses a restrained warm-light aesthetic: washi paper, near-black ink, vermillion for the primary action, and muted teal for secondary surfaces. The desktop shell is a fixed 56px header with the brand mark, search, notifications, account controls, and a collapsible navigation panel up to 320px wide; navigation reflects the current Home, News, Library, Browse Novels, Ranking, Random Novel, Request Novels, Contributions, and FAQ surfaces. Mobile uses a compact header and fixed bottom tabs for Home, Browse, Search, Library, and Account. Cards use quiet paper surfaces, thin borders, six-pixel corners, and restrained elevation. Covers use deterministic bookplate or gradient treatments; illustrations are reserved for empty, error, and maintenance states. Serif typography carries titles and reading matter, sans-serif handles interface text, and monospace is reserved for metadata. Motion is brief and functional. The platform presents truthful ranking periods, loading, unavailable, and no-data states, while contribution settings show masked credential lifecycle and usage states without exposing key material. The settled state is calm, legible, tactile, and free of digital clutter.

## Page Goal
Show recent activity and let the reader control delivery.

## Audience and Access
Signed-in readers only.

## Primary Action
Reviewing a notification or toggling a preference.

## Information Hierarchy
- Page heading Notifications
- Description line
- Activity panel
- Delivery Preferences panel

## Desktop Composition
- Description under the heading
- Activity panel with a chronological item list
- Delivery Preferences panel with toggle rows

## Mobile Composition
- Panels stack
- Toggles remain full width and touch friendly

## Page Anatomy
- Account shell
- Page heading block
- Activity panel
- Delivery Preferences panel
- Public footer

## Key Components
- Activity item
- Toggle row
- Empty activity message

## Representative Content
- Notifications
- Translation updates and review requests for your novels.
- Activity
- Delivery Preferences

## Normal Settled State
Two quiet panels; activity items are text with timestamps and toggles are simple switches.

## Alternate Visual States
- Empty activity with a quiet message
- All preferences off

## Interaction Cues
- Toggles apply immediately
- Activity items link to their source novel or review

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive element
- Complete keyboard navigation, including the search overlay and the mobile tab bar
- Semantic heading order starting at H1
- Reduced motion honored: no movement when requested
- Tap targets at least 44 px on mobile

## Assets

## Preserve Exactly
- The exact description wording
- Panel names
- No fabricated notification types

## Avoid
- Notification badges with invented counts
- Confetti or celebratory states
- Email preview imagery

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
