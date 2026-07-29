# Project History

Concise record of completed, cancelled, and deferred specifications. Git history
contains full former requirements/design/task documents.

## Completed Specifications

| Specification area | Outcome | Current authority |
|---|---|---|
| Adapter plugins and source ingestion | Registry, adapters, offline fixtures, and safe fetch boundaries implemented. | `ARCHITECTURE.md` |
| Authentication and authorization | Owner/user/guest sessions, OAuth, password auth, CSRF, ownership, and rate limits implemented. | `ARCHITECTURE.md` |
| CI/CD and containers | CI gates, image publication, Compose topology, split services, and smoke tooling implemented. | `DEPLOYMENT.md` |
| S3/R2 storage and recovery | Storage abstraction, independent snapshots, retention, encrypted DB dumps, and restore verification implemented. | `STORAGE.md`, `OPERATIONS.md` |
| Translation chunking and resume | Deterministic paragraphs/chunks, bounded chapter parallelism, checkpoints, delta/resume hardening implemented. | `ARCHITECTURE.md`, `TRANSLATION.md` |
| Translation cache and QA | Exact cache identity, glossary invalidation, deterministic QA, prompt hardening, and advisory LLM-QA baseline implemented. | `TRANSLATION.md` |
| Glossary system | Suggestions, approval, sync, diagnostics, onboarding, revision invalidation, editor QA, and public annotations implemented. | `TRANSLATION.md` |
| Public reader | Catalog/detail/chapter routes, availability, SEO, accessibility baseline, performance budget, taxonomy, and annotations implemented locally. | `DESIGN.md` |
| Admin operations | Users, audit, analytics, metrics, notifications, credentials, requests, health, and library summary implemented locally. | `ARCHITECTURE.md`, `OPERATIONS.md` |
| Legal workflow | Contact/support/legal pages, DMCA intake, owner review, audit, HTTP 451, sitemap/cache enforcement implemented locally. | `ARCHITECTURE.md`, `DESIGN.md` |
| Scheduler durability | Runtime state persistence, cooldown/exhaustion/heartbeat, leases, backup scheduling, and worker observability implemented. | `ARCHITECTURE.md`, `OPERATIONS.md` |
| Error handling and storage safety | Structured safe errors, logging, atomic JSON writes, file locks, schema tests, and storage boundary consolidation implemented. | `ARCHITECTURE.md`, `STORAGE.md` |

## Cancelled

| Work | Reason |
|---|---|
| PDF/EPUB/HTML/Markdown translated-novel generation | Reader downloads removed from product scope. Input adapters remain. |
| Generated-file manifest UI and freshness scheduler | No generated reader artifacts remain to observe. |
| Historical one-shot operation prompts | Replaced by canonical docs, `AGENTS.md`, and bounded active specs. |

## Deferred Ideas

| Idea | Activation condition |
|---|---|
| Semantic cache | Approved evaluation, embedding/index, isolation, idempotency, and cost contract. |
| Expanded advisory LLM QA | Structured review-only findings and bounded provider/cost policy. |
| Contribution credentials | Full readiness gate in `ARCHITECTURE.md`. |
| Community and rankings | Public moderation, abuse controls, and trustworthy metrics. |

## Documentation Consolidation

Detailed completed/cancelled specs and archived prompts were collapsed into this
file because they were stale planning artifacts. Git remains the lossless record.
