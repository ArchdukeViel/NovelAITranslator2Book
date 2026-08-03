# Dokushodo - Analytics

## Design Task
Design the analytics surface with time windows and event groups.

## Product Context
Shows event counts by window: Views, Searches, and Feature interactions.

## Global Visual Snapshot
The admin console is a dense, quiet, data-first workspace for operating Dokushodo. It uses a near-black Midnight Slate dark theme and a cool light theme, with vermillion reserved for the primary action of each panel and for attention-required or destructive actions. The shell is a persistent left sidebar with grouped navigation and a compact top bar with theme and view controls; content is a full-bleed workspace of tables, panels, and status summaries. Tables are the default record surface: high row density, monospace identifiers, status badges in semantic colors, and direct row actions such as approve, reject, retry, run, and delete. Typography is sans-serif only; serif never appears, and public-facing motifs such as sakura accents do not appear. Elevation is flat with thin borders, six pixel card corners, and no floating elements. Empty tables show a plain message and a clear next action. Status truthfulness is absolute: schedules, health, credentials, and runtime state render exactly what the system reports, with no fabricated metrics. The settled state is orderly, legible, fast to scan, and free of decorative motion and imagery.

## Page Goal
Let the operator spot usage trends in the selected window.

## Audience and Access
Owner role.

## Primary Action
Switching the time window.

## Information Hierarchy
- Page heading Analytics
- Window selector: 5m, 15m, 1h, 24h, 7d, 30d
- Groups: Views, Searches, Feature interactions
- Event tables per group

## Desktop Composition
- Window selector as a segmented control
- Three group panels, each with an event table of name, count, and trend
- Tables sorted by count descending

## Mobile Composition
- Groups stack
- Window selector scrolls horizontally

## Page Anatomy
- Admin shell sidebar
- Top bar
- Window selector
- Group panels

## Key Components
- Window selector
- Group panel
- Event table

## Representative Content
- Analytics
- 5m, 15m, 1h, 24h, 7d, 30d
- Views, Searches, Feature interactions

## Normal Settled State
Three quiet tables of real numbers under a segmented window control.

## Alternate Visual States
- Empty window with a plain no data message
- Loading skeleton

## Interaction Cues
- Window switch reloads all groups
- Counts are monospace

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
- Window labels exactly as listed
- Group names exactly as listed
- Real counts only

## Avoid
- Sparklines without data
- Fabricated trends
- Public-facing copy

## Stitch Output Requirements
- Render the settled state as a 1440 px wide desktop frame
- Render the narrow tablet layout as a second frame
- Use only the labels and fields listed in this brief
- Do not invent metrics, charts, statuses, or features
