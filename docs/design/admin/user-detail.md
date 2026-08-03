# Dokushodo - User Detail

## Design Task
Design the single user record with summary, timestamps, and actions.

## Product Context
Reached from the users table for one account.

## Global Visual Snapshot
The admin console is a dense, quiet, data-first workspace for operating Dokushodo. It uses a near-black Midnight Slate dark theme and a cool light theme, with vermillion reserved for the primary action of each panel and for attention-required or destructive actions. The shell is a persistent left sidebar with grouped navigation and a compact top bar with theme and view controls; content is a full-bleed workspace of tables, panels, and status summaries. Tables are the default record surface: high row density, monospace identifiers, status badges in semantic colors, and direct row actions such as approve, reject, retry, run, and delete. Typography is sans-serif only; serif never appears, and public-facing motifs such as sakura accents do not appear. Elevation is flat with thin borders, six pixel card corners, and no floating elements. Empty tables show a plain message and a clear next action. Status truthfulness is absolute: schedules, health, credentials, and runtime state render exactly what the system reports, with no fabricated metrics. The settled state is orderly, legible, fast to scan, and free of decorative motion and imagery.

## Page Goal
See everything about a user and act on the account safely.

## Audience and Access
Owner role.

## Primary Action
Enabling or disabling the account.

## Information Hierarchy
- Breadcrumb back to Users
- Profile header with initial, name, email, role badge, status badge
- Account Summary card
- Timestamps card
- Disabled Metadata card when disabled
- Actions: Disable, Enable, Change Role, Revoke Sessions

## Desktop Composition
- Profile header row
- Two summary cards side by side
- Disabled Metadata card appears only for disabled accounts
- Actions with danger styling on destructive ones

## Mobile Composition
- Header stacks
- Cards stack full width

## Page Anatomy
- Admin shell sidebar
- Top bar
- Breadcrumb
- Profile header
- Summary cards
- Actions

## Key Components
- Profile header
- Account Summary card
- Timestamps card
- Disabled Metadata card
- Action buttons
- Confirmation dialogs

## Representative Content
- Users breadcrumb
- Account Summary
- Timestamps
- Disabled Metadata
- Disable
- Enable
- Change Role
- Revoke Sessions

## Normal Settled State
One quiet profile header, two summary cards, and a clear action row.

## Alternate Visual States
- Disabled account with metadata card
- Change Role dialog
- Confirmation for revoking sessions

## Interaction Cues
- Destructive actions require confirmation
- Role and status changes reflect immediately

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
- Card names exactly as listed
- Action labels
- Confirmation before destructive actions

## Avoid
- One-click account deletion
- Secrets or session tokens in view

## Stitch Output Requirements
- Render the settled state as a 1440 px wide desktop frame
- Render the narrow tablet layout as a second frame
- Use only the labels and fields listed in this brief
- Do not invent metrics, charts, statuses, or features
