# Public Design System — Shuji Vermillion & Washi

Visual identity and token specification for public surfaces.

## 1. Scope and Ownership

This document defines the **canonical visual-token contract** for all public-facing surfaces (route group `(public)`). It is the single source of truth for color, spacing, radius, elevation, z-index, typography, motion, visual identity hierarchy, brand asset taxonomy, gradient boundaries, and accessibility requirements.

### 1.1 Visual Identity Hierarchy

- **Product Name**: Dokushodo (読書道)
- **Public Design Direction**: Modern Japanese Literary
- **Primary Theme**: Shuji Vermillion & Washi Warm Paper (light mode) / Midnight Slate (dark mode)
- **Supporting Motifs**: Restrained lantern geometry, yokocho alley warmth, bunko-bon bookplate framing

- **Owner**: Frontend lead
- **Review cadence**: Every release that touches `frontend/app/globals.css`, `frontend/tailwind.config.ts`, or public route components
- **Automated verification**: `npx vitest run "app/(public)/__tests__/token-contrast.test.ts"`, `npm run lint`, `npm run typecheck`, `npm run build`
- **Manual acceptance**: Visual regression review for token changes; contrast audit for color changes
- **Admin surfaces**: Inherit global tokens but maintain their own override document at `docs/design/admin/design-system.md`

---

## 2. Token Architecture

### 2.1 Primitive Roles

All tokens are CSS custom properties defined on `:root` (light) and `.dark` (dark mode). Two tiers:

| Tier | Suffix | Role | Example |
|------|--------|------|---------|
| Semantic fill | (none) | Background/fill color for a semantic surface | `--primary`, `--success` |
| Text on fill | `-foreground` | Text color **on** the corresponding semantic fill (e.g., white text on green badge) | `--primary-foreground`, `--success-foreground` |
| Text on neutral | `-text` | Colored text **on** neutral page/card background (e.g., green inline status) | `--primary-text`, `--success-text` |

### 2.2 Naming Rules

- All tokens use **HSL values** (space-separated `H S% L%`) except `--border` which includes alpha: `H S% L% / A`. `--input` is space-separated HSL (`38 20% 90%` in root, `222 16% 16%` in dark).
- `--radius` is a **length** (`0.375rem`), not a color
- No raw hex/rgb in globals.css — all color tokens are HSL
- Semantic tokens map 1:1 to Tailwind config extensions (see Section 3)

### 2.3 Raw-Color Restrictions

- **MUST NOT** use raw color values in components or CSS modules
- **MUST** reference tokens via `hsl(var(--token))` in CSS or Tailwind utilities (`bg-primary`, `text-primary-foreground`, etc.)
- **MUST NOT** create new semantic tokens without updating this document, Tailwind config, and both mode tables
- Illustration assets (SVGs) may use raw colors; UI surfaces must not

---

## 3. Complete Color Token Tables

### 3.1 Light Mode (`:root`)

| Token | Value | Purpose |
|-------|-------|---------|
| `--background` | `38 25% 96%` | Warm Washi Paper page background |
| `--foreground` | `222 20% 14%` | Default body text |
| `--card` | `0 0% 100%` | Card, popover, modal surfaces |
| `--card-foreground` | `222 20% 14%` | Text on card surfaces |
| `--popover` | `0 0% 100%` | Popover/dropdown surfaces |
| `--popover-foreground` | `222 20% 14%` | Text on popover surfaces |
| `--primary` | `14 80% 50%` | Shuji Vermillion — primary CTAs, active states |
| `--primary-foreground` | `14 20% 4%` | Text on primary fill (buttons) |
| `--primary-text` | `14 75% 32%` | Primary-colored text on neutral background |
| `--secondary` | `195 25% 88%` | Soft teal — structural chips, dividers |
| `--secondary-foreground` | `222 20% 14%` | Text on secondary fill |
| `--muted` | `38 18% 90%` | Muted backgrounds (secondary content areas) |
| `--muted-foreground` | `222 20% 14%` | Text on muted backgrounds — **see limitation note** |
| `--accent` | `340 55% 40%` | Sakura pink — favorites, ratings, save-to-library, and novel progress indicators |
| `--accent-foreground` | `340 25% 96%` | Text on accent fill |
| `--destructive` | `1 75% 55%` | Error, failed, deleted, blocked states |
| `--destructive-foreground` | `1 20% 4%` | Text on destructive fill |
| `--destructive-text` | `1 20% 22%` | Destructive-colored text on neutral background |
| `--border` | `222 20% 14% / 0.09` | Default border color (cards, inputs, dividers) |
| `--input` | `38 20% 90%` | Input field background |
| `--ring` | `14 80% 45%` | Default focus ring color |
| `--focus-ring` | `14 80% 45%` | Primary button outer focus ring |
| `--success` | `150 45% 32%` | Completed, published, healthy, active |
| `--success-foreground` | `150 70% 88%` | Text on success fill |
| `--success-text` | `150 20% 18%` | Success-colored text on neutral background |
| `--warning` | `45 80% 48%` | Stale, partial, degraded, hiatus |
| `--warning-foreground` | `45 20% 6%` | Text on warning fill |
| `--warning-text` | `45 20% 18%` | Warning-colored text on neutral background |
| `--info` | `205 70% 45%` | Running, scheduled, informational |
| `--info-foreground` | `205 20% 4%` | Text on info fill |
| `--info-text` | `205 20% 20%` | Info-colored text on neutral background |
| `--sidebar` | `38 20% 90%` | Sidebar background |
| `--sidebar-accent` | `38 18% 87%` | Sidebar hover/active accent |
| `--radius` | `0.375rem` | Base border radius (6px) |

### 3.2 Dark Mode (`.dark`)

| Token | Value | Purpose |
|-------|-------|---------|
| `--background` | `222 25% 10%` | Midnight Slate page background |
| `--foreground` | `38 20% 90%` | Default body text |
| `--card` | `222 20% 14%` | Card, popover, modal surfaces |
| `--card-foreground` | `38 20% 90%` | Text on card surfaces |
| `--popover` | `222 20% 14%` | Popover/dropdown surfaces |
| `--popover-foreground` | `38 20% 90%` | Text on popover surfaces |
| `--primary` | `14 85% 55%` | Vibrant Vermillion — primary CTAs, active states |
| `--primary-foreground` | `14 20% 4%` | Text on primary fill (buttons) |
| `--primary-text` | `14 70% 75%` | Primary-colored text on neutral background |
| `--secondary` | `195 25% 22%` | Soft teal — structural chips, dividers |
| `--secondary-foreground` | `38 25% 85%` | Text on secondary fill |
| `--muted` | `222 16% 20%` | Muted backgrounds |
| `--muted-foreground` | `38 20% 90%` | Text on muted backgrounds — **see limitation note** |
| `--accent` | `340 62% 66%` | Sakura pink — favorites, ratings, save-to-library **only** |
| `--accent-foreground` | `38 25% 7%` | Text on accent fill |
| `--destructive` | `1 75% 55%` | Error, failed, deleted, blocked states |
| `--destructive-foreground` | `1 20% 4%` | Text on destructive fill |
| `--destructive-text` | `1 20% 62%` | Destructive-colored text on neutral background |
| `--border` | `38 20% 87% / 0.1` | Default border color |
| `--input` | `222 16% 16%` | Input field background |
| `--ring` | `14 85% 60%` | Default focus ring color |
| `--focus-ring` | `14 85% 60%` | Primary button outer focus ring |
| `--success` | `150 45% 38%` | Completed, published, healthy, active |
| `--success-foreground` | `150 20% 4%` | Text on success fill |
| `--success-text` | `150 20% 58%` | Success-colored text on neutral background |
| `--warning` | `45 85% 55%` | Stale, partial, degraded, hiatus |
| `--warning-foreground` | `45 20% 14%` | Text on warning fill |
| `--warning-text` | `45 20% 58%` | Warning-colored text on neutral background |
| `--info` | `205 70% 55%` | Running, scheduled, informational |
| `--info-foreground` | `205 20% 4%` | Text on info fill |
| `--info-text` | `205 20% 58%` | Info-colored text on neutral background |
| `--sidebar` | `222 25% 8%` | Sidebar background |
| `--sidebar-accent` | `222 16% 16%` | Sidebar hover/active accent |
| `--radius` | `0.375rem` | Base border radius (6px) |

---

## 4. Semantic Usage Matrix

### 4.1 Canonical Status Mapping

| Status Token | Semantic Meaning | Allowed Uses | Prohibited Uses |
|--------------|------------------|--------------|-----------------|
| `success` | Completed, published, healthy, active | Badge "Completed", publish confirmation, health check "healthy" | In-progress states, warnings |
| `info` | Running, scheduled, informational | "Downloading", "Scheduled", toast info, progress steps | Success/error states |
| `warning` | Stale, partial, degraded, hiatus | "Hiatus", "Partial", "Stale data", degraded health | Critical failures |
| `destructive` | Failed, rejected, deleted, blocked | "Failed", "Rejected", delete confirmation, blocked content | Recoverable warnings |
| `muted` | Inactive, dropped, unavailable | "Dropped", "Unavailable", disabled states | Actionable states |

### 4.2 Color & Accent Usage Rules (Normative)

- **MUST** use `--accent` (sakura pink) for: favorites (heart), user ratings (stars), save-to-library actions, and active novel reading progress indicators
- **MUST** use `--primary` (Shuji Vermillion) for **all** primary CTAs: "Start Reading", "Sign In", "Continue", primary form submits
- **MUST** use `--secondary` (soft teal) for structural chips, section dividers, supporting emphasis
- **MUST NOT** use `--accent` for primary buttons, focus rings, or generic highlights
- **MUST NOT** use `--primary` for decorative accents or non-actionable highlights
- **SHOULD** use `-text` tokens for inline status text on neutral backgrounds; **MUST** use `-foreground` tokens for text on matching semantic fills

---

## 5. Spacing and Layout Tokens

- **Base unit**: 4px (standard Tailwind spacing scale)
- **No custom spacing tokens** — use Tailwind utilities directly
- **Key patterns** (documented for consistency, not tokenized):

| Pattern | Utility | Context |
|---------|---------|---------|
| Page gutters | `px-4 md:px-6` | Page-level horizontal padding |
| Card padding | `p-4` | Standard card interior |
| Section gaps | `space-y-6` or `gap-6` | Vertical rhythm between sections |
| Compact density | `gap-2`, `p-2`, `space-y-2` | Admin-dense tables, lists |
| Comfortable density | `gap-4`, `p-4`, `space-y-4` | Public reading, browse grids |

---

## 6. Radius

| Token | Value | Derived | Use |
|-------|-------|---------|-----|
| `--radius` (base) | `0.375rem` (6px) | — | Default `rounded` / `rounded-md` |
| `lg` | — | `var(--radius)` = 6px | Cards, modals, larger containers |
| `md` | — | `calc(var(--radius) - 2px)` = 4px | Buttons, inputs, badges |
| `sm` | — | `calc(var(--radius) - 4px)` = 2px | Small chips, compact elements |
| `full` / `pill` | `9999px` | — | Status badges, avatars, pill buttons |

**MUST** use Tailwind radius utilities (`rounded`, `rounded-lg`, `rounded-full`) — never hardcode pixel values.

---

## 7. Elevation

Dark-first design, minimal elevation. Flat default surfaces.

| Layer | Shadow | Use Cases |
|-------|--------|-----------|
| Flat (default) | `none` | Cards, pages, most surfaces — border only via `--border` |
| `shadow-sm` | `0 1px 2px 0 rgb(0 0 0 / 0.05)` | Dropdown menus, popovers (light) |
| `shadow-md` | `0 4px 6px -1px rgb(0 0 0 / 0.1)` | Popovers (dark), elevated cards |
| `shadow-lg` | `0 10px 15px -3px rgb(0 0 0 / 0.1)` | Complex dropdowns, hover elevation |
| `shadow-2xl` | `0 25px 50px -12px rgb(0 0 0 / 0.25)` | Modals, dialogs, drawers |
| Backdrop blur | `backdrop-blur-sm` | Modals, overlay backgrounds |

**MUST NOT** add decorative glow, colored shadows, or elevation on non-overlay UI surfaces. Illustration SVGs may use glow; UI surfaces must not.

---

## 8. Z-Index Layers

Named layers. Currently hardcoded in components — not yet CSS custom properties. Listed here as the canonical reference.

| Layer | Value | Use Cases |
|-------|-------|-----------|
| `--z-sticky-header` | `1` | Table sticky headers |
| `--z-sticky-content` | `10` | Sticky content, dropdown suggestions, nav section tabs |
| `--z-sidebar` | `20` | Admin sidebar, notification menu, novel detail section tabs |
| `--z-public-header` | `30` | Public header |
| `--z-mobile-nav` | `40` | Mobile tab bar, browse filter backdrop, novel detail fixed CTA |
| `--z-modal` | `50` | Modal dialogs, search overlay, reader controls, reader progress bar, glossary annotation popover |
| `--z-admin-overlay` | `60` | Admin toast, crawler dialog |
| `--z-skip-link` | `100` | Skip link (visible on focus only) |

**MUST** use these layers — no arbitrary `z-[9999]` values. New overlay components **MUST** request a layer assignment in PR review.

---

## 9. Typography

### 9.1 Font Families (via `next/font/local`)

| Tailwind Alias | CSS Variable | Font | Weights | Use |
|----------------|--------------|------|---------|-----|
| `font-sans` / `font-ui` | `--font-dm-sans` | DM Sans | Variable (single TTF) | UI, body text, buttons, forms |
| `font-serif` / `font-literary` | `--font-noto-serif-jp` | Noto Serif JP | Variable (single TTF) | Titles, literary content, chapter reading |
| `font-mono` / `font-metadata` | `--font-dm-mono` | DM Mono | 400, 500 only | Metadata, numbers, code, timestamps |

### 9.2 Usage Rules

- **MUST** use `font-sans` (DM Sans) for all UI chrome, navigation, forms, body copy
- **MUST** use `font-serif` (Noto Serif JP) for: novel titles, chapter titles, reading content, literary quotes
- **MUST** use `font-mono` (DM Mono) for: chapter numbers, timestamps, word counts, code snippets, metadata
- **MUST NOT** mix font families within a single semantic element (e.g., title + subtitle must share family)

---

## 10. Motion

| Duration | Easing | Use Cases |
|----------|--------|-----------|
| `120ms` | `ease-in-out` | Micro-interactions (checkbox transform, toggle switches) |
| `200ms` | CSS default `ease` | Standard transitions (color, background, reader theme switch, card hover) |
| `300ms` | CSS default `ease` | Emphasis transitions (cover zoom, progress bar, modal enter/exit) |

### 10.1 Reduced Motion

- Global `@media (prefers-reduced-motion: reduce)` sets **all** `animation-duration` and `transition-duration` to `0.01ms`
- **MUST** test with reduced motion enabled — no functionality loss, no stuck states
- **MUST NOT** use animation for critical state communication without a non-animated fallback

---

## 11. Accessibility Requirements

### 11.1 Shared Baseline

See `docs/design/shared/accessibility.md` for cross-surface requirements (WCAG 2.2 AA target, focus management, landmarks, ARIA).

### 11.2 Public-Specific Requirements

| Requirement | Specification | Verification |
|-------------|---------------|--------------|
| **Contrast** | All text/foreground tokens **MUST** meet 4.5:1 (normal) / 3:1 (large) against their semantic backgrounds in both modes | Automated: `app/(public)/__tests__/token-contrast.test.ts` (17 pairs × 2 modes = 34 pair checks); Manual: contrast audit on token changes |
| **Focus Ring** | Default: `2px solid hsl(var(--ring))` offset `2px`; Primary buttons: two-layer — `2px solid hsl(var(--foreground))` inner + `4px` box-shadow `hsl(var(--focus-ring))` outer offset | Visual regression; keyboard navigation test |
| **Two-Layer Focus** | Primary buttons **MUST** use dual-ring pattern; all other interactive elements use single ring | Code review; automated lint for `focus-visible` |
| **Color Independence** | Status **MUST NOT** rely on color alone — pair with icon, label, or pattern (e.g., badge text + icon) | Manual acceptance; design review |
| **Forced Colors** | **MUST** preserve borders, focus rings, and text contrast in Windows High Contrast / forced-colors mode; **MUST NOT** use `currentColor` for semantic fills | Manual test in forced-colors mode |

### 11.3 Known Limitation: Muted Foreground

In both light and dark modes, `--muted-foreground` equals `--foreground`. This means `text-muted-foreground` provides **no visual hierarchy** over default text. This is a known limitation — adjusting requires contrast verification and aesthetic review. **DO NOT** rely on `text-muted-foreground` for de-emphasis; use `text-sm`, `font-light`, or structural separation instead.

---

## 12. Implementation and Verification Mapping

| Token/System | Source File | Tailwind Config | Verification |
|--------------|-------------|-----------------|--------------|
| Color tokens | `frontend/app/globals.css` | `frontend/tailwind.config.ts` (colors) | `token-contrast.test.ts` (17 pairs × 2 modes), `npm run typecheck`, `npm run build` |
| Radius | `globals.css` `--radius` | `tailwind.config.ts` (borderRadius) | Visual regression |
| Font families | `frontend/app/layout.tsx` `next/font` | `tailwind.config.ts` (fontFamily) | `npm run build` |
| Z-index | Component-level (hardcoded) | — | Manual PR review for new overlays |
| Motion | `globals.css` `@media (prefers-reduced-motion)` | — | Reduced-motion test |
| Focus rings | Component-level `focus-visible` styles | — | Keyboard nav test, visual regression |

### 12.1 Automated Checks

- **Lint**: `npm run lint` — catches invalid Tailwind class usage
- **Typecheck**: `npm run typecheck` — catches invalid config references
- **Build**: `npm run build` — fails on missing tokens, invalid CSS
- **CI**: Runs lint, typecheck, and build via `.github/workflows/ci.yml`

### 12.2 Manual Acceptance Gates

| Change Type | Required Review |
|-------------|-----------------|
| Color token value change | Contrast audit (both modes), visual regression, forced-colors test |
| New semantic token | This doc + Tailwind config + both mode tables updated; design review |
| Radius change | Visual regression across cards, buttons, modals, badges |
| Font change | Reading experience test (serif), UI density test (sans), metadata alignment (mono) |
| Z-index addition | PR review with layer assignment; no conflicts with existing layers |

---

## 13. Reader Theme (Subordinate Token System)

The chapter reader uses an **independent token system** in `frontend/app/(public)/reader.css` controlled by `data-reader-theme` attribute (`light`, `dark`, `sepia`).

- **MUST NOT** toggle `html.dark` for reader theme changes
- Reader tokens use **raw hex colors** (not HSL CSS variables)
- Three themes: light, dark, sepia — documented in `docs/design/public/reading/chapter-reader.md`
- Reader tokens are **subordinate** to the global token system — global tokens apply to reader chrome (header, controls, glossary popover); reader tokens apply only to the reading surface (text, background, annotations)
- **MUST** verify reader theme changes do not leak into global surfaces

---

*End of Public Design System specification.*
