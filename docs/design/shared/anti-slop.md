# Anti-Slop Contract

Canonical rules for preventing generic AI SaaS visual clutter, marketing fluff, and unbacked UI patterns in Dokushodo.

## 1. Prohibited Generic Patterns

Unless explicitly required by a route contract, the following patterns are strictly **PROHIBITED** across all public and admin surfaces:

1. **Centered Generic Hero with Dual CTAs**: No generic "Transform your reading experience / Get Started / Learn More" dual-button hero banners.
2. **Default Three-Card Feature Rows**: No boilerplate SaaS marketing grid ("Fast Reading", "AI Translation", "Cloud Sync").
3. **Mesh Gradients & Blurred Blobs**: No background CSS mesh blobs, ambient blurred circles, or floating color gradients behind UI text.
4. **Glassmorphism on Ordinary Surfaces**: No widespread `backdrop-blur` on static cards, sidebars, or table containers. Allowed ONLY on sticky navigation headers and modal overlays.
5. **Every Section in a Card**: Do not wrap every text block or list in elevated/bordered cards. Prefer clean white/paper space and structural dividers.
6. **Excessive Pills, Badges & Decorative Icons**: No decorative icons beside every single heading; no random status pills without semantic meaning.
7. **Fake Metrics & Unbacked Social Proof**: No simulated "10,000+ happy readers", fake rating stars, artificial live reading feeds, or synthetic review counts.
8. **Arbitrary Monospaced Uppercase Eyebrows**: No uppercase monospaced labels (`OVERVIEW`, `FEATURES`, `UPDATES`) floating above every section title.
9. **Numbered Marketing Steps**: No "Step 1: Choose Novel / Step 2: Read / Step 3: Enjoy" onboarding strips.
10. **Ticker Strips & Floating Badges**: No scrolling marquee text, floating feedback widgets, or corner promotional badges.
11. **Ubiquitous Hover Motion**: Cards and buttons must NOT scale, tilt, or jump on hover across the entire page.
12. **Scroll Hijacking & Smooth-Scroll Interception**: Custom JavaScript wheel interception or forced section scrolling is prohibited.
13. **Decorative Reader Animation**: Reading body text MUST NOT animate, fade in word-by-word, or shift during reading.
14. **Identical Composition Across Routes**: Home, Browse, Novel Detail, and Account pages MUST maintain distinct layouts matching their specific user goals.
15. **Unmodified Library Defaults**: Standard Shadcn or Tailwind component library defaults MUST be styled to Dokushodo's Shuji Vermillion & Washi design contract.
16. **Generic Promotional Copy**: Words like "seamless", "unlock", "elevate", "cutting-edge", or "the future of reading" are banned from UI text.

---

## 2. Restrained Motif Rules

The following motifs define Dokushodo's Japanese literary visual identity and MUST be applied with restraint:

- **Shuji Vermillion Action**: `--primary` vermillion fill is reserved for primary focal actions and active selection states.
- **Lantern Geometry**: Pinched lantern shapes are allowed ONLY on brand marks (`brand-mark.png`, `icon.svg`) and specific top-level navigation headers — NEVER as repeating background icons or bullet markers.
- **Bunko-bon Bookplate Composition**: Novel detail hero and library shelf headers use bookplate borders and clean serif title hierarchy informed by Japanese paperback design.
- **Vertical Japanese Typography (Sparse)**: Vertical text (`writing-mode: vertical-rl`) is permitted ONLY as sparse, low-contrast background brand decoration (e.g. `読書道`) — NEVER for primary UI navigation or interactive text.
- **Zero Motifs in Admin**: The admin surface (`/admin/*`) MUST NOT display public motifs, lantern badges, or decorative borders.
- **Signature Focal Idea**: Every major route surface MUST have exactly ONE signature visual focal point (e.g. sticky novel cover panel on novel detail; quiet typography focus on chapter reader).
