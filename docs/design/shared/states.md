# Standard Data States

Universal UI state definitions for data-fetching surfaces.

## States

| State | Condition | Presentation |
|---|---|---|
| Initial | Page load prior to data fetch | Skeleton loaders or quiet placeholder |
| Loading | Async fetch in progress | Non-blocking spinner or pulse skeleton |
| Empty | Query returned 0 results | Clear explanatory message + recovery action CTA |
| Pending | Mutation in flight | Disabled control with inline spinner |
| Settled | Operation completed | Success toast, badge, or state update |
| Recoverable Error | Network or transient API error | Inline error banner + retry button |
| Partial / Stale Data | Background revalidation failed | Display cached data + subtle stale indicator |
| Unavailable | Feature or backend service offline | Honest unavailable banner |
| Unauthorized / Forbidden | Guest accessing auth route / insufficient role | Authentication prompt or clear role message |
| Not Found | Entity or route missing | 404 illustration + link to catalog |
| Legal / Takedown | Content removed under DMCA/legal | Honest HTTP 451 legal notification |
| Success | Mutation succeeded | Toast or inline checkmark confirmation |
