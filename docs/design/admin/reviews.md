# Dokushodo - Reviews

## Design Task
Design the review moderation table with publish and reject actions.

## Product Context
Reader reviews awaiting moderation before publication.

## Global Visual Snapshot
The admin console is a dense, quiet, data-first workspace for operating Dokushodo. It uses a near-black Midnight Slate dark theme and a cool light theme, with vermillion reserved for the primary action of each panel and for attention-required or destructive actions. The shell is a persistent left sidebar with grouped navigation and a compact top bar with theme and view controls; content is a full-bleed workspace of tables, panels, and status summaries. Tables are the default record surface: high row density, monospace identifiers, status badges in semantic colors, and direct row actions such as approve, reject, retry, run, and delete. Typography is sans-serif only; serif never appears, and public-facing motifs such as sakura accents do not appear. Elevation is flat with thin borders, six pixel card corners, and no floating elements. Empty tables show a plain message and a clear next action. Status truthfulness is absolute: schedules, health, credentials, and runtime state render exactly what the system reports, with no fabricated metrics. The settled state is orderly, legible, fast to scan, and free of decorative motion and imagery.

## Page Goal
Moderate reviews quickly with full context in the row.

## Audience and Access
Owner role.

## Primary Action
Publishing a review.

## Information Hierarchy
- Page heading Reviews
- Status filter
- Moderation table
- Row actions

## Desktop Composition
- Rows: novel, reviewer, star rating, review text excerpt, date, status badge
- Row actions: Publish, Reject
- Row click opens the full review

## Mobile Composition
- Rows stack with text first, actions below

## Page Anatomy
- Admin shell sidebar
- Top bar
- Filter row
- Moderation table

## Key Components
- Moderation table
- Star rating
- Status badge
- Publish action
- Reject action

## Representative Content
- Reviews
- Publish
- Reject

## Normal Settled State
A quiet moderation table with accent-filled stars and two clear actions per pending row.

## Alternate Visual States
- Empty queue
- Full review dialog open

## Interaction Cues
- Publish and Reject update the row immediately
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
- Accent color for stars
- Action labels

## Avoid
- Editing review text in the table
- Public-facing copy

## Stitch Output Requirements
- Render the settled state as a 1440 px wide desktop frame
- Render the narrow tablet layout as a second frame
- Use only the labels and fields listed in this brief
- Do not invent metrics, charts, statuses, or features
