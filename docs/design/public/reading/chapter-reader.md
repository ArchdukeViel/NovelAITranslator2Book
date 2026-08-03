# Reading — Chapter Reader Page

## Contract Metadata

| Field | Value |
|---|---|
| Surface | public |
| Domain | reading |
| Routes | `/novels/[slug]/chapter/[chapterId]` |
| Design status | approved |
| Implementation status | implemented |
| Active work | none |
| Implementation | `frontend/app/(public)/novels/[slug]/chapter/[chapterId]/page.tsx`, `frontend/components/public/reader-controls.tsx` |

## Purpose
Distraction-free, long-form Japanese-to-English web novel chapter reading surface.

## User Goal
Read chapter text comfortably with customizable typography, dark/light/sepia themes, and seamless chapter navigation.

## Audience and Permissions
- **Guests & Authenticated Users:** Full reading access.
- **Authenticated Users:** Automatic reading progress tracking synced across sessions.

## Primary Action
Read chapter content and navigate to Next Chapter.

## Information Hierarchy
1. Minimal Header (Back caret to novel detail + chapter title)
2. Reading Progress Bar (Thin 2-3px `--primary` bar fixed to top viewport edge)
3. Main Text Column (Chapter title header, Japanese/English paragraph blocks, inline glossary annotations)
4. Footer Navigation (Previous Chapter button, Back to Novel link, Next Chapter CTA)
5. Floating "Aa" Controls Button (Bottom-right thumb-reachable trigger opening settings popover)

## Page Anatomy
- **Suppressed Chrome:** Global navigation header, bottom tab bar, and footer hidden.
- **Reader Text Column:** Max width 680px (default), customizable via settings.
- **"Aa" Settings Popover:**
  - Font Size Stepper: 16px, 18px (default), 20px, 22px.
  - Text Column Width: Narrow (560px), Standard (680px), Wide (800px).
  - Reader Theme: Light, Dark, Sepia.
  - Reset Action: Reverts settings to defaults.

## Desktop Layout
Centered text column (680px max width). Top progress bar spans full viewport width.

## Mobile Layout
Full width text column with 16px side padding. Floating "Aa" button positioned above safe area insets.

## Interaction Flow
- Scrolling page updates top progress bar percentage.
- Tapping "Aa" button opens typography settings sheet. Adjusting font size recalculates progress position.
- Tapping "Next Chapter" CTA loads subsequent chapter.
- Tapping inline glossary terms toggles term definition popover.

## Authentication or Authorization Behavior
- Authenticated readers automatically sync current chapter scroll position via `useUpdateProgress`.

## States

### Initial
Skeleton text block loaders.

### Loading
Pulse loading placeholder matching text column.

### Empty
If chapter content is empty, displays "Chapter text unavailable."

### Pending
Not applicable.

### Settled
Chapter text fully rendered with interactive glossary terms.

### Recoverable Error
"Could not load chapter content. Check network connection." with Retry CTA.

### Unavailable
Chapter untranslated or removed. Displays explanation banner with link back to chapter list.

### Unauthorized or Forbidden
Not applicable.

### Success
Not applicable.

## Components
- `ReaderControls`
- `ReaderTheme`
- `GlossaryTooltip`

## Content and Copy
- End of chapter CTA: "Next Chapter →"
- Back link: "← Back to novel"

## Reader Theme Token System

The reader uses an **independent token system** defined in `frontend/app/(public)/reader.css`, controlled by `data-reader-theme` attribute on the reader container. This system **MUST NOT** toggle `html.dark` or modify the global theme.

### Theme Tokens

| Theme | Background | Foreground | Secondary | Border | Nav Background |
|---|---|---|---|---|---|
| Light | `#ffffff` | `#1a1a1a` | `#6b7280` | `rgba(0,0,0,0.1)` | `rgba(255,255,255,0.95)` |
| Dark | `#0e0c12` | `#e4ddd0` | `#8a8298` | `rgba(228,221,208,0.08)` | `rgba(14,12,18,0.95)` |
| Sepia | `#f8f1e4` | `#3c2a1a` | `#816353` | `rgba(60,42,26,0.12)` | `rgba(248,241,228,0.95)` |

### Token Architecture

- `background` and `color` set directly on `[data-reader-theme]` selector (raw hex)
- `--reader-secondary`: muted text for back links, navigation disabled states, metadata
- `--reader-border`: theme-appropriate border color with alpha
- `--reader-nav-background`: semi-transparent nav background for blur-through effect
- Reader container overrides global Tailwind classes: `.text-muted-foreground`, `.border-border`, `.bg-background`

### Contrast Requirements

All reader themes MUST maintain WCAG AA (4.5:1) text contrast:

| Pair | Light | Dark | Sepia |
|---|---|---|---|
| Foreground on background | ✓ Required | ✓ Required | ✓ Required |
| Secondary on background | ✓ Required | ✓ Required | ✓ Required |

Automated coverage: `reader-contrast.test.ts` (if present).

### Normative Rules

- Reader theme MUST be selectable via Aa panel (light, dark, sepia)
- Reader theme MUST persist across page loads (localStorage or account settings)
- Reader theme changes MUST NOT leak to global surfaces (header, tab bar, other pages)
- Reader theme transition: `background-color 0.2s, color 0.2s`
- Reduced motion: transitions become instant

## Accessibility
- Full keyboard shortcuts: `←`/`→` for prev/next chapter, `.` opens "Aa" settings panel
- Shortcuts MUST NOT fire when focus is inside editable controls (input, textarea, contenteditable)
- Contrast compliant across all three reader themes (Light, Dark, Sepia)
- `content-visibility: auto` used for section performance without breaking find-in-page or screen readers
- Progress bar: `role="progressbar"` with `aria-valuemin`, `aria-valuemax`, `aria-valuenow`
- Aa button: `aria-label` present, sheet has `role="dialog"` and `aria-modal="true"`
- Font size and width changes MUST recalculate scroll position to preserve reading location

## Responsive Behavior
- Reader column width adjusts safely between 320px mobile viewports and wide desktop displays.

## Data Requirements
- Translated chapter paragraphs, chapter metadata (slug, title, number, prev/next chapter IDs), glossary terms.

## Privacy, Safety, and Security
- Public reader; no credentials or private data rendered.

## Acceptance Criteria
- Global header and mobile tab bar suppressed on chapter routes.
- "Aa" panel operable by keyboard and closable without a mouse.
- Reading position restored accurately on returning to novel.

## Implementation Mapping
- `frontend/app/(public)/novels/[slug]/chapter/[chapterId]/page.tsx`
- `frontend/components/public/reader-controls.tsx`
