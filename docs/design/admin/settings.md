# Dokushodo - Settings

## Design Task
Design the admin settings with runtime state and destructive clear.

## Product Context
Workspace settings and runtime state for the admin instance.

## Global Visual Snapshot
The admin console is a dense, quiet, data-first workspace for operating Dokushodo. It uses a near-black Midnight Slate dark theme and a cool light theme, with vermillion reserved for the primary action of each panel and for attention-required or destructive actions. The shell is a persistent left sidebar with grouped navigation and a compact top bar with theme and view controls; content is a full-bleed workspace of tables, panels, and status summaries. Tables are the default record surface: high row density, monospace identifiers, status badges in semantic colors, and direct row actions such as approve, reject, retry, run, and delete. Typography is sans-serif only; serif never appears, and public-facing motifs such as sakura accents do not appear. Elevation is flat with thin borders, six pixel card corners, and no floating elements. Empty tables show a plain message and a clear next action. Status truthfulness is absolute: schedules, health, credentials, and runtime state render exactly what the system reports, with no fabricated metrics. The settled state is orderly, legible, fast to scan, and free of decorative motion and imagery.

## Page Goal
Let the owner review configuration and reset runtime state safely.

## Audience and Access
Owner role.

## Primary Action
Reviewing or clearing runtime state.

## Information Hierarchy
- Page heading Settings
- Intro line: Configure workspace settings and runtime state.
- Provider Credential card
- Runtime State card
- Clear State action

## Desktop Composition
- Provider Credential card linking to the credentials surface
- Runtime State card with a state summary
- Clear State as a destructive button with a confirmation dialog

## Mobile Composition
- Cards stack full width

## Page Anatomy
- Admin shell sidebar
- Top bar
- Provider Credential card
- Runtime State card

## Key Components
- Provider Credential card
- Runtime State card
- Clear State button
- Confirmation dialog

## Representative Content
- Settings
- Configure workspace settings and runtime state.
- Provider Credential
- Runtime State
- Clear State

## Normal Settled State
Two quiet cards; the destructive action sits apart in danger styling.

## Alternate Visual States
- Confirmation dialog open
- State cleared confirmation

## Interaction Cues
- Clear State always asks for confirmation
- Danger styling only on destructive actions

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
- Intro line exactly as listed
- Card names
- Confirmation before clearing

## Avoid
- Secrets in the state summary
- One-click destructive actions

## Stitch Output Requirements
- Render the settled state as a 1440 px wide desktop frame
- Render the narrow tablet layout as a second frame
- Use only the labels and fields listed in this brief
- Do not invent metrics, charts, statuses, or features
