# Dokushodo - Activity Log

## Design Task
Design the per-novel activity log with status filtering and bulk delete.

## Product Context
Records every crawl and translation activity in the durable activity control
plane, grouped by novel. The API exposes pending, running, paused, completed,
failed, and retryable states without exposing lease tokens, prompts, keys, or
provider response secrets.

## Global Visual Snapshot
The admin console is a dense, quiet, data-first workspace for operating Dokushodo. It uses a near-black Midnight Slate dark theme and a cool light theme, with vermillion reserved for the primary action of each panel and for attention-required or destructive actions. The shell is a persistent left sidebar with grouped navigation and a compact top bar with theme and view controls; content is a full-bleed workspace of tables, panels, and status summaries. Tables are the default record surface: high row density, monospace identifiers, status badges in semantic colors, and direct row actions such as approve, reject, retry, run, and delete. Typography is sans-serif only; serif never appears, and public-facing motifs such as sakura accents do not appear. Elevation is flat with thin borders, six pixel card corners, and no floating elements. Empty tables show a plain message and a clear next action. Status truthfulness is absolute: schedules, health, credentials, and runtime state render exactly what the system reports, with no fabricated metrics. The settled state is orderly, legible, fast to scan, and free of decorative motion and imagery.

## Page Goal
Let the operator audit runs and clean up stale records.

## Audience and Access
Owner role.

## Primary Action
Opening a novel group to inspect runs.

## Information Hierarchy
- Page heading Activity Log
- Status filter
- Groups by novel
- Queue age and current worker status
- Bulk selection toolbar with Delete selected

## Desktop Composition
- Filter row above the list
- Groups: novel title header with chapter count, then rows per chapter
- Rows show phase results, status badge, timestamp, retry count, and bounded error summary
- Checkboxes enable the delete toolbar

## Mobile Composition
- Groups collapse to novel headers
- Rows compact

## Page Anatomy
- Admin shell sidebar
- Top bar
- Filter row
- Grouped list
- Bulk toolbar

## Key Components
- Status filter
- Novel group header
- Activity row
- Status badge
- Bulk toolbar

## Representative Content
- Activity Log
- Delete selected
- Status names from the activity status set

## Normal Settled State
A scannable grouped list with quiet status badges and monospace timestamps;
new submissions appear immediately as pending while the dedicated worker owns
provider execution.

## Alternate Visual States
- Empty log with a plain message
- Filter with no matches
- Selection mode with the toolbar visible
- Worker unavailable or queue degraded
- Failed activity with Retry action and bounded retry history

## Interaction Cues
- Bulk delete requires confirmation
- Group headers are sticky on scroll
- Pending activities link to their durable activity detail and do not imply synchronous request progress

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
- Grouping by novel
- Status badge semantics
- Delete confirmation

## Avoid
- Auto-expanded detail rows
- Timestamps in prose format
- Raw error text in rows

## Stitch Output Requirements
- Render the settled state as a 1440 px wide desktop frame
- Render the narrow tablet layout as a second frame
- Use only the labels and fields listed in this brief
- Do not invent metrics, charts, statuses, or features
