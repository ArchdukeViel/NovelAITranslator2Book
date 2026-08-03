# Verification Contract

Canonical testing and visual acceptance contract for Frontend V2.

## 1. Automated Verification Suite

All frontend modifications MUST pass the following automated test commands from `frontend/`:

```powershell
# 1. Token Contrast & CSS Infrastructure Test (34 pair checks across :root and .dark)
npx vitest run "app/(public)/__tests__/token-contrast.test.ts"

# 2. Complete Frontend Unit & Component Test Suite
cd frontend; npm run test

# 3. TypeScript Type Checking
cd frontend; npm run typecheck

# 4. ESLint Static Analysis
cd frontend; npm run lint

# 5. Production Next.js Build
cd frontend; npm run build
```

---

## 2. Visual Snapshot & Viewport Matrix

Visual regression acceptance requires verifying key representative routes (`/`, `/browse-novels`, `/novels/[slug]`, `/novels/[slug]/chapter/[chapterId]`, `/account/library`, `/admin/dashboard`) across four viewports:

| Viewport Category | Width | Use Case | Target Testing States |
|---|---|---|---|
| Mobile Small | `320px` | Small screen reflow / minimum target | Light, Dark, Empty, Loading |
| Mobile Standard | `768px` | Tablet / Mobile tab bar breakpoint | Light, Dark, Settled, Error |
| Desktop Medium | `1024px` | Admin sidebar breakpoint / Laptop | Light, Dark, High Density |
| Desktop Large | `1440px` | Widescreen layout / Max content width | Light, Dark, Long content stress |

---

## 3. Reader Theme Testing Matrix

Chapter reader testing MUST verify all three subordinate reader themes without leaking into global CSS:
- `data-reader-theme="light"`: Light paper fill + dark body text
- `data-reader-theme="dark"`: Midnight Slate fill + light body text
- `data-reader-theme="sepia"`: Warm sepia fill + dark brown body text

---

## 4. Manual Accessibility Acceptance Gate

Operator manual acceptance (DEBT-FE-01A) requires verifying:
1. Keyboard navigation (Tab focus order, two-layer focus rings on primary buttons, visible focus indicators).
2. Screen reader announcements (NVDA / VoiceOver reading page titles, form errors via `aria-describedby`, live regions).
3. Forced Colors mode (Windows High Contrast mode border visibility).
4. 200% browser zoom reflow without horizontal scroll collision.
