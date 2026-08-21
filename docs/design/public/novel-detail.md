# Dokushodo - Novel Detail

## Design Task
Design the public novel detail page as a quiet, reading-first entry point for translated web novels.

## Product Context
The destination of every novel card and the entry point for reading, saving, reviewing, and inspecting the source chapter hierarchy.

## Global Visual Snapshot
Dokushodo is a quiet Japanese literary reading platform for translated web novels. The interface uses a restrained warm-light aesthetic: washi paper, near-black ink, vermillion for the primary action, and muted teal for secondary surfaces. The desktop shell is a fixed 56px header with the brand mark, search, notifications, account controls, and a collapsible navigation panel up to 320px wide; navigation reflects the current Home, News, Library, Browse Novels, Ranking, Random Novel, Request Novels, Contributions, and FAQ surfaces. Mobile uses a compact header and fixed bottom tabs for Home, Browse, Search, Library, and Account. Cards use quiet paper surfaces, thin borders, six-pixel corners, and restrained elevation. Covers use deterministic bookplate or gradient treatments; illustrations are reserved for empty, error, and maintenance states. Serif typography carries titles and reading matter, sans-serif handles interface text, and monospace is reserved for metadata. Motion is brief and functional. The platform presents truthful ranking periods, loading, unavailable, and no-data states, while contribution settings show masked credential lifecycle and usage states without exposing key material. The settled state is calm, legible, tactile, and free of digital clutter.

## Page Goal
Give a reader the full picture of a novel and put the first readable chapter or saved position one click away.

## Audience and Access
All visitors can view the novel, inspect the synopsis, browse chapters, read available chapters, and view published reviews. Signed-in readers can continue from saved progress, save the novel, and write a review or request.

## Primary Action
Guests see `Start Reading` when a translated chapter is available. Signed-in readers with saved progress see `Continue Reading`; signed-in readers without progress see `Start Reading`. `Save to Library` is always secondary and prompts for authentication only when needed.

## Information Hierarchy
- Novel hero: cover or bookplate, title, source title, author text, status, truthful metadata, one reading CTA, and Save to Library
- Tabs: Overview, Chapters, Reviews
- Overview: synopsis, added date when present, language-aware genre and tag links, and a quiet Report an issue link
- Chapters: real section groups when supplied by the public API, flat lists when no section exists, search, order, First unread, Latest, and a closed Request translation disclosure at the bottom
- Reviews: existing rating and published review behavior
- Footer

Recommendations are intentionally deferred. The public API has no bounded related-novels contract, so the page must not show a fourth tab or fabricate similarity, popularity, or reader behavior.

## Desktop Composition
- A full-width hero grid places the bookplate or real cover beside the title block and a compact action cluster
- The title block contains the H1, plain-text author, source title label only when distinct, status badge, and a compact metadata row for real language, chapter counts, and latest update data
- The tab bar sits below the hero and remains visible while the active panel changes
- Overview is open by default and does not contain an operational request form
- Chapters preserve API order and render consecutive section runs with their exact returned section titles

## Mobile Composition
- The hero stacks the cover, title, author, source title, status, metadata, and actions in that order
- Reading and Save targets remain at least 44px high and do not create a second primary action
- Tabs scroll horizontally without page overflow and use semantic tab states
- Chapter rows keep the source title prominent and omit generated numbering when the source title already carries it
- The request form stays closed behind a compact disclosure after the chapter list

## Page Anatomy
- Public header
- Back to Browse link
- Reading-first novel hero
- Semantic tab list
- Active tab panel
- Public footer

## Key Components
- Deterministic Dokushodo bookplate fallback or a contract-backed cover
- Status badge with text
- Semantic tab list and tab panel
- Compact metadata row
- Chapter list with source hierarchy, search, ordering, First unread, and Latest
- Closed Request translation disclosure containing the existing RequestControl
- Quiet Report an issue link to the existing contact route
- Review card, rating form, Save to Library, and Start or Continue Reading

## Representative Content
- Novel title, source title, and author
- Status badge: Ongoing, Completed, Hiatus, or Dropped
- Real chapter and translated counts when present
- Overview, Chapters, Reviews
- First unread, Latest, Start Reading, Continue Reading, Save to Library
- Exact source section titles such as `1章　8歳`, `閑話`, or `第一部　天国篇` when returned by the API

## Normal Settled State
A calm editorial hero with one vermillion reading action, a quiet secondary save action, a short synopsis, and a chapter tab that makes real source hierarchy easy to scan.

## Alternate Visual States
- Guest view with Start Reading and a secondary sign-in path for Save to Library
- Signed-in view with Continue Reading from saved progress
- Novel with no translated chapters yet: honest unavailable reading state
- Novel without a public cover contract: deterministic bookplate
- Novel without a source title or author: omit the optional field or use the existing safe author fallback
- Loading, not found, and API error states

## Interaction Cues
- Tab buttons update the shareable `tab` URL parameter and expose selected state through `aria-selected`
- First unread and Latest are real anchors to stable chapter row IDs
- Search and order controls update only the chapter list
- Source section disclosures preserve their open or closed state without changing source order
- Save to Library toggles its existing authenticated state
- Request translation remains closed until explicitly opened
- Report an issue is a small text link to `/contact`

## Accessibility and Legibility
- WCAG AA contrast in both themes
- One H1 for the novel and H2 headings for the active content sections
- `role="tablist"`, `role="tab"`, `aria-selected`, `aria-controls`, and `role="tabpanel"` are present and coherent
- Visible focus rings on every interactive element
- Keyboard-operable tabs, links, disclosures, filters, and chapter controls
- Accurate bookplate alternative text and no color-only status meaning
- Reduced motion honored
- Tap targets at least 44px on mobile
- 320px, 390px, and 1440px layouts have no horizontal overflow

## Assets
- `brand-mark.png` only where the public shell requires it
- A persisted public cover asset only when the API contract supplies one
- Deterministic bookplate fallback for missing covers
- `empty.png` only for the existing no-chapters state when appropriate

## Preserve Exactly
- Tab labels `Overview`, `Chapters`, and `Reviews`
- The `Source title` label wording
- Existing review, request, library, progress, and contact routes
- Exact source episode titles and section titles returned by the public API
- Honest chapter availability and status labels

## Avoid
- Recommendations or related-novel rails without a truthful bounded public contract
- Fake views, readers, rankings, word counts, patrons, ratings, or popularity
- Large request or report cards beside the synopsis
- Duplicate generated numbering beside source titles such as `1話　聖水要員`
- Fake author routes, hotlinked artwork, nested interactive elements, or a second primary CTA

## Stitch Output Requirements
- Produce the settled state as a 1440px desktop frame and a 390px mobile frame
- Show a 320px reflow check in addition to the required frames
- Use only the copy, labels, and data states described in this brief
- Do not invent features, badges, metrics, assets, or colors
