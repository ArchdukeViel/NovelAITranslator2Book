# Component Contract — Feedback & Status

Feedback components for status communication, validation, and user notification.

## Status Badges ("Lantern Badges")

- Shape: `rounded-md` border + 20% tinted fill (NOT `rounded-full` / pill)
- Size: `px-2 py-0.5 text-xs font-medium`
- Implementation: `frontend/components/ui/badge.tsx`
- Token pattern: `border-{status} bg-{status}/20 text-{status}-text`

### Canonical Status Mapping

| Status Meaning | Token | Badge Tone | Label Examples |
|---|---|---|---|
| Completed, published, healthy, active | `success` | `green` | "Completed", "Published", "Active" |
| Running, scheduled, informational | `info` | `blue` | "Ongoing", "Scheduled", "In progress" |
| Stale, partial, degraded, hiatus | `warning` | `amber` | "Hiatus", "Stale", "Partial" |
| Failed, rejected, deleted, blocked | `destructive` | `red` | "Failed", "Rejected", "Removed" |
| Inactive, dropped, unavailable | `muted` | `neutral` | "Dropped", "Unavailable", "Unknown" |

This mapping is canonical across public and admin surfaces. See `docs/design/public/design-system.md` Section 4.

### Badge Tones

| Tone | Border | Background | Text |
|---|---|---|---|
| `neutral` | `--border` | `--muted` | `--muted-foreground` |
| `green` | `--success` | `--success/20` | `--success-text` |
| `amber` | `--warning` | `--warning/20` | `--warning-text` |
| `red` | `--destructive` | `--destructive/20` | `--destructive-text` |
| `blue` | `--info` | `--info/20` | `--info-text` |
| `violet` | Raw violet (admin review status only) | Raw violet | Raw violet |

## Inline Validation

- Error messages: `text-xs text-destructive-text`, positioned below input
- Success messages: `text-xs text-success-text`, positioned below input
- MUST associate with input via `aria-describedby`
- Error state: `aria-invalid="true"` on input

## Alert Banners

- Inline contextual messages using semantic tokens
- Pattern: `border-{status} bg-{status}/20 text-{status}-text rounded-md px-3 py-2`
- MUST include text content — not color-only communication
- SHOULD include relevant icon for color-independent identification

## Toast Notifications

- Position: fixed top-right (desktop) / top-center (mobile)
- Z-index: 60 (above modals)
- Auto-dismiss: 4 seconds minimum
- Manual close: always available
- Container: `aria-live="polite"` with `role="status"`
- MUST NOT be sole feedback for destructive or error actions
- MUST NOT overlap with skip link (z-100)
- Reduced motion: instant show/hide, no slide animation

## Progress Indicators

- Reading progress bar: 3px fixed top, `bg-primary`, z-50
- Admin progress bar: `bg-primary`, `transition-[width] duration-300`
- MUST use `role="progressbar"` with `aria-valuemin`, `aria-valuemax`, `aria-valuenow`

## Skeletons

- Animated pulse loading blocks: `animate-pulse bg-muted`
- MUST match approximate target component dimensions
- Reduced motion: pulse becomes static muted block
- Use `aria-hidden="true"` on skeleton elements; announce loading via `aria-live` region

## Status Indicators

- Health status: colored dot or badge with text label
- Online/offline: text label, never color-only
- Badge MUST include accessible text (not relying on color alone)

## Live Region Roles

| Feedback Type | `aria-live` | `role` |
|---|---|---|
| Toast (info/success) | `polite` | `status` |
| Toast (error) | `polite` | `status` |
| Form validation | `polite` | `status` |
| Destructive confirmation | `assertive` | `alert` |
| Session expiry | `assertive` | `alert` |
