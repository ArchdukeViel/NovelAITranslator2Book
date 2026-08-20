# Dokushodo - Dashboard

## Design Task
Design the admin home with metric cards and status panels.

## Product Context
The default landing after sign in; shows the operating state of the platform at a glance.

## Global Visual Snapshot
The admin console is a dense, quiet, data-first workspace for operating Dokushodo. It uses a near-black Midnight Slate dark theme and a cool light theme, with vermillion reserved for the primary action of each panel and for attention-required or destructive actions. The shell is a persistent left sidebar with grouped navigation and a compact top bar with theme and view controls; content is a full-bleed workspace of tables, panels, and status summaries. Tables are the default record surface: high row density, monospace identifiers, status badges in semantic colors, and direct row actions such as approve, reject, retry, run, and delete. Typography is sans-serif only; serif never appears, and public-facing motifs such as sakura accents do not appear. Elevation is flat with thin borders, six pixel card corners, and no floating elements. Empty tables show a plain message and a clear next action. Status truthfulness is absolute: schedules, health, credentials, and runtime state render exactly what the system reports, with no fabricated metrics. The settled state is orderly, legible, fast to scan, and free of decorative motion and imagery.

## Page Goal
Answer what is running, what needs attention, and what changed, in one screen.

## Audience and Access
Owner and admin roles only. The dashboard reads durable activity and queue
health. In production, provider-backed execution is owned by the dedicated
worker service; the web-process runner is disabled by the Compose topology.

## Primary Action
Drilling into the panel that needs attention.

## Information Hierarchy
- Metric cards row
- Activity panel
- Requests panel
- Worker status card
- Queue age, pending count, and provider timing summary when available

## Desktop Composition
- Four metric cards with number and label
- Activity panel with a recent events table
- Requests panel with pending requests and quick approve and reject actions
- Worker status card with truthful running, unavailable, and external-worker states; local Start, Stop, and Run Once controls are explicit owner/local overrides, while the dedicated worker remains the production execution path

## Mobile Composition
- Metrics stack in two columns
- Panels stack full width

## Page Anatomy
- Admin shell sidebar
- Top bar
- Metric cards
- Panels grid
- Worker card

## Key Components
- Metric card
- Activity table
- Requests table
- Worker status card
- Worker controls

## Representative Content
- Dashboard heading
- Metric labels for novels, chapters, users, and requests
- Start, Stop, Run Once

## Normal Settled State
Dense but calm: one row of numbers, two tables, one status card; no charts, no decoration.

## Alternate Visual States
- Worker stopped state with a prominent but quiet notice
- Empty activity with a plain message
- Loading skeleton rows

## Interaction Cues
- Worker controls change the state immediately
- Row hover highlights the full row
- Status badges use semantic colors

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
- Sidebar labels exactly as shipped
- Worker control labels
- No fabricated metrics

## Avoid
- Charts without data
- Hero imagery or public-facing motifs
- Auto-refresh without an indicator

## Stitch Output Requirements
- Render the settled state as a 1440 px wide desktop frame
- Render the narrow tablet layout as a second frame
- Use only the labels and fields listed in this brief
- Do not invent metrics, charts, statuses, or features
