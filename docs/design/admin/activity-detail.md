# Dokushodo - Activity Detail

## Design Task
Design the per-run activity detail with phase tabs and item actions.

## Product Context
Reached from the activity log for one novel; shows the durable activity state,
lease-safe phase detail, and per-chapter progress when available. Provider
credentials, prompts, authorization headers, and raw provider responses never
appear in the detail surface.

## Global Visual Snapshot
The admin console is a dense, quiet, data-first workspace for operating Dokushodo. It uses a near-black Midnight Slate dark theme and a cool light theme, with vermillion reserved for the primary action of each panel and for attention-required or destructive actions. The shell is a persistent left sidebar with grouped navigation and a compact top bar with theme and view controls; content is a full-bleed workspace of tables, panels, and status summaries. Tables are the default record surface: high row density, monospace identifiers, status badges in semantic colors, and direct row actions such as approve, reject, retry, run, and delete. Typography is sans-serif only; serif never appears, and public-facing motifs such as sakura accents do not appear. Elevation is flat with thin borders, six pixel card corners, and no floating elements. Empty tables show a plain message and a clear next action. Status truthfulness is absolute: schedules, health, credentials, and runtime state render exactly what the system reports, with no fabricated metrics. The settled state is orderly, legible, fast to scan, and free of decorative motion and imagery.

## Page Goal
Let the operator see exactly what ran, what failed, and retry.

## Audience and Access
Owner role.

## Primary Action
Retrying a failed item.

## Information Hierarchy
- Breadcrumb back to Activity Log
- Novel title heading
- Phase tabs: Crawl, Translate, Review
- Item table with per-row status
- Run and retry actions

## Desktop Composition
- Phase tabs above the item table
- Table rows with item title, status badge, duration, and timestamp
- Activity lifecycle with queue time, execution time, retry count, and bounded retry history
- Per-row retry action for failed items
- Row click opens a detail dialog with timestamps and messages, redacted of secrets

## Mobile Composition
- Tabs scroll horizontally
- Rows compact with actions on a second line

## Page Anatomy
- Admin shell sidebar
- Top bar
- Breadcrumb
- Heading
- Phase tabs
- Item table

## Key Components
- Breadcrumb
- Phase tabs
- Item table
- Status badge
- Retry action
- Detail dialog

## Representative Content
- Activity Log breadcrumb
- Crawl, Translate, Review
- Retry

## Normal Settled State
A focused phase table under quiet tabs; failed rows carry a clear retry affordance.

## Alternate Visual States
- Empty phase
- All succeeded state
- Detail dialog open
- Lease recovered and requeued
- Failed activity with Retry action

## Interaction Cues
- Retry runs the item again and updates the row
- Tabs preserve the novel scope

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
- Phase names exactly as listed
- Breadcrumb path
- Redacted detail content

## Avoid
- Secrets or credentials in any dialog
- Auto-running retries
- Stack traces on screen

## Stitch Output Requirements
- Render the settled state as a 1440 px wide desktop frame
- Render the narrow tablet layout as a second frame
- Use only the labels and fields listed in this brief
- Do not invent metrics, charts, statuses, or features
