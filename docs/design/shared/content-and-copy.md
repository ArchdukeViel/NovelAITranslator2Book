# Content and Copy Guidelines

Tone, terminology, and formatting standards.

## Tone

- **Public surface:** Warm, welcoming, Japanese web novel app vibe (Bunko-bon shelf / Yokocho Lantern). Clear and concise.
- **Admin surface:** Operational, precise, high-density, action-oriented.

## Terminology Rules

- Use canonical identifiers and names.
- Public copy must never leak internal backend codenames (e.g. "Novel AI" -> use "Dokushodo" on public surfaces).
- Safe error messages: Never expose raw stack traces, DB keys, or internal file paths to public users.

## Formatting

- **Dates and Numbers:** Format per visitor browser locale (`toLocaleDateString`).
- **CJK Text:** Long Japanese titles wrap by character (`break-all` / `line-break: strict`).
- **Title Hierarchy:** Translated title primary; original Japanese title secondary (using Noto Serif JP font).
