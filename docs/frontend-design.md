# Frontend Design Source of Truth

Status: Canonical frontend design contract  
Repository: `ArchdukeViel/NovelAITranslator2Book`  
Scope: Public frontend implementation under `/frontend`, especially `frontend/app/(public)` and `frontend/components/public`  
Last updated: 2026-06-16

---

## 0. Repository Integration

Canonical path recommendation:

```text
docs/frontend-design.md
```

This file is a design contract, not an implementation checklist. Codex or any implementation agent should read it before frontend design work and treat deviations as drift unless this document is intentionally updated first.

For this repository:

```text
Implementation surface: frontend/
Public app surface: frontend/app/(public)/
Public component surface: frontend/components/public/
Admin app surface: frontend/app/(admin)/ — out of scope for this document
Backend/API surface: backend/ — referenced only as integration dependency
```

OPS/production hardening work may proceed separately, but it must not silently change the public visual system.

## 1. Purpose

This document is the source of truth for the frontend's visual identity, layout behavior, theme system, page composition, and UI rules.

When implementation disagrees with this file, the implementation should be treated as drift unless the design source of truth is intentionally updated first.

This frontend is a public web-novel reading platform. It should feel like a quiet Japanese reading hall crossed with a modern translation dashboard: warm, restrained, readable, premium, and slightly mysterious. It should not feel like a generic SaaS admin panel, a neon anime forum, or a gambling leaderboard site.

This document governs the public frontend implementation inside the Novel AI main project. It must keep public UI design boundaries clear, especially from backend implementation, admin UI, deployment work, and provider/credential internals.

---

## 2. Design Principles

### 2.1 Reading comes first

The reader experience is the heart of the product. Every design decision must protect:

- long-form readability
- low visual fatigue
- fast novel discovery
- clear chapter navigation
- obvious save/history/account actions
- restrained decoration

If a visual element looks impressive but makes reading, browsing, or navigation harder, cut it. Pretty clutter is still clutter.

### 2.2 Literary, not loud

The design language should be:

- calm
- editorial
- Japanese-literary inspired
- warm and parchment-like in light mode
- ink-and-lacquer-like in dark mode
- minimal but not sterile

Avoid:

- saturated rainbow gradients
- excessive glassmorphism
- giant noisy animations
- overly rounded toy-like cards
- cyberpunk/neon palettes
- fake community/gamification UI before real data exists

### 2.3 Honest UI

If a feature is not integrated with real backend behavior yet, the UI must say so.

Use copy such as:

- `Coming soon`
- `Requires sign-in`
- `Backend integration pending`
- `Preview data`
- `Disabled until account support is connected`

Do not create fake production behavior, fake live metrics, fake credential storage, or fake request submission.

### 2.4 One route, one mental model

Routes should map cleanly to user intent.

- Browse means discovery.
- Ranking means popularity/trending.
- Request Novel means asking for a new source novel to be added.
- Contribute means helping translation capacity.
- Library means the user's personal reading state.

Do not create duplicate routes that do the same thing under different names.

---

## 3. Brand Direction

### 3.1 Final public reader brand

The public reader brand is:

```text
読書道 Dokushodo
```

This name means roughly "reading hall/book hall." It fits the desired design mood: quiet, Japanese-inspired, literary, and reader-first.

### 3.2 Platform/project name

`Novel AI` remains the backend, platform, and repository/project name.

Approved relationship wording:

```text
Dokushodo is powered by Novel AI.
```

Do not mix `Novel AI` and `Dokushodo` as competing public site names.

Allowed public-facing state:

```text
All Dokushodo public reader UI
```

Allowed platform/backend references:

```text
Dokushodo is powered by Novel AI.
Novel AI admin/platform/backend context
```

Avoid:

```text
Dokushodo in the header
Novel AI in footer as a competing public site name
WTR-style copy in page body
```

That is brand soup. Soup is for eating, not information architecture.

### 3.3 Brand tone

Voice should be:

- clear
- concise
- warm
- slightly literary
- never childish
- never manipulative

Example good copy:

```text
Read translated Japanese web novels with clean navigation, progress tracking, and source-aware metadata.
```

Example bad copy:

```text
THE ULTIMATE INSANE AI NOVEL POWER PLATFORM!!!
```

---

## 3A. Figma Reference Alignment

Figma Make reference:

```text
https://www.figma.com/make/EHzPgAm02lWvByCG5u5Ydm/Modern-Japanese-Webnovel-Website?t=K9EFQXjPrjTaV4at-1
```

The Figma Make file is a visual/prototype reference. This document remains the binding source of truth for frontend design decisions.

MCP access for this Make file provides source-resource and prototype context, such as resource listings for React pages, route files, layout files, theme/CSS files, shadcn UI components, and image assets. It does not provide normal Figma design-file canvas metadata, screenshots, or variable extraction for this Make file.

Because individual `file://figma/make/source/...` resources may not be dereferenceable in Codex, implementation should rely on this document plus the accepted patterns listed below. Do not spend implementation time troubleshooting Make resource dereferencing unless a later phase explicitly asks for it.

### 3A.1 Accepted Figma-inspired patterns

- red square brand mark with book icon
- Japanese/English stacked wordmark
- cover-forward novel cards
- cinematic home hero as target polish
- browse filter panel
- global light/dark toggle
- reader light/dark/sepia theme enforcement
- restrained ranking treatment
- overlay sidebar allowed but not mandatory

### 3A.2 Rejected Figma/prototype patterns

- fake global stats unless clearly labeled preview/mock data
- community CTA
- tag voting/suggestion UI
- emoji medals
- separate `/latest` route
- separate `/bookmarks` route
- route drift back to `/novel`, `/browse`, `/rankings`, or `/library`
- bookmark/community leaderboard categories

---

## 4. Color System

The app uses CSS variables as the canonical color tokens. Components should use semantic Tailwind token classes such as `bg-background`, `text-foreground`, `bg-card`, `border-border`, `text-muted-foreground`, `bg-primary`, and `text-accent`.

Do not hardcode colors in components unless there is a route-specific reason, such as reader themes.

### 4.1 Light theme

| Token | Value | Use |
|---|---:|---|
| `--background` | `#f5f2ec` | Main page background; warm parchment |
| `--foreground` | `#1c1714` | Primary text; dark ink |
| `--card` | `#ffffff` | Card and panel surfaces |
| `--card-foreground` | `#1c1714` | Card text |
| `--popover` | `#ffffff` | Popovers, floating panels |
| `--popover-foreground` | `#1c1714` | Popover text |
| `--primary` | `#c0392b` | Main CTA, brand mark, active states |
| `--primary-foreground` | `#ffffff` | Text/icons on primary |
| `--secondary` | `#ebe6de` | Secondary panels/buttons |
| `--secondary-foreground` | `#1c1714` | Text on secondary |
| `--muted` | `#e5e0d8` | Muted surfaces and quiet UI |
| `--muted-foreground` | `#7a7268` | Metadata, helper text |
| `--accent` | `#b8903a` | Gold accent, highlights, ranking numbers |
| `--accent-foreground` | `#ffffff` | Text/icons on accent |
| `--destructive` | `#e53935` | Error/destructive action |
| `--border` | `rgba(0, 0, 0, 0.09)` | Borders and separators |
| `--input-background` | `#ebe6de` | Input backgrounds |
| `--ring` | `#b8903a` | Focus ring |
| `--radius` | `0.375rem` | Base radius |
| `--sidebar` | `#ede8e0` | Sidebar surface |
| `--sidebar-accent` | `#e5e0d8` | Sidebar active/hover surface |

### 4.2 Dark theme

| Token | Value | Use |
|---|---:|---|
| `--background` | `#0e0c12` | Main dark background; ink-black violet |
| `--foreground` | `#e4ddd0` | Primary dark text; warm parchment ink |
| `--card` | `#16131e` | Card and panel surfaces |
| `--card-foreground` | `#e4ddd0` | Card text |
| `--popover` | `#1c1826` | Popovers, floating panels |
| `--popover-foreground` | `#e4ddd0` | Popover text |
| `--primary` | `#c0392b` | Main CTA, brand mark, active states |
| `--primary-foreground` | `#f5ede3` | Text/icons on primary |
| `--secondary` | `#1e1b28` | Secondary panels/buttons |
| `--secondary-foreground` | `#e4ddd0` | Text on secondary |
| `--muted` | `#1a1724` | Muted surfaces and quiet UI |
| `--muted-foreground` | `#8a8298` | Metadata, helper text |
| `--accent` | `#c9a365` | Gold accent, highlights, ranking numbers |
| `--accent-foreground` | `#0e0c12` | Text/icons on accent |
| `--destructive` | `#e53935` | Error/destructive action |
| `--border` | `rgba(228, 221, 208, 0.08)` | Borders and separators |
| `--input-background` | `#1a1724` | Input backgrounds |
| `--ring` | `#c9a365` | Focus ring |
| `--sidebar` | `#13111a` | Sidebar surface |
| `--sidebar-accent` | `#1e1b28` | Sidebar active/hover surface |

### 4.3 Semantic use rules

Use primary red for:

- main call-to-action buttons
- brand mark blocks
- active filter buttons
- important action emphasis

Use accent gold for:

- ranking numbers
- subtle highlights
- reader progress
- premium/literary emphasis
- hover emphasis for text links

Use muted colors for:

- metadata
- secondary descriptions
- timestamps
- helper copy
- disabled/pending states

Use destructive red only for:

- rejection
- delete account
- remove key
- critical validation failure

Do not use destructive red for ordinary warnings. It should sting only when the action is sharp.

---

## 5. Typography

The frontend uses three font families.

### 5.1 Font stack

| Font | Purpose |
|---|---|
| `Noto Serif JP` | Brand text, Japanese titles, novel titles, chapter headings, literary/editorial headings |
| `DM Sans` | Main UI text, page body, buttons, forms, navigation |
| `DM Mono` | Metadata, labels, stats, timestamps, compact technical text |

### 5.2 Typography rules

Use `Noto Serif JP` when the interface should feel literary or title-like:

- logo text
- hero titles
- novel titles
- chapter title
- Japanese source title
- editorial section headings

Use `DM Sans` for normal interface text:

- nav labels
- buttons
- filters
- cards
- descriptions
- account pages

Use `DM Mono` sparingly for structured metadata:

- `Ch. 418`
- timestamps
- rankings labels
- uppercase section labels
- stats
- table-like compact labels

Do not use mono for long paragraphs. That is how readability goes to die wearing tiny boots.

### 5.3 Default sizing

Base font size:

```css
--font-size: 16px;
```

Default heading behavior:

| Element | Default size | Weight | Line height |
|---|---:|---:|---:|
| `h1` | `var(--text-2xl)` | `500` | `1.5` |
| `h2` | `var(--text-xl)` | `500` | `1.5` |
| `h3` | `var(--text-lg)` | `500` | `1.5` |
| `h4` | `var(--text-base)` | `500` | `1.5` |

Large hero/page headings may override with utility classes, but should stay light or medium. Avoid heavy black weights.

---

## 6. Layout System

### 6.1 Page width

Primary content should use:

```tsx
max-w-7xl mx-auto px-4 sm:px-6 lg:px-8
```

Reader content should use a narrower measure:

```tsx
max-w-2xl or max-w-4xl
```

Use wide layouts for discovery. Use narrow layouts for reading.

### 6.2 Spacing rhythm

Preferred spacing scale:

| Use | Classes |
|---|---|
| Small internal spacing | `gap-2`, `p-3`, `px-3 py-2` |
| Card spacing | `p-4`, `p-5`, `gap-4` |
| Section spacing | `py-10`, `py-12`, `py-16` |
| Large page sections | `mt-16`, `mt-20`, `mb-10`, `mb-12` |

Do not cram pages. This product is about reading. Let the interface breathe.

### 6.3 Surfaces

Use:

```tsx
bg-card border border-border rounded-lg
```

for cards and panels.

Use:

```tsx
bg-secondary
```

for softer grouped UI such as filter chips, secondary buttons, and ticker bars.

Use:

```tsx
bg-muted
```

for input shells and subdued UI surfaces.

### 6.4 Radius

Base radius is:

```css
--radius: 0.375rem;
```

Use `rounded` or `rounded-lg`. Avoid excessive `rounded-3xl` pill aesthetics unless the component is explicitly a chip/filter.

This app should feel crafted, not squishy.

---

## 7. Navigation Design

### 7.1 Header

The top header should be minimal:

- hamburger/menu button
- logo/brand
- search field
- theme toggle
- account/library/login shortcut

The header should not become a crowded mega-nav.

### 7.2 Sidebar

The sidebar is the main navigation surface.

Approved future public nav items:

```text
Home
Browse Novels
Ranking
Request Novel
Contribute
Library
```

Approved account nav items:

```text
Library
Requests
Contributions
Settings
```

### 7.3 Footer

Footer should include legal and explanation links:

```text
About
Privacy
Terms
DMCA
Contact
Cookie Policy
```

Footer copy should be sober and legally cautious. Novel translation platforms should not swagger blindly into copyright fog.

---

## 8. Route Design Contract

The approved future public hierarchy is:

```text
/home
/browse-novels
/ranking

/novels/[slug]
/novels/[slug]/chapter/[chapterId]

/request-novel
/contribute

/account/library
/account/requests
/account/contributions
/account/settings

/login
/register
/auth/callback
/logout

/about
/privacy
/terms
/dmca
/contact
/cookie-policy

/not-found
/error
/maintenance
```

### 8.1 Current route drift to fix later

Older or prototype route names may exist temporarily:

```text
/
/browse
/latest
/rankings
/library
/bookmarks
(legacy; consolidated to /novels/[slug])
```

These are implementation drift relative to the approved future contract.

Do not create new design work around old names. Future route work should align toward:

```text
/home
/browse-novels
/ranking
/account/library
/novels/:slug
/novels/:slug/chapter/:chapterId
```

If old routes are still needed temporarily, preserve them as redirects or compatibility aliases. Do not let them become a second map.

---

## 9. Page Composition Standards

### 9.1 Home

Home should function as the public entry point.

Required sections:

- hero / featured novel
- latest updates ticker or section
- genre/discovery entry points
- featured/trending novels
- ranking preview
- clear links to browse and request novel

Avoid fake impressive stats unless clearly marked as demo data.

### 9.2 Browse Novels

Browse is the merged novel list + novel finder.

Required sections:

- search field
- filters
- sort controls
- status filter
- genre include/exclude behavior if implemented
- latest updates/latest releases area
- novel result cards
- empty state

Recommended card fields:

- cover
- translated title
- raw/source title
- status
- chapters
- rating/views if real or mock-labeled
- genres/tags
- latest updated time

### 9.3 Ranking

Ranking should be visually tighter and more numeric than Browse.

Recommended tabs:

- Daily
- Weekly
- Monthly
- All Time

Do not build leaderboard/community ranking yet. Novel ranking is enough.

### 9.4 Novel detail

Novel detail should sell the story and expose source metadata.

Required areas:

- cover
- translated title
- source title
- status badge
- author/source/translator metadata
- rating/view/bookmark/chapter stats if available
- genre and tag chips
- synopsis
- chapter list
- start reading/latest chapter actions
- report issue action

### 9.5 Chapter reader

The reader is sacred ground.

Required areas:

- top bar with back-to-novel and chapter title
- chapter body
- reader settings
- previous/next chapter controls
- progress indicator
- report chapter issue action

Reader content should be narrow, calm, and typographically generous.

### 9.6 Request Novel

Request Novel must require sign-in.

Required areas:

- sign-in required copy/guard
- supported sources section
- URL input scaffold
- validation message area
- request history table

Request history table columns:

```text
Requested Novel / URL
Source
Status
Rejection Reason
Requested At
Updated At
Action
```

Rejected requests must show a reason. Silent rejection makes users angry and makes them submit the same thing five times. That is not UX; that is a mosquito farm.

Supported source list:

```text
Kakuyomu
Syosetu
Syosetu18
```

### 9.7 Contribute

Contribute explains API key contribution.

Required areas:

- what contribution means
- provider selection placeholder
- security/privacy explanation
- CTA to account contribution dashboard

Do not implement real API key storage in the frontend prototype.

### 9.8 Account Library

The library page is a reading hub, not just bookmarks.

Required sections:

```text
Currently Reading
Reading History
Dropped
Updates
```

### 9.9 Account Requests

Required areas:

- full request history
- status filters
- rejection reason column
- links to imported/approved novels when available

### 9.10 Account Contributions

Required areas:

- contribution status
- provider/key label, masked only
- health status
- usage stats placeholder
- pause/remove actions, disabled or mock-only until backend exists

Never show a full API key after submission.

### 9.11 Account Settings

Required sections:

```text
Profile
Linked login methods
API key contribution settings
Privacy
Delete account
```

Delete account should use destructive styling and confirmation friction.

### 9.12 About

About includes FAQ.

Required areas:

- what the site is
- how AI translation works
- supported sources
- request novel explanation
- contribution explanation
- FAQ
- contact/legal links

Do not create separate `/faq` unless product direction changes.

---

## 10. Component Rules

### 10.1 Buttons

Primary button:

```tsx
bg-primary text-primary-foreground hover:bg-primary/90
```

Secondary button:

```tsx
border border-border text-muted-foreground hover:text-foreground hover:border-foreground/20
```

Accent button/link:

```tsx
border border-accent/40 text-accent hover:bg-accent/10
```

Destructive button:

```tsx
bg-destructive text-destructive-foreground
```

### 10.2 Cards

Standard card:

```tsx
bg-card border border-border rounded-lg p-4
```

Interactive card:

```tsx
bg-card border border-border rounded-lg hover:border-accent/30 transition-all duration-200
```

### 10.3 Badges/chips

Status badges should use restrained color.

Examples:

- Ongoing: green tint
- Complete: blue tint
- Hiatus: yellow tint
- Rejected/error: destructive tint
- Pending: muted/accent tint

Do not make badges visually louder than the main CTA.

### 10.4 Forms

Input shell:

```tsx
bg-muted border border-border rounded px-3 py-2
```

Input text:

```tsx
bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none
```

Focus states must remain visible through the ring/accent tokens.

### 10.5 Tables

Tables should be calm and dense but readable.

Use tables for:

- request history
- contribution history
- account management records

Required table behavior:

- readable on desktop
- collapsible/card layout on mobile if the table becomes wide
- muted metadata
- clear status badge
- rejection reason visible without opening developer tools like a goblin

---

## 11. Reader Theme System

The global app has light/dark themes. The chapter reader may use its own reader-specific themes:

```text
light
dark
sepia
```

Reader theme values:

| Reader theme | Background | Text | Secondary | Border | Nav background |
|---|---:|---:|---:|---:|---:|
| Light | `#ffffff` | `#1a1a1a` | `#6b7280` | `rgba(0,0,0,0.1)` | `rgba(255,255,255,0.95)` |
| Dark | `#0e0c12` | `#e4ddd0` | `#8a8298` | `rgba(228,221,208,0.08)` | `rgba(14,12,18,0.95)` |
| Sepia | `#f8f1e4` | `#3c2a1a` | `#8a7060` | `rgba(60,42,26,0.12)` | `rgba(248,241,228,0.95)` |

`reader.css` and any reader-theme implementation must match these documented reader theme hex and rgba values exactly unless this section is intentionally updated first.

Reader font sizes:

```text
14
16
18
20
22
```

Default reader font size should be comfortable, around `18px`.

Reader body should use `Noto Serif JP`, generous line-height, and a narrow column.

---

## 12. Imagery

### 12.1 Covers

Novel covers should be:

- portrait orientation
- consistent aspect ratio
- object-cover
- softly rounded
- placed on muted background while loading

Recommended classes:

```tsx
object-cover rounded bg-muted
```

### 12.2 Hero imagery

Hero background images should be:

- low opacity
- strongly gradient-masked
- atmospheric
- not visually competitive with text

Use overlays:

```tsx
bg-gradient-to-t from-background via-background/70 to-background/20
bg-gradient-to-r from-background/95 via-background/60 to-transparent
```

### 12.3 Image policy

Prototype imagery may use remote placeholder images, but production should move toward:

- real source covers when legally safe
- stored/cached cover assets
- fallback cover art component
- explicit alt text

---

## 13. Motion and Interaction

Motion should be subtle.

Allowed:

- `transition-colors`
- `transition-opacity`
- `transition-all duration-200`
- sidebar slide-in/out
- hover border/accent changes
- backdrop blur on nav/sidebar overlay

Avoid:

- bouncing cards
- auto-playing carousels
- large parallax effects
- excessive page transitions
- animations that delay reading

The interface should whisper, not juggle knives.

---

## 14. Accessibility Rules

Minimum requirements:

- every interactive icon-only button must have `aria-label`
- links must have meaningful text
- color cannot be the only status indicator
- focus states must remain visible
- text contrast must be checked in both light and dark themes
- reader controls must be keyboard reachable
- forms must have labels or accessible names
- images must have descriptive `alt` text

Reader page requirements:

- font size controls must be reachable by keyboard
- theme controls must be discoverable
- previous/next chapter links must be visible near the end of the chapter
- chapter title and novel title must be present as real text

---

## 15. Responsive Design

### 15.1 Breakpoints

Use Tailwind responsive utilities consistently:

```text
sm
md
lg
xl
```

### 15.2 Mobile rules

Mobile must prioritize:

- readable cards
- single-column flows
- accessible sidebar drawer
- compact search
- no horizontal overflow
- tables converted or scroll-safe

### 15.3 Desktop rules

Desktop can use:

- multi-column discovery grids
- sidebars
- ranking panels
- wider filter layouts

Do not design desktop first and then pray mobile forgives you. Mobile does not forgive. Mobile only scrolls away.

---

## 16. Implementation Rules

### 16.1 Token-first styling

Prefer semantic tokens:

```tsx
bg-background
text-foreground
bg-card
text-muted-foreground
border-border
bg-primary
text-primary-foreground
text-accent
```

Avoid hardcoded hex values in normal components.

Allowed exception:

- chapter reader themes
- temporary status colors
- one-off image overlays

### 16.2 No broad redesign during feature work

When adding a route or feature, do not simultaneously change:

- global colors
- fonts
- radius
- layout shell
- navigation model
- card system

Design system changes need their own phase.

### 16.3 Mock data labeling

If UI uses local mock data, name it honestly in code and copy.

Good:

```text
Preview data
Mock contribution health
Backend integration pending
```

Bad:

```text
Live usage
Real-time capacity
Verified requests
```

unless the backend actually supports it.

### 16.4 Security-sensitive UI

API key contribution is security-sensitive.

Frontend rules:

- never display full keys
- never store real keys in localStorage
- never simulate successful key storage as if real
- never expose provider credentials in mock objects that look real
- always explain risk and control

Real key handling belongs to backend architecture, not pretty frontend enthusiasm.

---

## 17. Design Debt Register

Known current drift/design debt to audit before implementation:

1. Legacy `/novel/` routes have been consolidated to `/novels/`.
2. Legacy browse routes such as `/browse` or `/novel-list` should not receive new design work; approved route is `/browse-novels`.
3. Legacy ranking route `/rankings` should not receive new design work; approved route is `/ranking`.
4. Legacy `/library` should not receive new design work; approved route is `/account/library`.
5. Separate latest-update routes should not become a second discovery map; approved direction keeps latest updates inside `/browse-novels`.
6. Legacy bookmark concepts should be absorbed into `/account/library` unless product direction explicitly changes.
7. Current footer lacks the full approved legal surface.
8. Current prototype contains demo stats and mock novel data; production copy must not present these as real.
9. Current reader uses localStorage for reader preferences, which is fine for prototype, but account-synced preferences should be handled later.

These are not emergencies. They are marked stones on the road. Fix them in planned frontend phases, not in a random midnight refactor bonfire.

---

## 18. Approval Rule

Before changing the design system, update this file first.

Design-changing work includes:

- color palette changes
- font changes
- route naming changes
- layout shell changes
- card system changes
- reader typography changes
- major navigation changes
- global radius/spacing changes

Feature work may proceed without editing this file only when it stays within the rules above.

---

## 19. One-line Design North Star

Build a quiet, elegant, source-aware novel reading platform where discovery feels polished, reading feels calm, and every unfinished backend feature tells the truth.
