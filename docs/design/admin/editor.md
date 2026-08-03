# Dokushodo - Editor

## Design Task
Design the chapter editor with navigation, draft editing, and QA.

## Product Context
Manual editing of translated chapters with glossary QA support.

## Global Visual Snapshot
The admin console is a dense, quiet, data-first workspace for operating Dokushodo. It uses a near-black Midnight Slate dark theme and a cool light theme, with vermillion reserved for the primary action of each panel and for attention-required or destructive actions. The shell is a persistent left sidebar with grouped navigation and a compact top bar with theme and view controls; content is a full-bleed workspace of tables, panels, and status summaries. Tables are the default record surface: high row density, monospace identifiers, status badges in semantic colors, and direct row actions such as approve, reject, retry, run, and delete. Typography is sans-serif only; serif never appears, and public-facing motifs such as sakura accents do not appear. Elevation is flat with thin borders, six pixel card corners, and no floating elements. Empty tables show a plain message and a clear next action. Status truthfulness is absolute: schedules, health, credentials, and runtime state render exactly what the system reports, with no fabricated metrics. The settled state is orderly, legible, fast to scan, and free of decorative motion and imagery.

## Page Goal
Edit a chapter draft with the source visible and QA feedback close by.

## Audience and Access
Owner and editor roles.

## Primary Action
Saving the draft.

## Information Hierarchy
- Left: novel and chapter navigation
- Center: source text and draft editor
- Right: QA panel with glossary terms
- Save bar

## Desktop Composition
- Left column: novel select, chapter select, chapter list
- Center: read-only source panel and draft textarea
- Right: QA panel with glossary terms and issues
- Save bar with saved and unsaved state

## Mobile Composition
- Panels collapse behind tabs
- Editor pane full width

## Page Anatomy
- Admin shell sidebar
- Top bar
- Navigation column
- Editor pane
- QA panel
- Save bar

## Key Components
- Chapter list
- Source panel
- Draft textarea
- QA panel
- Save bar

## Representative Content
- Editor
- Save
- QA terms from the glossary

## Normal Settled State
A three-column editing workspace with a visible save state in the bar.

## Alternate Visual States
- Unsaved changes state
- QA issues list with counts
- Empty chapter selection

## Interaction Cues
- Save bar shows saved or unsaved clearly
- QA issues are clickable and scroll to the term

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
- Three-column layout
- Save state indicator
- Source panel read-only

## Avoid
- Rich text toolbars the editor does not have
- Auto-save without an indicator

## Stitch Output Requirements
- Render the settled state as a 1440 px wide desktop frame
- Render the narrow tablet layout as a second frame
- Use only the labels and fields listed in this brief
- Do not invent metrics, charts, statuses, or features
