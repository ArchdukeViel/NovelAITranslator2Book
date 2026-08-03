# Dokushodo - Library

## Design Task
Design the admin novel library table with translation counts and actions.

## Product Context
The full catalog from the operator side, distinct from the public browse surface.

## Global Visual Snapshot
The admin console is a dense, quiet, data-first workspace for operating Dokushodo. It uses a near-black Midnight Slate dark theme and a cool light theme, with vermillion reserved for the primary action of each panel and for attention-required or destructive actions. The shell is a persistent left sidebar with grouped navigation and a compact top bar with theme and view controls; content is a full-bleed workspace of tables, panels, and status summaries. Tables are the default record surface: high row density, monospace identifiers, status badges in semantic colors, and direct row actions such as approve, reject, retry, run, and delete. Typography is sans-serif only; serif never appears, and public-facing motifs such as sakura accents do not appear. Elevation is flat with thin borders, six pixel card corners, and no floating elements. Empty tables show a plain message and a clear next action. Status truthfulness is absolute: schedules, health, credentials, and runtime state render exactly what the system reports, with no fabricated metrics. The settled state is orderly, legible, fast to scan, and free of decorative motion and imagery.

## Page Goal
Scan the whole catalog and act on any novel.

## Audience and Access
Owner role.

## Primary Action
Opening a novel row action such as Translate.

## Information Hierarchy
- Page heading Library
- Language filter
- Novels table
- Row actions

## Desktop Composition
- Language filter with the supported translation languages
- Sortable columns: title, author, language, raw, translated, failed, pending counts, updated
- Row actions: Translate, Recrawl, Delete
- Pagination

## Mobile Composition
- Table scrolls horizontally
- Actions in a compact menu

## Page Anatomy
- Admin shell sidebar
- Top bar
- Filter row
- Novels table
- Pagination

## Key Components
- Language filter
- Novels table
- Count cells
- Row actions
- Pagination

## Representative Content
- Library
- Translate
- Recrawl
- Delete

## Normal Settled State
A dense sortable table with monospace counts and quiet row actions.

## Alternate Visual States
- Empty library
- Delete confirmation dialog
- Filter with no matches

## Interaction Cues
- Sort headers show active state
- Delete requires confirmation
- Row hover highlights

## Accessibility and Legibility
- WCAG AA contrast in both themes
- Visible focus ring on every interactive control
- Full keyboard navigation of tables, filters, and dialogs
- Semantic table headers with sortable column state
- Reduced motion honored
- Dangerous actions require confirmation and are not reachable by accident

## Assets
- brand-mark.png in the sidebar header

## Preserve Exactly
- Column set exactly as listed
- Count cells never invented
- Action labels

## Avoid
- Cover imagery in the table
- Public browse styling in the admin table

## Stitch Output Requirements
- Render the settled state as a 1440 px wide desktop frame
- Render the narrow tablet layout as a second frame
- Use only the labels and fields listed in this brief
- Do not invent metrics, charts, statuses, or features
