# Component Contract — Buttons

Button variants, states, and usage rules.

## Implementation

`frontend/components/ui/button.tsx` — `cva`-based variant system.

## Variants

| Variant | Background | Text | Border | Use |
|---|---|---|---|---|
| `default` (primary) | `bg-primary` | `text-primary-foreground` | transparent | Primary CTAs: "Start Reading", "Sign In", "Save" |
| `secondary` | `bg-secondary` | `text-secondary-foreground` | transparent | Secondary actions: filters, toggles |
| `outline` | `bg-background` | foreground (inherited) | `border-border` | Tertiary actions: "Cancel", back navigation |
| `ghost` | transparent | foreground (inherited) | none | Icon buttons, toolbar actions, minimal UI |
| `destructive` | `bg-destructive` | `text-destructive-foreground` | transparent | Destructive confirmations: "Delete", "Remove", "Reject" |

## Sizes

| Size | Height | Padding | Font |
|---|---|---|---|
| `default` | `h-9` (36px) | `px-3` | `text-sm` |
| `sm` | `h-8` (32px) | `px-2.5` | `text-xs` |
| `icon` | `h-9 w-9` (36×36px) | `px-0` | — |

## Common Styles

- Border radius: `rounded-md` (4px)
- Font weight: `font-medium`
- Transition: `transition-colors`
- Gap (icon + text): `gap-2`
- Disabled: `disabled:pointer-events-none disabled:opacity-50`

## Focus Treatment

- Default (non-primary): `focus-visible:ring-2 focus-visible:ring-ring`
- Primary (`bg-primary`): **Two-layer** — `outline: 2px solid hsl(var(--foreground))` + `box-shadow: 0 0 0 4px hsl(var(--focus-ring))` (defined in `globals.css`)
- This ensures the focus ring is visible against the orange primary fill

## Hover States

| Variant | Hover |
|---|---|
| `default` | `bg-primary/90` (10% transparent) |
| `secondary` | `bg-secondary/85` |
| `outline` | `bg-muted` |
| `ghost` | `bg-muted` |
| `destructive` | `bg-destructive/90` |

## Usage Rules

- **MUST** use `default` variant for the single primary CTA on a page
- **MUST** use `destructive` variant only inside confirmation dialogs for irreversible actions
- **MUST NOT** use `destructive` as the initial trigger — use `outline` or `ghost` for the trigger, then `destructive` in the confirmation
- **MUST NOT** nest buttons inside links or links inside buttons
- Loading state: disable button + show spinner; MUST preserve button width
