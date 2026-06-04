# Frontend Architecture

## Admin Surface

`frontend/app/(admin)/admin` owns the controlled admin cockpit routes:

- `/admin`
- `/admin/library`
- `/admin/crawler`
- `/admin/activity`
- `/admin/activity/[activityId]`
- `/admin/requests`
- `/admin/settings`
- `/admin/translation`
- `/admin/editor`

Admin pages should render workflows and call typed functions from `frontend/lib/api.ts`. They must not read runtime storage directly, implement backend scheduling/QA logic, or invent alternate backend contracts.

## Public Surface

`frontend/app/(public)` contains the current public-facing route group. This refactor does not expand public reader functionality.

## Components

`frontend/components` contains reusable UI and admin presentation components.

- `frontend/components/ui` owns small design primitives such as buttons, panels, inputs, badges, and text areas.
- `frontend/components/admin` owns admin-specific tables, empty/error/loading states, dialogs, progress display, and feature panels.

Components may receive data and callbacks from pages. They should not call backend APIs directly unless they are deliberately API-bound widgets with a documented reason.

## Lib

`frontend/lib` is the frontend contract layer.

- `api.ts` is the only browser/backend API client.
- `novel-input.ts` owns source detection and novel ID derivation helpers.
- `format.ts` owns display formatting helpers.
- `admin-errors.ts` owns admin-facing error strings.
- `activity.ts`, `store.ts`, `query-client.tsx`, and `utils.ts` remain shared frontend utilities.

## Server

`frontend/server` is reserved for frontend server-side environment handling. It must not bypass backend API contracts or read private runtime storage directly.

## Non-Goals

- No public reader UI expansion in this refactor.
- No auth/user accounts.
- No backend contract changes.
- No route renames.
- No visual redesign.
- No public contribution credential flow.
- No scheduler logic in React.
