# Frontend Design

Canonical visual, interaction, accessibility, and frontend ownership contract for
Dokushodo (読書道) — a translated Japanese web novel reading site.

This revision preserves engineering sections covering ownership, states,
accessibility, and performance. `Direction` and `Visual System` changed because
the prior text had drifted from current implementation (the doc said "indigo
accents"; the CSS has none) and did not reflect what this product is.

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

**Selected design direction: Yokocho Lantern.** Four variations were drafted and
compared (Bunkobon Pop, Retro Shotengai, Origami Zine, Yokocho Lantern) —
Yokocho Lantern is the target for future implementation. It's kept below in
full; the other three are not part of the active contract and should not be
mixed in piecemeal.

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
| `--ring` | matches `--accent` | matches `--accent` |

### Usage rules

- **Sakura pink (`--accent`) is reserved for favorite/heart, rating, and
  save-to-library active states only — never for primary buttons or links.**
  This is the one rule most likely to get eroded over time; if pink starts
  showing up as a generic highlight color, that's drift, not a variant.
- Lantern orange (`--primary`) carries all primary CTAs: "Start Reading,"
  "Sign in," "Browse the catalog."
- Deep teal (`--secondary`) stays structural/quiet — chip backgrounds, subtle
  section dividers — never a call-to-action color.
- Typography: DM Sans stays for site chrome, no swap needed. Noto Serif JP
  stays for chapter text in both modes.

### Motifs

- Soft rounded "paper lantern" shape (a rounded rect with slightly pinched
  top/bottom, not a full lantern illustration) for status badges — ongoing /
  completed / hiatus read as lit lanterns of different colors rather than flat
  pills.
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
- No new font files needed; no motif requires new icon assets beyond restyling
  the existing generated-bookplate and status-badge components.

---

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
2. **Persistent nav + header theme toggle (resolves F1, F2).** Header shows
   inline links at `md:` and above; drawer becomes mobile-only. Toggle moves
   into the header, defaulting to its "dark" state to match Yokocho Lantern.
3. **Trim the homepage to one browse CTA (resolves F3).** Keep either the
   closing CTA or the Reading Paths box, not both — four entry points can
   become two without losing discoverability.
4. **Add a header "Sign up" link next to "Sign in" (resolves F4).**
5. **Remove the duplicate Start Reading CTA (resolves F5).**
   `ContinueReading` should render nothing (or a quieter line, not a second
   button) when the page already has its own hero CTA and there's no saved
   progress; keep its own CTA only where no hero button exists (library,
   history views).
6. **Prefill the review form (resolves F13; deferred feature).** Add a
   `useReview(slug)` query — this needs a matching GET endpoint on the backend,
   since none exists today — so a returning reviewer sees saved stars/text and
   "Update Review" immediately instead of a blank form.
7. **Safe validation errors and generic identity errors (resolves F14).**
   Field-format and password-policy errors may be specific. Duplicate-account,
   login, and recovery responses stay generic so callers cannot enumerate
   registered identities. Rate-limit and unavailable states may carry safe,
   actionable retry guidance.
8. **Consistent "unavailable" state instead of silent OAuth fallback (resolves
   F15).**
9. **One close affordance per modal (resolves F10).** Drop the bottom "Close"
   button, keep the X.
10. **Drop the tooltip on genre/tag chips, keep the inline label (resolves
    F11).** Remove the redundant `title=` attribute.
11. **Collapse reader controls behind a single "Aa" toggle (resolves F12,
    F19).** One button opens a small panel styled with the lantern-badge
    motif, instead of four separate controls sharing the header row.
12. **Deferred real-cover-art proposal (addresses F16/F17).** This requires a
    separately approved storage/API/admin specification preserving private
    storage and public-safe delivery boundaries. A future implementation could
    let an admin attach one hero image per novel (even a stock or generated
    illustration) that swaps in for
    the bookplate on that novel's card and detail page; everything else keeps
    the (now Yokocho-Lantern-styled) generated bookplate as the graceful
    fallback the existing contract already requires. Gets real art onto
    featured/flagship titles without reopening the cover-safety question.
13. **Spread the Japanese-vibe motifs beyond one hero element (resolves F18).**
    Apply the lantern-badge, noren divider, and halo-ring motifs (see Visual
    System above) across browse, detail, and reader — not just the homepage
    hero — so the identity is visible at every breakpoint, not once on
    desktop.
14. **Harden the card/save-button nesting pattern (resolves F20).** Extract
    the "interactive control inside a card-link" pattern into one small
    shared wrapper so future additions don't have to hand-roll
    `stopPropagation` again.

## Navigation & IA rework — status

Items 2–5 and 9–10 above are the navigation/IA-specific subset of the
improvement list; nothing further to add here beyond what's already
itemized above.

Improvement suggestions describe target work, not shipped behavior. Backend API,
storage, auth, or moderation changes require bounded implementation work and the
architecture/specification gates named in `ARCHITECTURE.md` and `WORK.md`.

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
- Novel detail prioritizes title, synopsis, status, chapters, and reading action.
- Chapter pages prioritize text width, line height, navigation, focus, and
  low-distraction controls. Consider collapsing font/theme/width controls
  behind a single "Aa" toggle rather than showing all four inline, especially
  on narrow viewports.
- Missing covers use generated bookplates, restyled with the lantern-badge
  motif (see Visual System above). One missing asset never collapses a route.
- Catalog remote-cover failures fall back locally to the same generated
  bookplate contract. Novel detail uses generated bookplates directly. Chapter
  and library routes render readable text and actions without cover assets.
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
- Error copy names the actual reason where it's safe to (see IA rework #6
  above); it never falls through to starting an OAuth flow after a
  provider-availability check fails for an unexpected reason — surface the
  same "unavailable" state consistently instead of assuming success.

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
- No decorative element (halftone texture, washi-tape strip, lantern glow)
  may reduce text contrast or be the sole carrier of state/meaning.

## Responsive Behavior

- Mobile first; content width follows reading needs, not viewport maximum.
- Primary navigation is inline on `md:`+ and collapses to a drawer only below
  that — see IA rework #1. Nothing that's "primary" may be collapse-only at
  every breakpoint.
- Tables may scroll only when a card/list representation would lose
  comparison value.
- Dialogs fit viewport, trap focus, close by keyboard, and restore trigger
  focus, with exactly one close affordance (see IA rework #7).

## SEO and Legal UX

- Public novel/chapter pages emit canonical URL, Open Graph/Twitter metadata,
  and escaped structured data.
- Site-wide metadata title reads the actual product name (see IA rework #5).
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
