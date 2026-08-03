# Dokushodo - Audit Log

## Design Task
Design the audit log with filters and an event detail dialog.

## Product Context
The security record of administrative events.

## Global Visual Snapshot
The admin console is a dense, quiet, data-first workspace for operating Dokushodo. It uses a near-black Midnight Slate dark theme and a cool light theme, with vermillion reserved for the primary action of each panel and for attention-required or destructive actions. The shell is a persistent left sidebar with grouped navigation and a compact top bar with theme and view controls; content is a full-bleed workspace of tables, panels, and status summaries. Tables are the default record surface: high row density, monospace identifiers, status badges in semantic colors, and direct row actions such as approve, reject, retry, run, and delete. Typography is sans-serif only; serif never appears, and public-facing motifs such as sakura accents do not appear. Elevation is flat with thin borders, six pixel card corners, and no floating elements. Empty tables show a plain message and a clear next action. Status truthfulness is absolute: schedules, health, credentials, and runtime state render exactly what the system reports, with no fabricated metrics. The settled state is orderly, legible, fast to scan, and free of decorative motion and imagery.

## Page Goal
Let the owner find any administrative action quickly.

## Audience and Access
Owner role.

## Primary Action
Filtering and opening an event.

## Information Hierarchy
- Page heading Audit log
- Filter row: action type, user, date range
- Events table
- Event detail dialog

## Desktop Composition
- Filters above the table
- Table columns: timestamp, user, action, target
- Row click opens the detail dialog with full event fields

## Mobile Composition
- Filters collapse into a single row
- Table scrolls horizontally

## Page Anatomy
- Admin shell sidebar
- Top bar
- Filter row
- Events table
- Detail dialog

## Key Components
- Filters
- Events table
- Detail dialog

## Representative Content
- Audit log
- Action type filter
- User filter
- Date range filter

## Normal Settled State
A dense filterable table; every row opens a complete but redacted record.

## Alternate Visual States
- Empty filter result
- Dialog open
- Loading skeleton

## Interaction Cues
- Filters apply instantly
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
- Filter names
- No credentials or secret values in any field

## Avoid
- Secrets in detail content
- Inline editable records

## Stitch Output Requirements
- Render the settled state as a 1440 px wide desktop frame
- Render the narrow tablet layout as a second frame
- Use only the labels and fields listed in this brief
- Do not invent metrics, charts, statuses, or features
