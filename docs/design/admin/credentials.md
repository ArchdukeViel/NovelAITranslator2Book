# Dokushodo - Credentials

## Design Task
Design the provider credential management surface.

## Product Context
Stores provider keys for translation models; keys are encrypted and never shown.

## Global Visual Snapshot
The admin console is a dense, quiet, data-first workspace for operating Dokushodo. It uses a near-black Midnight Slate dark theme and a cool light theme, with vermillion reserved for the primary action of each panel and for attention-required or destructive actions. The shell is a persistent left sidebar with grouped navigation and a compact top bar with theme and view controls; content is a full-bleed workspace of tables, panels, and status summaries. Tables are the default record surface: high row density, monospace identifiers, status badges in semantic colors, and direct row actions such as approve, reject, retry, run, and delete. Typography is sans-serif only; serif never appears, and public-facing motifs such as sakura accents do not appear. Elevation is flat with thin borders, six pixel card corners, and no floating elements. Empty tables show a plain message and a clear next action. Status truthfulness is absolute: schedules, health, credentials, and runtime state render exactly what the system reports, with no fabricated metrics. The settled state is orderly, legible, fast to scan, and free of decorative motion and imagery.

## Page Goal
Let the owner configure and verify provider credentials safely.

## Audience and Access
Owner role.

## Primary Action
Testing a connection.

## Information Hierarchy
- Page heading Provider Credentials
- Add credential form
- Credentials table
- Test result notices

## Desktop Composition
- Add form: provider select, model field, key input with show toggle
- Table: provider, model, masked fingerprint, status badge, created date
- Row actions: Test connection, Delete
- Test result shown as an inline notice

## Mobile Composition
- Form above table, table scrolls horizontally

## Page Anatomy
- Admin shell sidebar
- Top bar
- Add form
- Credentials table
- Notices

## Key Components
- Add form
- Masked fingerprint
- Test connection action
- Delete action
- Status badge

## Representative Content
- Provider Credentials
- Test connection
- Delete

## Normal Settled State
A quiet form over a dense table; keys exist only as masked fingerprints.

## Alternate Visual States
- Empty state with a clear add prompt
- Test failure notice
- Delete confirmation dialog

## Interaction Cues
- Test connection returns a clear pass or fail notice
- Delete requires confirmation

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
- Masked fingerprints only, never full keys
- Status badge semantics
- Confirmation before delete

## Avoid
- Full key values anywhere
- Key copy buttons
- Success confetti

## Stitch Output Requirements
- Render the settled state as a 1440 px wide desktop frame
- Render the narrow tablet layout as a second frame
- Use only the labels and fields listed in this brief
- Do not invent metrics, charts, statuses, or features
