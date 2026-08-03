# Dokushodo - Takedowns

## Design Task
Design the DMCA takedown review table with approve and reject actions.

## Product Context
DMCA requests submitted through the public form, awaiting operator review.

## Global Visual Snapshot
The admin console is a dense, quiet, data-first workspace for operating Dokushodo. It uses a near-black Midnight Slate dark theme and a cool light theme, with vermillion reserved for the primary action of each panel and for attention-required or destructive actions. The shell is a persistent left sidebar with grouped navigation and a compact top bar with theme and view controls; content is a full-bleed workspace of tables, panels, and status summaries. Tables are the default record surface: high row density, monospace identifiers, status badges in semantic colors, and direct row actions such as approve, reject, retry, run, and delete. Typography is sans-serif only; serif never appears, and public-facing motifs such as sakura accents do not appear. Elevation is flat with thin borders, six pixel card corners, and no floating elements. Empty tables show a plain message and a clear next action. Status truthfulness is absolute: schedules, health, credentials, and runtime state render exactly what the system reports, with no fabricated metrics. The settled state is orderly, legible, fast to scan, and free of decorative motion and imagery.

## Page Goal
Review takedown requests with full complainant context.

## Audience and Access
Owner role.

## Primary Action
Approving a takedown.

## Information Hierarchy
- Page heading DMCA takedown requests
- Status filter
- Takedown table
- Row actions and detail dialog

## Desktop Composition
- Rows: novel, complainant, reason, submitted date, status badge
- Row actions: Approve, Reject
- Row click opens the full request detail

## Mobile Composition
- Rows stack with actions below

## Page Anatomy
- Admin shell sidebar
- Top bar
- Filter row
- Takedown table

## Key Components
- Takedown table
- Status badge
- Approve action
- Reject action
- Detail dialog

## Representative Content
- DMCA takedown requests
- Approve
- Reject

## Normal Settled State
A dense table of pending requests with two clear actions per row.

## Alternate Visual States
- Empty queue
- Detail dialog open with full form data

## Interaction Cues
- Approve and Reject update the row immediately
- Reject asks for confirmation

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
- Heading exactly as listed
- Action labels

## Avoid
- Complainant contact data in the table itself
- Public-facing copy

## Stitch Output Requirements
- Render the settled state as a 1440 px wide desktop frame
- Render the narrow tablet layout as a second frame
- Use only the labels and fields listed in this brief
- Do not invent metrics, charts, statuses, or features
