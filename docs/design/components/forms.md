# Component Contract — Forms & Inputs

## Specifications

- **Input Fields (`<input>`, `<textarea>`):** Height 36px (sm) / 40px (default), 6px border-radius, `--border` stroke, `--background` fill. Focus-visible applies `--focus-ring`.
- **Validation Messages:** Rendered directly below inputs in 12px text using `--destructive` (errors) or `--success-text` (success).
- **Draft Preservation:** Form inputs preserve entered text across authentication detours.
- **Labels:** Always rendered above inputs with `text-xs font-medium text-muted-foreground`.
