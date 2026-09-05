---
trigger: always_on
description: Authoring, validation, delivery, and directory placement rules for Archify HTML/SVG architecture diagrams.
---

# Archify Diagram Authoring & Delivery Rules

This rule enforces standards for authoring, validating, delivering, and storing interactive HTML/SVG diagrams generated with [Archify](https://github.com/tt-a1i/archify).

## Directory Governance & Placement

- **Approved Diagram Location**: All diagram specifications (`*.json`), delivered HTML (`*.html`), visual-check contact sheets, and screenshots must be placed strictly under:
  ```
  docs/design/diagrams/
  ```
- **Prohibited Locations**: Never create `docs/diagrams/` or output HTML directly into `docs/` root. This triggers `unapproved_docs_directory` violations under `tools/docs-check.ps1`.

## CLI Tooling Wrappers

Always execute Archify through the repository wrapper script:
```powershell
# Health and diagnostics
powershell -File tools\archify.ps1 doctor

# Brand mark lookup (PostgreSQL, Redis, Cloudflare, Docker, Python, Next.js)
powershell -File tools\archify.ps1 brands <brand-name> --json

# Validation (showcase quality profile)
powershell -File tools\archify.ps1 validate <type> <spec.json> --quality showcase --json

# Delivery
powershell -File tools\archify.ps1 deliver <type> <spec.json> <output.html> --quality showcase --json

# Automated browser viewport check
powershell -File tools\archify.ps1 visual-check <output.html> --json
```

## Diagram Types & Usage Router

1. **`architecture`**: Multi-process systems, service boundaries, network routing, cloud infrastructure.
2. **`workflow`**: Asynchronous pipelines, crawl & extraction jobs, human review gates, error retries.
3. **`sequence`**: API request lifecycles, cache lookup sequences, prefetching traces, token validation.
4. **`dataflow`**: Novel content pipelines, storage tiering (local &rarr; PostgreSQL &rarr; R2 &rarr; Redis).
5. **`lifecycle`**: State machine transitions (e.g. Chapter status: `discovered` &rarr; `crawled` &rarr; `translating` &rarr; `published`).

## Authoring Invariants & Showcase Acceptance

- **Showcase Quality**: Author with `meta.quality_profile: "showcase"`. Validation must report all 9 artifact checks passing with 0 composition errors and 0 warnings before running `deliver`.
- **Node Limits & Rhythm**: Limit primary nodes to at most 12 per diagram. Maintain one clear primary flow.
- **Labels & Semantic Routing**: Keep relationship labels semantic; adjust `fromSide`, `toSide`, and `via` routing rather than deleting labels.
- **Brand Identity**: Use canonical brand IDs (`postgresql`, `redis`, `cloudflare`, `docker`, `python`, `next-js`) where applicable.
