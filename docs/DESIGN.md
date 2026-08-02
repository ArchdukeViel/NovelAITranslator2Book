# Frontend Design

Canonical visual, interaction, accessibility, and frontend ownership contract for
Dokushodo (読書道) — a translated Japanese web novel reading site.

This replaces `docs/DESIGN.md`. The engineering sections (ownership, states,
accessibility, performance) carry over largely unchanged — that discipline was
already solid. What changed is `Direction` and `Visual System`, which had drifted
from what's actually shipped (the doc said "indigo accents"; the CSS has none),
and which didn't yet reflect what this product actually is.

**Design status:** Approved target — Yokocho Lantern and the Layout Rework
below are the agreed direction, not one option among several.
**Implementation status:** FE-01 through FE-10 shipped including moderation
contract for reviews (status lifecycle: pending → published | rejected via
admin /api/admin/reviews). Public review listing with cursor pagination
(GET /api/public/novels/{slug}/reviews, published only). Review audits
emitted on write/delete/moderate. Remaining: operator accessibility
acceptance (DEBT-FE-01A), curated featured rotation, chapter/failure
metadata contracts. No gated surface is faked.
**Last implementation verification:** FE-10 + review moderation — backend
74 tests pass, ruff clean, pyright unchanged (1 pre-existing), guard clean;
frontend 828 Vitest/74 files, typecheck/lint clean, production build 50
pages (2026-08-02).

This distinction matters because this doc's own predecessor was the cautionary
tale: it described "indigo accents" that were never actually in the CSS, and
nothing caught the drift until this review. Keep this block current — update
it, don't just leave it — every time a section below actually ships, so a
future reader (human or agent) can tell "this is the plan" from "this is
real" without diffing against the codebase themselves:

```
Implemented:
- FE-01: Yokocho Lantern visual system, design tokens in globals.css
  (light/dark), DM Sans / Noto Serif JP / DM Mono font stack, brand mark +
  og:image, semantic status-color layer (--success/--warning/--info + -text
  tokens), two-layer primary-button focus treatment
- FE-02: token contrast enforced by a persistent regression test (34 checks, both modes,
  WCAG AA 4.5:1, 0 failures); -text context tokens on badge, notifications,
  contributions banner, rating/request success text, browse filter chips
- FE-03: hamburger drawer removed; desktop header inline nav (Home, Browse,
  Request, Library) + search + theme toggle + bell + account; mobile bottom
  tab bar (Home/Browse/Search/Library/Account) with safe-area padding and
  guest routing (Library/Account → sign-in preserving `next`); Account/More
  hub at /account; header/tab bar/footer suppressed on chapter routes;
  /browse-novels?focus=search focuses the catalog search
- FE-04: one shared search overlay (desktop header field, mobile Search tab,
  and `/` shortcut all open it; Enter navigates highlighted rows or falls
  back to full results; ArrowUp/Down cycle groups; Escape/backdrop close and
  restore focus); grouped results Novels/Authors/Genres & Tags with fuzzy
  title and exact tag matching; in-flight requests cancelled on new
  keystrokes with stale results kept until fresh response (no flicker);
  honest error state; local-only recent searches (8 max, min 2 chars) shown
  on empty query with genre shortcuts; catalog search now also matches the
  original Japanese title in both DB and storage-fallback paths
- FE-05: desktop left filter sidebar (only heading/actions sticky; page owns
  scrolling), mobile bottom-sheet filters with applied-count badge and pinned
  Apply/Clear, results count + compact sort + URL-backed grid/list toggle +
  loaded-results Surprise me, individually removable active-filter chips,
  pagination and catalog scroll restoration; `/tags/[tag]`,
  `/genres/[genre]`, and `/sources/[source-key]` canonical browse routes;
  utility-filter SEO noindex/follow and sort-only canonicalization; exact
  `source_key` catalog filtering in DB and storage-fallback paths
- FE-06: homepage long stacks and duplicate browse boxes replaced by
  keyboard-scrollable, labeled New Releases, Recently Updated, Continue
  Reading, and catalog-derived genre rails with real See-all links; guests
  get a quiet sign-in continuation tile; reduced motion disables smooth rail
  scrolling; `/random` redirects uniformly across the catalog with an honest
  empty fallback; hero uses one Start Reading CTA and a neutral, eligibility-
  gated Spotlight label instead of falsely claiming admin curation. Manual
  admin-selected featured rotation remains pending its persistence/API
  contract.
- FE-07: novel detail uses a desktop sticky cover/title/status/action panel
  and a mobile sticky reading bar that replaces the global tab bar; one
  adaptive Start/Continue CTA; URL-backed Overview/Chapters/Reviews tabs;
  canonical taxonomy links; chapter search, ascending/descending order,
  collapse/expand-all, first-unread/latest anchors, read and last-read state,
  explicit not-translated rows and community reviews with cursor pagination
  (published only, guest-visible, no author identity). No fake states rendered.
- FE-08: floating safe-area Aa button opens a reader settings sheet with
  exact 16/18/20/22px font choices, 560/680/800px text widths, light/dark/
  sepia themes, and reset preserving the saved theme; fixed 3px live reading
  progress; signed account-position and guest local-only restore/update with
  pagehide flush; layout-aware resume correction; keyboard previous/next and
  `.` settings shortcuts; explicit Previous chapter · Back to novel · Next
  chapter footer with strongest bottom Next action.
- FE-09: desktop account sidebar and honest account summary; responsive
  library board/list with status grouping, slug search, supported sorts,
  per-item removal, and empty state. Unsupported status mutation, bulk action,
  progress, title, and update fields remain absent pending backend contracts.
- FE-10: `/faq` (flat categorized Q&A) and `/news` (flat dated list) static
  pages, no auth, linked from the footer and the mobile Account More hub;
  `/account/reviews` lists the signed-in reader's own reviews (rating, body,
  novel link, edit link to the novel's reviews tab, removal) backed by a new
  `GET /api/user/reviews` endpoint scoped to the session user; review
  moderation contract (status lifecycle: pending → published/rejected via
  admin, published reviews visible publicly on novel detail with cursor
  pagination); audit events written/rejected/moderated; account overview
  and `/random` already shipped in FE-06/FE-09.
- Review moderation: new `status` (pending|published|rejected), `updated_at`,
  `moderated_at`, `reviewer_notes`, `reviewed_by_user_id` columns on reviews;
  `GET /api/public/novels/{slug}/reviews` (guest, published only, cursor
  pagination); `GET/POST /api/admin/reviews` (owner moderation with audit);
  user write/delete emit audit; admin Reviews page in dashboard sidebar;
  status badges on `/account/reviews`.

Pending:
- Approved brand/empty/404/maintenance asset inventory

Deferred:
- Public profile pages (Guiding Principle 4)
- Tickets/gems/leaderboard/community-folders (see "What this intentionally
  leaves out")
```

## Direction

This is a place to binge translated isekai, fantasy, and romance web novels —
not a museum reading room. The previous direction ("literary, calm, trustworthy")
produced a warm-sepia, vermillion-and-gold palette that reads more like an
antiquarian bookshop than a place built for the content it's actually serving.

New direction: **keep the calm reading experience, drop the solemnity elsewhere.**
The chapter reader stays quiet and distraction-free — that part was right. The
site *around* the reader (browse, cards, header, homepage) should feel closer to
a bunko-bon shelf or a webnovel app: warm, a little playful, unmistakably
Japanese-flavored without leaning on temple/washi/museum signifiers. Do not copy
another product's branding.

**Committed direction: Yokocho Lantern.** Four variations were drafted and
compared (Bunkobon Pop, Retro Shotengai, Origami Zine, Yokocho Lantern) —
Yokocho Lantern is the one shipping. It's kept below in full; the other three
are archived in conversation history if this ever needs revisiting, but they
are not part of the active contract and should not be mixed in piecemeal.

## Visual System — Yokocho Lantern

*A back-alley night market — dark-first, cozy, made for reading after dark.*

Deep plum-charcoal background, warm paper-lantern orange as primary, sakura
pink reserved for favorite/heart/rating actions only, and a quiet deep teal as
secondary. The goal is casual hangout energy — like ducking into a yokocho
alley of tiny bars and food stalls — instead of library energy. This is the
only one of the four candidates that's dark-first: dark is the default
experience, with a light alt for people who prefer it.

Maps directly onto the existing CSS variable names in `globals.css`
(`--background`, `--foreground`, `--card`, `--primary`, `--secondary`,
`--muted`, `--accent`, `--border`) — this is a token swap, not a rebuild.
`--font-noto-serif-jp` stays the chapter-reading font unchanged.

| Token | Dark (default) | Light (alt) |
|---|---|---|
| `--background` | `280 20% 10%` | `35 35% 96%` |
| `--foreground` | `35 30% 90%` | `280 18% 14%` |
| `--card` | `275 16% 14%` | `0 0% 100%` |
| `--primary` | `28 85% 55%` (lantern orange) | `28 78% 50%` |
| `--secondary` | `190 30% 22%` (deep teal) | `190 30% 85%` |
| `--muted` | `275 12% 20%` | `30 20% 90%` |
| `--accent` | `340 62% 66%` (sakura pink) | `340 60% 60%` |
| `--destructive` | keep existing red — unrelated to this palette | same |
| `--border` | `35 30% 90% / 0.1` | `280 18% 14% / 0.09` |
| `--focus-ring` | `28 85% 65%` (bright lantern orange, not accent) | `28 78% 45%` |
| `--ring` | matches `--focus-ring`, **not** `--accent` | matches `--focus-ring` |

### Usage rules

- **Sakura pink (`--accent`) is reserved for favorite/heart, rating, and
  save-to-library active states only — never for primary buttons, links, or
  focus rings.** This is the one rule most likely to get eroded over time;
  if pink starts showing up as a generic highlight color, that's drift, not
  a variant. This includes the keyboard focus ring specifically — an earlier
  draft of this table set `--ring` to match `--accent`, which would have put
  pink around every button, form field, tab, and dialog a keyboard user
  focuses. `--ring` now maps to the dedicated `--focus-ring` token instead.
- Lantern orange (`--primary`) carries all primary CTAs: "Start Reading,"
  "Sign in," "Browse the catalog."
- Deep teal (`--secondary`) stays structural/quiet — chip backgrounds, subtle
  section dividers — never a call-to-action color.
- Typography: DM Sans stays for site chrome, no swap needed. Noto Serif JP
  stays for chapter text in both modes.

### Motifs

- Soft rounded "paper lantern" shape (a rounded rect with slightly pinched
  top/bottom, not a full lantern illustration) for status badges. Exact
  status-to-color mapping is defined once, deterministically, in Design
  Tokens → Status roles below — not left as "different colors" here.
- A flat-fill halo ring (color only, **no blur or glow** — see Accessibility)
  around the cover on whichever novel the reader is currently partway
  through, using `--primary`.
- A thin noren-style (izakaya curtain) divider — a row of short vertical
  hairline strokes — as an optional section-break motif on the homepage,
  used sparingly (one section, not every divider).
- Genre chips keep their current shape; only the color role changes.

### Implementation notes

- `frontend/app/globals.css`: replace the `:root` block with the *Light
  (alt)* column above, and the `.dark` block with the *Dark (default)*
  column — same mechanism the app already uses, just new values.
- `components/public/public-theme-toggle.tsx`: `getInitialTheme()` currently
  falls back to light when there's no stored preference and no system
  preference. Since dark is now the intended default experience, change the
  no-preference fallback to `"dark"` (still respect an explicit stored
  preference, and still respect `prefers-color-scheme: light` when a visitor's
  system is explicitly set to light).
- Reader-specific themes (`light` / `dark` / `sepia` in `reader.css`) are
  intentionally unrelated to this site-wide palette and don't need to change —
  that separation was already correct and stays correct.
- No new font files are needed. The public brand does require the asset family
  defined in **Brand and Illustration Asset System** below; the lantern/noren
  motifs themselves do not require additional one-off icons beyond that shared
  family and the existing generated-bookplate/status-badge components.

---

## Design Tokens

Colors and two font families were defined above; everything else an
implementer needs was missing. This section is the rest of the visual
system — deliberately terse and tabular, since the goal here is a lookup
reference, not more prose.

### Typography scale

Three families total, all already loaded in the codebase today — none of
this table introduces a new font file. Verified directly against
`app/layout.tsx`: Noto Serif JP and DM Sans were already in use; DM Mono is
also already there (`localFont` from `public/fonts/DM_Mono_*.ttf`, wired to
Tailwind's `font-metadata`/`font-mono`) — it's just been sitting unused by
this doc's earlier drafts, not something new to add. The "no new font
files needed" line in Implementation notes above was correct; it just
didn't say so explicitly enough to make that obvious.

| Role | Font | Size / line-height | Use |
|---|---|---|---|
| Display | Noto Serif JP | 32/40px | Hero title, novel title on detail |
| H1 | Noto Serif JP | 26/34px | Page titles |
| H2 | DM Sans, 600 | 20/28px | Section/rail headers |
| H3 | DM Sans, 600 | 16/24px | Card titles, tab labels |
| Body | DM Sans, 400 | 15/24px | UI copy, synopsis, reviews |
| Small | DM Sans, 400 | 13/20px | Metadata, timestamps, chip labels |
| Metadata (mono) | DM Mono, 400 | 12/18px | Chapter numbers, counts, IDs |
| Chapter text | Noto Serif JP | 18/32px (reader-adjustable, see below) | Chapter body only |

Chapter text size is the one user-adjustable value (the "Aa" panel), ranging
16–22px in 2px steps; line-height stays proportional (≈1.75×) at every step
so the reader's rhythm doesn't change, only its scale.

### Spacing scale

4px base unit: `4, 8, 12, 16, 24, 32, 48, 64`. Fixed roles:
- Page gutter: 16px mobile, 24px tablet, 32px desktop.
- Section gap (between homepage rails, between account sections): 32px.
- Card internal padding: 12px (compact rail card), 16px (rich browse card).
- Form field spacing: 16px between fields, 24px between field groups.

### Radius

| Element | Radius |
|---|---|
| Card, cover bookplate | 8px |
| Button, input, chip | 6px |
| Modal, bottom sheet (top corners only) | 16px |
| Popover (Aa panel, search overlay) | 12px |
| Status badge ("lantern") | 999px pill; a noninteractive pseudo-element may create two tiny symmetric side notches using the surrounding surface color. No inset shadow. The underlying hit target remains a full rectangle. |

### Elevation

No drop shadows — matches the flat, motif-driven visual language (see
Accessibility: motifs are flat-fill, no blur/glow). Elevation is expressed
as a 1px `--border` outline plus a background-color step up from
`--background`, in this order, lightest to most elevated: `--background` →
`--muted` → `--card` → popover/dialog surface (same as `--card`, always
paired with a visible border since there's no shadow to imply separation).

### Container widths

| Surface | Max width |
|---|---:|
| Marketing/legal pages | 720px |
| Catalog / browse grid | 1280px |
| Novel detail | 1120px |
| Account | 960px |
| Chapter reader text column | 680px **default** — see reader width options below; this is the one dimension that intentionally doesn't grow with viewport, it changes only via the Aa panel, never via monitor size |

### Motion

- Duration: 120ms for hover/pressed state changes, 200ms for popovers and
  the search overlay, 250ms for sheet/dialog open-close.
- Easing: ease-out on enter, ease-in on exit — standard, no custom curves.
- Rail scroll: instant under `prefers-reduced-motion`, smooth otherwise (see
  Homepage rail accessibility notes above).
- Nothing loops, auto-plays, or requires motion to convey state — motion is
  always a transition between two states a static screenshot could also show.

### Interaction states

Every interactive element defines: default, hover (pointer only), pressed,
selected/active, disabled, pending (async in flight — spinner or skeleton,
never a frozen button with no feedback), and focus-visible (uses
`--focus-ring`, see the pink/focus-ring fix above). Disabled elements drop
opacity to 50% and lose pointer events; they never simply disappear, since a
missing control is harder to understand than a visibly-disabled one.

### Media

- Bookplate/cover aspect ratio: 2:3 (portrait, matches the generated
  fallback plates already in use).
- Real cover art (Improvement 12) crops to the same 2:3 ratio, center-weighted;
  never stretched.
- Broken/missing image always falls back to the generated bookplate, never a
  broken-image icon or blank box.

### Z-index scale

```
0    base content
10   sticky panel (novel detail), sticky action bar
20   bottom tab bar / reader header
30   popovers (Aa panel, filter sheet)
40   search overlay
50   dialog / modal
60   toast / notification
```

### Status roles (semantic layer — resolves F9)

Two things were wrong with the first draft of this section: it named the
roles without giving them actual values, and it described the status
mapping in "glow"/"flicker" language that directly contradicts the
no-blur-no-glow rule in Motifs and the no-looping-motion rule in Motion
above. Fixed — everything below is a flat fill or a flat outline, described
as exactly that, no lighting-effect metaphors:

| Token | Dark (default) | Light (alt) |
|---|---|---|
| `--success` | `150 45% 38%` | `150 45% 32%` |
| `--success-foreground` | `150 20% 96%` | `0 0% 100%` |
| `--warning` | `45 85% 55%` | `45 80% 48%` |
| `--warning-foreground` | `45 40% 12%` | `45 40% 10%` |
| `--info` | `205 70% 55%` | `205 70% 45%` |
| `--info-foreground` | `205 20% 98%` | `0 0% 100%` |

These complete the token set — the earlier Visual System table defined the
base roles without their foreground pairs or a couple of surfaces this
rework now needs. Full set, for one place to check against `globals.css`:

```css
--background        --foreground
--card               --card-foreground
--popover            --popover-foreground   /* same as --card, see Elevation */
--primary            --primary-foreground   /* foreground: near-white on lantern orange */
--secondary          --secondary-foreground
--muted              --muted-foreground
--accent             --accent-foreground
--success            --success-foreground
--warning            --warning-foreground
--info               --info-foreground
--destructive        --destructive-foreground  /* unchanged, pre-existing */
--border
--input              /* same value as --border, distinct name for form-field use */
--focus-ring
--ring               /* = --focus-ring, not --accent — see the pink-ring fix above */
```

These values are concrete enough to implement against but not yet
contrast-verified — that verification is still a required Review Checklist
step below, same as the existing lantern-orange/sakura-pink/teal callout in
Accessibility.

Deterministic status mapping — flat states only, no animation or lighting
effect of any kind:

| Novel status | Visual (static) | Token |
|---|---|---|
| Ongoing | Solid fill, pill badge | `--primary` (lantern orange) |
| Completed | Solid fill, pill badge | `--info` |
| Hiatus | Outlined badge (border + text, transparent fill) | `--warning` |
| Dropped | Solid fill, pill badge | `--muted-foreground` on `--muted` |
| Plan to read (library board only) | Outlined badge | `--muted-foreground` |
| Updated (library "+N new" badge) | Small solid marker | `--info` |

| Notification / message severity | Token |
|---|---|
| Success (review submitted, request submitted) | `--success` |
| Warning (contribution banner, rate-limit notice) | `--warning` |
| Info (general notification) | `--info` |
| Error | `--destructive` |

This is what Improvement Suggestion 1 refactors `rating-review.tsx`,
`request-control.tsx`, `notification-list.tsx`, `components/ui/badge.tsx`,
and the contributions-page banner *to* — those components currently
hardcode Tailwind `amber-`/`green-`/`blue-`/`yellow-` classes instead of
reading any of this.

## Brand and Illustration Asset System

The production prompts live in `assets-prompt.md` (generated externally and
not tracked in this repository). This section is the contract they implement;
prompts may be revised without changing the product direction as long as they
continue to satisfy these rules.

### Simplicity is hierarchical, not uniform

The assets should not all carry the same amount of visual information. The
brand mark must be nearly irreducible; the page illustrations may be richer
without becoming detailed or decorative:

| Asset | Intended complexity | Reason |
|---|---|---|
| Brand mark / favicon | One continuous silhouette | Must survive at 16px |
| Empty state | One subject plus one grounding plane | Reused broadly; should stay quiet |
| 404 | Small scene with 2–3 depth planes | Needs a playful narrative cue |
| Maintenance | Small shopfront scene with 2–3 depth planes | Needs to feel temporary, not broken |
| Default OG image | Richest asset in the family, still flat | Must carry the brand when no novel cover exists |

“Flat” does not mean “empty.” The scene assets create depth through scale,
overlap, perspective, cropping, and distinct solid-color planes — never through
gradients, blur, glow, texture, realistic lighting, or drop shadows. The OG,
404, and maintenance assets should use asymmetry and layered geometry so they
do not read as generic centered clip art.

### Shared visual grammar

- Every lantern uses the same recognizable pinched-waist silhouette as the
  brand mark. Do not let each generated asset invent a different lantern.
- Use at most four main colors plus the two illustration neutrals below.
- Sakura pink remains a small accent, never the dominant scene color.
- Japanese character comes from lantern rhythm, compact shopfronts, awning and
  noren geometry, and narrow-alley composition — not from torii gates, pagodas,
  ukiyo-e imitation, cherry-blossom overload, fake kanji, anime characters, or
  other generic “Japan” shorthand.
- No generated or baked-in text. Empty, 404, and maintenance copy remains real
  HTML. The generated OG *backdrop* also contains no text, but the final
  `og:image` must be a single exported image: typeset the Dokushodo wordmark
  during a build/compositing step or in a design tool. Social crawlers do not
  render an HTML/CSS overlay on top of `og:image`.
- Generated color is only a starting point. Normalize the final vector/raster
  to the exact export palette before shipping.

### Canonical export palette

The first four values are derived from the approved Yokocho Lantern design
tokens, so the assets and the application do not drift apart:

| Role | Export color |
|---|---|
| Deep plum-charcoal | `#1B141F` |
| Lantern orange | `#EE862B` |
| Sakura accent | `#DE7396` |
| Deep teal | `#274349` |
| Unlit warm neutral | `#8A6B52` |
| Signpost / closed-state neutral | `#4A4550` |
| Warm foreground / paper | `#EDE7DE` |

If the UI token values change, regenerate or recolor the asset family in the
same change set.

### Theme and export behavior

- **Brand source:** one transparent vector master. Export orange, white, and
  dark monochrome variants from the same path; do not regenerate variants.
- **Favicon:** prefer SVG plus 16px and 32px PNG fallbacks. Check the actual
  raster result at 16px; the pinch must remain visible without becoming an
  hourglass.
- **PWA/app icons:** do not rely on the transparent favicon alone. Export an
  “any” icon and a separate maskable icon on a solid plum background, keeping
  the mark inside the maskable safe area. Also export an Apple touch icon.
- **Default OG:** fixed dark composition at 1200×630. Keep important artwork
  and typeset text away from the outer crop edges.
- **In-app empty/404/maintenance illustrations:** SVG with transparent canvas
  is preferred so the app supplies the dark or light page background. If the
  generation tool cannot produce clean transparency, create dark and light
  exports from one vector source; do not place a permanent dark rectangle
  inside an otherwise light-mode page.
- Illustrations are decorative because the adjacent heading/body copy conveys
  their meaning. Use empty alt text and hide them from assistive technology;
  never rely on the illustration to explain the state.

### Asset inventory and ownership

| Asset | Source | Required exports | Used by |
|---|---|---|---|
| Brand mark | `brand-mark.svg` | SVG; 16/32 favicon PNG; white/dark variants; PWA any/maskable; touch icon | Header, favicon, manifest |
| Default social image | `og-default-source.*` | Final 1200×630 PNG/JPEG after wordmark compositing | Homepage and generic public routes |
| Empty state | `empty-state.svg` | Transparent SVG; optional optimized raster fallback | Library, browse, search |
| Not found | `not-found.svg` | Transparent SVG; optional optimized raster fallback | 404 |
| Maintenance | `maintenance.svg` | Transparent SVG; optional optimized raster fallback | Maintenance/downtime |

Novel-specific social previews use the approved novel cover and page metadata,
not the default OG illustration.

### Asset acceptance checks

- Brand mark is recognizable at 16, 20, 24, 32, 192, and 512px.
- No generated text, accidental glyphs, watermark, pseudo-kanji, or malformed
  signage survives final cleanup.
- All lanterns share one silhouette family.
- No gradient, blur, bloom, shadow, texture, or animated lighting effect.
- Empty state remains neutral enough for library, browse, and search copy.
- 404 reads as a wrong turn; maintenance reads as temporarily closed; neither
  reads as danger, damage, abandonment, or horror.
- Dark- and light-mode placements have sufficient subject/background contrast.
- Final files are cropped, optimized, and stripped of unnecessary metadata.

## Known UI/UX Flaws

Full catalog from review, kept here so it doesn't just live in chat history.
Each flaw has an ID so later sections and future revisions can reference it
directly instead of restating it.

**Navigation & information architecture**

- **F1** — Primary nav (Home / Browse / Ranking / Request / Contribute) exists
  only inside the hamburger drawer, at every breakpoint including desktop.
  `public-header.tsx` has no inline links at all.
- **F2** — The site-wide dark/light toggle lives only inside that same drawer
  (`public-sidebar.tsx`) — no toggle in the header itself.
- **F3** — Four separate "browse the catalog" entry points exist on the
  homepage alone: a utility tile, a "View all," a "Browse by genre" link in
  the Reading Paths box, and a closing full-width CTA.
- **F4** — No "Sign up" affordance in the header — only "Sign in," which then
  requires switching modes inside the modal.
- **F5** — *(new this pass)* Duplicate "Start Reading" CTA on the novel detail
  page. The hero CTA and the `ContinueReading` component both render a
  "Start Reading" link to the same first chapter, directly beneath each other,
  whenever a signed-in reader hasn't started a novel yet
  (`app/(public)/novels/[slug]/page.tsx` + `continue-reading.tsx`).

**Branding / doc-vs-code consistency**

- **F6** — `<title>` metadata defaults to "Novel AI" (`app/layout.tsx`) while
  the on-screen brand everywhere else is 読書道 / Dokushodo.
- **F7** — The old `docs/DESIGN.md` said "restrained indigo accents"; the
  shipped CSS has a vermillion-red primary and gold accent, no indigo
  anywhere — the written contract had drifted from the implementation.
- **F8** — "Dokushodo is powered by Novel AI" leaks an internal backend
  project codename into user-facing footer/sidebar copy with no explanation.

**Design-system architecture gap** *(new this pass — the most consequential
finding of this round)*

- **F9** — There is no semantic status-color layer in the token system.
  `--primary` / `--secondary` / `--accent` / `--muted` / `--destructive` exist,
  but nothing for success/warning/info. As a result, five public surfaces
  hardcode raw Tailwind palette classes instead of theme tokens:
  - `rating-review.tsx` — the star rating literally uses `amber-400` /
    `amber-500`, and the "Review submitted" message uses
    `text-green-600 dark:text-green-400`.
  - `request-control.tsx` — "Request submitted" uses the same hardcoded
    green.
  - `notification-list.tsx` — unread/info/success/warning notification
    styling is entirely hardcoded (`bg-blue-500/10`, `bg-green-500/10`,
    `bg-yellow-500/10`).
  - `components/ui/badge.tsx` — the shared `Badge` primitive's green / amber /
    red / blue / violet tones are hardcoded Tailwind classes, not CSS
    variables, so `StatusBadge` (ongoing / completed / hiatus / dropped)
    never actually reads from the site's palette.
  - `app/(public)/account/contributions/page.tsx` — a notice banner hardcodes
    `amber-500` / `amber-600` / `amber-800`.

  Practical consequence: none of these five surfaces will visually match
  Yokocho Lantern (or any future palette) without a code change, and this
  doc's own rule that "sakura pink is reserved for ratings" is currently
  impossible to honor, since the star component doesn't read `--accent` at
  all today.

**Component-level redundancy**

- **F10** — The login modal has two ways to close it: an X icon top-right and
  a full-width "Close" button at the very bottom, below the mode-switch link.
- **F11** — Genre/tag chips show the Japanese label twice: once as a `title`
  hover tooltip (dead on touch devices) and again always inline right next to
  it.
- **F12** — Reader controls (font-size stepper, theme select, width select,
  reset) are all exposed simultaneously in the chapter header instead of
  behind one settings toggle.

**Data / functional UX gaps**

- **F13** — *(new this pass)* The Rate & Review widget never loads the signed-
  in user's existing review on mount. `useUpsertReview` / `useDeleteReview`
  exist, but there is no query hook or API call anywhere to fetch a prior
  review (confirmed — no GET-review endpoint exists in `public-api.ts`).
  A returning reviewer sees a blank 0-star form every time, with the button
  reading "Submit Review" (not "Update Review") until they've submitted again
  in that session.

**Auth / error UX**

- **F14** — Every signup failure (duplicate email, weak password, rate limit)
  collapses into one message: "Could not create that account. Check your
  details and try again." Every login failure becomes "Invalid email or
  password," regardless of actual cause.
- **F15** — The Google login handler's availability probe
  (`googleStartCheck()`) falls through to starting OAuth anyway on any error
  that isn't a 503 — some backend failure states get silently swallowed
  instead of surfaced consistently.

**Visual identity**

- **F16** — Every catalog cover is a generated initials-plate; there's no real
  cover art anywhere, so the strongest "pick something to read" signal for a
  discovery product doesn't exist yet.
- **F17** — The prior palette (warm sepia, vermillion, gold) read like a
  premium literary archive rather than a casual place to binge web novels —
  the tone/content mismatch that motivated this whole rework.
- **F18** — The only overt Japanese-vibe flourish site-wide (vertical hero
  text 異世界の物語) is gated behind the `xl:` breakpoint and appears exactly
  once — thin, inconsistent identity that most visitors never see.

**Mobile-specific**

- **F19** — The reader controls row wraps across multiple lines on narrow
  viewports, competing with the back-link/title directly above the reading
  content.
- **F20** — `NovelCard` wraps the whole card in one large `<Link>`, with the
  Save button carved out via manual `stopPropagation` / `preventDefault`.
  Functional today, but a fragile pattern — a future nested control that
  forgets the same treatment will silently double-navigate.

## Improvement Suggestions

Organized by leverage — highest-impact first. Each references the flaw
ID(s) it resolves; a few are proactive additions with no flaw ID because
they're new ideas, not fixes.

1. **Add a semantic status-color layer (resolves F9).** Add `--success`,
   `--warning`, `--info` HSL tokens to `globals.css` alongside the existing
   `--destructive` (same `role` + `role-foreground` pattern), wire them into
   `tailwind.config.ts`, then refactor `rating-review.tsx`,
   `request-control.tsx`, `notification-list.tsx`, `components/ui/badge.tsx`,
   and the contributions-page banner to consume them instead of hardcoded
   Tailwind classes. This is the single highest-leverage fix in this list —
   without it, Yokocho Lantern is real in four places and "default Tailwind"
   in five others, and the rating-star color rule in this doc stays
   unenforceable.
2. **Persistent nav + header theme toggle (resolves F1, F2).** *Superseded
   by the fuller Navigation system spec below — this entry originally said
   "drawer becomes mobile-only," which stopped being accurate once the
   bottom tab bar replaced the drawer at every breakpoint. Current version:*
   desktop gets persistent inline header navigation; mobile gets the bottom
   tab bar plus the Account/More hub. The public hamburger drawer is removed
   entirely, not just hidden above `md:`.
3. **Trim the homepage to one browse CTA (resolves F3).** Keep either the
   closing CTA or the Reading Paths box, not both — four entry points can
   become two without losing discoverability.
4. **Add a header "Sign up" link next to "Sign in" (resolves F4).**
5. **Remove the duplicate Start Reading CTA (resolves F5).**
   `ContinueReading` should render nothing (or a quieter line, not a second
   button) when the page already has its own hero CTA and there's no saved
   progress; keep its own CTA only where no hero button exists (library,
   history views).
6. **Prefill the review form (resolves F13).** Add a `useReview(slug)` query
   — this needs a matching GET endpoint on the backend, since none exists
   today — so a returning reviewer sees their saved stars/text and "Update
   Review" immediately instead of a blank form.
7. **Reason-carrying signup errors, generic login errors (resolves F14).**
   Signup can safely be specific ("That email's already registered," "Needs
   at least 10 characters") since you're not confirming anything about
   someone else's account. Login should stay generic ("Invalid email or
   password") — being specific there would let someone probe whether an
   email is registered. Don't apply the same fix to both indiscriminately.
8. **Consistent "unavailable" state instead of silent OAuth fallback (resolves
   F15).**
9. **One close affordance per modal (resolves F10).** Drop the bottom "Close"
   button, keep the X.
10. **Drop the tooltip on genre/tag chips, keep the inline label (resolves
    F11).** Remove the redundant `title=` attribute.
11. **Collapse reader controls behind a single "Aa" toggle (resolves F12,
    F19).** One button opens a small panel styled with the lantern-badge
    motif, instead of four separate controls sharing the header row.
12. **A lightweight real-cover-art step (addresses F16/F17), short of solving
    "safe remote covers" all at once.** Let an admin attach one hero image per
    novel (even a simple stock or generated illustration) that swaps in for
    the bookplate on that novel's card **and** detail page — see the single
    cover-source rule in Public Reader below, which applies this
    consistently everywhere rather than detail-page-only or card-only.
    Everything without an attached cover keeps the (now Yokocho-Lantern
    -styled) generated bookplate as the graceful fallback the existing
    contract already requires. Gets real art onto featured/flagship titles
    without reopening the cover-safety question, and ingests through
    controlled storage rather than hot-linking a remote URL.
13. **Spread the Japanese-vibe motifs beyond one hero element (resolves F18).**
    Apply the lantern-badge, noren divider, and halo-ring motifs (see Visual
    System above) across browse, detail, and reader — not just the homepage
    hero — so the identity is visible at every breakpoint, not once on
    desktop.
14. **Harden the card/save-button nesting pattern (resolves F20) — now a
    concrete rule, see Novel-card anatomy below**, not just a suggestion:
    no interactive element nests inside another one; card, cover-link,
    action, and Save are four separate elements sharing one visual card,
    never one link wrapping the rest.

## Layout Rework — Full Site (v2)

This is a full pass at Dokushodo's layout, not a patch list. It carries
forward Yokocho Lantern and every flaw fix above, folds in what was worth
adapting from the WTR-LAB comparison, and adds new structural ideas beyond
either source. Written as a working designer + user-tester would hand it
off: per-surface, with the reference pattern named, the reasoning, and which
flaw IDs it resolves.

### Guiding principles

1. **One primary action per decision region, not one per page.** A region —
   the hero, a rail, a card, a form — gets exactly one visually dominant next
   action. This isn't "a page may only have one button": the homepage
   legitimately has many novel cards, several "See all" links, search, and a
   Surprise Me tile, and none of that is wrong. What's wrong is two actions
   inside the *same* region competing for the same decision, which is what
   F3 and F5 actually were. Secondary navigation can stay visible; it just
   can't visually out-compete its region's primary action.
2. **Chrome recedes, content leads.** Navigation and controls should be
   quick to find and quick to stop noticing — the Yokocho Lantern motifs
   decorate structure, they don't compete with it.
3. **Never show a number you can't stand behind.** The existing
   ranking-honesty pattern (an explicit "not live yet" state instead of fake
   data) is the correct instinct — extend it, don't override it, when adding
   anything WTR-LAB-inspired that implies live stats (rankings, leaderboards).
4. **Reader identity stays low-key by default.** WTR-LAB ties reviews to
   public profiles; people read things — romance, isekai, whatever — they
   may not want attached to a public identity. Default to pseudonymous,
   opt-in visibility. This is a product/privacy call the designer has to
   make, not just a routing one, so it's made explicitly here.

### Sitemap (revised)

```
/                          → redirects to /home (unchanged)
/home                      → reworked: rails, not a long vertical stack
/browse-novels             → reworked: see Browse / Catalog spec below
/tags/[tag]                → [NEW] canonical, prefilters browse-novels
/genres/[genre]            → [NEW] canonical, prefilters browse-novels
/sources/[source-key]      → [NEW] "everything scraped from this source" listing
/authors/[author-slug]     → [NEW] "everything by this author" listing
/random                    → [NEW] server redirect straight to a surprise novel
/novels/[slug]             → reworked: sticky panel + tabs
/novels/[slug]/chapter/[id]→ unchanged structure, reworked controls (Aa panel)
/ranking                   → unchanged (stays an honest "not live yet" state)
/request-novel             → unchanged
/contribute                → unchanged
/faq                       → [NEW] flat categorized Q&A, no auth
/news                      → [NEW] flat dated list, no auth
/account                   → [NEW] account overview/summary, see Desktop
                             account shell below — this was referenced by
                             that section but missing from the sitemap itself
/account/library           → reworked: status board, replaces flat list
/account/history           → unchanged (reading log, reverse-chronological)
/account/reviews           → [NEW] reviews authored by the current user —
                             also referenced by the desktop sidebar without
                             being listed here; fixed
/account/notifications     → unchanged list, tokens fixed (F9)
/account/requests          → unchanged
/account/contributions     → unchanged
/account/settings          → unchanged
/about, /contact, /support,
/legal, /terms, /privacy,
/cookie-policy, /dmca      → unchanged, already solid
/login, /logout,
/auth/callback             → /login is the canonical, independently-usable
                             auth surface (see Auth surface note below)
```

Public `profile/{id}` is deliberately **not** in this pass — see Guiding
Principle 4. If reviews later get a "post publicly under my username"
opt-in toggle, a profile route becomes a small addition, not a rebuild.

`source` and `author` are genuinely different fields (`novel.source_key` vs.
`novel.author`, confirmed in `novel-card.tsx`) — a novel's scraping origin
and its actual writer aren't the same thing, so these get two routes, not
one conflated route. Both use a stable-key/slug shape (`/sources/[source-key]`,
plural, matching `/authors`/`/tags`/`/genres`/`/novels`) rather than a raw
display name in the URL, since names can be renamed or vary in spelling —
`source_key` already exists as a stable field today. **Author identity is
the one open question here**: nothing in the current data model gives an
author a stable ID or handles aliases, so `/authors/[author-slug]` for now
is a slugified name, with the known limitation that the same real author
under two spellings would show as two separate pages until the backend
gains an actual author-identity concept. Worth a backend ticket, not
something this frontend doc can resolve alone.

**Auth surface note (resolves the login-route/modal question):** `/login`
is the canonical, independently-usable page — direct visits, OAuth
callback returns, and any no-JavaScript fallback all land here. The
"login modal" referenced in the flaw list and elsewhere is a convenience
wrapper: desktop shows it as a dialog, mobile shows it as a full-screen
sheet, and both render the *same* underlying auth form component as
`/login` rather than a second, divergent implementation. The modal does
not change the URL; only a direct visit or a callback redirect does.
"Sign up" is the same form in its sign-up mode, reached from the header
(desktop) or the Account hub (mobile) next to "Sign in," not a separate
page. After an OAuth failure, the modal/page shows the same "unavailable"
state defined for F15, and returns the visitor to whatever they were doing
before, not a dead end.

### Navigation system

Reference: Letterboxd and Notion-style persistent top nav on desktop; the
Webtoon/Tapas/BookWalker pattern of a bottom tab bar on mobile, since a
reading app is used one-handed far more than a productivity app is.

- **Desktop (`md:` and up):** header shows inline links — Home, Browse,
  Recently Updated, Request, Library — plus search, theme toggle,
  notification bell, and account, all in the header itself. No hamburger
  exists at this width. (Resolves F1, F2.) **This replaces an earlier
  version of this list that included Ranking and Contribute** — both are
  explicitly "not live yet" per this doc's own honesty principle, and
  spending two of five primary-nav slots on destinations that currently do
  nothing meaningful contradicts that principle as surely as showing fake
  numbers would. Ranking and Contribute move to the Account/More hub
  (mobile) and stay reachable but de-emphasized on desktop too, until they
  have real data or a real action behind them.
- **Mobile (below `md:`):** header shrinks to brand + notification bell only.
  Primary navigation moves to a **bottom tab bar**: Home, Browse, Search,
  Library, Account — five fixed icons, thumb-reachable. This replaces the
  hamburger drawer entirely rather than just hiding it at a bigger
  breakpoint. **Search lives in the tab bar only** — the earlier draft of
  this section put a search icon in both the header and the tab bar at once,
  which is exactly the kind of duplicate-entry-point problem this whole doc
  exists to remove (see F3). One search surface, reached from the tab bar.
- **Ranking, Contribute, Request, FAQ, and News have no dedicated mobile
  tab — fixed.** Removing the drawer took away their only mobile entry point
  along with it; the first draft of this rework didn't account for that.
  Resolution: the **Account tab doubles as a hub**, the way Spotify's or
  Duolingo's profile tab does — tapping it opens the account dashboard *and*
  a "More" list underneath the account-specific items (library shortcuts,
  settings) linking out to Ranking, Request Novel, Contribute, FAQ, News,
  About, Support, and Legal. Nothing loses its route; it just moves from a
  drawer to a predictable single hub instead of floating in the header on
  desktop with no mobile equivalent. The theme toggle lives here too, not
  buried in a menu a level deeper.
- **Guest mobile navigation was undefined — three of the five tab-bar/header
  controls implicitly assumed a signed-in reader:**

  | Control | Guest behavior |
  |---|---|
  | Library tab | Opens a plain sign-in explanation, preserving the destination so a successful sign-in lands back on Library, not the homepage |
  | Account tab | Opens the sign-in/create-account surface directly — there's no "guest account dashboard" to show instead |
  | Notification bell | Hidden entirely for guests — never shown disabled or empty, since an unusable control invites a tap that goes nowhere |
  | Save-to-library button | Opens an inline auth prompt; on successful sign-in, completes the save the guest was originally trying to make, rather than requiring them to find and re-tap it |
  | Continue Reading (homepage rail) | Uses locally-stored progress for a guest instead of account data; if there's none yet, shows the existing "Sign in to pick up where you left off" tile |

  In every case above, **authentication preserves the action or route that
  triggered it** — this is a general rule, not just a library-tab rule: a
  guest who was mid-action never has to repeat themselves after signing in.
- **At most one fixed-bottom bar on screen at a time.** The tab bar and the
  novel-detail sticky action bar (see below) are both bottom-fixed; stacking
  both would eat a large strip of a small screen. Rule: the tab bar is
  global chrome and stays present on browsing surfaces (home, browse,
  library, account); on a page that defines its own contextual sticky bar
  (novel detail's action bar, the chapter reader's controls) that page's bar
  replaces the tab bar for the duration of that screen, not stacks under it.
  The tab bar reappears the moment the reader navigates back out.
- **Safe-area and overlap rules**, added because the fixed-bottom-bar rule
  above isn't sufficient on its own once toasts, sheets, and the floating
  Aa button are all in the mix:
  - Every fixed-bottom element pads for `env(safe-area-inset-bottom)` so
    nothing sits under an iOS home indicator or Android gesture bar.
  - Toasts render above whichever fixed-bottom bar is currently active,
    never underneath or overlapping it.
  - The floating Aa button (chapter reader) is positioned so it never
    overlaps the previous/next chapter controls at the bottom of the text.
  - Opening a bottom sheet (the mobile filter sheet, the Aa panel)
    temporarily suppresses whatever fixed-bottom bar was showing, rather
    than stacking the sheet on top of it.
  - A focused text input that triggers the on-screen keyboard never leaves
    that form's primary action hidden beneath the keyboard.
- **On desktop, FAQ and News aren't header links either** — they'd crowd
  the five primary items. They join the existing footer (which already
  lists About, Contact, Legal) instead, on both desktop and mobile-scrolled-
  to-bottom, so there's still a zero-click-deep path to them without
  competing with primary navigation.
- **Search becomes one shared overlay**, not two different search boxes.
  Reference: the Notion/Linear "Cmd+K" command palette, scaled down to a
  reading app — tap the search tab (desktop: click the header search field,
  or the `/` shortcut) and a centered overlay opens with recent searches, a
  few genre shortcuts, and live results as you type. Fits the "not too
  serious" brief too — it's the one place a little personality (playful
  empty-state copy, e.g. "nothing here yet — try a genre?") can live without
  getting in the way of reading.
- **Focus-ring contrast on the primary button specifically.** A lantern
  -orange ring around a lantern-orange button is the one place
  `--focus-ring` (defined in Design Tokens) doesn't separate cleanly by
  color alone — same hue family, similar lightness. Primary buttons use a
  two-layer focus treatment instead of a single ring: an inner ring in a
  high-contrast neutral (near-white/cream), then an outer offset ring in
  `--focus-ring`, so the focus indicator reads clearly even against its own
  fill color. Every other control keeps the single-ring treatment; this
  two-layer version is specifically for primary-colored buttons.

### Search contract

The overlay above needs an actual behavior spec, not just a UI reference:

- **Fields searched:** translated title, original (Japanese) title, author,
  tags. Not synopsis body text — full-text synopsis search is a later-stage
  feature, not v1.
- **Grouped results**, in this order: Novels, Authors, Genres & Tags, Recent
  searches (shown only when the query is empty).
- **Fuzzy matching** on translated/romanized titles; exact substring on tags.
- **Title normalization:** both translated and original titles are indexed;
  a search for either the English or the Japanese title should surface the
  same novel. Long CJK titles wrap by character, not by forcing a horizontal
  scroll inside the result row.
- **Enter key opens the currently highlighted result**, not always the top
  one — the earlier draft said "opens the top result directly," which risks
  accidental navigation the moment arrow keys are added. When nothing is
  highlighted (query just typed, no arrow-key interaction yet), Enter opens
  the full results page instead of guessing. There's always a "See all
  results for '...'" row as the last item either way.
- **Request/keyboard mechanics**, missing from the first draft: input is
  debounced 200–250ms before firing a search; a new keystroke cancels
  whatever request is still in flight, so a slow late response can't
  overwrite a newer, faster one; queries under 2 characters show recent
  searches/genre shortcuts instead of firing a request; arrow keys move a
  visible highlighted state up and down across grouped results; `Escape`
  closes the overlay and returns focus to whatever opened it; each group
  caps at a handful of results (e.g. 5) with its own "see all" rather than
  one long mixed list; a new response replaces stale results in place
  rather than clearing to a blank/loading state first, so the overlay
  doesn't flicker empty between keystrokes.
- **Recent searches are local only** (not synced to the account) unless a
  concrete privacy-reviewed reason to sync them shows up later — searches
  can reveal reading interests someone may not want stored server-side by
  default, consistent with Guiding Principle 4.
- **Network failure:** the overlay shows a plain "Search's unavailable right
  now" state, never a silent empty-results list that looks like "no
  matches."
- **Mobile:** full-screen surface, not a narrow centered modal — there's no
  room for a centered overlay to breathe on a small viewport.

### Browse / Catalog

This was the single most under-specified page relative to how much traffic
it'll actually carry — "unchanged core, + view toggle + Random button" isn't
a layout. Full spec:

**Desktop**
- Filters live in a left sidebar (not a top bar) — the existing filter
  system (include/exclude tags and genres, chapter-count range, status,
  sort) is genuinely good; it just needs a permanent home instead of
  competing with results for vertical space. **Only the sidebar's heading
  and Clear-all action are sticky; the filter list itself scrolls with the
  page**, not independently — an earlier version of this spec made the
  whole sidebar independently scrollable, which creates two adjacent
  scroll containers and makes keyboard/touchpad/screen-reader navigation
  harder than it needs to be. Revisit independent scrolling only if the
  filter set demonstrably outgrows the viewport and testing supports it.
- Header row above the grid: results count, sort selector, grid/list view
  toggle, and the Random ("🎲 Surprise me") entry point from Improvement
  discussions.
- Active-filter chips sit directly under that header row, each removable
  individually, plus one "Clear all."
- Pagination, not infinite scroll (matches the existing choice — no change).
- **Filter state lives in the URL** (query params), not just client state —
  this is what makes `/tags/[tag]` and `/genres/[genre]` work as real
  prefilter links, and it's what lets a filtered view be bookmarked, shared,
  or indexed.

**Mobile**
- Sort becomes a compact single control in the results header.
- Filters open as a bottom sheet (not the sidebar), with a persistent
  "Apply" and "Clear" pair pinned to the sheet's bottom edge so a long
  filter list doesn't strand the action below the fold.
- The results header shows an applied-filter count badge on the filter
  button itself ("Filters (3)") so the state is visible without opening the
  sheet.
- Scroll position restores when navigating back from a novel detail page —
  a common, easy-to-miss regression once tabs/sticky panels are added
  elsewhere.

**Recommended filter set** (beyond what exists today): title/original-title
search, author, source, status, genre, tags, translation availability,
chapter-count range, recently-updated, and — signed-in only — saved/not
saved.

**Empty results:** a real recovery state, not a blank grid — "No novels
matched. Clear filters, or try a broader genre" with the clear-all action
right there, not just implied.

**Filtered-page SEO policy** — "indexed where appropriate" wasn't defined,
this is the definition:
- `/tags/[tag]` and `/genres/[genre]`: indexable — these are the canonical
  taxonomy pages this whole scheme exists to make shareable.
- `/authors/[author-slug]` and `/sources/[source-key]`: indexable when they
  contain at least one novel; not indexed if empty.
- Arbitrary multi-filter query strings on `/browse-novels` itself: `noindex,
  follow` — real utility, not real SEO value, and indexing every filter
  combination would just create thin-content duplicates.
- Sort-only variants of an otherwise-identical filter set canonicalize to
  the unsorted version.
- Any `saved=true` or other account-scoped filter: `noindex` — it's not
  the same page for two different visitors.
- Paginated results: each page is self-canonical, not folded into page 1.

### Novel-card anatomy

Two explicit variants — otherwise every page that renders a card
(homepage rails, browse grid, author page, tag page, library board) risks
inventing its own slightly-different one:

- **Compact rail card** (homepage rails, "See all" grid overflow): cover,
  translated title, status lantern, chapter count or latest-chapter label,
  progress indicator when the reader has one, save-state icon. No synopsis.
- **Rich browse card** (browse grid, author/tag/source pages): cover,
  translated + original title, author, status, chapter count, last-updated
  timestamp, rating and review count, up to three genre chips, a one-line
  synopsis excerpt, and the start/continue action. This is the one that
  matches most of what's already in `NovelCard` today — the addition is
  being explicit that it's a *variant*, not the only card, so the compact
  rail card doesn't quietly grow the same density over time.
- **Breakpoint rule:** the rich card drops synopsis and original title
  first as the viewport narrows; cover, translated title, status, and the
  action button are the four fields that never disappear at any width.
- **The F20 fix, made concrete** (Improvement 14 said "harden the pattern"
  without saying what the pattern should be — this is what):
  - The card container itself is not an anchor.
  - Cover and title are their own link to the novel.
  - The start/continue action is its own separate link.
  - Save is its own separate button.
  - No interactive element is ever nested inside another interactive
    element — this is what makes the rule enforceable in review rather than
    a style preference: a nested `<a>`-in-`<a>` or button-in-link is a
    structural violation, not a judgment call.
  - The card surface can still look and feel clickable (cursor, hover
    state) without depending on `stopPropagation`/`preventDefault` to fake
    single-click-anywhere behavior.

### `/authors/[author-slug]` and `/sources/[source-key]`

Both are the same shape — "everything matching this one field" — so one
spec covers both:

- Header: name (author's name in original + normalized form for
  `/authors`; source platform name for `/sources`), novel count, ongoing vs.
  completed counts.
- Body: rich browse cards, same sort/filter affordances as `/browse-novels`
  scoped to this author/source.
- `/authors` additionally needs alias handling — the same author's name may
  appear inconsistently across scraped sources; until the backend has an
  actual author-identity concept (see the sitemap note above), this page
  degrades to an honest "may not include every novel by this author" note
  rather than silently presenting incomplete results as complete.
- Safe empty/not-found state for both if the author or source has zero
  novels currently indexed.

### Homepage

Reference: Spotify/Netflix-style horizontal rails instead of a long
vertical stack of full-width sections; the actual card component
(`NovelCard`) doesn't change, just how it's arranged.

- One hero: the current featured-novel spotlight, kept, but with a single
  CTA ("Start Reading") — no secondary competing button in the hero.
  **Selection was undefined; fixed:** manual, admin-selected — a small
  admin control picks which novel is featured, rather than an algorithm
  guessing from incomplete signals. Requirements to be eligible: an
  approved cover (real or a well-formed bookplate), a synopsis, and at
  least one available chapter. Rotates on a fixed cadence (e.g. weekly) set
  by whoever's curating it, not on page load. If the currently-featured
  novel becomes unavailable (taken down, translation pulled) the hero
  falls back to the most recent otherwise-eligible pick rather than
  breaking or showing a stale/broken card. Mature-rated novels can be
  featured only if the visitor's content-safety preference (Content Safety
  and Moderation, below) allows mature content — the hero respects that
  filter like everything else does. Signed-in personalization doesn't
  replace the hero for v1; Continue Reading immediately below it already
  covers the personalized case.
- Below the hero, horizontal scrolling rails, each with its own "See all"
  link pointing at a real filtered URL (`/tags/[tag]`, `/genres/[genre]`,
  or `/browse-novels?...`) rather than a generic "browse everything" link:
  - **Continue Reading** (signed-in only, personalized, pulled from
    existing progress data — no new backend needed). Guests see a single
    quiet tile in its place — "Sign in to pick up where you left off" —
    never an empty rail with nothing in it.
  - **New Releases**
  - **Recently Updated** (the existing "Recent Updates" list, reshaped into
    a rail)
  - One or two **genre rails**, chosen from actual catalog composition (the
    genres with the most translated novels) rather than hardcoded — "Isekai"
    and "Romance" above were illustrative, not a fixed list to hardcode.
    For a signed-in reader with rated/saved novels, these can lean toward
    their most-read genres instead of the global default.
  - A **Surprise Me** rail entry point — not a rail of its own, just one
    card-sized tile linking to `/random` (see below)
- This removes the "Reading Paths" box and the multiple duplicate browse
  CTAs entirely — rails already are the browse entry points. (Resolves F3.)
- **Rails need their own accessibility spec, not just the general
  Accessibility section below** — this is a new interaction pattern this doc
  introduces, so it has to say how it behaves for someone who isn't swiping
  with a thumb or dragging with a mouse:
  - Each rail is a labeled scroll region (`role="region"`, `aria-label`
    naming the rail — "Continue reading," "New releases") so a screen reader
    user knows what they've entered and can move on.
  - Horizontally scrollable by keyboard when focused (arrow keys), not
    mouse/touch-drag only.
  - Visible previous/next affordances on hover/focus for pointer users —
    never scroll-only with no indication more content exists off-screen.
  - `prefers-reduced-motion` gets instant scroll, not smooth/snap animation.
  - The "See all" link is real markup, not a JS-only escape hatch — a
    keyboard or screen-reader user can reach the full filtered list without
    ever needing to interact with the horizontal scroller itself.

### `/random` — a new small idea

Reference: Wikipedia's "Random article." One click, straight to a surprise
novel detail page — no listing page in between. A `/random-novels` *listing*
page (WTR-LAB has one) was considered and dropped in favor of this: a direct
redirect is a more delightful, lower-friction version of the same idea, and
it's cheap — a randomized query plus a 302, no new UI to design or maintain.
If the catalog is ever empty (e.g. a fresh install with zero translated
novels), redirect to `/browse-novels` with a plain explanatory message
instead of erroring — same "never show a broken state where an honest empty
state would do" instinct as the ranking page.

### Novel detail page

Reference: WTR-LAB's tabbed novel page combined with the sticky-sidebar
pattern from Goodreads/MyAnimeList (cover and primary action stay pinned
while the reader scrolls through synopsis, chapters, or reviews).

- **Desktop:** two columns. Left column is sticky — cover (bookplate),
  title, status lantern-badge, one primary action button that already knows
  the right label and destination (`Start Reading` / `Continue from Ch. X`
  — one button, one component, replacing the current hero-CTA-plus-separate-
  `ContinueReading` duplication), Save to Library, and the star rating
  summary. Right column holds tabs:
  - **Overview** — synopsis, tags, genres (today's default view)
  - **Chapters** — the existing volume-grouped list, plus the behavior it
    was missing: a chapter search/filter field, ascending/descending order
    toggle, collapse/expand-all on volume groups, a "jump to first unread"
    and a "jump to latest" shortcut, a last-read marker on whichever chapter
    the reader stopped at, read/unread visual state per chapter, a "new"
    marker on recently-added chapters, and an explicit unavailable/failed
    -translation state per row rather than the row just not appearing.
    Very long chapter lists (100+) virtualize rather than render every row
    at once.
  - **Reviews** — the existing rate/review form, plus other readers' reviews
    listed below it (if that data isn't already surfaced elsewhere, this is
    the first place it should be)
  - No **Related/Recommendations** tab unless there's real recommendation
    data behind it — an empty or fake-feeling tab is worse than no tab, per
    Guiding Principle 3.
  - Tab selection is reflected in the URL (`?tab=chapters`), so a link to
    "the reviews tab of novel X" is a real, shareable URL, not just a client
    state that resets on reload.
  (Resolves F5 directly — there is now exactly one "start/continue reading"
  control on the page, not two.)
- **Mobile:** the sticky sidebar collapses into a slim sticky bar pinned to
  the bottom of the viewport — small cover thumbnail, title, one action
  button — reference the "sticky add to cart" pattern common in mobile
  commerce, adapted here as a sticky "start reading" bar. Per the
  fixed-bottom-bar rule above, this bar *replaces* the tab bar on this
  screen; it doesn't stack on top of it. Tabs become a horizontally
  -scrollable segmented control directly under the header; on mobile
  specifically, "Chapters" can also open as a full-screen drawer instead of
  an in-place tab, since a long chapter list benefits from the extra
  vertical room a drawer gives it.

### Chapter reader

Mostly right already — two focused refinements, plus one thing the previous
draft left unsaid:

- **Collapse font size / theme / width / reset into one "Aa" control.**
  Concretely: a small circular button, floating bottom-right, thumb-reachable,
  respecting the device's safe-area inset — not sitting in a header row.
  Tapping it opens a popover sheet with the four settings, reference
  Kindle/Apple Books' reading-settings sheet. (Resolves F12, F19.) Exact
  values, since the first draft specified the font-size range but left
  width and theme as unstated options:
  ```
  Font size: 16, 18, 20, 22px (as already specified above)
  Text width: Narrow 560px · Standard 680px (default) · Wide 800px
  Theme: Light · Dark · Sepia (reader-specific, independent of site theme)
  Reset: back to Standard width, 18px, and the reader's last-saved theme
  ```
  The Container Widths table above listing 680px as the reader column's
  width meant "default," not "only option" — this is the clarification.
- **The bottom tab bar and header both go quiet while reading.** This
  should have been explicit the first time: Guiding Principle 2 says chrome
  recedes, but introducing a global bottom tab bar elsewhere in this rework
  without saying it disappears here would quietly break the reader's
  distraction-free goal. Concretely: header collapses to a small back-caret
  plus chapter title only; the tab bar is not rendered on chapter routes at
  all — the floating "Aa" button and the thin progress bar (below) are the
  only persistent controls.
- **A thin reading-progress bar** (2–3px, `--primary`-colored) fixed to the
  very top of the viewport, filling as the reader scrolls through the
  chapter. Reference Medium's progress bar. Small, cheap, and it quietly
  reinforces the "quiet, focused reading" goal instead of adding chrome.
- **Navigation and recovery** — the previous draft covered controls but not
  behavior:
  - Previous/next chapter stays at both the top and bottom of the chapter
    (already true today — this rework doesn't remove it) plus a footer row
    reading `Previous chapter · Back to novel · Next chapter` at the very
    end of the text.
  - Keyboard shortcuts: `←`/`→` for previous/next chapter, `.` opens the Aa
    panel — documented once, visibly, inside the Aa panel itself so they're
    discoverable rather than hidden trivia.
  - At the end of a chapter, "Next chapter" becomes the single strongest CTA
    on screen — visually promoted the moment the reader reaches the bottom,
    not equal-weight with "Back to novel" the whole way down.
  - **Resume position:** reopening a novel returns to the last scroll
    position within the last-read chapter, not just the last chapter as a
    whole. Progress is account-level, so it's consistent across devices for
    a signed-in reader; for a guest, it's local-only and should say so if
    they view it from a second device.
  - Changing font size mid-chapter recalculates the progress percentage
    against the new layout rather than freezing it at whatever it was —
    otherwise the progress bar visibly lies the moment someone adjusts text
    size.
  - **Edge states:** offline/reconnect shows a quiet inline banner, not a
    blocking error, and never discards reading position; a chapter that's
    missing or has an unavailable translation shows an explanation with a
    link back to the chapter list, not a blank page; the existing
    report-translation-issue link stays, unchanged.
  - Glossary annotations keep their current toggle/interaction — this
    rework doesn't touch that, it was already solid.
  - **Long chapters and long chapter lists — the previous draft's advice
    here was technically risky and needed correcting, not just expanding.**
    DOM virtualization of prose text breaks things people actually rely on:
    browser find-in-page, text selection/copying, screen-reader navigation,
    in-page anchor links, and accurate scroll-based progress. So, for
    chapter text specifically: render the full chapter in the DOM and apply
    `content-visibility: auto` to off-screen block sections for the
    performance win instead, or split an exceptionally long chapter into
    stable semantic segments that all stay in the DOM rather than being
    mounted/unmounted on scroll. Only reach for server-side chapter
    segmentation if real performance measurements later prove
    `content-visibility` isn't enough — don't pre-optimize with it. For the
    Chapters-tab list specifically: 100 rows almost certainly doesn't
    justify virtualization either; collapsed volume groups (already
    specified) or simple pagination handle that size comfortably, and
    virtualization is worth revisiting only for genuinely enormous chapter
    counts with real measurements behind the decision. Inline images (rare
    — glossary or illustration content) can still lazy-load below the fold;
    that's an image-loading optimization, not a text-virtualization one, and
    doesn't carry the same risks.

### Library / Account

Reference: the Anilist/MyAnimeList status-board pattern (Reading / Plan to
Read / Completed / Dropped columns) instead of one flat list — but reframed
on-theme rather than copied outright: **"Your Yokocho"** — each status is a
row of lanterns in the alley rather than a generic Kanban column. Reuses the
lantern-badge motif already defined in Visual System — flat fills, per the
corrected Status roles table above, not lighting effects:
- Reading → solid `--primary` fill ("lit" lantern shape, static)
- Plan to read → outlined, `--muted-foreground` border and text
- Completed → solid `--info` fill
- Dropped → solid fill, `--muted-foreground` on `--muted`

This also absorbs the WTR-LAB "Updates" tab idea without adding a whole new
tab, but not through sort order alone — a prior draft of this doc leaned
entirely on "recently updated first" sorting, and sorting alone doesn't
tell someone *which* novels actually gained chapters, only that they're
near the top for some reason. Fix: default sort stays "recently updated
first," and each card additionally carries a visible "+N new" badge (using
`--info`, per Design Tokens) when chapters have arrived since the reader's
last-read point. `account/history` stays a separate, simpler
reverse-chronological reading log (reference Letterboxd's diary), since
"what did I read, in order" and "what's the state of things I'm reading"
are genuinely different questions and shouldn't be forced into one screen.

A brand-new account has an empty board by definition — this needs its own
state, not four columns of unlit lanterns with nothing behind them. The
empty board shows one centered invitation ("Nothing saved yet — browse the
catalog to start your shelf") with a single CTA into `/browse-novels`,
replacing the columns entirely until at least one novel is saved.

**The board doesn't scale to hundreds of titles on its own**, so it needs a
list alternative, not a replacement:
- A board/list view toggle, same idea as the Browse/Catalog grid/list
  toggle. List view is a compact row per novel: cover thumbnail, title,
  status lantern, updated-badge, progress, last-read timestamp.
- **Compact list is the mobile default**; the board (which needs horizontal
  room for four columns) is the desktop default. Both remain available at
  either width via the toggle.
- Search-within-library, and sort by last read, last updated, title, or
  progress — independent of which view is active.
- A "recently updated" filter as a shortcut, separate from the default sort,
  for someone who wants to see *only* what's new right now.
- Bulk status change (multi-select → move several novels from Plan to Read
  to Dropped at once) — a board with hundreds of entries makes one-at-a-time
  status changes tedious fast.

**Desktop account shell** — the mobile Account/More hub was specified above;
desktop had nothing. Desktop uses a persistent left sidebar plus content
pane, not a hub screen (a hub pattern makes sense on mobile where it
replaces a missing nav destination; on desktop, the primary header nav
already covers Ranking/Request/Contribute, so Account's sidebar only needs
account-scoped items):

```
Desktop:
[Account sidebar]      [Page content]
 Library
 Reading history
 Notifications
 Requests
 Contributions
 Reviews
 Settings
 Support
```

The account landing view (`/account` itself, distinct from `/account/library`)
shows a short summary — reading streak or count, unread-update count, most
recent activity — rather than acting purely as a route directory with
nothing on it until a sub-page is clicked.

### Notifications

Layout stays as-is — it was already reasonably designed. The only change is
underneath it: once the semantic status tokens exist (Improvement #1 /
resolves F9), `notification-list.tsx`'s unread/info/success/warning styling
switches from hardcoded Tailwind classes to those tokens, and severity
colors finally match Yokocho Lantern instead of default-Tailwind
blue/green/yellow.

### What this intentionally leaves out

Kept out on purpose, not overlooked — consistent with the WTR-LAB comparison
from earlier: tickets/gems economy, batch chapter-unlocking, community
folders and voting, and a leaderboard. All four assume either a monetization
model or a live-stats integrity system this project doesn't have. Adding
the routes without the substance behind them would violate Guiding
Principle 3 faster than it would improve discovery.

### Remaining routes — minimum viable spec

Every route in the sitemap needs at least a purpose, a primary action, and
its states — most of this doc's attention went to homepage/detail/reader,
leaving these named but unspecified. One pass, kept intentionally terse
since these are genuinely simpler pages:

| Route | Purpose | Primary action | Guest vs. auth | Backend need |
|---|---|---|---|---|
| `/account` | Account overview/summary | none — dashboard | auth required | reading streak/count, unread-update count, recent activity summary |
| `/ranking` | Honest placeholder until live stats exist | none (informational) | same for both | none yet — stays static until real data backs it |
| `/request-novel` | Submit a new novel for translation | Submit request form | guest sees and fills the form, submission requires sign-in | existing request queue |
| `/contribute` | Explain + (later) accept API-key contribution | currently informational only ("not available yet") | same for both | none yet |
| `/faq` | Answer common questions, reduce support load | none — reading is the action | same for both | static content |
| `/news` | Dated changelog/announcements | none — reading is the action | same for both | static/CMS content |
| `/account/notifications` | Review + manage alerts | mark read / adjust preferences | auth required | existing notifications API, tokens fixed per F9 |
| `/account/requests` | Track requests the reader submitted | view status | auth required | existing request queue, scoped to session |
| `/account/contributions` | Track contribution status | view status | auth required | existing contributions data |
| `/account/reviews` | Reviews the current reader has authored | view/edit own reviews | auth required | needs the review-fetch endpoint from Improvement 6 anyway |
| `/account/settings` | Manage profile, password, session | save changes | auth required | existing settings API |
| Legal/support pages | Compliance + policy text | none — reading is the action | same for both | static content |

**Form data survives an authentication detour** — a gap the `/request-novel`
row above would otherwise hide: a guest filling out the request form (or
writing a review, or tapping Save) who gets sent to sign in should come back
to a restored draft, not a blank form and not a silent auto-submit. Sequence:
preserve the entered data locally → authenticate → return to the same
form → restore the draft → the reader still takes an explicit final
submit action. This is the same "preserve the action that triggered
auth" rule from the guest-navigation table above, applied to forms
specifically.

All of the above inherit the standard states from Page Structure and States
below (loading, empty, recoverable error, unavailable, settled) — that
section already covers it generically; this table exists so each route has
at minimum a named purpose and primary action on record, not just a path.

## Ownership

- `frontend/app/(admin)/admin/*`: owner interface. Unaffected by this rework —
  admin stays plain/functional, no Japanese-vibe styling needed there.
- `frontend/app/(public)/*`: guest and public-user interface — everything above
  applies here.
- Shared components: `frontend/components/`; route-local components stay local.
- TanStack Query owns server state; Zustand owns client-only state.
- Tailwind plus `cn()` owns styling; no CSS modules or styled-components.
- Hooks own business/data flow; components own presentation.

## Page Structure and States

Public shell owns header, skip link, and focusable `#main-content`. Each page
owns exactly one `main`. Admin shell owns primary navigation and page frame.

Every data surface defines loading, empty, recoverable error, unavailable, and
settled states. Add not-found/legal states where relevant and preserve useful
stale data during background-refetch failure. Never render raw API error
objects. (This was already true and stays true — it's genuinely good.)

## Public Reader

- Catalog cards show bookplate/cover, translated title, author, localized
  taxonomy, status, and useful progress without crowding.
- Novel detail: see Layout Rework above for the full sticky-panel/tabbed
  spec — this line stays only as the one-sentence summary: title, synopsis,
  status, chapters, and one unambiguous reading action, always.
- Chapter pages prioritize text width, line height, navigation, focus, and
  low-distraction controls. Font/theme/width controls live behind the single
  "Aa" toggle specified in Layout Rework, not four inline controls.
- Missing covers use generated bookplates, restyled with the lantern-badge
  motif (see Visual System above). One missing asset never collapses a route.
- **One consistent cover-source rule, replacing an earlier contradiction**
  (Improvement 12 said an attached cover replaces the bookplate everywhere;
  this section separately said novel detail always uses the generated
  bookplate — those can't both be true, so): catalog, detail, and library
  surfaces all use an approved attached cover when one exists; missing,
  rejected, or failed cover images fall back to the generated bookplate,
  on every surface, with no exception for novel detail specifically.
- Attached covers are **ingested and re-served from controlled storage**,
  not hot-linked or rendered directly from an arbitrary remote URL —
  matches the R2/storage hardening work already done elsewhere in this
  project. A submitted cover URL gets fetched once, validated, and stored;
  the page never makes the visitor's browser request a third-party URL
  directly.
- Chapter and library routes render readable text and actions without cover
  assets.
- Cover fallbacks receive public display metadata only. They never fetch
  storage keys, reveal backend paths, add landmarks, or replace route-level
  text.
- Glossary annotations are keyboard accessible and contain public-safe terms
  only.
- Reader controls remain visible by keyboard and usable at 200% zoom.

Performance budgets (unchanged):

| Surface | Budget |
|---|---:|
| Catalog API p95 | <= 500 ms, <= 250 KiB |
| Novel API p95 | <= 300 ms, <= 100 KiB |
| Chapter API p95 | <= 750 ms, <= 1 MiB |
| Catalog page size | default 24, maximum 100 |
| Glossary annotations | maximum 50 |
| Public route first-load JS | <= 250 KiB |

## Content Safety and Moderation

Missing entirely from earlier drafts — a real gap for a public platform
hosting user-submitted reviews and requests, and translated fiction that can
range from all-ages to mature themes:

- **Mature-content labeling.** Novels carry a content rating; browse/search
  respects a filter for it, defaulting to hiding mature content for
  signed-out/unset-preference sessions.
- **Spoiler formatting in reviews** — a reviewer can mark text as a spoiler;
  it renders blurred/collapsed until tapped, not just a plain-text warning
  sentence someone can accidentally read past.
- **Report actions** exist on reviews and requests, not just on translation
  issues (which already have a report link per the reader spec above).
- **Removed/blocked content** shows a clear "no longer available" state
  rather than a broken link or silent disappearance from lists that
  reference it.
- **Copyright/takedown status** — the legal pages already handle DMCA
  process; this adds that a taken-down novel's own page reflects its status
  honestly instead of 404ing with no explanation.
- **Cover-image provenance.** The "lightweight real-cover-art" idea
  (Improvement 12) needs licensing/attribution tracking, safe center-crop
  behavior (see Design Tokens → Media), and a record of replacement history
  if a cover is swapped — otherwise there's no way to know later whether an
  image was ever cleared to use.
- **Pseudonymous review defaults** — ties directly to Guiding Principle 4:
  reviews display a username, not a real identity, by default, with no
  public profile page to aggregate them (until/unless that becomes opt-in).

## Localization

The product shows both translated and original-language metadata today but
never states its own scope. Making that explicit:

- **English-only is the intentional v1 scope**, not an oversight — this doc
  should say so directly rather than leaving it ambiguous, since WTR-LAB's
  locale-prefixed routes (`/en`, `/pt`, `/tr`, `/id`) could otherwise read as
  a gap rather than a deliberate boundary. Locale-prefixed routes are a
  later-stage decision, not part of this rework.
- **Title hierarchy:** translated title is always primary/larger; original
  (Japanese) title is secondary, smaller, and uses the Noto Serif JP face
  so it actually renders correctly rather than tofu-boxing in a Latin font.
- **Long CJK titles wrap by character**, not by breaking mid-word the way
  Latin text does — this was already called out for the browse card and
  applies everywhere a title can be long.
- **Dates and numbers** format per the visiting browser's locale, not
  hardcoded to one format.
- **Search normalization** (see Search contract above) indexes both title
  forms so a query in either script finds the same novel.
- **Missing-translation labels** use one consistent phrase across chapter
  lists, cards, and search results ("Not yet translated") rather than
  each surface inventing its own wording.

## Admin

- Use tables only when comparison matters; label failures and next actions.
- Destructive actions require explicit labels and confirmation.
- Mask credentials through `frontend/lib/mask-token.ts`; raw values never
  render.
- Admin mutations use `frontend/lib/api.ts` and CSRF handling.
- Operators should see status, evidence, and failure reason without browser
  logs.
- `/admin/maintenance` shows every registered task, cron/timezone, durable
  state, last completion, safe result, and next eligibility. Raw DB error
  text, lock holders, metadata, paths, and hosts never render.
- Admin intentionally does not carry the Japanese-vibe restyle — it's an
  internal operator tool, not part of the reader-facing brand.

## Auth and User Data

- Public UI offers Google OAuth and email/password only; never owner/bootstrap
  wording.
- Guests retain reader access without blocking account prompts.
- Library, history, progress, reviews, and requests derive identity from
  session.
- Disabled/unavailable account features provide a safe recovery path.
- Error copy names the actual reason where it's safe to (resolves F14, see
  Improvement Suggestion 7); it never falls through to starting an OAuth flow
  after a provider-availability check fails for an unexpected reason (F15) —
  surface the same "unavailable" state consistently instead of assuming
  success.

## Accessibility

- Native elements before ARIA; every control has an accessible name.
- Full keyboard operation and visible focus.
- Logical heading and landmark order; status announcements only where useful.
- Color never carries meaning alone; target WCAG AA contrast. Check
  specifically: lantern orange text/icons on the dark `--background`, sakura
  pink on `--card` (both modes), and deep teal chip text on `--secondary` —
  dark, saturated-hue palettes like this one can quietly fail contrast at
  exactly the tones meant to stand out most.
- Respect `prefers-reduced-motion`; no required motion.
- Usable touch targets and no content loss at 320px width.
- No decorative element (the noren divider, the halo ring, a status badge's
  fill) may reduce text contrast or be the sole carrier of state/meaning —
  and per Motifs/Motion above, none of them render as a blur, shadow, or
  animated glow in the first place; this rule is about color-as-meaning,
  not about effects that shouldn't exist anyway.

## Responsive Behavior

- Mobile first; content width follows reading needs, not viewport maximum.
- Primary navigation is inline in the header on `md:`+ and becomes a bottom
  tab bar below that (see Layout Rework — Navigation system), not a
  hamburger drawer at any width. Nothing that's "primary" may be
  collapse-only at every breakpoint (resolves F1).
- Tables may scroll only when a card/list representation would lose
  comparison value.
- Dialogs fit viewport, trap focus, close by keyboard, and restore trigger
  focus, with exactly one close affordance (resolves F10).

## SEO and Legal UX

- Public novel/chapter pages emit canonical URL, Open Graph/Twitter metadata,
  and escaped structured data.
- Site-wide metadata title reads the actual product name (resolves F6).
- `robots.txt` and sitemap remain framework-native.
- 404 and HTTP 451 content is excluded from sitemap and uses safe unavailable
  UI.
- Legal responses never reveal complainant or private review details.

## Review Checklist

- Route group and API client boundaries preserved.
- Every async surface owns honest states and retry behavior.
- Keyboard, focus, zoom, reduced motion, and contrast checked against the
  actual shipped Yokocho Lantern token values, not assumed from the table
  above.
- No raw secret, token, path, storage key, or backend error rendered.
- Public route budgets remain under ceilings.
- This doc's token table matches what's actually in `globals.css` — re-check
  after any palette change, the same way you'd re-check documented security
  properties against actual code.
- The Design status / Implementation status block near the top is current —
  update it as sections actually ship, don't let it silently go stale the
  way the "indigo accents" line did.
- The brand mark passes real 16px raster checks, and all illustration exports
  follow the shared silhouette and palette contract in Brand and Illustration
  Asset System.
- The final default `og:image` is a single composited 1200×630 file; no
  implementation assumes social crawlers will render HTML/CSS text over a
  backdrop image.

### Page-level acceptance criteria

Broad checklist bullets above are necessary but not sufficient — a few
pages need criteria specific enough to actually fail a review against:

```
Homepage
- No more than 5 rails above the footer.
- Each rail visibly overflows (partial next card showing) so horizontal
  content is obvious without hovering.
- Every rail is keyboard-traversable and keyboard-exitable (no focus trap).
- No duplicate generic "browse everything" CTA outside the rails themselves.

Novel detail
- Exactly one Start/Continue primary button rendered, ever.
- Sticky left panel never exceeds viewport height without its own internal
  scroll — it must not push the tab content below the fold.
- Selected tab is reflected in and restorable from the URL.

Chapter reader
- Aa panel fully operable by keyboard, including closing it without a mouse.
- Previous/next chapter reachable without opening the Aa panel at all.
- Reading position restores within a small, defined tolerance (a few
  paragraphs, not "somewhere on the right page").
- Neither the header nav nor the bottom tab bar renders on this route.
```

### Test matrix

- **Viewports:** 320, 375, 768, 1024, 1440, 1920px.
- **Modes:** light, dark, and reader-sepia — screenshot all three for any
  page that touches reader theming.
- **Data states:** empty, loading, error, and maximum-data fixtures (a
  library with hundreds of entries, a chapter list with hundreds of
  chapters) — the board/list toggle and chapter virtualization above exist
  specifically because "looks fine with 8 items" isn't a real test.
- **Automated:** axe accessibility checks and a keyboard-only pass (tab
  order, focus visibility, no traps) on every new/changed surface.
- **Visual regression:** screenshot diffing on the pages this rework
  actually changes, so a future token or component edit can't silently
  drift the shipped palette away from this doc the way the old one did.
