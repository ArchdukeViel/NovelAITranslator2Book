# Dokushodo - Add Novel

## Design Task
Design the novel import surface with add form, import now, and source health.

## Product Context
The crawler entry point for adding and importing novels from supported sources.

## Global Visual Snapshot
The admin console is a dense, quiet, data-first workspace for operating Dokushodo. It uses a near-black Midnight Slate dark theme and a cool light theme, with vermillion reserved for the primary action of each panel and for attention-required or destructive actions. The shell is a persistent left sidebar with grouped navigation and a compact top bar with theme and view controls; content is a full-bleed workspace of tables, panels, and status summaries. Tables are the default record surface: high row density, monospace identifiers, status badges in semantic colors, and direct row actions such as approve, reject, retry, run, and delete. Typography is sans-serif only; serif never appears, and public-facing motifs such as sakura accents do not appear. Elevation is flat with thin borders, six pixel card corners, and no floating elements. Empty tables show a plain message and a clear next action. Status truthfulness is absolute: schedules, health, credentials, and runtime state render exactly what the system reports, with no fabricated metrics. The settled state is orderly, legible, fast to scan, and free of decorative motion and imagery.

## Page Goal
Add a novel, import it, and see source health in one place.

## Audience and Access
Owner role.

## Primary Action
Adding a novel from a source URL.

## Information Hierarchy
- Page heading Add Novel
- Add Novel form card
- Import Now panel
- Source Health panel
- Recent activity list

## Desktop Composition
- Form card: source provider select with Kakuyomu, Syosetu, Syosetu18, novel URL field, submit
- Import Now panel with novel select and import trigger
- Source Health table with source, reachability, last check, and status badge
- Recent activity list below

## Mobile Composition
- Cards stack full width

## Page Anatomy
- Admin shell sidebar
- Top bar
- Add form card
- Import Now panel
- Source Health panel
- Recent activity

## Key Components
- Provider select
- URL field
- Add Novel button
- Import trigger
- Source Health table

## Representative Content
- Add Novel
- Kakuyomu, Syosetu, Syosetu18
- Import Now
- Source Health

## Normal Settled State
Three quiet cards and a short list; one primary action per card.

## Alternate Visual States
- Import running state with progress
- Source unreachable state in health table
- Validation error on URL

## Interaction Cues
- Add and Import triggers give inline result feedback
- Health badges use semantic colors

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
- Provider names exactly as listed
- Card titles
- Health badge semantics

## Avoid
- Public-facing copy
- Logs dumped on screen
- Auto-starting imports

## Stitch Output Requirements
- Render the settled state as a 1440 px wide desktop frame
- Render the narrow tablet layout as a second frame
- Use only the labels and fields listed in this brief
- Do not invent metrics, charts, statuses, or features
