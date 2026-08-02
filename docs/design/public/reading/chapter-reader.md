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

## Accessibility
- Full keyboard shortcuts: `←`/`→` for prev/next chapter, `.` opens "Aa" settings panel.
- Contrast compliant across all three reader themes (Light, Dark, Sepia).
- `content-visibility: auto` used for section performance without breaking find-in-page or screen readers.

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
