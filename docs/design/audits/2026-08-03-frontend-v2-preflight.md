# Frontend V2 Preflight Audit

**Date**: 2026-08-03
**Baseline Commit**: `d1d2238606cad910126546453ba30be89e35483c`
**Commits Reviewed**: `2f8ed99` through `d1d2238` (PR #23 to PR #36)

---

## 1. Executive Summary

This audit reconciles production behavior, current code/test state, backend capability, and PR #36 changes (Shuji Vermillion theme & brand asset infrastructure) to set frozen contracts for the Frontend V2 reconstruction.

---

## 2. Review Inventory & Classification

### 2.1 Findings Matrix

| Ref | Finding | Category | Classification | Resolution / Action for V2 |
|---|---|---|---|---|
| **P-01** | Theme naming conflict (docs say Yokocho Lantern / Lantern Orange / Plum; PR #36 shipped Shuji Vermillion, Washi Paper, Midnight Slate) | Theme Identity | Corrected in canonical docs | Standardize hierarchy: Product: Dokushodo, Public Direction: Modern Japanese Literary, Primary Theme: Shuji Vermillion & Washi, Supporting Motifs: Restrained lantern, yokocho, bunko/bookplate. |
| **P-02** | Token contrast & WCAG reference conflict (docs specify WCAG 2.1 AA and stale check counts like "34 checks across 17 pairs") | Accessibility | Corrected in canonical docs | Target WCAG 2.2 AA. `token-contrast.test.ts` runs 4 test suites testing 17 WCAG AA token pairs across 2 modes (:root and .dark) totaling 34 pair checks. |
| **P-03** | Brand asset taxonomy drift (docs claimed SVG source unavailable, favicon SVG future, old Plum maskable background) | Brand Assets | Corrected in canonical docs | Asset taxonomy updated: `icon.svg` is canonical scalable mark; `icon-512.png` is maskable; `apple-touch-icon.png` is touch icon; `favicon.ico` fallback; `open-graph.png` default OG image. |
| **P-04** | Metadata color drift (`manifest.ts` used `#140f17` background/theme color instead of Midnight Slate `#131822`) | Metadata / PWA | Implementation requirement | Standardize `theme_color` and `background_color` contract to Midnight Slate HSL converted hex (`#131822`) for dark mode PWA consistency. |
| **P-05** | Gradient and glow policy ambiguity (`icon.svg` uses gradients and radial glows, while UI docs prohibit all gradients) | Brand / UI Boundary | Corrected in canonical docs | Define strict gradient ladder: permitted on brand app icon (`icon.svg`) and decorative SVG illustrations; strictly prohibited on UI buttons, cards, headers, or backgrounds. |
| **P-06** | Muted foreground contrast parity limitation (`--muted-foreground` equals default `--foreground` in both light/dark HSL tokens) | Token Semantics | Intentionally preserved | Documented limitation: `--muted-foreground` does not provide color de-emphasis. UI hierarchy MUST use font size (`text-sm`), weight (`font-normal`), or structural layout instead. |
| **P-07** | Admin vs Public surface visual boundary (admin must not display Yokocho/Shuji motifs, sakura pink accents, or Noren dividers) | System Boundary | Corrected in canonical docs | Enforce high-density, utilitarian admin control plane using neutral slate and operational status tokens (`success`, `warning`, `destructive`, `info`). |
| **P-08** | Automated vs manual testing claims (docs previously implied test suite proves complete WCAG accessibility) | Verification Contract | Corrected in canonical docs | Clarify automated tests verify color contrast ratios, ARIA roles, and component props; manual acceptance (keyboard trap, screen reader, high-contrast, zoom) remains required. |
| **P-09** | Lack of explicit anti-slop & motion contracts in design docs | Quality & Governance | Corrected in canonical docs | Add mandatory Anti-Slop (Phase 6) and 6-level Motion & Graphics (Phase 7) contracts prohibiting generic AI SaaS templates, scroll hijacking, and 3D bloat. |
| **P-10** | Missing explicit Next.js App Router component architecture classification per route | Handoff Contract | Implementation requirement | Map every route to Server Component, Client Component, or Server Shell + Client Island in `docs/design/frontend-v2-implementation-handoff.md`. |

---

## 3. Decisions & Freeze List for Prompt 2

1. **Theme Identity**: Product is **Dokushodo (読書道)**. Public direction is **Modern Japanese Literary**. Primary theme is **Shuji Vermillion & Washi Warm Paper** (light) / **Midnight Slate** (dark).
2. **Accessibility Baseline**: Canonical standard is **WCAG 2.2 Level AA**.
3. **Asset & Icon Rules**: Single scalable vector `icon.svg` is canonical app icon. Minimalist pinched-lantern `brand-mark.png` is canonical brand mark for UI headers.
4. **Motion Ladder**: Level 0 (none) to Level 3 (Motion for React) allowed in public UI. Level 4 (GSAP) restricted to single signature sequence. Level 5 (Three.js/WebGL) strictly prohibited.
5. **No Fake Data**: All counts, ratings, reviews, and progress bars must reflect actual API responses. Non-functional endpoints return explicit unavailable states.

---

*End of Preflight Audit.*
