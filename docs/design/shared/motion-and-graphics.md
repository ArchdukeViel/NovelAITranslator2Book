# Motion and Graphics Contract

Canonical specification governing animation, transitions, visual graphics, and 3D rendering tiers for Dokushodo.

## Motion Tier Ladder

| Tier | Category | Approved Technology | Allowed Contexts | Prohibitions & Fallbacks |
|---|---|---|---|---|
| **Level 0** | Zero Motion | Pure Static CSS | Chapter reader body, dense admin tables, critical operator buttons, `prefers-reduced-motion: reduce` state | Zero CSS transitions or transforms permitted |
| **Level 1** | Standard UI Micro-interactions | Utility CSS Transitions / Animations (`120ms`–`200ms`) | Button hover/focus, checkbox ticks, accordion expand, dropdown opacity, card outline hover | No spring physics or complex chained sequences |
| **Level 2** | Page & Navigation Continuity | Native View Transition API (Progressive Enhancement) | Catalog-to-Novel transition, Novel-to-Reader transition, sticky cover morphing | Application MUST remain 100% functional if View Transition API is unsupported |
| **Level 3** | Layout & Presence Transitions | Motion for React (`framer-motion`) | AnimatePresence modal dialogs, search overlay enter/exit, mobile drawer slide | Isolated client components only. Requires strict reduced-motion check and bundle isolation |
| **Level 4** | Signature Complex Sequences | GSAP (GreenSock Animation Platform) | Restricted to SINGLE approved brand introduction sequence (if requested by owner) | Strictly prohibited on routine UI, reader routes, admin routes, and scroll triggers. Requires cleanup & lazy loading |
| **Level 5** | 3D Graphics & Canvas | Three.js / WebGL | **PROHIBITED BY DEFAULT** | Requires explicit owner written authorization and real 3D information requirement. Floating books, particles, and cursor 3D are BANNED |

---

## Technical Constraints & Verification

- **Bundle Isolation**: Level 3 (`framer-motion`) and Level 4 (`gsap`) MUST be dynamically imported inside client components to avoid inflating main bundle size on static reader/catalog routes.
- **Reduced Motion Mandatory Rule**:
  ```css
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      scroll-behavior: auto !important;
      transition-duration: 0.01ms !important;
    }
  }
  ```
- **Performance Budget**: Motion work MUST NOT cause frame drops below 60fps on modern mobile browsers or increase cumulative layout shift (CLS > 0.0).
