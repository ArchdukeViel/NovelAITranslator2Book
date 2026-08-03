# Dokushodo - Users

## Design Task
Design the user list with search and role and status filters.

## Product Context
All platform accounts from the operator side.

## Global Visual Snapshot
The admin console is a dense, quiet, data-first workspace for operating Dokushodo. It uses a near-black Midnight Slate dark theme and a cool light theme, with vermillion reserved for the primary action of each panel and for attention-required or destructive actions. The shell is a persistent left sidebar with grouped navigation and a compact top bar with theme and view controls; content is a full-bleed workspace of tables, panels, and status summaries. Tables are the default record surface: high row density, monospace identifiers, status badges in semantic colors, and direct row actions such as approve, reject, retry, run, and delete. Typography is sans-serif only; serif never appears, and public-facing motifs such as sakura accents do not appear. Elevation is flat with thin borders, six pixel card corners, and no floating elements. Empty tables show a plain message and a clear next action. Status truthfulness is absolute: schedules, health, credentials, and runtime state render exactly what the system reports, with no fabricated metrics. The settled state is orderly, legible, fast to scan, and free of decorative motion and imagery.

## Page Goal
Find any user and open their record.

## Audience and Access
Owner role.

## Primary Action
Opening a user record.

## Information Hierarchy
- Page heading Users
- Search field
- Role filter: All roles, User, Guest, Owner
- Status filter: All, Active, Disabled
- Users table

## Desktop Composition
- Search and filters in one row
- Table: name, email, role badge, status badge, joined date
- Row click opens the user detail

## Mobile Composition
- Filters collapse
- Table scrolls horizontally

## Page Anatomy
- Admin shell sidebar
- Top bar
- Search and filter row
- Users table

## Key Components
- Search field
- Role filter
- Status filter
- Users table
- Role badge
- Status badge

## Representative Content
- Users
- All roles, User, Guest, Owner
- All, Active, Disabled

## Normal Settled State
A dense user table under one quiet filter row.

## Alternate Visual States
- Empty search result
- Filter with no matches

## Interaction Cues
- Filters apply instantly
- Row hover highlights

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
- Filter labels exactly as listed
- Badge semantics

## Avoid
- Avatars in the table
- Email address truncation that hides data

## Stitch Output Requirements
- Render the settled state as a 1440 px wide desktop frame
- Render the narrow tablet layout as a second frame
- Use only the labels and fields listed in this brief
- Do not invent metrics, charts, statuses, or features
