# Dokushodo - Maintenance

## Design Task
Design the maintenance task table with schedule and run state.

## Product Context
Runs allowlisted cleanup tasks on a schedule.

## Global Visual Snapshot
The admin console is a dense, quiet, data-first workspace for operating Dokushodo. It uses a near-black Midnight Slate dark theme and a cool light theme, with vermillion reserved for the primary action of each panel and for attention-required or destructive actions. The shell is a persistent left sidebar with grouped navigation and a compact top bar with theme and view controls; content is a full-bleed workspace of tables, panels, and status summaries. Tables are the default record surface: high row density, monospace identifiers, status badges in semantic colors, and direct row actions such as approve, reject, retry, run, and delete. Typography is sans-serif only; serif never appears, and public-facing motifs such as sakura accents do not appear. Elevation is flat with thin borders, six pixel card corners, and no floating elements. Empty tables show a plain message and a clear next action. Status truthfulness is absolute: schedules, health, credentials, and runtime state render exactly what the system reports, with no fabricated metrics. The settled state is orderly, legible, fast to scan, and free of decorative motion and imagery.

## Page Goal
Show every task, its schedule, and its last result in one table.

## Audience and Access
Owner role.

## Primary Action
Running a task now.

## Information Hierarchy
- Page heading Maintenance
- Tasks table
- Run now control

## Desktop Composition
- Table columns: task name, Schedule, State, Last completed, Next eligible, Result
- Per-row run control
- Overdue tasks carry a warning badge

## Mobile Composition
- Table scrolls horizontally
- Run control per row

## Page Anatomy
- Admin shell sidebar
- Top bar
- Tasks table

## Key Components
- Tasks table
- State badge
- Result cell
- Run control

## Representative Content
- Maintenance
- Schedule, State, Last completed, Next eligible, Result

## Normal Settled State
A quiet table of task states with one run affordance per row.

## Alternate Visual States
- Task running state
- Overdue warning badge
- Empty task list

## Interaction Cues
- Run now updates the row in place
- Warning badges use semantic colors

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
- Column labels exactly as listed
- State badge semantics

## Avoid
- Fake progress bars
- Destructive language for safe tasks

## Stitch Output Requirements
- Render the settled state as a 1440 px wide desktop frame
- Render the narrow tablet layout as a second frame
- Use only the labels and fields listed in this brief
- Do not invent metrics, charts, statuses, or features
