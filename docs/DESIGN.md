# Frontend Design

Canonical visual, interaction, accessibility, and frontend ownership contract.

## Direction

Reading comes first. UI should feel literary, calm, trustworthy, and functional:
warm neutral surfaces, restrained indigo accents, strong typography, low visual
noise, and honest status feedback. Do not copy another product's branding.

## Ownership

- `frontend/app/(admin)/admin/*`: owner interface.
- `frontend/app/(public)/*`: guest and public-user interface.
- Shared components: `frontend/components/`; route-local components stay local.
- TanStack Query owns server state; Zustand owns client-only state.
- Tailwind plus `cn()` owns styling; no CSS modules or styled-components.
- Hooks own business/data flow; components own presentation.

## Visual System

- Readable sans-serif UI; literary serif permitted for chapter text.
- Near-black text on warm white/stone surfaces, subtle borders, restrained shadows.
- Indigo for primary action/selection, amber for warnings, red for destructive action.
- Use a 4/8px rhythm, moderate radii, and compact information hierarchy.
- Avoid gradients, glass effects, oversized hero text, excessive cards, and
  motion without information value.

## Page Structure and States

Public shell owns header, skip link, and focusable `#main-content`. Each page owns
exactly one `main`. Admin shell owns primary navigation and page frame.

Every data surface defines loading, empty, recoverable error, unavailable, and
settled states. Add not-found/legal states where relevant and preserve useful
stale data during background-refetch failure. Never render raw API error objects.

## Public Reader

- Catalog cards show bookplate/cover, translated title, author, localized
  taxonomy, status, and useful progress without crowding.
- Novel detail prioritizes title, synopsis, status, chapters, and reading action.
- Chapter pages prioritize text width, line height, navigation, focus, and
  low-distraction controls.
- Missing covers use generated bookplates. One missing asset never collapses a route.
- Catalog remote-cover failures fall back locally to the same generated
  bookplate contract. Novel detail uses generated bookplates directly. Chapter
  and library routes render readable text and actions without cover assets.
- Cover fallbacks receive public display metadata only. They never fetch storage
  keys, reveal backend paths, add landmarks, or replace route-level text.
- Glossary annotations are keyboard accessible and contain public-safe terms only.
- Reader controls remain visible by keyboard and usable at 200% zoom.

Performance budgets:

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
- Mask credentials through `frontend/lib/mask-token.ts`; raw values never render.
- Admin mutations use `frontend/lib/api.ts` and CSRF handling.
- Operators should see status, evidence, and failure reason without browser logs.
- `/admin/maintenance` shows every registered task, cron/timezone, durable state,
  last completion, safe result, and next eligibility. Raw DB error text, lock
  holders, metadata, paths, and hosts never render.

## Auth and User Data

- Public UI offers Google OAuth and email/password only; never owner/bootstrap wording.
- Guests retain reader access without blocking account prompts.
- Library, history, progress, reviews, and requests derive identity from session.
- Disabled/unavailable account features provide a safe recovery path.

## Accessibility

- Native elements before ARIA; every control has an accessible name.
- Full keyboard operation and visible focus.
- Logical heading and landmark order; status announcements only where useful.
- Color never carries meaning alone; target WCAG AA contrast.
- Respect `prefers-reduced-motion`; no required motion.
- Usable touch targets and no content loss at 320px width.

## Responsive Behavior

- Mobile first; content width follows reading needs, not viewport maximum.
- Navigation may collapse but primary actions remain discoverable.
- Tables may scroll only when a card/list representation would lose comparison value.
- Dialogs fit viewport, trap focus, close by keyboard, and restore trigger focus.

## SEO and Legal UX

- Public novel/chapter pages emit canonical URL, Open Graph/Twitter metadata,
  and escaped structured data.
- `robots.txt` and sitemap remain framework-native.
- 404 and HTTP 451 content is excluded from sitemap and uses safe unavailable UI.
- Legal responses never reveal complainant or private review details.

## Review Checklist

- Route group and API client boundaries preserved.
- Every async surface owns honest states and retry behavior.
- Keyboard, focus, zoom, reduced motion, and contrast checked.
- No raw secret, token, path, storage key, or backend error rendered.
- Public route budgets remain under ceilings.
