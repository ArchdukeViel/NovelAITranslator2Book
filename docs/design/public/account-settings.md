# Dokushodo - Account Settings

## Design Task
Design the account settings page with profile, login methods, and key contribution.

## Product Context
Account settings expose authenticated profile/session facts, appearance, reader defaults, notifications, security, and a link to the live contributor dashboard. Profile editing and account deletion remain unavailable.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface uses a restrained warm-light aesthetic: washi paper, near-black ink, vermillion for the primary action, and muted teal for secondary surfaces. The desktop shell is a fixed 56px header with the brand mark, search, notifications, account controls, and a collapsible navigation panel up to 320px wide; navigation reflects the current Home, News, Library, Browse Novels, Ranking, Random Novel, Request Novels, Contributions, and FAQ surfaces. Mobile uses a compact header and fixed bottom tabs for Home, Browse, Search, Library, and Account. Cards use quiet paper surfaces, thin borders, six-pixel corners, and restrained elevation. Covers use deterministic bookplate or gradient treatments; illustrations are reserved for empty, error, and maintenance states. Serif typography carries titles and reading matter, sans-serif handles interface text, and monospace is reserved for metadata. Motion is brief and functional. The platform presents truthful ranking periods, loading, unavailable, and no-data states, while contribution settings show masked credential lifecycle and usage states without exposing key material. The settled state is calm, legible, tactile, and free of digital clutter.

## Page Goal
Provide structured reader and account preferences (Account Profile, Appearance & Display, Reading Defaults, Notifications, and Account Security).

## Audience and Access
Signed-in readers only.

## Primary Action
Updating reader and account preferences.

## Information Hierarchy
- Page heading Account Settings
- Account Profile card (Email, User ID, Role badge)
- Appearance & Display card (Theme selector, Density)
- Reading Preferences card (Font size, Line spacing, Reader background)
- Notifications Shortcut card
- Account Security & Danger Zone card (Sign out, Account deletion info)

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
- API Key Contributions card linking to the live credential dashboard
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
Quiet preference and security cards; contribution availability is represented by a real dashboard link, while unsupported profile/deletion controls remain plainly unavailable.

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
- Honest not-available wording for profile editing and account deletion

## Avoid
- Password change forms the system does not support
- Fake connected device lists

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
