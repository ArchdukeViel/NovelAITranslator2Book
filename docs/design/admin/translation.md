# Dokushodo - Scheduler Health

## Design Task
Design the translation scheduler health and model configuration surface.

## Product Context
Shows the state of the translation scheduler, configured models, provider
budgets, and the dedicated worker/queue boundary.

## Global Visual Snapshot
The admin console is a dense, quiet, data-first workspace for operating Dokushodo. It uses a near-black Midnight Slate dark theme and a cool light theme, with vermillion reserved for the primary action of each panel and for attention-required or destructive actions. The shell is a persistent left sidebar with grouped navigation and a compact top bar with theme and view controls; content is a full-bleed workspace of tables, panels, and status summaries. Tables are the default record surface: high row density, monospace identifiers, status badges in semantic colors, and direct row actions such as approve, reject, retry, run, and delete. Typography is sans-serif only; serif never appears, and public-facing motifs such as sakura accents do not appear. Elevation is flat with thin borders, six pixel card corners, and no floating elements. Empty tables show a plain message and a clear next action. Status truthfulness is absolute: schedules, health, credentials, and runtime state render exactly what the system reports, with no fabricated metrics. The settled state is orderly, legible, fast to scan, and free of decorative motion and imagery.

## Page Goal
Confirm the scheduler is healthy and see every model configuration.

## Audience and Access
Owner role.

## Primary Action
Reviewing scheduler and model states.

## Information Hierarchy
- Page heading Scheduler Health
- Scheduler health card
- Model Configurations table
- Provider budget and timing summary

## Desktop Composition
- Health card with scheduler state, last tick, next tick, and worker availability
- Model Configurations table: provider, model, purpose, status badge
- Budget summary: concurrency, RPM/TPM/RPD reservations, queue age, and recent provider timing
- Enable and disable toggle per row

## Mobile Composition
- Cards stack
- Table scrolls horizontally

## Page Anatomy
- Admin shell sidebar
- Top bar
- Health card
- Model table

## Key Components
- Health card
- Model table
- Status badge
- Enable toggle

## Representative Content
- Scheduler Health
- Model Configurations

## Normal Settled State
One health card over a dense model table; states are truthful and quiet.

## Alternate Visual States
- Scheduler or worker unavailable state with a clear notice
- Empty model table

## Interaction Cues
- Toggle updates the row state immediately
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
- Heading and panel names exactly as listed
- State semantics

## Avoid
- Fake health metrics
- Provider branding graphics

## Stitch Output Requirements
- Render the settled state as a 1440 px wide desktop frame
- Render the narrow tablet layout as a second frame
- Use only the labels and fields listed in this brief
- Do not invent metrics, charts, statuses, or features
