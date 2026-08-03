# Standard Data States

Universal UI state definitions for data-fetching and mutation surfaces.

## Core States

| State | Condition | Presentation | Token/Pattern |
|---|---|---|---|
| Initial | Page load prior to first data fetch | Skeleton loaders or quiet placeholder | `animate-pulse` on `bg-muted` |
| Loading | Async fetch in progress | Non-blocking spinner or pulse skeleton | Spinner: `border-2 border-muted border-t-foreground animate-spin` |
| Empty | Query returned 0 results | Clear explanatory message + recovery CTA | `EmptyState` component |
| Pending Mutation | Mutation in flight | Disabled control with inline spinner, `aria-busy="true"` | Button disabled + spinner |
| Settled | Data loaded successfully | Normal content rendering | — |
| Success | Mutation completed | Toast or inline confirmation | `--success-text` token |
| Partial / Stale | Background revalidation failed or partial data | Display cached data + subtle stale indicator | `--warning-text` or muted badge |
| Recoverable Error | Network or transient API error | Inline error banner + retry button | `ErrorState` component, `--destructive-text` |
| Unavailable | Feature or backend service offline | Honest unavailable banner | `UnavailableState` component |
| Unauthorized | Guest accessing authenticated route | Redirect to sign-in, preserving intended destination | Login redirect with `next` param |
| Forbidden | Authenticated user lacking required role | Clear role message, no redirect loop | `ForbiddenState` component |
| Not Found | Entity or route missing | 404 illustration + link to catalog | `NotFoundState` component |
| Legal / Takedown | Content removed under DMCA/legal | HTTP 451 legal notification | Honest explanation, no-store cache |
| Offline | Browser offline or connection lost | Toast or banner with "offline" message | `--warning-text` |
| Rate-Limited | Too many requests | "Please wait" message with countdown or retry delay | `--warning-text` |
| Cancelled | User cancelled an operation | Restore previous state, no error shown | — |
| Optimistic Update | Mutation applied locally before server confirmation | Show updated state immediately; rollback on failure | TanStack Query optimistic update |
| Background Revalidation | Stale data displayed while fresh data loads | Show existing data; replace silently on success | TanStack Query `staleTime` |

## State Relationships

- **Initial → Loading → Settled/Empty/Error**: Standard fetch lifecycle
- **Settled → Pending Mutation → Success/Error → Settled**: Mutation lifecycle
- **Settled → Background Revalidation → Settled/Stale**: Background refresh
- **Any → Offline**: Network loss overlay
- **Any → Unauthorized**: Session expiry redirect

## State Implementation

| Component | File | States Covered |
|---|---|---|
| `LoadingState` | `frontend/components/ui/page-state.tsx` | Loading, initial |
| `EmptyState` | `frontend/components/ui/page-state.tsx` | Empty |
| `ErrorState` | `frontend/components/ui/page-state.tsx` | Recoverable error |
| `UnavailableState` | `frontend/components/ui/page-state.tsx` | Unavailable |
| `UnauthorizedState` | `frontend/components/ui/page-state.tsx` | Unauthorized |
| `ForbiddenState` | `frontend/components/ui/page-state.tsx` | Forbidden |
| `NotFoundState` | `frontend/components/ui/page-state.tsx` | Not found |
| `PartialErrorState` | `frontend/components/ui/page-state.tsx` | Partial failure |

## Normative Rules

- **MUST** show loading state within 100ms of initiating a fetch
- **MUST** preserve user input during error recovery (retry MUST NOT clear form)
- **MUST NOT** show a blank page — always show skeleton, loading, or error state
- **MUST NOT** mix error and success states in the same region simultaneously
- **SHOULD** use optimistic updates for low-risk mutations (save to library, toggle)
- **SHOULD** use pessimistic updates for high-risk mutations (delete, status change)
- **MUST** announce state changes via `aria-live` regions (see `docs/design/shared/accessibility.md`)
