# Admin Design System

Visual direction, layout, and UI specifications for operator surfaces (`frontend/app/(admin)/admin/*`).

## Scope and Boundaries

This document defines design rules for administrative surfaces. It is subordinate to `docs/ARCHITECTURE.md` and `docs/DESIGN.md`.

- **Scope**: All routes under `/admin/*`
- **Inheritance**: Inherits global CSS tokens (`--background`, `--foreground`, `--card`, `--primary`, `--border`, `--success`, `--warning`, `--destructive`, `--info`) from `frontend/app/globals.css`
- **Overrides**: Overrides public visual identity — **MUST NOT** display Yokocho Lantern decorations, lantern badges, sakura pink accents (`--accent`), or Noren curtain dividers
- **Public vs Admin boundary**: Admin routes are served by the admin process (port 8000), require cookie authentication + CSRF protection, and require `role="owner"` for detailed diagnostics/actions

## Visual Direction

- **Operator-first & High-density**: Designed for rapid scanning, maximum data density, and administrative decision-making
- **Neutral dark/light contrast**: Focuses on legibility, status visibility, and tabular data over atmosphere
- **No decorative flourishes**: Clean rectangular frames, standard borders, strict information hierarchy

## Typography

- **UI & Navigation**: DM Sans (`font-sans`), weight 400/500/600
- **Identifiers, Timestamps, Hashes, Logs**: DM Mono (`font-mono`), weight 400/500
- **Tables**: DM Sans for text columns; DM Mono for IDs, timestamps, status codes, and counts
- **No serif font**: Noto Serif JP is NOT used on admin surfaces

## Compact Density Scale

Admin surfaces use a more compact density scale than public surfaces:

| Element | Admin Size | Utility | Public Contrast |
|---|---|---|---|
| Page padding | 20px | `px-5 py-4` | 16-24px (`px-4 md:px-6`) |
| Table cells | Compact | `py-2 px-3` | Comfortable (`py-3 px-4`) |
| Input height | 32px (sm) / 36px | `h-8` or `h-9` | 36px (`h-9`) |
| Button height | 32px (sm) / 36px | `h-8` or `h-9` | 36px (`h-9`) |
| Badge padding | Compact | `px-2 py-0.5 text-xs` | Same |
| Card/Panel gap | 16px | `gap-4` | 24px (`gap-6`) |

## Data Tables

- **Header**: Sticky top (`sticky top-0 z-[1]`), muted background (`bg-muted/55`), uppercase 12px text (`text-xs uppercase text-muted-foreground`), bottom border (`border-b`)
- **Rows**: Hover highlight (`hover:bg-muted/50`), thin border divider between rows
- **Checkboxes**: `.table-checkbox` class (0.95rem grid-centered checkmark) for bulk selection
- **Scroll**: Container uses `overflow-x-auto` for horizontal scrolling on narrow viewports
- **Pagination**: Compact Previous/Next controls + page indicator at bottom right

## Semantic Operational Roles

Canonical mapping for admin operational status indicators:

| Status Role | Token | Badge Tone | Examples |
|---|---|---|---|
| **Success** | `--success` | `green` | Job completed, backup fresh, health 200 OK, review published |
| **Warning** | `--warning` | `amber` | Backup stale, health degraded, job partial, review pending |
| **Danger / Destructive** | `--destructive` | `red` | Job failed, review rejected, user disabled, takedown enforced |
| **Info** | `--info` | `blue` | Crawler active, translation running, task scheduled |
| **Neutral** | `--muted` | `neutral` | Task idle, feature disabled, log entry |
| **Violet** (Override) | Violet tone | `violet` | Admin review status override |

Admin components MAY use direct Tailwind status classes (`text-green-600`, `bg-red-500/15`, etc.) where legacy operational components require them, but new work SHOULD prefer semantic token classes (`text-success-text`, `bg-destructive/20`, etc.).

## Security, PII, and Redaction Rules

- **API Credentials**: MUST be masked using `frontend/lib/mask-token.ts` before rendering (e.g., `sk-proj-...` → `sk-p...3a4f`)
- **Secrets & Connection Strings**: MUST NOT be exposed in raw form in any admin page or log viewer
- **Stack Traces**: Internal paths, DB error details, and stack traces MUST NOT be exposed to public users; admin surfaces MAY display sanitized logs for owners
- **Destructive Confirmation**: Takedowns, user disables, DB purges, and job cancellations MUST require explicit modal confirmation specifying the affected target

## Interactive Controls & Bulk Actions

- **Bulk Selection**: Header checkbox selects/deselects all visible rows
- **Selected Row Bar**: Appears above table when `selected.length > 0`, showing count and available bulk actions (e.g., "Publish selected (3)", "Reject selected (3)")
- **Action Buttons**: Inline icon buttons (`variant="ghost" size="sm"`) for per-row actions; primary CTA at top right of page header
- **Filter Bar**: Inline search input + select dropdowns above data table

## Responsive Adaptation

- Desktop (≥1024px): Fixed left sidebar (`w-64 z-20`) + main content area
- Mobile (<1024px): Sidebar collapses; header displays toggle trigger for sidebar drawer
- Tables scroll horizontally on viewports narrower than table min-width
