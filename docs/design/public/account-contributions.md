# Dokushodo - Contributions

## Design Task
Design the live contributor credential dashboard with clear lifecycle and usage states.

## Product Context
Authenticated users can add one Gemini contribution to the unified provider-credential registry, validate it explicitly, pause/resume it, replace it, delete it, and review sanitized usage. The key is never read back; owner-managed rows are not shown in this user surface.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface uses a restrained warm-light aesthetic: washi paper, near-black ink, vermillion for the primary action, and muted teal for secondary surfaces. The desktop shell is a fixed 56px header with the brand mark, search, notifications, account controls, and a collapsible navigation panel up to 320px wide; navigation reflects the current Home, News, Library, Browse Novels, Ranking, Random Novel, Request Novels, Contributions, and FAQ surfaces. Mobile uses a compact header and fixed bottom tabs for Home, Browse, Search, Library, and Account. Cards use quiet paper surfaces, thin borders, six-pixel corners, and restrained elevation. Covers use deterministic bookplate or gradient treatments; illustrations are reserved for empty, error, and maintenance states. Serif typography carries titles and reading matter, sans-serif handles interface text, and monospace is reserved for metadata. Motion is brief and functional. The platform presents truthful ranking periods, loading, unavailable, and no-data states, while contribution settings show masked credential lifecycle and usage states without exposing key material. The settled state is calm, legible, tactile, and free of digital clutter.

## Page Goal
Present the API-backed contribution dashboard without inventing health, quota, or usage values.

## Audience and Access
Signed-in readers only.

## Primary Action
Add or replace a Gemini contributor credential after accepting the current consent version.

## Information Hierarchy
- Page heading Contribution Dashboard
- Credential intake with consent checkbox and masked key ending
- Validation, active, invalid, paused, revoked, and unavailable states
- Usage summary with real request/token limits and recent ledger entries
- Pause, resume, replace, and permanent delete controls

## Desktop Composition
- Consent and key-entry panel at the top
- Credential status panel with provider, fingerprint, validation timestamp, and lifecycle action
- Usage panel with current-minute/today counters, configured limits, and recent activity
- Security copy explaining encryption, ownership isolation, and no-readback behavior

## Mobile Composition
- Panels stack full width

## Page Anatomy
- Account shell
- Page heading block
- Notice callout
- Panel grid
- Public footer

## Key Components
- Credential intake form
- Credential status card
- Usage summary card
- Lifecycle action controls
- Security notice

## Representative Content
- Contributions
- Add a Google Gemini API key
- Active, Invalid, Paused, Revoked
- Usage, requests per minute, tokens per minute, requests per day

## Normal Settled State
One quiet intake/status surface with masked credential metadata and API-backed usage; no raw key readback or fabricated health text.

## Alternate Visual States
- Guest sign-in prompt
- Loading, service error, disabled/encryption-unready, invalid validation, paused, revoked, and usage-error states

## Interaction Cues
- Consent gates the submit action
- Successful validation activates the credential immediately
- Pause/resume, replace, and delete use explicit confirmation where destructive

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive element
- Complete keyboard navigation, including the search overlay and the mobile tab bar
- Semantic heading order starting at H1
- Reduced motion honored: no movement when requested
- Tap targets at least 44 px on mobile

## Assets

## Preserve Exactly
- No complete key value is displayed after submission
- Status and usage text comes only from the authenticated API response
- Current consent version and configured limits remain visible

## Avoid
- Raw credential values, fake quota counters, fake health scores, or owner-only controls

## Stitch Output Requirements
- Produce the settled state as a 1440 px desktop frame and a 390 px mobile frame
- Use only the copy, labels, and elements listed in this brief
- Do not invent features, badges, text, or colors
- Show the primary alternate state as an additional frame only when listed above
