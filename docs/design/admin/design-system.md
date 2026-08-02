# Admin Design System

Visual direction and UI specifications for operator surfaces (`/admin/*`).

## Visual Direction

- **Operator-first & High-density:** Designed for rapid scanning, data density, and administrative decision-making.
- **Independent Palette:** Does NOT inherit public Yokocho Lantern Japanese-vibe visual decorations (no lantern badges or sakura pink accents).
- **Clean Contrast:** Neutral dark/light theme focusing on readability, status visibility, and tabular data.

## Typography & Components

- Font: DM Sans for UI, DM Mono for IDs, hashes, timestamps, and log outputs.
- Controls: Compact inputs, high-density buttons, precise data tables.

## Semantic Operational Roles

- **Success (`--success`):** Operational green for completed jobs, active status.
- **Warning (`--warning`):** Amber for stale backups, degraded health.
- **Danger (`--destructive`):** Red for failed jobs, rejected items, destructive actions.
- **Info (`--info`):** Blue for active crawling/translating in-progress tasks.

## Security & Redaction Rules

- Raw API credentials masked using `frontend/lib/mask-token.ts`.
- DB connection strings, secrets, and internal paths redacted from view.
- Destructive actions (takedowns, user disables, database purges) require explicit modal confirmation.
