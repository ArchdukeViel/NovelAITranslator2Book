# Frontend V2 Implementation Handoff Architecture

Canonical architectural handoff document for the Frontend V2 reconstruction (Prompt 2 input).

## 1. Frozen Decisions & Environment

- **Theme Identity**: Dokushodo (読書道) — Modern Japanese Literary aesthetic with Shuji Vermillion (`--primary`) & Washi Warm Paper (light) / Midnight Slate (dark).
- **Accessibility Standard**: Target WCAG 2.2 Level AA across all public and admin surfaces.
- **Brand Asset Baseline**:
  - Header Mark: `frontend/public/assets/dokushodo/brand/brand-mark.png`
  - Scalable Vector Mark: `frontend/public/assets/dokushodo/brand/icon.svg`
  - PWA Maskable Icon: `frontend/public/assets/dokushodo/brand/icon-512.png`
  - Open Graph Image: `frontend/public/assets/dokushodo/brand/open-graph.png`

---

## 2. Rendering and Component Classification Matrix

Every route MUST adhere to its rendering classification to preserve SEO, performance, and security boundaries:

| Route Path | Component Type | Rendering Strategy | State Scope | Direct `fetch()` |
|---|---|---|---|---|
| `/` | Server Shell + Client Islands | Static / ISR (`revalidate: 60`) | React Query (Home Rails) | BANNED (Use `lib/public-api.ts`) |
| `/browse-novels` | Client Component Island | Dynamic (Search / Filter Params) | React Query + URL SearchParams | BANNED |
| `/novels/[slug]` | Server Shell + Client Island | ISR (`revalidate: 300`) | React Query (Tabs & Rating) | BANNED |
| `/novels/[slug]/chapter/[chapterId]` | Client Component | Dynamic / Client-Side Navigation | Reader Store (Zustand) + Query | BANNED |
| `/account/*` | Client Component Shell | Client-Side Authenticated | React Query + Auth Session | BANNED |
| `/admin/*` | Client Component Shell | Admin Split Process (Port 8000) | React Query + CSRF Cookie | BANNED (Use `lib/api.ts`) |

---

## 3. Data Flow & State Management Rules

1. **Server State**: Managed exclusively via `@tanstack/react-query`. No manual `useEffect` fetching or raw global fetch states.
2. **Client State**: Local UI state uses `zustand` (e.g. reader theme preferences, search overlay open state).
3. **No Direct `fetch()`**: Components MUST NOT call global `fetch()` directly. All public requests pass through `lib/public-api.ts`; admin requests pass through `lib/api.ts`.
4. **Invalidation Policy**: Mutations MUST invalidate corresponding Query keys upon success (e.g. bookmarking invalidates `["library"]`).

---

## 4. Implementation Phase Order for Prompt 2

1. **Phase A — Foundational Shell & System Tokens**: Verify `globals.css` Shuji Vermillion CSS variables, root fonts, and public navigation header.
2. **Phase B — Discovery & Public Routes**: Reconstruct Home, Browse, Search overlay, and Novel Detail pages.
3. **Phase C — Quiet Chapter Reader**: Reconstruct chapter reading view with independent reader token system and chrome suppression.
4. **Phase D — Account & Library Board**: Reconstruct authenticated user dashboard, reading history, and reviews.
5. **Phase E — Admin Utilitarian Control Plane**: Reconstruct high-density admin tables, moderation queues, and operational status indicators.
