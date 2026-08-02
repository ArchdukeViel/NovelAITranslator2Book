# Component Contract — Forms & Inputs

Shared form component specifications across public and admin surfaces.

## Implemented Primitives

| Component | File | Status |
|---|---|---|
| `Input` | `frontend/components/ui/input.tsx` | Implemented |
| `Textarea` | `frontend/components/ui/textarea.tsx` | Implemented |
| `Button` | `frontend/components/ui/button.tsx` | Implemented |
| Select | Native `<select>` with Tailwind styling | Implemented |
| Checkbox | `.table-checkbox` class in `globals.css` (admin tables) | Implemented |
| Switch | Not implemented as shared primitive | — |
| Radio | Not implemented as shared primitive | — |
| File input | Not used | — |

## Input

- Height: `h-9` (36px)
- Border: `border-input` token
- Background: `bg-background`
- Border radius: `rounded-md` (4px)
- Focus: `focus-visible:ring-2 focus-visible:ring-ring`
- Disabled: `disabled:cursor-not-allowed disabled:opacity-50`
- Placeholder: `placeholder:text-muted-foreground`
- Full width by default (`w-full`)

## Textarea

- Minimum height: `min-h-32` (128px)
- Same border, background, radius, focus, disabled treatment as Input
- Resizable vertically by default

## Labels

- Position: above input
- Style: `text-xs font-medium text-muted-foreground`
- Association: `htmlFor` attribute linking to input `id`

## Validation Messages

- Position: directly below associated input
- Error text: `text-xs text-destructive-text`
- Success text: `text-xs text-success-text`
- Error inputs: MUST set `aria-invalid="true"` and `aria-describedby` pointing to error message ID
- Error MUST NOT disappear while user is still editing — clear on valid input or form resubmit

## Draft Preservation

- Form inputs MUST preserve entered text across authentication detours
- Login redirect with `next` parameter restores user to form page
- Form data persisted via component state or session storage

## Mobile Input Modes

- Email fields: `inputMode="email"`, `type="email"`
- URL fields: `inputMode="url"`, `type="url"`
- Search fields: `type="search"` for virtual keyboard search action
- Numeric fields: `inputMode="numeric"` where appropriate

## Required Fields

- Required inputs MUST have `required` attribute or `aria-required="true"`
- SHOULD show visual required indicator (asterisk or "Required" label)
- Required validation fires on blur or form submit, not on every keystroke

## Autofill

- Login/registration forms MUST set `autocomplete` attributes (`username`, `current-password`, `new-password`, `email`)
- MUST NOT break layout or validation on browser autofill
- Autofill styling handled by browser; no override

## Sizing and Radius

| Element | Height | Radius | Token |
|---|---|---|---|
| Input (default) | `h-9` (36px) | `rounded-md` (4px) | `--input`, `--border`, `--ring` |
| Input (sm) | `h-8` (32px) | `rounded-md` (4px) | Same |
| Textarea | `min-h-32` (128px) | `rounded-md` (4px) | Same |
| Button (default) | `h-9` (36px) | `rounded-md` (4px) | Variant-dependent |
| Button (sm) | `h-8` (32px) | `rounded-md` (4px) | Same |
| Button (icon) | `h-9 w-9` (36×36px) | `rounded-md` (4px) | Same |
