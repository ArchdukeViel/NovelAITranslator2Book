---
trigger: always_on
description: Architecture, state management, route boundaries, API clients, and verification rules for the Next.js frontend.
---

# Frontend Architecture & Next.js Rules

This rule enforces frontend architecture, route boundaries, and state management standards for the Dokushodo Next.js application (`frontend/`).

## Route Groups & Boundaries

- **Admin Routes (`frontend/app/(admin)/admin/*`)**:
  - Exclusively for authenticated administrators and operators.
  - Must use `frontend/lib/api.ts` for all backend communication.
  - Never place public-facing reader components or routes inside the `(admin)` route group.
- **Public Reader Routes (`frontend/app/(public)/*`)**:
  - Exclusively for public readers, novel listings, and chapter readers.
  - Must use `frontend/lib/public-api.ts` targeting Reader API (`:8001`) or public paths.
  - Never call admin endpoints or import admin utilities from public routes.

## State Management & Data Fetching

- **Server State (`@tanstack/react-query`)**:
  - All asynchronous backend data must use React Query hooks (`useQuery`, `useMutation`).
  - Use query key factories or consistent query keys for caching and invalidation.
  - For prefetching (e.g. next chapter prefetching on scroll), use `queryClient.prefetchQuery` safely wrapped in `useSafeQueryClient()`.
- **Client UI State (`zustand`)**:
  - Use Zustand stores exclusively for client-only UI state (theme, reader font size/line height, sidebar drawer toggle).
- **Prohibited Libraries**:
  - **PROHIBITED**: Never call `fetch()` or `axios` directly inside UI components.
  - **PROHIBITED**: Do not introduce Redux, MobX, CSS Modules, or CSS-in-JS (styled-components, emotion). Use Tailwind CSS and existing design tokens.

## UI Components & Accessibility

- **Modal Dialogs**: Modals must wrap in `DialogShell` (or follow its pattern) providing `Escape` key dismissal, backdrop click closing, and body scroll locking (`overflow: hidden`).
- **Icons**: Use `lucide-react` exclusively for icons; do not introduce competing icon packages (`react-icons`, `@heroicons/react`).
- **Images**: Novel covers must use `next/image` with configured `remotePatterns` in `next.config.mjs`. Never disable optimization (`unoptimized: true`) or bypass loaders in production components.
- **SSR Hydration Safety (React 19 / Next.js 16)**: Components depending on browser APIs (`localStorage`, `window.innerWidth`, audio/TTS) must guard against SSR mismatch using `useEffect` or client-only mounting state (`mounted` flag).

## Verification Commands

Run verification from the `frontend/` directory:
```powershell
cd frontend
npm run typecheck
npm run lint
npm run test
```
