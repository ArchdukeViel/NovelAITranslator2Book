# Product UX Principles

Canonical product design principles for Dokushodo (読書道).

## Core Direction

> A quiet editorial reading environment informed by Japanese paperback (bunko-bon) composition and restrained signage, with a separate utilitarian admin control plane.

## 1. Respect the Reader (Quiet Chrome)

Reading web novels requires high focus. UI controls, navigation, and background decorations must fade away while reading.

- **Reader chrome suppression**: The chapter reader hides top navigation, tab bar, and footer by default. Controls appear only on toggle/hover or tap in designated safe zones.
- **Zero intrusive prompts**: No mid-chapter rating popups, floating banners, social share prompts, or newsletter popups.
- **Calm typography**: High legibility serif typography (Noto Serif JP) for reading content with comfortable line-height (1.8) and line-length limits (65–85 characters).

## 2. Japanese Literary Aesthetic (Restrained Motifs)

Japanese web novel app aesthetic without museum stiffness, antiquarian tropes, or arcade visual noise.

- **Color Hierarchy**: Primary Shuji Vermillion (`--primary`), Washi Warm Paper background (`--background` in light mode), Midnight Slate background (`--background` in dark mode), Soft Teal structural accents (`--secondary`), and Sakura Pink (`--accent`) strictly for library bookmarking, ratings, and progress indicators.
- **Bunko-bon Framing**: Bookplate layout structures novel detail headers; vertical title accents are permitted as sparse, readable decoration (never blocking UI).
- **Restrained Lantern Elements**: Lantern geometry is restricted to brand app icons and specific focal headers — never repeated across section background cards or list items.

## 3. Truthful Data & Honest UI

Never invent numbers, activity, or curation.

- **No Fake Metrics**: No "trending now", simulated read counts, generated reviews, or false stock counters. If data is unavailable from backend API, state "Data unavailable" or omit section entirely.
- **One primary action per region**: Hero, rail, card, form, or modal regions get exactly one visually dominant action.
- **Explicit Administrative Boundary**: Admin control plane MUST maintain high-density information layout, slate background, and zero public visual motifs.

## 4. Utilitarian Admin Control Plane

The admin surface (`/admin/*`) prioritizes density, speed, safety, and auditability over warmth or literary visual identity.

- High-density data tables with monospaced numbers (`font-mono`).
- Masked PII and security credentials by default (`mask-token.ts`).
- Clear confirmation dialogs for destructive, crawler, or bulk actions.
