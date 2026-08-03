# Dokushodo - Glossary

## Design Task
Design the glossary management surface with status summaries and entries.

## Product Context
Term management for translation consistency, with import candidates.

## Global Visual Snapshot
The admin console is a dense, quiet, data-first workspace for operating Dokushodo. It uses a near-black Midnight Slate dark theme and a cool light theme, with vermillion reserved for the primary action of each panel and for attention-required or destructive actions. The shell is a persistent left sidebar with grouped navigation and a compact top bar with theme and view controls; content is a full-bleed workspace of tables, panels, and status summaries. Tables are the default record surface: high row density, monospace identifiers, status badges in semantic colors, and direct row actions such as approve, reject, retry, run, and delete. Typography is sans-serif only; serif never appears, and public-facing motifs such as sakura accents do not appear. Elevation is flat with thin borders, six pixel card corners, and no floating elements. Empty tables show a plain message and a clear next action. Status truthfulness is absolute: schedules, health, credentials, and runtime state render exactly what the system reports, with no fabricated metrics. The settled state is orderly, legible, fast to scan, and free of decorative motion and imagery.

## Page Goal
Approve, edit, and track glossary terms quickly.

## Audience and Access
Owner role.

## Primary Action
Approving a pending term.

## Information Hierarchy
- Page heading Glossary
- Status summary cards: Total, Approved, Pending, Rejected
- Filter and search row
- Entries table
- Import candidates panel

## Desktop Composition
- Four summary cards in a row
- Entries table: term, reading, definition, language, status, actions
- Row actions: edit, approve, delete
- Import candidates panel for auto-extracted terms

## Mobile Composition
- Summary cards scroll horizontally
- Entries table scrolls horizontally

## Page Anatomy
- Admin shell sidebar
- Top bar
- Summary cards
- Entries table
- Import candidates

## Key Components
- Summary card
- Entries table
- Status badge
- Row actions
- Import candidates panel

## Representative Content
- Glossary
- Total, Approved, Pending, Rejected

## Normal Settled State
Four quiet numbers over a dense term table with clear status badges.

## Alternate Visual States
- Empty glossary
- Import candidates available
- Edit dialog open

## Interaction Cues
- Approve updates counts instantly
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
- Summary card names
- Status badge semantics

## Avoid
- Public-facing glossary browsing
- Bulk edits without confirmation

## Stitch Output Requirements
- Render the settled state as a 1440 px wide desktop frame
- Render the narrow tablet layout as a second frame
- Use only the labels and fields listed in this brief
- Do not invent metrics, charts, statuses, or features
